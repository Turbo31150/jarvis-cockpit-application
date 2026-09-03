#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — APPLICATIONS & TOOLS REGISTRY
High-performance scanner and launcher for all desktop applications, launchers, and scripts.
"""

import os
import re
import json
import subprocess
import shutil
from .config import HOME, JARVIS_DIR, APP_CATEGORIES

PREFS_FILE = os.path.join(JARVIS_DIR, "cockpit", ".cockpit_prefs.json")


_SHELLS_NEUTRES = {"env", "sh", "bash", "/bin/bash", "/bin/sh", "xdg-open",
                   "gio", "flatpak", "snap", "nohup", "exec", "sudo"}


def cible_dispo(exec_cmd: str) -> bool:
    """Le binaire vise par un Exec= est-il reellement present ?

    Ajoute le 2026-09-03 : l'audit du bureau a trouve 21 lanceurs sur 225
    pointant dans le vide (11 vers /home/rempc, l'utilisateur d'une AUTRE
    machine). L'application les affichait comme les autres, sans rien dire ;
    on ne decouvrait la panne qu'au clic. On marque desormais l'entree.
    Un shell neutre en tete (env, bash, xdg-open...) n'est pas la vraie cible :
    on ne sait pas trancher sans interpreter la ligne, donc on ne juge pas.
    """
    if not exec_cmd:
        return False
    tete = exec_cmd.strip().strip('"').split()[0].strip('"')
    if tete in _SHELLS_NEUTRES:
        return True
    return bool(shutil.which(tete)) or os.path.exists(tete)


def categorize_app(name: str, path: str, exec_cmd: str) -> str:
    """Détermine intelligemment la catégorie d'une application."""
    s = f"{name} {path} {exec_cmd}".lower()
    
    if any(k in s for k in ["claude", "agent", "mistral", "vibe", "table ronde", "gemini", "antigravity", "openclaw", "board", "llm", "expert", "ia", "moisson"]):
        return "AGENTS & IA"
    elif any(k in s for k in ["m1", "m2", "m3", "m4", "m5", "m6", "cluster", "ssh", "direct", "asix", "sync", "wol", "wake"]):
        return "CLUSTER & MACHINES"
    elif any(k in s for k in ["chrome", "browser", "cdp", "n8n", "portainer", "requestly", "notion", "trello", "perplexity", "slack", "discord", "pwa"]):
        return "SAAS & WEB"
    elif any(k in s for k in ["terminal", "tmux", "code", "cursor", "ide", "git", "jupyter", "python", "docker", "postgres", "redis", "sql", "bash"]):
        return "DÉVELOPPEMENT"
    elif any(k in s for k in ["whisper", "vocal", "voice", "audio", "obs", "sound", "micro", "s8", "tts", "stt", "lumen", "screen", "capture"]):
        return "MULTIMÉDIA & AUDIO"
    elif any(k in s for k in ["w10", "windows", "bureau distant", "anydesk", "rdp", "clair", "remote"]):
        return "WINDOWS REMOTE"
    elif any(k in s for k in ["prospection", "linkedin", "upwork", "vente", "candidature", "lead", "moissonneur"]):
        return "PROSPECTION & VENTE"
    else:
        return "SYSTÈME & OUTILS"

def extract_desktop_entry(filepath: str) -> dict:
    """Extrait les métadonnées d'un fichier .desktop."""
    name, exec_cmd, icon, comment, terminal = "", "", "", "", False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Name=") and not name:
                    name = line.split("=", 1)[1]
                elif line.startswith("Exec=") and not exec_cmd:
                    exec_cmd = line.split("=", 1)[1]
                    exec_cmd = re.sub(r" %([fFuUdDnNickvm])", "", exec_cmd)
                elif line.startswith("Icon=") and not icon:
                    icon = line.split("=", 1)[1]
                elif line.startswith("Comment=") and not comment:
                    comment = line.split("=", 1)[1]
                elif line.startswith("Terminal="):
                    terminal = line.split("=", 1)[1].lower() == "true"
    except Exception:
        pass

    if not name:
        name = os.path.splitext(os.path.basename(filepath))[0].replace("-", " ").replace("_", " ").title()

    cat = categorize_app(name, filepath, exec_cmd)
    return {
        "name": name,
        "path": filepath,
        "exec": exec_cmd,
        "icon": icon or "utilities-terminal",
        "comment": comment,
        "terminal": terminal,
        "category": cat,
        "type": "desktop",
        "dispo": cible_dispo(exec_cmd),
    }

