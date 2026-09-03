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

PORT = 9222
BIN = "/opt/browseros/opt/browseros/browseros"
PROFIL_SRC = os.path.expanduser("~/chrome-m1")
PROFIL_CDP = os.path.expanduser("~/chrome-m1-cdp")
LOG_FILE = os.path.expanduser("~/jarvis/logs/browseros-cdp.log")


def is_cdp_alive() -> bool:
    """Vérifie si le port 9222 répond à /json/version."""
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
        
    script = os.path.expanduser("~/jarvis/bin/browseros-cdp-authentifie")
    if os.path.exists(script) and os.access(script, os.X_OK):
        r = subprocess.run([script, "demarrer"], capture_output=True, text=True, timeout=25)
        return {
            "success": (r.returncode == 0 or is_cdp_alive()),
            "output": r.stdout or r.stderr,
            "alive": is_cdp_alive()
        }
    return {"success": False, "error": "Script browseros-cdp-authentifie introuvable"}


def stop_cdp() -> dict:
    """Arrête le CDP 9222."""
    script = os.path.expanduser("~/jarvis/bin/browseros-cdp-authentifie")
    if os.path.exists(script):
        r = subprocess.run([script, "arreter"], capture_output=True, text=True, timeout=10)
        return {"success": True, "output": r.stdout or r.stderr}
    subprocess.run(f"pkill -f 'remote-debugging-port={PORT}'", shell=True)
    return {"success": True, "output": "Arrêt forcé"}


def verify_cdp() -> dict:
    """Vérifie l'authentification réelle de la session."""
    if not is_cdp_alive():
        return {"success": False, "error": f"CDP inactif sur :{PORT}. Démarrez-le d'abord."}
    script = os.path.expanduser("~/jarvis/bin/browseros-cdp-authentifie")
    if os.path.exists(script):
        r = subprocess.run([script, "verifier"], capture_output=True, text=True, timeout=35)
        is_auth = ("AUTHENTIFIE" in r.stdout and "NON AUTHENTIFIE" not in r.stdout)
        return {
            "success": is_auth,
            "output": r.stdout or r.stderr,
            "authenticated": is_auth
        }
    return {"success": False, "error": "Script de vérification introuvable"}
