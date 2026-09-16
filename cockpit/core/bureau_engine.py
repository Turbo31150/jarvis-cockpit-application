#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — BUREAU ENGINE
Pilotage tracé du bureau GNOME (session Wayland, GNOME Shell 46).

Quatre domaines :
  • BARRE   — dock / barre des tâches (schéma dash-to-dock, extension ubuntu-dock)
  • ICONES  — icônes du bureau (extension ding) + déverrouillage des lanceurs .desktop
  • VERROUS — org.gnome.desktop.lockdown, écran de veille, verrous dconf système
  • ECRANS  — org.gnome.Mutter.DisplayConfig (lecture + bascule miroir/étendu)

DOCTRINE — reprise de ~/jarvis/bin/jarvis-reconcilier, sans couplage de code :
  · get_bureau_etat() est un CONSTAT : il n'écrit JAMAIS rien, nulle part.
  · run_bureau_action() est IDEMPOTENT : si la valeur est déjà celle voulue,
    aucune commande n'est exécutée et le verdict est CONSTAT.
  · La PREUVE est relue APRÈS l'écriture. Sans preuve → ROLLBACK + verdict ECHEC.
  · La TRACE ne fait jamais échouer l'action métier (chaque étage en try/except).

TRACE À TROIS ÉTAGES :
  1. JOURNAL  jarvis_logs.db → bureau_actions        (INSERT, append-only)
  2. ÉTAT     etoile.db → jarvis_project_state       (UPSERT, category=hmi_desktop)
  3. DOCTRINE etoile.db → bios_boyau_layers          (UPDATE valise, layer_id=09)

PIÈGES ENCODÉS (tous mesurés le 2026-08-31) :
  · Le schéma est « dash-to-dock » mais l'extension à recharger est « ubuntu-dock@ubuntu.com ».
  · dash-to-panel est installé mais NON activé : ne jamais y toucher.
  · gnome-shell --replace TUE la session sous Wayland. Rechargement = disable puis enable.
  · xrandr est présent (XWayland) et MENT : un seul écran virtuel. Ne jamais s'en servir.
  · Le « serial » de GetCurrentState est un jeton à usage unique : le relire avant Apply.
  · ApplyMonitorsConfig : method 0=VERIFY (à blanc), 2=PERSISTENT. 1=TEMPORARY s'auto-annule.
  · Types GVariant : ding icon-size est une CHAÎNE, dash-max-icon-size un ENTIER,
    background-opacity un DOUBLE, idle-delay un UINT32.