def scan_all_applications() -> list[dict]:
    """Scanne le Bureau, .local/share/applications et scripts clés."""
    apps = []
    seen_paths = set()
    bureau_dir = os.path.join(HOME, "Bureau")
    local_apps_dir = os.path.join(HOME, ".local", "share", "applications")

    # 1. Bureau (racine et sous-dossiers)
    if os.path.exists(bureau_dir):
        for root, dirs, files in os.walk(bureau_dir):
            if any(p in root for p in [".backup", "_RACCOURCIS_INACTIFS"]):
                continue
            for f in files:
                full_p = os.path.join(root, f)
                if f.endswith(".desktop") and full_p not in seen_paths:
                    seen_paths.add(full_p)
                    apps.append(extract_desktop_entry(full_p))
                elif f.endswith(".sh") and os.access(full_p, os.X_OK) and full_p not in seen_paths:
                    seen_paths.add(full_p)
                    name = os.path.splitext(f)[0].replace("-", " ").replace("_", " ").title()
                    cat = categorize_app(name, full_p, full_p)
                    apps.append({
                        "name": name,
                        "path": full_p,
                        "exec": f"bash '{full_p}'",
                        "icon": "application-x-executable",
                        "comment": f"Script Shell: {f}",
                        "terminal": True,
                        "category": cat,
                        "type": "script",
                        "dispo": True,
                    })

    # 1bis. Dossiers du Bureau — ajoute le 2026-09-03.
    # Le scan ne ramassait que les .desktop et les .sh : les DOSSIERS du bureau
    # (VENTE, publications-pretes, video1, 02_CLUSTER_ET_TERMINAUX, NOTION_JARVIS_BACKUP...)
    # n'apparaissaient nulle part dans l'application, alors qu'ils portent une
    # part du travail. La demande etant "tout dans une seule application",
    # ils deviennent des entrees ouvrables au meme titre que les lanceurs.
    if os.path.exists(bureau_dir):
        for nom in sorted(os.listdir(bureau_dir)):
            chemin = os.path.join(bureau_dir, nom)
            if not os.path.isdir(chemin) or nom.startswith("."):
                continue
            if chemin in seen_paths:
                continue
            seen_paths.add(chemin)
            try:
                nb = len(os.listdir(chemin))
            except OSError:
                nb = 0
            apps.append({
                "name": nom,
                "path": chemin,
                "exec": f"xdg-open '{chemin}'",
                "icon": "folder",
                "comment": f"Dossier du Bureau — {nb} element(s)",
                "terminal": False,
                "category": categorize_app(nom, chemin, chemin),
                "type": "dossier",
                "dispo": True,
            })

    # 2. .local/share/applications
    if os.path.exists(local_apps_dir):
        for f in os.listdir(local_apps_dir):
            if f.endswith(".desktop"):
                full_p = os.path.join(local_apps_dir, f)
                if full_p not in seen_paths:
                    seen_paths.add(full_p)
                    apps.append(extract_desktop_entry(full_p))

    # Tri par catégorie puis par nom
    apps.sort(key=lambda x: (x["category"], x["name"].lower()))
    return apps

def launch_application(app_entry: dict) -> tuple[bool, str]:
    """Lance une application de façon sécurisée et détachée."""
    path = app_entry.get("path", "")
    exec_cmd = app_entry.get("exec", "")
    terminal = app_entry.get("terminal", False)

    try:
        if path.endswith(".desktop") and shutil.which("gio"):
            subprocess.Popen(["gio", "launch", path], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            record_recent_launch(app_entry.get("name", ""))
            return True, f"Application lancée via GIO : {app_entry.get('name')}"
        elif terminal:
            # Lancement dans un terminal graphique
            term_bin = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator") or "xterm"
            subprocess.Popen([term_bin, "--title", app_entry.get("name", "JARVIS App"), "--", "bash", "-lc", exec_cmd or f"bash '{path}'"],
                             start_new_session=True)
            record_recent_launch(app_entry.get("name", ""))
            return True, f"Lancé dans le terminal : {app_entry.get('name')}"
        else:
            cmd = exec_cmd if exec_cmd else f"bash '{path}'"
            subprocess.Popen(cmd, shell=True, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            record_recent_launch(app_entry.get("name", ""))
            return True, f"Processus détaché lancé : {app_entry.get('name')}"
    except Exception as e:
        return False, f"Erreur lors du lancement : {e}"

def load_prefs() -> dict:
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"favorites": [], "recents": []}

def save_prefs(prefs: dict):
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass

def record_recent_launch(name: str):
    prefs = load_prefs()
    recents = prefs.get("recents", [])
    if name in recents:
        recents.remove(name)
    recents.insert(0, name)
    prefs["recents"] = recents[:20]
    save_prefs(prefs)
