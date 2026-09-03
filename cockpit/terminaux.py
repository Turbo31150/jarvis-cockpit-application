#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — MOTEUR DE TERMINAUX INTERACTIFS (PTY + TMUX)
=============================================================
Sert l'onglet « Terminal & Bash » du cockpit : au lieu d'un unique
`subprocess.run` en un coup (aucun dialogue possible), chaque application est
lancée dans un VRAI pseudo-terminal, lui-même client d'une session TMUX.
On DIALOGUE ainsi avec les CLI interactives de l'écosystème — Claude Code,
Antigravity (agy), Gemini, le Board, l'orchestrateur JMO, un shell Bash, un
REPL Python, une session SSH M6 — et l'on rattache aussi les hubs tmux déjà
debout (COCKPIT, jarvis-cluster, JARVIS-SHELLS…).

Pourquoi tmux plutôt qu'un PTY nu :
  • la session SURVIT au rechargement du navigateur et au redémarrage du
    serveur cockpit — le PTY nu mourait avec la page ;
  • elle est rattachable depuis un vrai terminal (`tmux attach -t jc-claude`),
    donc le cockpit et le terminal physique voient la MÊME session ;
  • le multiplexage (fenêtres, volets) est celui que Turbo utilise déjà.

Rattachement sans effet de bord : une vue sur une session existante passe par
une session GROUPÉE (`new-session -t cible`). Elle partage les fenêtres mais
garde sa propre taille — sans quoi ouvrir le cockpit rétrécirait la session
ouverte dans le terminal physique à la taille de l'onglet web.

