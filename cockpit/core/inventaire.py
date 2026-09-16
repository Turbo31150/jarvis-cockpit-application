#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventaire.py — JARVIS COCKPIT · RECENSEMENT DU MATERIEL ET DES BASES DEPORTEES

Ajoute le 2026-09-03. Le cockpit savait deja recenser les bases SQLite (65),
les applications et les services swarm, mais trois familles manquaient :

  · PostgreSQL — 2 conteneurs pgvector/pg16 tournent (jarvis-postgres,
    jarvis-pg-biblio) et :5432 est ouvert ; aucune vue dans l'application.
  · Tailscale  — 6 pairs declares, dont l'etat conditionne la voie vers M6.
  · Peripheriques — disques, cles USB, GPU, interfaces reseau.

Regle de conduite tenue ici : on ne rend que ce qui est MESURE. Une commande
absente ou un service muet donne un etat explicite ("indisponible", avec la
raison), jamais une valeur inventee ni un tableau vide qui ressemble a un
succes. Toute sonde porte un timeout : le cockpit se rafraichit en boucle et
un appel bloquant y gele l'interface entiere.
"""

import json
import os
import shutil
import subprocess

from .platform_compat import (IS_WINDOWS, run_cmd_ok, tailscale_cmd, tailscale_reason,
                              list_disks, list_usb, list_net_ifaces, nvidia_smi_exe)

TIMEOUT = 6
DOCKER = os.path.expanduser("~/jarvis/bin/jarvis-docker")
# Docker Desktop expose son moteur par ce tube nomme ; absent = moteur arrete.
# Sans ce test, `docker ps` echoue proprement mais en 1,5 s (mesure 2026-09-15).
DOCKER_PIPE_WIN = r"\\.\pipe\docker_engine"
# Le CLI Windows met 1,7 a 3 s a repondre meme pour `version` (mesure) :
# 3 s etait trop juste et rendait un faux "depassement".
TAILSCALE_TIMEOUT_WIN = 8


def _run(cmd, timeout=TIMEOUT):
    """Execute une commande et rend (ok, sortie). Ne leve jamais."""
    if IS_WINDOWS:
        # CREATE_NO_WINDOW (pas de console clignotante depuis pythonw) et
        # decodage tolerant (sortie console en cp850/cp1252).
        return run_cmd_ok(cmd, timeout=timeout)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except FileNotFoundError:
        return False, f"commande introuvable : {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"depassement de {timeout}s"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ─────────────────────────────── POSTGRESQL ───────────────────────────────

def get_postgres() -> dict:
    """Conteneurs PostgreSQL et bases qu'ils portent.

    On passe par ~/jarvis/bin/jarvis-docker et non par `docker` nu : la pile
    locale est PERIMEE et des ecritures y ont deja ete perdues (incident du
    2026-08-11). Le wrapper vise la bonne pile.
    """
    binaire = DOCKER if os.path.exists(DOCKER) else shutil.which("docker")
    if not binaire:
        return {"disponible": False, "raison": "ni jarvis-docker ni docker",
                "conteneurs": []}
    if IS_WINDOWS and not os.path.exists(DOCKER_PIPE_WIN):
        return {"disponible": False,
                "raison": "Docker Desktop arrete (tube docker_engine absent)",
                "conteneurs": []}

    ok, out = _run([binaire, "ps", "--format",
                    "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"])
    if not ok:
        return {"disponible": False, "raison": out[:200], "conteneurs": []}

    conteneurs = []
    for ligne in out.splitlines():
        p = ligne.split("|")
        if len(p) < 3:
            continue
        nom, image, statut = p[0], p[1], p[2]
        if "postgres" not in (nom + image).lower() and "pgvector" not in image.lower():
            continue
        entree = {"nom": nom, "image": image, "statut": statut,
                  "ports": p[3] if len(p) > 3 else "", "bases": [],
                  "bases_erreur": None}
        # L'utilisateur n'est PAS "postgres" ici : l'image porte POSTGRES_USER
        # (mesure du 2026-09-03 : "jarvis"). Et il faut passer par TCP —
        # psql sur le socket unix du conteneur echoue ("role ... does not exist"
        # pour postgres, socket refuse par defaut). On lit donc l'utilisateur
        # dans l'environnement du conteneur, puis on force -h 127.0.0.1.
        utilisateur = "postgres"
        ok_env, env = _run([binaire, "exec", nom, "env"], timeout=8)
        if ok_env:
            for l in env.splitlines():
                if l.startswith("POSTGRES_USER="):
                    utilisateur = l.split("=", 1)[1].strip() or utilisateur
                    break
        entree["utilisateur"] = utilisateur
        # -d postgres explicite : sans base nommee, psql vise une base
        # homonyme de l'utilisateur, qui n'existe pas sur jarvis-pg-biblio
        # (mesure du 2026-09-03 : FATAL database "jarvis" does not exist).
        ok2, out2 = _run([binaire, "exec", nom, "psql", "-h", "127.0.0.1",
                          "-U", utilisateur, "-d", "postgres",
                          "-tAc", "SELECT datname||'|'||"
                          "pg_size_pretty(pg_database_size(datname)) "
                          "FROM pg_database WHERE NOT datistemplate "
                          "ORDER BY pg_database_size(datname) DESC"], timeout=12)
        if ok2:
            for l in out2.splitlines():
                if "|" in l:
                    d, t = l.split("|", 1)
                    entree["bases"].append({"nom": d.strip(), "taille": t.strip()})
        else:
            # Cause honnete plutot qu'une liste vide qui passerait pour un succes.
            entree["bases_erreur"] = out2[:160]
        conteneurs.append(entree)

    return {"disponible": True, "conteneurs": conteneurs,
            "total_bases": sum(len(c["bases"]) for c in conteneurs)}


# ─────────────────────────────── TAILSCALE ────────────────────────────────

def get_tailscale() -> dict:
    """Pairs du tailnet, avec en ligne de mire l'accessibilite de M6."""
    if IS_WINDOWS:
        # Le CLI Windows parle au service par tube nomme : JAMAIS --socket
        # (l'ancienne sonde de socket unix rendait un faux "demon inactif").
        base = tailscale_cmd()
        if not base:
            return {"disponible": False, "raison": tailscale_reason() or "tailscale absent",
                    "pairs": []}
        ok, out = _run(base + ["status", "--json"], timeout=TAILSCALE_TIMEOUT_WIN)
    else:
        ts_bin = shutil.which("tailscale") or os.path.expanduser("~/.local/bin/tailscale")
        if not (ts_bin and os.path.exists(ts_bin)):
            return {"disponible": False, "raison": "tailscale absent", "pairs": []}

        # Socket : système OU userspace custom (rig 'mining' : tailscaled --tun=userspace-networking,
        # socket ~/.config/tailscale-state/tailscaled.sock). L'ancien test ne voyait que le socket
        # système → renvoyait toujours "démon inactif" alors que le tailnet marche via SOCKS5 :1055.
        sock = next((s for s in (
            "/var/run/tailscale/tailscaled.sock",
            "/run/tailscale/tailscaled.sock",
            os.path.expanduser("~/.config/tailscale-state/tailscaled.sock"),
        ) if os.path.exists(s)), None)
        if not sock:
            return {"disponible": False, "raison": "démon tailscaled inactif (socket absent)", "pairs": []}

        ok, out = _run([ts_bin, "--socket", sock, "status", "--json"], timeout=3)
    if not ok:
        return {"disponible": False, "raison": out[:200], "pairs": []}
    try:
        d = json.loads(out)
    except json.JSONDecodeError as e:
        return {"disponible": False, "raison": f"JSON illisible: {e}", "pairs": []}

    def _ligne(p, moi=False):
        return {
            "nom": (p.get("HostName") or p.get("DNSName", "").split(".")[0] or "?"),
            "ip": (p.get("TailscaleIPs") or ["?"])[0],
            "os": p.get("OS", ""),
            "en_ligne": bool(p.get("Online")),
            "actif": bool(p.get("Active")),
            "relais": p.get("Relay", ""),
            "vu_le": p.get("LastSeen", ""),
            "rx": p.get("RxBytes", 0),
            "tx": p.get("TxBytes", 0),
            "moi": moi,
        }

    # Les "funnel-ingress-node" sont des relais d'infrastructure Tailscale,
    # pas des machines du parc : 20 d'entre eux noyaient les 6 vraies machines
    # dans la liste (mesure du 2026-09-03). On les compte a part.
    pairs = [_ligne(d.get("Self", {}), moi=True)]
    infra = 0
    for p in (d.get("Peer") or {}).values():
        if "funnel-ingress" in (p.get("HostName") or "").lower():
            infra += 1
            continue
        pairs.append(_ligne(p))
    pairs.sort(key=lambda x: (not x["moi"], not x["en_ligne"], x["nom"]))
    return {"disponible": True, "pairs": pairs,
            "en_ligne": sum(1 for p in pairs if p["en_ligne"]),
            "total": len(pairs),
            "relais_infra_masques": infra,
            "etat_backend": d.get("BackendState", "")}