"""

import os
import re
import json
import time
import sqlite3
import threading
import subprocess

from .config import LOGS_DB, ETOILE_DB
from .platform_compat import (IS_WINDOWS, NO_WINDOW, runtime_dir, desktop_dir,
                              session_graphique, indisponible)

# Sous Windows il n'existe AUCUN équivalent de dash-to-dock, ding, dconf ou
# Mutter : le moteur est court-circuité (constat vide conforme, actions refusées
# en HORS-LOGICIEL sans trace). Le chemin Linux reste inchangé.
NOTE_WINDOWS = "Pilotage du bureau GNOME indisponible sous Windows"


def _assurer_gi_dist_packages():
    """Rend `gi` (python3-gi, apt) importable depuis le venv du cockpit.

    Le service tourne via ~/jarvis/.venv (include-system-site-packages = false),
    or python3-gi vit dans /usr/lib/python3/dist-packages et n'est PAS installable
    par pip. Sans ce pont, la bascule d'écran (Mutter/Gio) tombe en mode dégradé
    « No module named 'gi' ». Idempotent et non destructif : on ajoute le chemin
    système en fin de sys.path (priorité au venv) uniquement s'il manque.
    """
    import sys
    _dp = "/usr/lib/python3/dist-packages"
    if _dp not in sys.path:
        sys.path.append(_dp)

MACHINE = os.environ.get("JARVIS_MACHINE", "M4")

# ── Schémas et identifiants d'extension (à ne pas confondre) ──
SCHEMA_BARRE = "org.gnome.shell.extensions.dash-to-dock"
EXT_BARRE = "ubuntu-dock@ubuntu.com"
SCHEMA_ICONES = "org.gnome.shell.extensions.ding"
EXT_ICONES = "ding@rastersoft.com"
SCHEMA_LOCKDOWN = "org.gnome.desktop.lockdown"
SCHEMA_SAVER = "org.gnome.desktop.screensaver"
SCHEMA_SESSION = "org.gnome.desktop.session"

MUTTER_DEST = "org.gnome.Mutter.DisplayConfig"
MUTTER_PATH = "/org/gnome/Mutter/DisplayConfig"

DCONF_PROFILS = "/etc/dconf/profile"
DCONF_DBS = "/etc/dconf/db"

# Un seul écrivain à la fois : ThreadingHTTPServer sert un thread par requête.
_VERROU = threading.Lock()

# ── Tables déclaratives (patron core/swarm_manager.py) ──
CLES_BARRE = [
    {"cle": "dock-position", "type": "s", "libelle": "Position de la barre",
     "choix": ["BOTTOM", "TOP", "LEFT", "RIGHT"]},
    {"cle": "dock-fixed", "type": "b", "libelle": "Toujours visible"},
    {"cle": "autohide", "type": "b", "libelle": "Masquage automatique"},
    {"cle": "intellihide", "type": "b", "libelle": "Masquage intelligent"},
    {"cle": "extend-height", "type": "b", "libelle": "Pleine hauteur"},
    {"cle": "multi-monitor", "type": "b", "libelle": "Sur tous les écrans"},
    {"cle": "dash-max-icon-size", "type": "i", "libelle": "Taille des icônes", "min": 16, "max": 64},
    {"cle": "background-opacity", "type": "d", "libelle": "Opacité du fond", "min": 0.0, "max": 1.0},
]

CLES_ICONES = [
    {"cle": "show-home", "type": "b", "libelle": "Dossier personnel"},
    {"cle": "show-trash", "type": "b", "libelle": "Corbeille"},
    {"cle": "show-volumes", "type": "b", "libelle": "Disques montés"},
    {"cle": "show-network-volumes", "type": "b", "libelle": "Volumes réseau"},
    {"cle": "keep-arranged", "type": "b", "libelle": "Alignement forcé"},
    {"cle": "keep-stacked", "type": "b", "libelle": "Empilement forcé"},
    {"cle": "start-corner", "type": "s", "libelle": "Coin de départ",
     "choix": ["top-left", "top-right", "bottom-left", "bottom-right"]},
    {"cle": "icon-size", "type": "s", "libelle": "Taille des icônes",
     "choix": ["tiny", "small", "standard", "large"]},
]

CLES_VERROUS = [
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-lock-screen", "type": "b", "libelle": "Verrouillage d'écran"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-command-line", "type": "b", "libelle": "Ligne de commande"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-log-out", "type": "b", "libelle": "Déconnexion"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-printing", "type": "b", "libelle": "Impression"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-print-setup", "type": "b", "libelle": "Config. impression"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-save-to-disk", "type": "b", "libelle": "Sauvegarde disque"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-user-switching", "type": "b", "libelle": "Changement d'utilisateur"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-application-handlers", "type": "b", "libelle": "Gestionnaires d'applications"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "disable-show-password", "type": "b", "libelle": "Affichage du mot de passe"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "user-administration-disabled", "type": "b", "libelle": "Administration"},
    {"schema": SCHEMA_LOCKDOWN, "cle": "mount-removable-storage-devices-as-read-only", "type": "b",
     "libelle": "Amovibles en lecture seule"},
    {"schema": SCHEMA_SAVER, "cle": "lock-enabled", "type": "b", "libelle": "Verrouillage à la veille"},
    {"schema": SCHEMA_SESSION, "cle": "idle-delay", "type": "u", "libelle": "Délai d'inactivité (s)"},
]


# ═══════════════════════════════════════════════════════════════════════════
#  PRIMITIVES — aucune ne lève jamais
# ═══════════════════════════════════════════════════════════════════════════


def _session_graphique():
    """Type et nom du bureau, avec repli loginctl.

    Defaut mesure le 2026-09-03 : le cockpit tourne en service systemd --user,
    dont l'environnement ne porte que DBUS_SESSION_BUS_ADDRESS, XDG_DATA_DIRS
    et XDG_RUNTIME_DIR. XDG_SESSION_TYPE et XDG_CURRENT_DESKTOP sont ABSENTS,
    donc os.environ.get(...) rendait "?" et wayland=False alors que la session
    reelle est bien wayland / ubuntu:GNOME. On interroge loginctl en repli :
    il lit la session logind, qui ne depend pas de l'environnement du process.
    """
    if IS_WINDOWS:
        return session_graphique()   # aucun sous-processus (pas de logind)
    typ = os.environ.get("XDG_SESSION_TYPE", "")
    bureau = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if not typ or not bureau:
        try:
            sid = subprocess.run(
                ["loginctl", "list-sessions", "--no-legend"],
                capture_output=True, text=True, timeout=4).stdout
            sid = next((l.split()[0] for l in sid.splitlines()
                        if " seat" in l or l.strip()), "")
            if sid:
                out = subprocess.run(
                    ["loginctl", "show-session", sid, "-p", "Type", "-p", "Desktop"],
                    capture_output=True, text=True, timeout=4).stdout
                vals = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
                typ = typ or vals.get("Type", "")
                bureau = bureau or vals.get("Desktop", "")
        except Exception:
            pass
    if not bureau and typ == "wayland" and os.path.exists("/run/user/1000/wayland-0"):
        bureau = "GNOME"
    return {"type": typ or "?", "wayland": typ == "wayland", "bureau": bureau or "?"}


def _env_session() -> dict:
    """Environnement garantissant l'accès au bus de session (utile sous systemd --user)."""
    env = dict(os.environ)
    if IS_WINDOWS:
        # os.getuid n'existe pas sous Windows (AttributeError mesurée le
        # 2026-09-15, avalée par _run et faisant échouer TOUTE commande avant
        # même le spawn). Pas de bus de session D-Bus non plus.
        env.setdefault("XDG_RUNTIME_DIR", runtime_dir())
        return env
    if not env.get("XDG_RUNTIME_DIR"):
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    if not env.get("DBUS_SESSION_BUS_ADDRESS"):
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={env['XDG_RUNTIME_DIR']}/bus"
    return env