Le flux binaire brut du PTY est renvoyé en base64 : aucune séquence ANSI n'est
perdue, et un caractère UTF-8 coupé en deux entre deux lectures ne casse rien.
"""

import os
import pty
import signal
import base64
import shlex
import shutil
import struct
import fcntl
import termios
import threading
import subprocess
import time
import uuid

HOME = os.path.expanduser("~")

# Fenêtre de sortie conservée par session. Au-delà, on rogne le début : c'est
# un terminal, pas un journal — l'historique long vit dans les logs des apps.
TAILLE_TAMPON = 512 * 1024
MAX_SESSIONS = 12
# Une session morte reste lisible un moment : l'utilisateur doit pouvoir lire
# le message d'erreur d'une app qui a quitté aussitôt.
RETENTION_MORTE_S = 900


# ---------------------------------------------------------------------------
# COUCHE TMUX
# ---------------------------------------------------------------------------

TMUX = shutil.which("tmux")
# Préfixe des sessions créées par le cockpit : `tmux ls` reste lisible et
# `tmux attach -t jc-claude` fonctionne depuis n'importe quel terminal.
PREFIXE_APP = "jc-"
# Une vue est jetable : elle ne porte aucun état, seulement une taille.
PREFIXE_VUE = "cockpit-vue-"
TOUT_OUVRIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmux-tout-ouvrir.sh")


def tmux_sessions():
    """Sessions tmux réellement vivantes, avec leurs fenêtres."""
    if not TMUX:
        return []
    fmt = "#{session_name}\t#{session_windows}\t#{session_attached}\t#{session_created}\t#{session_group}"
    r = subprocess.run([TMUX, "ls", "-F", fmt], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    out = []
    for ligne in r.stdout.splitlines():
        champs = ligne.split("\t")
        if len(champs) < 5:
            continue
        nom = champs[0]
        # Les vues du cockpit sont un détail d'implémentation : les lister
        # ferait croire à des sessions de travail qu'elles ne sont pas.
        if nom.startswith(PREFIXE_VUE):
            continue
        fen = subprocess.run(
            [TMUX, "list-windows", "-t", f"={nom}", "-F", "#{window_index}:#{window_name}:#{pane_current_command}"],
            capture_output=True, text=True)
        out.append({
            "nom": nom,
            "fenetres": int(champs[1]) if champs[1].isdigit() else 0,
            "attachee": champs[2] == "1",
            "cree": int(champs[3]) if champs[3].isdigit() else 0,
            "cockpit": nom.startswith(PREFIXE_APP),
            "detail": [l for l in fen.stdout.splitlines() if l],
        })
    return sorted(out, key=lambda x: x["nom"])


def tmux_tout_ouvrir():
    """Rejoue le lanceur de hubs tmux du cockpit (idempotent)."""
    if not os.path.exists(TOUT_OUVRIR):
        return {"success": False, "sortie": f"script absent : {TOUT_OUVRIR}"}
    r = subprocess.run(["bash", TOUT_OUVRIR], capture_output=True, text=True, timeout=90)
    return {"success": r.returncode == 0, "sortie": (r.stdout + r.stderr).strip(),
            "sessions": tmux_sessions()}


def _enveloppe(app):
    """Enveloppe shell autour de la commande de l'app.

    Deux apps sur trois du catalogue ne sont PAS des REPL : `board.py` sans
    argument imprime son aide et rend 0, `lms` et `jarvis` aussi. Lancées nues,
    elles refermaient la session dans la seconde — l'onglet mourait avant
    d'avoir montré quoi que ce soit (mesuré sur board : code 0 en 4 s).

    On rend donc la main à un shell interactif après l'app : la sortie reste
    lisible, et la sous-commande suivante se tape sur place.
    """
    # La barre de statut par défaut se redessine toutes les secondes ; à 5 s
    # elle reste utile sans réveiller le client en continu.
    calme = 'tmux set-option -q status-interval 5 2>/dev/null || true'
    cmd = " ".join(shlex.quote(x) for x in app["cmd"])
    fin = (f'printf "\n\033[38;5;244m── %s terminé (code %s) — shell rendu, '
           f'\033[0m\033[38;5;51m{shlex.quote(app["cmd"][0])}\033[38;5;244m relançable ──\033[0m\n" '
           f'{shlex.quote(app["nom"])} "$?"')
    return f'{calme}; {cmd}; {fin}; exec /bin/bash -i'


def _cmd_app(app, cols, rows):
    """Commande à lancer dans le PTY pour dialoguer avec `app`.

    Sous tmux : `-A` rattache la session si elle existe déjà, ce qui rend le
    bouton idempotent — recliquer sur « Claude Code » retrouve la conversation
    en cours au lieu d'en démarrer une seconde en parallèle.
    """
    interne = ["/bin/bash", "-lc", _enveloppe(app)]
    if not TMUX:
        return interne, None
    nom = PREFIXE_APP + app["id"]
    return ([TMUX, "new-session", "-A", "-s", nom, "-x", str(cols), "-y", str(rows), "--"]
            + interne), nom


def _cmd_vue(cible, cols, rows):
    """Commande PTY pour observer une session tmux existante sans la rétrécir."""
    nom = PREFIXE_VUE + uuid.uuid4().hex[:6]
    # `-t cible` groupe la vue avec la session : fenêtres partagées, taille
    # indépendante. Surtout PAS `destroy-unattached` ici — la session naît
    # détachée, l'option la tuerait dans l'intervalle avant l'attachement
    # (vue morte en 40 octets, mesuré). Le ménage est fait explicitement par
    # Session.fermer() et par la purge, donc sous notre contrôle.
    script = (f"{TMUX} new-session -d -s {nom} -t {cible} -x {cols} -y {rows} && "
              f"exec {TMUX} attach-session -t {nom}")
    return ["/bin/bash", "-c", script], nom


def _tuer_vue(nom):
    if TMUX and nom and nom.startswith(PREFIXE_VUE):
        subprocess.run([TMUX, "kill-session", "-t", f"={nom}"],
                       capture_output=True, text=True)


def purger_vues_orphelines():
    """Vues tmux dont plus aucun client cockpit ne dépend."""
    if not TMUX:
        return 0
    r = subprocess.run([TMUX, "ls", "-F", "#{session_name}\t#{session_attached}"],
                       capture_output=True, text=True)
    n = 0
    for ligne in r.stdout.splitlines():
        champs = ligne.split("\t")
        if len(champs) == 2 and champs[0].startswith(PREFIXE_VUE) and champs[1] == "0":
            _tuer_vue(champs[0])
            n += 1
    return n


# ---------------------------------------------------------------------------
# CATALOGUE DES APPLICATIONS DIALOGUABLES
# ---------------------------------------------------------------------------
# `sonde` est le chemin/binaire dont l'existence est VÉRIFIÉE à chaud avant
# d'annoncer une app comme disponible. Rien n'est présenté comme utilisable
# sans cette mesure : « installé » et « lançable » ne sont pas la même chose.

CATALOGUE = [
    {
        "id": "bash", "nom": "Bash", "groupe": "Système", "icone": "fa-terminal",
        "couleur": "#a78bfa", "sonde": "/bin/bash", "cmd": ["/bin/bash", "-il"],
        "desc": "Shell de connexion complet, alias JARVIS chargés.",
    },
    {
        "id": "claude", "nom": "Claude Code", "groupe": "Agents IA", "icone": "fa-robot",
        "couleur": "#f59e0b", "sonde": f"{HOME}/.local/bin/claude",
        "cmd": [f"{HOME}/.local/bin/claude"],
        "desc": "Agent Claude Code (cloud Anthropic). Consomme des tokens.",
    },
    {
        "id": "claude-m6", "nom": "Claude Code · M6", "groupe": "Agents IA", "icone": "fa-microchip",
        "couleur": "#10b981", "sonde": f"{HOME}/.local/bin/claude-m6",
        "cmd": [f"{HOME}/.local/bin/claude-m6", "--model", "qwen2.5-coder-14b-instruct"],
        "desc": "Claude Code branché sur les GPU de M6 — 0 token.",
    },
    {
        "id": "agy", "nom": "Antigravity (agy)", "groupe": "Agents IA", "icone": "fa-meteor",
        "couleur": "#38bdf8", "sonde": f"{HOME}/.local/bin/agy",
        "cmd": [f"{HOME}/.local/bin/agy"],
        "desc": "Agent CLI Antigravity, session interactive.",
    },
    {
        "id": "gemini", "nom": "Gemini CLI", "groupe": "Agents IA", "icone": "fa-gem",
        "couleur": "#818cf8", "sonde": f"{HOME}/.local/bin/gemini",
        "cmd": [f"{HOME}/.local/bin/gemini", "--yolo"],
        "desc": "Gemini CLI en mode YOLO (auto-approbation).",
    },
    {
        "id": "jmo", "nom": "JMO Orchestrateur", "groupe": "Agents IA", "icone": "fa-sitemap",
        "couleur": "#fb7185", "sonde": f"{HOME}/jarvis/bin/jarvis-master-orchestrateur",
        "cmd": ["python3", f"{HOME}/jarvis/bin/jarvis-master-orchestrateur"],
        "desc": "Double maître orchestrateur local.",
    },
    {
        "id": "board", "nom": "Bibliothèque Vivante", "groupe": "Savoir", "icone": "fa-book-open",
        "couleur": "#22d3ee", "sonde": f"{HOME}/jarvis/board/board.py",
        "cmd": ["python3", f"{HOME}/jarvis/board/board.py", "status"],
        "desc": "Board OS — état du corpus, puis shell pour `ask`, `ingest`, `embed`.",
    },
    {
        "id": "table-ronde", "nom": "Table Ronde", "groupe": "Savoir", "icone": "fa-users-viewfinder",
        "couleur": "#a3e635", "sonde": f"{HOME}/jarvis/board/dispatch_table_ronde.py",
        "cmd": ["python3", f"{HOME}/jarvis/board/dispatch_table_ronde.py"],
        "desc": "Débat multi-experts avec citations du corpus.",
    },
    {
        "id": "qwen-cli", "nom": "Qwen CLI", "groupe": "Agents IA", "icone": "fa-comment-dots",
        "couleur": "#2dd4bf", "sonde": f"{HOME}/.shell-remotes/qwen-cli.sh",
        "cmd": ["bash", f"{HOME}/.shell-remotes/qwen-cli.sh"],
        "desc": "Inférence interactive Qwen sur le cluster local.",
    },
    {
        "id": "jarvis", "nom": "CLI JARVIS", "groupe": "Système", "icone": "fa-wand-magic-sparkles",
        "couleur": "#f472b6", "sonde": f"{HOME}/.local/bin/jarvis",
        "cmd": [f"{HOME}/.local/bin/jarvis"],
        "desc": "Méta-lanceur des briques souveraines JARVIS.",
    },
    {
        "id": "ollama", "nom": "Ollama · gemma3:4b", "groupe": "Modèles", "icone": "fa-brain",
        "couleur": "#34d399", "sonde": "/usr/local/bin/ollama",
        "cmd": ["/usr/local/bin/ollama", "run", "gemma3:4b"],
        "desc": "Modèle local M4, dialogue direct — 0 token.",
    },
    {
        "id": "lms", "nom": "LM Studio CLI", "groupe": "Modèles", "icone": "fa-server",
        "couleur": "#60a5fa", "sonde": f"{HOME}/.lmstudio/bin/lms",
        "cmd": [f"{HOME}/.lmstudio/bin/lms", "ps"],
        "desc": "Pilotage LM Studio (modèles chargés, statut).",
    },
    {
        "id": "m6-ssh", "nom": "SSH · M6", "groupe": "Cluster", "icone": "fa-network-wired",
        "couleur": "#fbbf24", "sonde": "/usr/bin/ssh",
        "cmd": ["/usr/bin/ssh", "m6"],
        "desc": "Session sur la tour multi-GPU par le câble direct.",
    },
    {
        "id": "python", "nom": "Python 3", "groupe": "Système", "icone": "fa-code",
        "couleur": "#facc15", "sonde": "/usr/bin/python3",
        "cmd": ["/usr/bin/python3", "-q"],
        "desc": "REPL Python interactif.",
    },
    {
        "id": "htop", "nom": "htop", "groupe": "Système", "icone": "fa-gauge-high",
        "couleur": "#94a3b8", "sonde": "htop",
        "cmd": ["htop"],
        "desc": "Moniteur système temps réel.",
    },
]

APPS_PAR_ID = {a["id"]: a for a in CATALOGUE}


def _resoudre(sonde):
    """Chemin absolu de la sonde, ou None si l'app n'est pas installée."""
    if os.path.sep in sonde:
        return sonde if os.path.exists(sonde) else None
    return shutil.which(sonde)


def catalogue_mesure():
    """Catalogue enrichi de la disponibilité RÉELLE, mesurée à l'instant."""
    out = []
    for a in CATALOGUE:
        chemin = _resoudre(a["sonde"])
        out.append({
            "id": a["id"], "nom": a["nom"], "groupe": a["groupe"],
            "icone": a["icone"], "couleur": a["couleur"], "desc": a["desc"],
            "cmd": " ".join(a["cmd"]),
            "dispo": chemin is not None,
            "chemin": chemin or "",
        })
    return out