# ────────────────────────────── PERIPHERIQUES ─────────────────────────────

def _gpu_nvidia(inv: dict, binaire: str = "nvidia-smi") -> None:
    ok, out = _run([binaire, "--query-gpu=index,name,temperature.gpu,"
                    "memory.used,memory.total,utilization.gpu",
                    "--format=csv,noheader,nounits"], timeout=10)
    if ok:
        for l in out.splitlines():
            c = [x.strip() for x in l.split(",")]
            if len(c) >= 6:
                inv["gpu"].append({
                    "index": c[0], "nom": c[1], "temperature_c": c[2],
                    "vram_utilisee_mo": c[3], "vram_totale_mo": c[4],
                    "charge_pct": c[5],
                })


def _peripheriques_windows() -> dict:
    """Meme schema que sous Linux ; lsblk/lsusb/ip n'existent pas : psutil pour
    les disques et le reseau, PowerShell Get-PnpDevice pour l'USB (1-4 s,
    borne — appele depuis un thread de requete, jamais du thread GUI).
    Une famille vide porte sa raison dans `raisons` plutot qu'un tableau vide
    qui passerait pour un succes."""
    inv = {"disques": [], "usb": [], "gpu": [], "reseau": [], "raisons": {}}
    try:
        inv["disques"] = list_disks()
    except Exception as e:
        inv["raisons"]["disques"] = f"{type(e).__name__}: {e}"
    if not inv["disques"]:
        inv["raisons"].setdefault("disques", "psutil indisponible")

    try:
        usb, raison = list_usb(timeout=8)
        inv["usb"] = usb
        if raison:
            inv["raisons"]["usb"] = raison
    except Exception as e:
        inv["raisons"]["usb"] = f"{type(e).__name__}: {e}"

    smi = nvidia_smi_exe()
    if smi:
        _gpu_nvidia(inv, smi)
    else:
        inv["raisons"]["gpu"] = "nvidia-smi introuvable"

    try:
        inv["reseau"] = list_net_ifaces()
    except Exception as e:
        inv["raisons"]["reseau"] = f"{type(e).__name__}: {e}"
    if not inv["reseau"]:
        inv["raisons"].setdefault("reseau", "psutil indisponible")
    return inv