def _run(cmd: list, timeout: int = 8) -> dict:
    """Exécute une commande bornée. Retourne toujours un dict, ne lève jamais."""
    try:
        extra = {}
        if IS_WINDOWS:
            # Jamais atteint avec le stub, mais si un jour un outil GNOME est
            # porté : pas de console clignotante, sortie cp850 tolérée.
            extra = {"creationflags": NO_WINDOW, "encoding": "utf-8", "errors": "replace"}
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=_env_session(), **extra)
        return {"code": p.returncode, "stdout": p.stdout.strip(),
                "stderr": p.stderr.strip(), "cmd": " ".join(cmd)}
    except subprocess.TimeoutExpired:
        return {"code": 124, "stdout": "", "stderr": f"délai dépassé ({timeout}s)",
                "cmd": " ".join(cmd)}
    except Exception as e:
        return {"code": 1, "stdout": "", "stderr": f"{type(e).__name__}: {e}",
                "cmd": " ".join(cmd)}


def _gvariant_py(brut: str):
    """'BOTTOM' -> BOTTOM · true -> True · uint32 0 -> 0 · 0.8 -> 0.8"""
    if brut is None:
        return None
    t = brut.strip()
    if t in ("true", "false"):
        return t == "true"
    for prefixe in ("uint32 ", "int32 ", "uint64 ", "int64 ", "double "):
        if t.startswith(prefixe):
            t = t[len(prefixe):].strip()
            break
    if len(t) >= 2 and t[0] == "'" and t[-1] == "'":
        return t[1:-1]
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _py_gvariant(valeur, type_: str) -> str:
    """Construit l'argument textuel attendu par « gsettings set »."""
    if type_ == "b":
        if isinstance(valeur, str):
            return "true" if valeur.strip().lower() in ("true", "1", "oui", "yes") else "false"
        return "true" if valeur else "false"
    if type_ in ("i", "u"):
        return str(int(valeur))
    if type_ == "d":
        return str(float(valeur))
    return f"'{valeur}'"


def _gsettings_get(schema: str, cle: str):
    r = _run(["gsettings", "get", schema, cle], timeout=5)
    if r["code"] != 0:
        return None
    return _gvariant_py(r["stdout"])


def _gsettings_set(schema: str, cle: str, valeur, type_: str) -> dict:
    arg = _py_gvariant(valeur, type_)
    return _run(["gsettings", "set", schema, cle, arg], timeout=6)


def _gsettings_writable(schema: str, cle: str) -> bool:
    r = _run(["gsettings", "writable", schema, cle], timeout=5)
    return r["code"] == 0 and r["stdout"].strip() == "true"


def _extension_active(ext_id: str) -> bool:
    r = _run(["gnome-extensions", "info", ext_id], timeout=6)
    return r["code"] == 0 and "ACTIVE" in r["stdout"]


def _bureau_dir() -> str:
    if IS_WINDOWS:
        return desktop_dir()   # SHGetKnownFolderPath (gère la redirection OneDrive)
    r = _run(["xdg-user-dir", "DESKTOP"], timeout=4)
    if r["code"] == 0 and r["stdout"] and os.path.isdir(r["stdout"]):
        return r["stdout"]
    for cand in (os.path.expanduser("~/Bureau"), os.path.expanduser("~/Desktop")):
        if os.path.isdir(cand):
            return cand
    return os.path.expanduser("~/Bureau")


# ═══════════════════════════════════════════════════════════════════════════
#  TRACE À TROIS ÉTAGES — ne fait JAMAIS échouer l'action métier
# ═══════════════════════════════════════════════════════════════════════════

_SCHEMA_TRACE = """
CREATE TABLE IF NOT EXISTS bureau_actions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  horodatage   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  machine      TEXT NOT NULL DEFAULT 'M4',
  domaine      TEXT NOT NULL,
  cle          TEXT,
  valeur_avant TEXT,
  valeur_apres TEXT,
  commande     TEXT,
  verdict      TEXT NOT NULL,
  mesure       TEXT,
  reversible   TEXT
);
CREATE INDEX IF NOT EXISTS idx_bureau_dom ON bureau_actions(domaine);
CREATE INDEX IF NOT EXISTS idx_bureau_hor ON bureau_actions(horodatage);
"""