# ---------------------------------------------------------------------------
# SESSIONS PTY
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, app_id, nom, cmd, cols=120, rows=32, cwd=None, tmux_nom=None):
        self.id = uuid.uuid4().hex[:12]
        self.app_id = app_id
        self.nom = nom
        self.cmd = list(cmd)
        self.tmux_nom = tmux_nom
        # Nom de la session tmux JETABLE créée pour cette vue (vide pour une
        # app : sa session, elle, doit survivre).
        self.vue_tmux = ""
        self.cree_a = time.time()
        self.fin_a = None
        self.code_sortie = None
        self._verrou = threading.Lock()
        # `base` = nombre d'octets déjà rognés du début du tampon. Le client
        # raisonne en offset absolu depuis le début de la session ; sans ce
        # décalage, un rognage ferait silencieusement rejouer du vieux texte.
        self._base = 0
        self._tampon = bytearray()
        # Réveille les lecteurs en attente longue : sans lui, le client devrait
        # sonder en boucle serrée pour rester réactif.
        self._reveil = threading.Event()

        env = os.environ.copy()
        env.update({
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "LANG": env.get("LANG") or "fr_FR.UTF-8",
            "LC_ALL": env.get("LC_ALL") or env.get("LANG") or "fr_FR.UTF-8",
            "COLUMNS": str(cols),
            "LINES": str(rows),
            "JARVIS_COCKPIT_TERM": "1",
        })
        # Un pager qui attend une touche bloque une session qu'on ne voit pas
        # forcément : on le neutralise d'office.
        env.setdefault("PAGER", "cat")

        self.maitre, esclave = pty.openpty()
        _fixer_taille(self.maitre, cols, rows)

        def _preexec():
            # Nouvelle session + PTY comme terminal contrôlant : c'est ce qui
            # rend Ctrl-C, le redimensionnement et les TUI réellement corrects.
            os.setsid()
            fcntl.ioctl(esclave, termios.TIOCSCTTY, 0)

        try:
            self.proc = subprocess.Popen(
                self.cmd,
                stdin=esclave, stdout=esclave, stderr=esclave,
                cwd=cwd or HOME, env=env,
                preexec_fn=_preexec, close_fds=True,
            )
        finally:
            os.close(esclave)

        self.lecteur = threading.Thread(target=self._boucle_lecture, daemon=True)
        self.lecteur.start()

    def _boucle_lecture(self):
        while True:
            try:
                bloc = os.read(self.maitre, 65536)
            except OSError:
                bloc = b""
            if not bloc:
                break
            with self._verrou:
                self._tampon.extend(bloc)
                surplus = len(self._tampon) - TAILLE_TAMPON
                if surplus > 0:
                    del self._tampon[:surplus]
                    self._base += surplus
            self._reveil.set()
        self.code_sortie = self.proc.wait()
        self.fin_a = time.time()
        self._reveil.set()

    # -- lecture / écriture ------------------------------------------------
    def lire_attendre(self, offset, delai=20.0):
        """Lecture bloquante : rend la main dès qu'il y a des octets.

        Le sondage serré (60 ms) marchait mais tournait à vide en permanence :
        la barre de statut tmux se redessine chaque seconde, donc le client
        n'aurait JAMAIS considéré la session calme. L'attente longue supprime
        le problème à la racine — une requête dort jusqu'à ce qu'il se passe
        quelque chose, au lieu de demander seize fois par seconde s'il se passe
        quelque chose.
        """
        fin_attente = time.time() + delai
        while True:
            data, fin = self.lire(offset)
            if data or not self.vivante():
                return data, fin
            reste = fin_attente - time.time()
            if reste <= 0:
                return b"", fin
            self._reveil.clear()
            self._reveil.wait(min(reste, 1.0))

    def lire(self, offset):
        """Octets produits depuis `offset` (offset absolu de session)."""
        with self._verrou:
            fin = self._base + len(self._tampon)
            depart = max(offset, self._base)
            if depart >= fin:
                return b"", fin
            return bytes(self._tampon[depart - self._base:]), fin

    def ecrire(self, data: bytes):
        if not self.vivante():
            return False
        try:
            os.write(self.maitre, data)
            return True
        except OSError:
            return False

    def redimensionner(self, cols, rows):
        try:
            _fixer_taille(self.maitre, cols, rows)
            if self.vivante():
                os.killpg(os.getpgid(self.proc.pid), signal.SIGWINCH)
            return True
        except OSError:
            return False

    def signaler(self, sig):
        if not self.vivante():
            return False
        try:
            os.killpg(os.getpgid(self.proc.pid), sig)
            return True
        except OSError:
            return False

    def vivante(self):
        return self.proc.poll() is None

    def fermer(self):
        if self.vivante():
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGHUP)
                time.sleep(0.15)
                if self.vivante():
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except OSError:
                pass
        try:
            os.close(self.maitre)
        except OSError:
            pass
        _tuer_vue(self.vue_tmux)

    def resume(self):
        with self._verrou:
            octets = self._base + len(self._tampon)
        return {
            "id": self.id, "app": self.app_id, "nom": self.nom,
            "pid": self.proc.pid, "vivante": self.vivante(),
            "code_sortie": self.code_sortie,
            "cree_a": self.cree_a, "age_s": round(time.time() - self.cree_a, 1),
            "octets": octets, "tmux": self.tmux_nom or "",
        }


