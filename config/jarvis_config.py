#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS OS & BOX — CONFIGURATION SOUVERAINE DÉCOUPLÉE
===================================================
Module d'abstraction des chemins d'accès et des paramètres de l'appliance.
Élimine tout chemin codé en dur ("/home/turbo") pour garantir la portabilité
sur n'importe quel matériel cible (JARVIS Box, serveur sur site, conteneur).

Copie du module vivant du rig (~/jarvis/config/jarvis_config.py) : sur le rig,
la racine est ~/jarvis (parent de config/). Ici, dans le dépôt cockpit, la
racine de DONNÉES est JARVIS_HOME (%USERPROFILE%\\jarvis sous Windows, posé par
jarvis_cockpit_launcher.pyw / JARVIS-Cockpit.cmd) — jamais le dépôt lui-même.
"""

import os
import sys
import platform
import socket

# Détection automatique de la racine JARVIS
_DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JARVIS_ROOT = os.environ.get("JARVIS_ROOT") or os.environ.get("JARVIS_HOME") or _DEFAULT_ROOT

# Arborescence standard
CONFIG_DIR = os.path.join(JARVIS_ROOT, "config")
DATA_DIR = os.environ.get("JARVIS_DATA", os.path.join(JARVIS_ROOT, "data"))
LOGS_DIR = os.environ.get("JARVIS_LOGS", os.path.join(JARVIS_ROOT, "logs"))
SCRIPTS_DIR = os.path.join(JARVIS_ROOT, "scripts")
COCKPIT_DIR = os.path.join(JARVIS_ROOT, "cockpit")
BOARD_DIR = os.path.join(JARVIS_ROOT, "board")
OMEGA_DIR = os.path.join(JARVIS_ROOT, "omega")

# Bases de données SQLite souveraines
MASTER_DB = os.environ.get("JARVIS_MASTER_DB", os.path.join(JARVIS_ROOT, "jarvis_master.db"))
BOARD_DB = os.environ.get("JARVIS_BOARD_DB", os.path.join(BOARD_DIR, "board.db"))
DOMINO_DB = os.path.join(OMEGA_DIR, "domino-continu", "domino_continu.db")

# Environnement d'exécution Python
VENV_PYTHON = os.environ.get("JARVIS_PYTHON", os.path.join(JARVIS_ROOT, ".venv", "bin", "python3"))
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

# Sécurité & Authentification (P0)
JARVIS_AUTH_TOKEN = os.environ.get("JARVIS_AUTH_TOKEN", "")
REQUIRE_AUTH = os.environ.get("JARVIS_REQUIRE_AUTH", "0").lower() in ("1", "true", "yes")

TOKEN_FILE = os.path.join(CONFIG_DIR, "auth_token.secret")
if not JARVIS_AUTH_TOKEN:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                JARVIS_AUTH_TOKEN = f.read().strip()
        except Exception:
            pass
    if not JARVIS_AUTH_TOKEN:
        import secrets
        JARVIS_AUTH_TOKEN = secrets.token_hex(24)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(JARVIS_AUTH_TOKEN)
            os.chmod(TOKEN_FILE, 0o600)
        except Exception:
            pass


def rotate_auth_token() -> str:
    """Régénère un jeton Bearer cryptographique et met à jour TOKEN_FILE (0600)."""
    global JARVIS_AUTH_TOKEN
    import secrets
    JARVIS_AUTH_TOKEN = secrets.token_hex(24)
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(JARVIS_AUTH_TOKEN)
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass
    return JARVIS_AUTH_TOKEN


def is_authorized(client_ip: str, headers: dict, params: dict = None) -> bool:
    """Valide l'accès : Loopback sans restriction, LAN/WAN filtré par Bearer Token."""
    clean_ip = (client_ip or "").replace("::ffff:", "")
    # Loopback toujours autorisé sans friction (Application Bureau locale)
    if clean_ip in ("127.0.0.1", "::1", "localhost") or clean_ip.startswith("127."):
        return True

    token = None
    auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Jarvis-Token" in headers or "x-jarvis-token" in headers:
        token = headers.get("X-Jarvis-Token") or headers.get("x-jarvis-token")
    elif params and "token" in params:
        t = params.get("token")
        token = t[0] if isinstance(t, list) else t

    if JARVIS_AUTH_TOKEN and token == JARVIS_AUTH_TOKEN:
        return True

    # Tether USB téléphone ou Tailscale si REQUIRE_AUTH n'est pas forcé à 1
    if not REQUIRE_AUTH:
        if clean_ip.startswith("192.168.42."):
            return True
        try:
            parts = clean_ip.split(".")
            if len(parts) >= 2:
                a, b = parts[:2]
                if a == "100" and 64 <= int(b) <= 127:
                    return True
        except Exception:
            pass

    return False


# Création automatique des répertoires vitaux
for d in (DATA_DIR, LOGS_DIR, CONFIG_DIR):
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass


def resolve_path(path_str: str) -> str:
    """Résout un chemin relatif à JARVIS_ROOT ou absolu."""
    if not path_str:
        return JARVIS_ROOT
    if os.path.isabs(path_str):
        return os.path.normpath(path_str)
    return os.path.normpath(os.path.join(JARVIS_ROOT, path_str))


def get_environment_summary() -> dict:
    """Fournit la synthèse de l'environnement de l'appliance pour l'audit."""
    return {
        "jarvis_root": JARVIS_ROOT,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "venv_python": VENV_PYTHON,
        "master_db_exists": os.path.exists(MASTER_DB),
        "board_db_exists": os.path.exists(BOARD_DB),
        "auth_enabled": REQUIRE_AUTH or bool(JARVIS_AUTH_TOKEN),
        "board_db_size_mb": round(os.path.getsize(BOARD_DB) / (1024**2), 1) if os.path.exists(BOARD_DB) else 0,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_environment_summary(), indent=2, ensure_ascii=False))