def _tracer(domaine: str, cle: str, avant, apres, commande: str,
            verdict: str, mesure: str = "", reversible: str = "") -> None:
    """Étage 1 — journal append-only. Silencieux en cas d'échec, par conception."""
    try:
        con = sqlite3.connect(LOGS_DB, timeout=5.0)
        con.executescript(_SCHEMA_TRACE)
        con.execute(
            """INSERT INTO bureau_actions
               (machine, domaine, cle, valeur_avant, valeur_apres,
                commande, verdict, mesure, reversible)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (MACHINE, domaine, cle,
             None if avant is None else str(avant),
             None if apres is None else str(apres),
             commande, verdict, mesure, reversible))
        con.commit()
        con.close()
    except Exception:
        return


def _maj_etoile(cles: dict) -> None:
    """Étage 2 — état courant dans ÉTOILE (jarvis_project_state, key UNIQUE)."""
    if not cles:
        return
    try:
        con = sqlite3.connect(ETOILE_DB, timeout=5.0)
        for k, v in cles.items():
            con.execute(
                """INSERT INTO jarvis_project_state (ts, category, key, value, source)
                   VALUES (datetime('now','localtime'), 'hmi_desktop', ?, ?, 'bureau_engine')
                   ON CONFLICT(key) DO UPDATE SET
                     value = excluded.value,
                     source = excluded.source,
                     ts = excluded.ts""",
                (f"hmi_desktop.{k}", str(v)))
        con.commit()
        con.close()
    except Exception:
        return


def _maj_boyau(valise: str) -> None:
    """Étage 3 — doctrine : couche 09 HMI_DESKTOP du BIOS Boyau."""
    try:
        con = sqlite3.connect(ETOILE_DB, timeout=5.0)
        con.execute(
            "UPDATE bios_boyau_layers SET valise = ?, updated_at = datetime('now','localtime') "
            "WHERE layer_id = '09'", (valise,))
        con.commit()
        con.close()
    except Exception:
        return


def lire_traces(limite: int = 20) -> list:
    """Lecture des dernières lignes du journal (pour l'onglet BUREAU)."""
    try:
        con = sqlite3.connect(f"file:{LOGS_DB}?mode=ro", uri=True, timeout=3.0)
        con.row_factory = sqlite3.Row
        c = con.cursor()
        c.execute("""SELECT id, horodatage, domaine, cle, valeur_avant, valeur_apres,
                            verdict, mesure, reversible
                     FROM bureau_actions ORDER BY id DESC LIMIT ?""", (limite,))
        lignes = [dict(r) for r in c.fetchall()]
        con.close()
        return lignes
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
#  LECTEURS DE DOMAINE — aucun n'écrit quoi que ce soit
# ═══════════════════════════════════════════════════════════════════════════

def get_etat_barre() -> dict:
    cles = []
    for d in CLES_BARRE:
        cles.append({**d,
                     "valeur": _gsettings_get(SCHEMA_BARRE, d["cle"]),
                     "writable": _gsettings_writable(SCHEMA_BARRE, d["cle"])})
    return {"schema": SCHEMA_BARRE, "extension": EXT_BARRE,
            "active": _extension_active(EXT_BARRE), "cles": cles}


def get_etat_icones() -> dict:
    cles = []
    for d in CLES_ICONES:
        cles.append({**d,
                     "valeur": _gsettings_get(SCHEMA_ICONES, d["cle"]),
                     "writable": _gsettings_writable(SCHEMA_ICONES, d["cle"])})

    rep = _bureau_dir()
    total = executables = trusted = 0
    try:
        for f in sorted(os.listdir(rep)):
            if not f.endswith(".desktop"):
                continue
            chemin = os.path.join(rep, f)
            total += 1
            if os.access(chemin, os.X_OK):
                executables += 1
            r = _run(["gio", "info", "-a", "metadata::trusted", chemin], timeout=4)
            if r["code"] == 0 and "true" in r["stdout"]:
                trusted += 1
    except Exception:
        pass

    return {"schema": SCHEMA_ICONES, "extension": EXT_ICONES,
            "active": _extension_active(EXT_ICONES), "cles": cles,
            "lanceurs": {"repertoire": rep, "total": total,
                         "executables": executables, "trusted": trusted,
                         "a_traiter": max(0, total - min(executables, trusted))}}


def get_etat_verrous() -> dict:
    cles = []
    for d in CLES_VERROUS:
        cles.append({**d,
                     "valeur": _gsettings_get(d["schema"], d["cle"]),
                     "writable": _gsettings_writable(d["schema"], d["cle"])})

    # Audit dconf : un verrou dont la base n'est chargée par AUCUN profil est INERTE.
    bases_chargees, profils = set(), []
    try:
        for nom in sorted(os.listdir(DCONF_PROFILS)):
            chemin = os.path.join(DCONF_PROFILS, nom)
            contenu = ""
            try:
                with open(chemin, "r", errors="replace") as fh:
                    contenu = fh.read()
            except Exception:
                pass
            bases = re.findall(r"^\s*system-db:(\S+)", contenu, re.MULTILINE)
            bases_chargees.update(bases)
            profils.append({"nom": nom, "bases": bases})
    except FileNotFoundError:
        pass
    except Exception:
        pass

    locks, inertes = [], 0
    try:
        for entree in sorted(os.listdir(DCONF_DBS)):
            rep_locks = os.path.join(DCONF_DBS, entree, "locks")
            if not os.path.isdir(rep_locks):
                continue
            base = entree[:-2] if entree.endswith(".d") else entree
            for fichier in sorted(os.listdir(rep_locks)):
                chemin = os.path.join(rep_locks, fichier)
                try:
                    with open(chemin, "r", errors="replace") as fh:
                        verrouillees = [l.strip() for l in fh if l.strip()
                                        and not l.strip().startswith("#")]
                except Exception:
                    verrouillees = []
                charge = base in bases_chargees
                if not charge:
                    inertes += len(verrouillees)
                locks.append({"fichier": chemin, "base": base,
                              "cles": verrouillees, "nb": len(verrouillees),
                              "charge": charge,
                              "desactive": fichier.endswith(tuple([".desactive"])) or ".desactive" in fichier})
    except Exception:
        pass

    return {"cles": cles,
            "dconf": {"profils": profils, "bases_chargees": sorted(bases_chargees),
                      "locks": locks, "inertes": inertes,
                      "profil_user": os.path.exists(os.path.join(DCONF_PROFILS, "user"))}}


def _mutter_lire() -> dict:
    """GetCurrentState via gi/Gio, repli gdbus. Ne lève jamais."""
    # Voie A — gi.repository.Gio : dépaquetage propre, pas de parsing de GVariant.
    try:
        _assurer_gi_dist_packages()
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib  # noqa: F401
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        rep = bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST,
                            "GetCurrentState", None, None,
                            Gio.DBusCallFlags.NONE, 6000, None)
        serial, moniteurs, logiques, props = rep.unpack()

        mons = []
        for spec, modes, mprops in moniteurs:
            connecteur, fabricant, produit, serie = spec
            courant = next((m[0] for m in modes
                            if m[6].get("is-current")), None)
            mons.append({"connecteur": connecteur, "fabricant": fabricant,
                         "modele": produit,
                         "nom": mprops.get("display-name", produit),
                         "builtin": bool(mprops.get("is-builtin", False)),
                         "mode_courant": courant,
                         "modes": sorted({m[0].split("@")[0] for m in modes})})

        logs = []
        for x, y, echelle, transform, primaire, lmons, _lp in logiques:
            logs.append({"x": x, "y": y, "echelle": echelle,
                         "primaire": bool(primaire),
                         "connecteurs": [m[0] for m in lmons]})

        if len(logs) == 1 and len(logs[0]["connecteurs"]) > 1:
            mode = "MIROIR"
        elif len(logs) > 1:
            mode = "ETENDU"
        else:
            mode = "SIMPLE"

        return {"ok": True, "via": "gi/Gio", "serial": serial,
                "moniteurs": mons, "logiques": logs, "mode": mode,
                "apply_autorise": bool(props.get("apply-monitors-config-allowed", True)),
                "layout_mode": props.get("layout-mode")}
    except Exception as e:
        erreur_gi = f"{type(e).__name__}: {e}"

    # Voie B — repli gdbus dégradé : on ne déduit que le mode, par comptage.
    r = _run(["gdbus", "call", "--session", "--dest", MUTTER_DEST,
              "--object-path", MUTTER_PATH,
              "--method", f"{MUTTER_DEST}.GetCurrentState"], timeout=10)
    if r["code"] != 0:
        return {"ok": False, "via": "aucune", "erreur": erreur_gi or r["stderr"],
                "moniteurs": [], "logiques": [], "mode": "INCONNU"}
    connecteurs = sorted(set(re.findall(r"'(eDP-\d+|HDMI-\d+|DP-\d+)'", r["stdout"])))
    return {"ok": True, "via": "gdbus (dégradé)", "serial": None,
            "moniteurs": [{"connecteur": c} for c in connecteurs],
            "logiques": [], "mode": "INDETERMINE",
            "note": "gi indisponible — bascule d'écran désactivée", "erreur_gi": erreur_gi}


def get_etat_ecrans() -> dict:
    return _mutter_lire()


def _etat_stub_windows() -> dict:
    """Constat de MÊME FORME que get_bureau_etat() (tab_bureau.refresh_bureau
    accède aux clés sans .get) : vide, conforme, marqué indisponible. Aucune
    commande, aucune écriture — l'invariant du constat est conservé."""
    rep = _bureau_dir()
    etat = {
        "success": True,
        "machine": MACHINE,
        "session": _session_graphique(),
        "barre": {"schema": SCHEMA_BARRE, "extension": EXT_BARRE,
                  "active": None, "cles": []},
        "icones": {"schema": SCHEMA_ICONES, "extension": EXT_ICONES,
                   "active": None, "cles": [],
                   "lanceurs": {"repertoire": rep, "total": 0, "executables": 0,
                                "trusted": 0, "a_traiter": 0}},
        "verrous": {"cles": [],
                    "dconf": {"profils": [], "bases_chargees": [], "locks": [],
                              "inertes": 0, "profil_user": False}},
        "ecrans": {"ok": False, "via": "aucune", "mode": "INDISPONIBLE",
                   "moniteurs": [], "logiques": [],
                   "erreur": "Mutter/D-Bus inexistants sous Windows"},
        "conforme": True, "derives": [],
        "traces": lire_traces(20),
    }
    etat.update(indisponible("Pilotage du bureau GNOME"))
    etat["note"] = NOTE_WINDOWS
    return etat


def get_bureau_etat() -> dict:
    """CONSTAT global. N'écrit rien, nulle part. C'est l'invariant du module."""
    if IS_WINDOWS:
        return _etat_stub_windows()
    try:
        barre = get_etat_barre()
        icones = get_etat_icones()
        verrous = get_etat_verrous()
        ecrans = get_etat_ecrans()

        derives = []
        if not barre.get("active"):
            derives.append("extension du dock inactive")
        if not icones.get("active"):
            derives.append("extension des icônes inactive")
        for d in verrous["cles"]:
            if not d["writable"]:
                derives.append(f"clé non modifiable : {d['cle']}")
        if verrous["dconf"]["inertes"]:
            derives.append(f"{verrous['dconf']['inertes']} verrou(s) dconf inerte(s)")
        lanceurs = icones["lanceurs"]
        if lanceurs["a_traiter"]:
            derives.append(f"{lanceurs['a_traiter']} lanceur(s) à déverrouiller")

        return {
            "success": True,
            "machine": MACHINE,
            "session": _session_graphique(),
            "barre": barre, "icones": icones, "verrous": verrous, "ecrans": ecrans,
            "conforme": not derives, "derives": derives,
            "traces": lire_traces(20),
        }
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
#  ACTIONS — idempotentes, preuve APRÈS, rollback si la preuve manque
# ═══════════════════════════════════════════════════════════════════════════

def _appliquer_cle(domaine: str, schema: str, cle: str, valeur, type_: str) -> dict:
    """Cœur idempotent : lire → comparer → écrire → prouver → tracer (ou rollback)."""
    avant = _gsettings_get(schema, cle)
    voulue = _py_gvariant(valeur, type_)
    actuelle = _py_gvariant(avant, type_) if avant is not None else None
    reversible = f"gsettings set {schema} {cle} {_py_gvariant(avant, type_)}" if avant is not None else ""

    if actuelle == voulue:
        _tracer(domaine, f"{schema} {cle}", avant, avant,
                f"gsettings set {schema} {cle} {voulue}",
                "CONSTAT", "déjà conforme — aucune commande exécutée", reversible)
        return {"success": True, "verdict": "CONSTAT", "cle": cle,
                "valeur_avant": avant, "valeur_apres": avant,
                "message": f"{cle} était déjà à {avant}"}

    if not _gsettings_writable(schema, cle):
        _tracer(domaine, f"{schema} {cle}", avant, None,
                f"gsettings set {schema} {cle} {voulue}", "HORS-LOGICIEL",
                "clé verrouillée par un profil dconf système — root requis, "
                "voir jarvis-reconcilier / etat-desire.conf", reversible)
        return {"success": False, "verdict": "HORS-LOGICIEL", "cle": cle,
                "error": f"{cle} n'est pas modifiable (verrou dconf système)"}

    r = _gsettings_set(schema, cle, valeur, type_)
    apres = _gsettings_get(schema, cle)  # ← la PREUVE, relue APRÈS
    conforme = (_py_gvariant(apres, type_) == voulue) if apres is not None else False

    if r["code"] == 0 and conforme:
        _tracer(domaine, f"{schema} {cle}", avant, apres, r["cmd"], "APPLIQUE",
                f"preuve relue après action : {cle} = {apres}", reversible)
        return {"success": True, "verdict": "APPLIQUE", "cle": cle,
                "valeur_avant": avant, "valeur_apres": apres,
                "message": f"{cle} : {avant} → {apres}"}

    # Preuve absente → ROLLBACK
    if avant is not None:
        _gsettings_set(schema, cle, avant, type_)
    _tracer(domaine, f"{schema} {cle}", avant, apres, r["cmd"], "ECHEC",
            f"preuve absente (code {r['code']}) : {r['stderr'] or 'valeur non relue'} "
            f"— rollback vers {avant}", reversible)
    return {"success": False, "verdict": "ECHEC", "cle": cle,
            "error": r["stderr"] or f"valeur non confirmée après écriture ({apres})"}


def _recharger_extension(ext_id: str, domaine: str) -> dict:
    """Seul moyen sous Wayland de forcer un recalcul. JAMAIS gnome-shell --replace."""
    r1 = _run(["gnome-extensions", "disable", ext_id], timeout=10)
    time.sleep(0.8)
    r2 = _run(["gnome-extensions", "enable", ext_id], timeout=10)
    time.sleep(1.2)
    active = _extension_active(ext_id)
    cmd = f"gnome-extensions disable {ext_id} && gnome-extensions enable {ext_id}"
    if active:
        _tracer(domaine, ext_id, "ACTIVE", "ACTIVE", cmd, "APPLIQUE",
                "extension rechargée, état final ACTIVE vérifié", cmd)
        return {"success": True, "verdict": "APPLIQUE",
                "message": f"{ext_id} rechargée et ACTIVE"}
    _tracer(domaine, ext_id, "ACTIVE", "INACTIVE", cmd, "ECHEC",
            f"disable={r1['code']} enable={r2['code']} — état final non ACTIVE", cmd)
    return {"success": False, "verdict": "ECHEC",
            "error": f"{ext_id} n'est pas ACTIVE après rechargement"}


def _deverrouiller_lanceurs() -> dict:
    """Idempotent : ne touche QUE les lanceurs qui dévient. 0 modifié = sain."""
    rep = _bureau_dir()
    total = modifies = 0
    details = []
    try:
        for f in sorted(os.listdir(rep)):
            if not f.endswith(".desktop"):
                continue
            chemin = os.path.join(rep, f)
            total += 1
            besoin_x = not os.access(chemin, os.X_OK)
            info = _run(["gio", "info", "-a", "metadata::trusted", chemin], timeout=4)
            besoin_t = not (info["code"] == 0 and "true" in info["stdout"])
            if not (besoin_x or besoin_t):
                continue
            if besoin_x:
                try:
                    os.chmod(chemin, os.stat(chemin).st_mode | 0o111)
                except Exception:
                    pass
            if besoin_t:
                _run(["gio", "set", "-t", "string", chemin, "metadata::trusted", "true"], timeout=4)
                _run(["gio", "set", "-t", "string", chemin,
                      "metadata::nautilus-trusted-launcher", "true"], timeout=4)
            modifies += 1
            details.append(f)
    except Exception as e:
        return {"success": False, "verdict": "ECHEC", "error": f"{type(e).__name__}: {e}"}

    verdict = "APPLIQUE" if modifies else "CONSTAT"
    mesure = (f"{modifies} lanceur(s) modifié(s) sur {total}" if modifies
              else f"{total} lanceurs déjà exécutables et fiables — rien à faire")
    _tracer("ICONES", rep, f"{total} lanceurs", f"{modifies} modifiés",
            "chmod +x && gio set metadata::trusted true", verdict, mesure, "")
    return {"success": True, "verdict": verdict, "total": total,
            "modifies": modifies, "details": details[:20], "message": mesure}


def _action_ecrans(params: dict) -> dict:
    """Bascule miroir/étendu. Le serial est relu juste avant Apply (jeton unique)."""
    cible = (params.get("mode") or "").upper()
    if cible not in ("MIROIR", "ETENDU"):
        return {"success": False, "error": "mode attendu : MIROIR ou ETENDU"}

    etat = _mutter_lire()
    if not etat.get("ok") or etat.get("via", "").startswith("gdbus"):
        _tracer("ECRANS", "mode", etat.get("mode"), None, "ApplyMonitorsConfig",
                "HORS-LOGICIEL",
                "gi.repository indisponible — bascule d'écran refusée par sécurité", "")
        return {"success": False, "verdict": "HORS-LOGICIEL",
                "error": "pilotage des écrans indisponible (gi.repository absent)"}

    if etat["mode"] == cible:
        _tracer("ECRANS", "mode", cible, cible, "ApplyMonitorsConfig", "CONSTAT",
                "déjà dans ce mode — aucune commande exécutée", "")
        return {"success": True, "verdict": "CONSTAT",
                "message": f"les écrans sont déjà en {cible}"}

    mons = etat["moniteurs"]
    if len(mons) < 2:
        return {"success": False, "verdict": "CONSTAT",
                "error": "un seul écran connecté : rien à basculer"}

    try:
        _assurer_gi_dist_packages()
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        if cible == "MIROIR":
            communs = set(mons[0]["modes"])
            for m in mons[1:]:
                communs &= set(m["modes"])
            if not communs:
                _tracer("ECRANS", "mode", etat["mode"], None, "ApplyMonitorsConfig",
                        "ECHEC", "aucune définition commune aux deux écrans", "")
                return {"success": False, "verdict": "ECHEC",
                        "error": "aucune définition commune : miroir impossible"}
            choisi = sorted(communs, key=lambda r: int(r.split("x")[0]), reverse=True)[0]
            ecrans_log = [(0, 0, 1.0, 0, True,
                           [(m["connecteur"],
                             next(md for md in [m["mode_courant"]] if md) if m["mode_courant"]
                             and m["mode_courant"].startswith(choisi) else choisi, {})
                            for m in mons])]
        else:
            ecrans_log, decalage = [], 0
            for i, m in enumerate(mons):
                mode = m["mode_courant"] or (m["modes"][-1] if m["modes"] else "1920x1080")
                ecrans_log.append((decalage, 0, 1.0, 0, i == 0,
                                   [(m["connecteur"], mode, {})]))
                try:
                    decalage += int(mode.split("x")[0])
                except Exception:
                    decalage += 1920

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        frais = bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST,
                              "GetCurrentState", None, None,
                              Gio.DBusCallFlags.NONE, 6000, None).unpack()[0]

        gabarit = "(uua(iiduba(ssa{sv}))a{sv})"
        # method 0 = VERIFY : essai à blanc, ne change rien
        bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST, "ApplyMonitorsConfig",
                      GLib.Variant(gabarit, (frais, 0, ecrans_log, {})), None,
                      Gio.DBusCallFlags.NONE, 8000, None)
        # method 2 = PERSISTENT (1 = TEMPORARY s'auto-annule : piège)
        bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST, "ApplyMonitorsConfig",
                      GLib.Variant(gabarit, (frais, 2, ecrans_log, {})), None,
                      Gio.DBusCallFlags.NONE, 8000, None)

        time.sleep(1.5)
        apres = _mutter_lire()  # ← PREUVE
        if apres.get("mode") == cible:
            _tracer("ECRANS", "mode", etat["mode"], cible,
                    f"ApplyMonitorsConfig(method=2, {cible})", "APPLIQUE",
                    f"preuve relue : {len(apres['logiques'])} écran(s) logique(s)",
                    f"bascule inverse vers {etat['mode']}")
            return {"success": True, "verdict": "APPLIQUE",
                    "message": f"écrans basculés en {cible}", "etat": apres}

        _tracer("ECRANS", "mode", etat["mode"], apres.get("mode"),
                f"ApplyMonitorsConfig(method=2, {cible})", "ECHEC",
                f"preuve absente : mode relu = {apres.get('mode')}",
                f"bascule vers {etat['mode']}")
        return {"success": False, "verdict": "ECHEC",
                "error": f"mode relu après action : {apres.get('mode')} (attendu {cible})"}

    except Exception as e:
        _tracer("ECRANS", "mode", etat.get("mode"), None,
                f"ApplyMonitorsConfig({cible})", "ECHEC", f"{type(e).__name__}: {e}", "")
        return {"success": False, "verdict": "ECHEC", "error": f"{type(e).__name__}: {e}"}


