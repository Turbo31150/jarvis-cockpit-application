#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CDP AUTHENTIFIÉ (PORT 9222) ENGINE
===================================================
Gestionnaire intégré de session Chrome/BrowserOS avec port de débogage 9222 :
  • Démarrage / Arrêt du CDP authentifié avec clonage de session
  • Télémétrie et liste des onglets ouverts (/json/list)
  • Vérification temps réel de l'authentification LinkedIn
"""

import os
import json
import time
import socket
import urllib.request
import subprocess
from .platform_compat import (
    IS_WINDOWS, HOME, JARVIS_DIR, find_browser, run_cmd, popen_detached_kwargs,
    kill_processes_matching, local_listening_ports, unavailable,
)

PORT = 9222


def _premier_binaire(candidats):
    """Retourne le premier binaire existant/exécutable parmi les candidats."""
    for c in candidats:
        c = os.path.expanduser(c)
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


# Chemins réels de la machine (rig « mining ») : le binaire browseros vit sous
# ~/.local/bin, pas /opt. On retombe sur google-chrome si browseros est absent.
if IS_WINDOWS:
    # Windows : chrome.exe (Program Files / LOCALAPPDATA) puis msedge.exe en dernier recours.
    BIN = find_browser() or ""
else:
    BIN = _premier_binaire([
        "~/.local/bin/browseros",
        "/opt/browseros/opt/browseros/browseros",
        "/usr/bin/google-chrome",
        "/opt/google/chrome/chrome",
    ]) or "/usr/bin/google-chrome"
PROFIL_SRC = os.path.join(HOME, "chrome-m1")
PROFIL_CDP = os.path.join(HOME, "chrome-m1-cdp")
LOG_FILE = os.path.join(JARVIS_DIR, "logs", "browseros-cdp.log")
# Script bash du rig (absent sous Windows → repli lancement direct du navigateur)
SCRIPT_CDP = os.path.join(JARVIS_DIR, "bin", "browseros-cdp-authentifie")


def _script_utilisable() -> bool:
    """Le script authentifié du rig n'est exécutable que hors Windows (bash)."""
    return (not IS_WINDOWS) and os.path.exists(SCRIPT_CDP) and os.access(SCRIPT_CDP, os.X_OK)


def is_cdp_alive() -> bool:
    """Vérifie si le port 9222 répond à /json/version."""
    if IS_WINDOWS:
        # Port loopback fermé = ~1,2 s brûlées sous Windows → pré-test psutil (2 ms)
        ports = local_listening_ports()
        if ports and PORT not in ports:
            return False
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/version")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_cdp_status() -> dict:
    """Récupère l'état complet du CDP 9222, version et liste des onglets."""
    alive = is_cdp_alive()
    tabs = []
    version_info = {}
    
    if alive:
        try:
            req_v = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/version")
            with urllib.request.urlopen(req_v, timeout=1.5) as r:
                version_info = json.loads(r.read().decode())
        except Exception:
            pass

        try:
            req_t = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/list")
            with urllib.request.urlopen(req_t, timeout=1.5) as r:
                tabs = json.loads(r.read().decode())
        except Exception:
            pass

    return {
        "alive": alive,
        "port": PORT,
        "profile_source": PROFIL_SRC,
        "profile_cdp": PROFIL_CDP,
        "browser": version_info.get("Browser", "BrowserOS CDP"),
        "user_agent": version_info.get("User-Agent", ""),
        "tabs_count": len(tabs),
        "tabs": [
            {
                "id": t.get("id"),
                "title": t.get("title", "Sans titre"),
                "url": t.get("url", ""),
                "type": t.get("type", "page")
            }
            for t in tabs[:10]
        ]
    }


def start_cdp() -> dict:
    """Démarre le service CDP 9222 en arrière-plan."""
    if is_cdp_alive():
        return {"success": True, "message": f"CDP déjà actif sur le port {PORT}."}
        
    if _script_utilisable():
        r = run_cmd([SCRIPT_CDP, "demarrer"], timeout=25)
        return {
            "success": (r.returncode == 0 or is_cdp_alive()),
            "output": r.stdout or r.stderr,
            "alive": is_cdp_alive()
        }

    # ── Repli : lancement direct du navigateur avec débogage distant sur 9222 ──
    # Le script authentifié est absent : on démarre le binaire détecté (browseros
    # ou google-chrome) en headless=new avec un profil CDP dédié. headless évite
    # tout dialogue GUI bloquant et ne dépend pas d'un affichage.
    if not BIN or not os.path.exists(BIN):
        return {"success": False, "error": "Aucun navigateur (browseros/chrome) trouvé"}
    os.makedirs(PROFIL_CDP, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    cmd = [
        BIN,
        f"--remote-debugging-port={PORT}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={PROFIL_CDP}",
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "about:blank",
    ]
    try:
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as log:
            # Linux : start_new_session=True ; Windows : DETACHED_PROCESS|NEW_PROCESS_GROUP
            subprocess.Popen(cmd, stdout=log, stderr=log, **popen_detached_kwargs())
    except Exception as e:
        return {"success": False, "error": f"Lancement échoué : {e}"}
    for _ in range(20):
        if is_cdp_alive():
            break
        time.sleep(0.5)
    return {
        "success": is_cdp_alive(),
        "output": f"Lancé : {BIN} (headless, profil {PROFIL_CDP})",
        "alive": is_cdp_alive(),
    }


def stop_cdp() -> dict:
    """Arrête le CDP 9222."""
    if not IS_WINDOWS and os.path.exists(SCRIPT_CDP):
        r = run_cmd([SCRIPT_CDP, "arreter"], timeout=10)
        return {"success": True, "output": r.stdout or r.stderr}
    if IS_WINDOWS:
        # pkill n'existe pas sous Windows → psutil (terminate puis kill) sur la ligne de commande
        n = kill_processes_matching(f"remote-debugging-port={PORT}")
        return {"success": True, "output": f"Arrêt forcé ({n} processus)"}
    subprocess.run(f"pkill -f 'remote-debugging-port={PORT}'", shell=True)
    return {"success": True, "output": "Arrêt forcé"}


def verify_cdp() -> dict:
    """Vérifie l'authentification réelle de la session."""
    if not is_cdp_alive():
        return {"success": False, "error": f"CDP inactif sur :{PORT}. Démarrez-le d'abord."}
    if IS_WINDOWS:
        return unavailable("Vérification d'authentification CDP (script du rig)", authenticated=False)
    if os.path.exists(SCRIPT_CDP):
        r = run_cmd([SCRIPT_CDP, "verifier"], timeout=35)
        is_auth = ("AUTHENTIFIE" in r.stdout and "NON AUTHENTIFIE" not in r.stdout)
        return {
            "success": is_auth,
            "output": r.stdout or r.stderr,
            "authenticated": is_auth
        }
    return {"success": False, "error": "Script de vérification introuvable"}