def _fixer_taille(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


class Gestionnaire:
    def __init__(self):
        self.sessions = {}
        self._verrou = threading.Lock()

    def _purger(self):
        purger_vues_orphelines()
        maintenant = time.time()
        for sid, s in list(self.sessions.items()):
            if s.fin_a and (maintenant - s.fin_a) > RETENTION_MORTE_S:
                s.fermer()
                del self.sessions[sid]

    def _place_libre(self):
        self._purger()
        vivantes = sum(1 for s in self.sessions.values() if s.vivante())
        if vivantes >= MAX_SESSIONS:
            raise RuntimeError(f"limite de {MAX_SESSIONS} sessions simultanées atteinte")

    def ouvrir(self, app_id, cols=120, rows=32):
        app = APPS_PAR_ID.get(app_id)
        if not app:
            raise ValueError(f"application inconnue : {app_id}")
        if _resoudre(app["sonde"]) is None:
            raise FileNotFoundError(f"{app['nom']} n'est pas installé sur cette machine")
        cmd, tmux_nom = _cmd_app(app, cols, rows)
        with self._verrou:
            self._place_libre()
            s = Session(app["id"], app["nom"], cmd, cols=cols, rows=rows, tmux_nom=tmux_nom)
            self.sessions[s.id] = s
            return s

    def ouvrir_vue(self, cible, cols=120, rows=32):
        """Rattache une session tmux DÉJÀ debout (hub COCKPIT, jarvis-cluster…)."""
        if not TMUX:
            raise RuntimeError("tmux n'est pas installé sur cette machine")
        if not any(x["nom"] == cible for x in tmux_sessions()):
            raise KeyError(f"session tmux introuvable : {cible}")
        cmd, tmux_nom = _cmd_vue(cible, cols, rows)
        with self._verrou:
            self._place_libre()
            s = Session("tmux", f"tmux · {cible}", cmd, cols=cols, rows=rows, tmux_nom=cible)
            s.vue_tmux = tmux_nom
            self.sessions[s.id] = s
            return s

    def get(self, sid):
        s = self.sessions.get(sid)
        if not s:
            raise KeyError("session inconnue ou expirée")
        return s

    def fermer(self, sid):
        with self._verrou:
            s = self.sessions.pop(sid, None)
        if s:
            s.fermer()
            return True
        return False

    def lister(self):
        with self._verrou:
            self._purger()
            return [s.resume() for s in self.sessions.values()]


GESTIONNAIRE = Gestionnaire()


# ---------------------------------------------------------------------------
# COUCHE API — appelée par serveur.py
# ---------------------------------------------------------------------------

def api_apps():
    return {"success": True, "apps": catalogue_mesure(),
            "max_sessions": MAX_SESSIONS, "sessions": GESTIONNAIRE.lister(),
            "tmux_dispo": TMUX is not None, "tmux": tmux_sessions()}


def api_ouvrir(d):
    cols, rows = int(d.get("cols", 120)), int(d.get("rows", 32))
    if d.get("tmux"):
        s = GESTIONNAIRE.ouvrir_vue(d["tmux"], cols, rows)
    else:
        s = GESTIONNAIRE.ouvrir(d.get("app", "bash"), cols, rows)
    r = s.resume()
    r["success"] = True
    return r


def api_tmux():
    return {"success": True, "dispo": TMUX is not None, "sessions": tmux_sessions()}


def api_tmux_tout_ouvrir():
    return tmux_tout_ouvrir()


def api_lire(sid, offset, attente=20.0):
    s = GESTIONNAIRE.get(sid)
    data, fin = s.lire_attendre(offset, attente) if attente > 0 else s.lire(offset)
    return {
        "success": True, "id": sid,
        "data": base64.b64encode(data).decode("ascii"),
        "offset": fin, "vivante": s.vivante(), "code_sortie": s.code_sortie,
    }


def api_ecrire(d):
    s = GESTIONNAIRE.get(d.get("id", ""))
    brut = d.get("data", "")
    octets = base64.b64decode(brut) if d.get("b64") else brut.encode("utf-8")
    return {"success": s.ecrire(octets), "vivante": s.vivante()}


def api_redimensionner(d):
    s = GESTIONNAIRE.get(d.get("id", ""))
    return {"success": s.redimensionner(int(d.get("cols", 120)), int(d.get("rows", 32)))}


SIGNAUX = {"INT": signal.SIGINT, "TERM": signal.SIGTERM,
           "QUIT": signal.SIGQUIT, "KILL": signal.SIGKILL}


def api_signal(d):
    s = GESTIONNAIRE.get(d.get("id", ""))
    sig = SIGNAUX.get(str(d.get("sig", "INT")).upper())
    if sig is None:
        raise ValueError("signal non autorisé")
    return {"success": s.signaler(sig)}


def api_fermer(d):
    return {"success": GESTIONNAIRE.fermer(d.get("id", ""))}


def api_sessions():
    return {"success": True, "sessions": GESTIONNAIRE.lister()}