def get_peripheriques() -> dict:
    """Disques, USB, GPU et interfaces reseau reellement presents."""
    if IS_WINDOWS:
        inv = _peripheriques_windows()
        inv["resume"] = {
            "disques": len(inv["disques"]),
            "usb": sum(1 for u in inv["usb"] if not u["hub"]),
            "gpu": len(inv["gpu"]),
            "reseau": len(inv["reseau"]),
        }
        return inv

    inv = {"disques": [], "usb": [], "gpu": [], "reseau": []}

    ok, out = _run(["lsblk", "-J", "-o",
                    "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,FSUSE%"])
    if ok:
        try:
            def _plat(n, parent=None):
                if n.get("type") != "loop":
                    inv["disques"].append({
                        "nom": n.get("name", ""), "taille": n.get("size", ""),
                        "type": n.get("type", ""),
                        "montage": n.get("mountpoint") or "",
                        "modele": (n.get("model") or parent or "").strip(),
                        "usage": n.get("fsuse%") or "",
                    })
                for e in n.get("children", []):
                    _plat(e, parent=n.get("model"))
            for n in json.loads(out).get("blockdevices", []):
                _plat(n)
        except (json.JSONDecodeError, KeyError):
            pass

    ok, out = _run(["lsusb"])
    if ok:
        for l in out.splitlines():
            # "Bus 003 Device 005: ID 0951:1666 Kingston ..."
            if ": ID " not in l:
                continue
            tete, reste = l.split(": ID ", 1)
            morceaux = tete.split()
            ident, _, libelle = reste.partition(" ")
            inv["usb"].append({
                "bus": morceaux[1] if len(morceaux) > 1 else "",
                "device": morceaux[3] if len(morceaux) > 3 else "",
                "id": ident, "libelle": libelle.strip(),
                "hub": "root hub" in l,
            })

    _gpu_nvidia(inv)

    ok, out = _run(["ip", "-br", "-j", "addr"])
    if ok:
        try:
            for i in json.loads(out):
                nom = i.get("ifname", "")
                if nom == "lo" or nom.startswith(("veth", "br-", "docker")):
                    continue
                inv["reseau"].append({
                    "nom": nom,
                    "etat": i.get("operstate", ""),
                    "mac": i.get("address", ""),
                    "adresses": [a.get("local", "") for a in i.get("addr_info", [])],
                })
        except json.JSONDecodeError:
            pass

    inv["resume"] = {
        "disques": len(inv["disques"]),
        # Les root hubs ne sont pas des peripheriques branches : on les exclut
        # du compte pour ne pas gonfler artificiellement le chiffre affiche.
        "usb": sum(1 for u in inv["usb"] if not u["hub"]),
        "gpu": len(inv["gpu"]),
        "reseau": len(inv["reseau"]),
    }
    return inv


def get_inventaire_complet() -> dict:
    return {"postgres": get_postgres(),
            "tailscale": get_tailscale(),
            "peripheriques": get_peripheriques()}