# ── Table de dispatch déclarative ──
def _index_cles(liste, schema_defaut=None):
    return {d["cle"]: (d.get("schema", schema_defaut), d["type"]) for d in liste}


_IDX_BARRE = _index_cles(CLES_BARRE, SCHEMA_BARRE)
_IDX_ICONES = _index_cles(CLES_ICONES, SCHEMA_ICONES)
_IDX_VERROUS = _index_cles(CLES_VERROUS)

ACTIONS = [
    "constat", "barre.set", "barre.recharger", "icones.set", "icones.recharger",
    "icones.deverrouiller", "verrous.set", "verrous.tout-lever",
    "ecrans.miroir", "ecrans.etendu", "trace.recent",
]


def run_bureau_action(action: str, params: dict = None) -> dict:
    """Point d'entrée unique des actions. Ne laisse JAMAIS échapper d'exception."""
    params = params or {}
    try:
        if action not in ACTIONS:
            return {"success": False,
                    "error": f"action inconnue : {action}",
                    "actions_valides": ACTIONS}

        if action == "constat":
            return get_bureau_etat()
        if action == "trace.recent":
            return {"success": True, "traces": lire_traces(int(params.get("limite", 20)))}

        if IS_WINDOWS:
            # Refus net, SANS _tracer : le sondage du 2026-09-15 avait créé
            # jarvis_logs.db avec des lignes ECHEC fictives. Rien à écrire ici.
            return {"success": False, "verdict": "HORS-LOGICIEL", "action": action,
                    "indisponible": True, "plateforme": "windows",
                    "error": f"{action} : {NOTE_WINDOWS}"}

        with _VERROU:
            if action in ("barre.set", "icones.set", "verrous.set"):
                idx = {"barre.set": _IDX_BARRE, "icones.set": _IDX_ICONES,
                       "verrous.set": _IDX_VERROUS}[action]
                domaine = {"barre.set": "BARRE", "icones.set": "ICONES",
                           "verrous.set": "VERROUS"}[action]
                cle = params.get("cle")
                if cle not in idx:
                    return {"success": False,
                            "error": f"clé inconnue pour {action} : {cle}",
                            "cles_valides": sorted(idx)}
                schema, type_ = idx[cle]
                res = _appliquer_cle(domaine, schema, cle, params.get("valeur"), type_)
                _maj_etoile({f"{domaine.lower()}.{cle}": res.get("valeur_apres")})
                return res

            if action == "barre.recharger":
                return _recharger_extension(EXT_BARRE, "BARRE")
            if action == "icones.recharger":
                return _recharger_extension(EXT_ICONES, "ICONES")
            if action == "icones.deverrouiller":
                return _deverrouiller_lanceurs()

            if action == "verrous.tout-lever":
                resultats, appliques = [], 0
                for d in CLES_VERROUS:
                    voulue = 0 if d["type"] == "u" else False
                    r = _appliquer_cle("VERROUS", d["schema"], d["cle"], voulue, d["type"])
                    resultats.append(r)
                    if r.get("verdict") == "APPLIQUE":
                        appliques += 1
                _maj_etoile({"verrous.tous_leves": "oui", "verrous.leves_ce_passage": appliques})
                return {"success": True,
                        "verdict": "APPLIQUE" if appliques else "CONSTAT",
                        "appliques": appliques, "total": len(CLES_VERROUS),
                        "message": (f"{appliques} verrou(s) levé(s) sur {len(CLES_VERROUS)}"
                                    if appliques else
                                    f"les {len(CLES_VERROUS)} verrous étaient déjà levés"),
                        "details": resultats}

            if action in ("ecrans.miroir", "ecrans.etendu"):
                return _action_ecrans({"mode": "MIROIR" if action.endswith("miroir") else "ETENDU"})

        return {"success": False, "error": f"action non traitée : {action}"}

    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def sceller_doctrine() -> dict:
    """Inscrit le périmètre bureau dans la couche 09 HMI_DESKTOP du BIOS Boyau."""
    valise = ("Table Ronde TMUX, HUD, Dashboards, Bureau GNOME piloté "
              "(barre, icônes, verrous, écrans) — tracé bureau_actions + ÉTOILE")
    _maj_boyau(valise)
    return {"success": True, "valise": valise}
