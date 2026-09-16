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
from .platform_compat import (IS_WINDOWS, LAUNCHER_EXTS, desktop_dir, app_launcher_dirs,
                              bash_exe, exec_head, open_path_msg, open_in_terminal,
                              popen_detached, which)

PREFS_FILE = os.path.join(JARVIS_DIR, "cockpit", ".cockpit_prefs.json")


_SHELLS_NEUTRES = {"env", "sh", "bash", "/bin/bash", "/bin/sh", "xdg-open",
                   "gio", "flatpak", "snap", "nohup", "exec", "sudo",
                   # interpréteurs Windows (inoffensif sous Linux)
                   "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
                   "wt", "wt.exe", "start", "explorer", "explorer.exe", "wsl", "wsl.exe"}

# Scan Windows : le Bureau de ce poste porte des projets entiers (mesuré le
# 2026-09-15 : 6 605 dossiers / 36 088 fichiers, 2 s de parcours complet).
# On borne la profondeur et on saute les dossiers de build ; le Menu Démarrer
# (233 raccourcis) se parcourt en 10 ms.
_WIN_PROFONDEUR_MAX = 2
_WIN_DOSSIERS_IGNORES = {".git", "node_modules", "__pycache__", ".venv", "venv",
                         "dist", "build", ".backup", "_raccourcis_inactifs"}


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
    if IS_WINDOWS:
        # shlex posix=False : `"C:\Program Files\X\x.exe" --flag` -> chemin complet,
        # et non 'C:\Program' (jugé introuvable).
        tete = exec_head(exec_cmd)
    else:
        tete = exec_cmd.strip().strip('"').split()[0].strip('"')
    if tete.lower() in _SHELLS_NEUTRES:
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

def extract_win_entry(filepath: str, origine: str = "", base: str = "") -> dict | None:
    """Entrée Windows (.lnk/.url/.exe/.bat/.cmd/.ps1/.sh) sans résolution COM :
    os.startfile résout lui-même les .lnk, inutile (et trop lent pour ~300
    raccourcis) de passer par WScript.Shell. None si l'extension est inconnue.
    La catégorie est calculée sur le chemin RELATIF à `base` : le chemin absolu
    du Menu Démarrer contient « Microsoft » et « Windows », ce qui classait
    184 entrées sur 307 en MULTIMÉDIA (mot-clé « micro », mesuré le 2026-09-15)."""
    ext = os.path.splitext(filepath)[1].lower()
    chemin_cat = os.path.relpath(filepath, base) if base else os.path.basename(filepath)
    nom_fichier = os.path.basename(filepath)
    name = os.path.splitext(nom_fichier)[0].replace("_", " ").strip() or nom_fichier
    if ext in (".lnk", ".url"):
        typ, terminal, icon = "raccourci", False, ("web" if ext == ".url" else "application")
        exec_cmd, dispo = filepath, True
        comment = ("Raccourci web" if ext == ".url" else "Raccourci") + (f" — {origine}" if origine else "")
    elif ext == ".exe":
        typ, terminal, icon = "exe", False, "application-x-executable"
        exec_cmd, dispo = f'"{filepath}"', True
        comment = f"Exécutable : {nom_fichier}"
    elif ext in (".bat", ".cmd"):
        typ, terminal, icon = "script", True, "utilities-terminal"
        exec_cmd, dispo = f'"{filepath}"', True
        comment = f"Script cmd : {nom_fichier}"
    elif ext == ".ps1":
        typ, terminal, icon = "script", True, "utilities-terminal"
        psh = which("powershell") or "powershell.exe"
        exec_cmd, dispo = f'"{psh}" -NoProfile -ExecutionPolicy Bypass -File "{filepath}"', True
        comment = f"Script PowerShell : {nom_fichier}"
    elif ext == ".sh":
        typ, terminal, icon = "script", True, "utilities-terminal"
        bash = bash_exe()   # Git bash uniquement — jamais System32\bash.exe (WSL)
        exec_cmd = f'"{bash}" -l "{filepath}"' if bash else f'bash "{filepath}"'
        dispo = bool(bash)
        comment = f"Script Shell : {nom_fichier}" + ("" if bash else " (Git bash introuvable)")
    else:
        return None
    return {
        "name": name,
        "path": filepath,
        "exec": exec_cmd,
        "icon": icon,
        "comment": comment,
        "terminal": terminal,
        # exec (chemin absolu / Git bash) volontairement exclu du classement.
        "category": categorize_app(name, chemin_cat, ""),
        "type": typ,
        "dispo": dispo,
    }


def _scan_windows(apps: list, seen_paths: set) -> None:
    """Bureau (profondeur bornée) + menus Démarrer utilisateur et machine."""
    bureau = desktop_dir()
    if os.path.isdir(bureau):
        for root, dirs, files in os.walk(bureau):
            profondeur = 0 if root == bureau else os.path.relpath(root, bureau).count(os.sep) + 1
            if profondeur >= _WIN_PROFONDEUR_MAX:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs
                           if not d.startswith(".") and d.lower() not in _WIN_DOSSIERS_IGNORES]
            for f in files:
                if not f.lower().endswith(LAUNCHER_EXTS):
                    continue
                full_p = os.path.join(root, f)
                if full_p in seen_paths:
                    continue
                entree = extract_win_entry(full_p, "Bureau", bureau)
                if entree:
                    seen_paths.add(full_p)
                    apps.append(entree)

        # Dossiers du Bureau : ouverts par l'Explorateur (os.startfile).
        for nom in sorted(os.listdir(bureau)):
            chemin = os.path.join(bureau, nom)
            if not os.path.isdir(chemin) or nom.startswith(".") or chemin in seen_paths:
                continue
            seen_paths.add(chemin)
            try:
                nb = len(os.listdir(chemin))
            except OSError:
                nb = 0
            apps.append({
                "name": nom, "path": chemin, "exec": chemin, "icon": "folder",
                "comment": f"Dossier du Bureau — {nb} element(s)", "terminal": False,
                "category": categorize_app(nom, nom, ""), "type": "dossier",
                "dispo": True,
            })

    for base in app_launcher_dirs():
        libelle = "Menu Démarrer" + (" (machine)" if "programdata" in base.lower() else "")
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if not f.lower().endswith((".lnk", ".url")):
                    continue
                full_p = os.path.join(root, f)
                if full_p in seen_paths:
                    continue
                sous = os.path.relpath(root, base)
                entree = extract_win_entry(full_p, libelle + ("" if sous == "." else f" · {sous}"), base)
                if entree:
                    seen_paths.add(full_p)
                    apps.append(entree)


def scan_all_applications() -> list[dict]:
    """Scanne le Bureau, .local/share/applications et scripts clés."""
    apps = []
    seen_paths = set()
    if IS_WINDOWS:
        try:
            _scan_windows(apps, seen_paths)
        except Exception:
            pass
        apps.sort(key=lambda x: (x["category"], x["name"].lower()))
        return apps

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

    if IS_WINDOWS:
        return _launch_windows(app_entry)

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

def _launch_windows(app_entry: dict) -> tuple[bool, str]:
    """Lancement Windows : jamais `bash '<chemin>'` en shell=True (sur ce poste
    `bash` du PATH est le lanceur WSL, mesuré le 2026-09-15). Les scripts
    console partent dans une NOUVELLE console avec leurs handles standard
    (rien n'est redirigé : sous pythonw les handles hérités sont invalides)."""
    path = app_entry.get("path", "")
    exec_cmd = app_entry.get("exec", "")
    terminal = app_entry.get("terminal", False)
    nom = app_entry.get("name", "JARVIS App")
    typ = app_entry.get("type", "")
    ext = os.path.splitext(path)[1].lower()
    dossier = os.path.dirname(path) if os.path.isfile(path) else (path if os.path.isdir(path) else None)
    console = dict(new_console=True, cwd=dossier, stdin=None, stdout=None, stderr=None)
    try:
        if typ == "dossier" or ext in (".lnk", ".url", ".exe"):
            ok, msg = open_path_msg(path)
            if ok:
                record_recent_launch(nom)
            return ok, (f"Ouvert : {nom}" if ok else f"Erreur lors du lancement : {msg}")
        if ext in (".bat", ".cmd") and os.path.isfile(path):
            # argv passé tel quel à CreateProcess : les espaces du chemin sont
            # préservés (cmd /k "C:\a b\x.bat" garde ses guillemets).
            popen_detached(["cmd.exe", "/d", "/k", path], **console)
            record_recent_launch(nom)
            return True, f"Lancé dans une console : {nom}"
        if ext == ".ps1" and os.path.isfile(path):
            psh = which("powershell") or "powershell.exe"
            popen_detached([psh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit",
                            "-File", path], **console)
            record_recent_launch(nom)
            return True, f"Lancé dans PowerShell : {nom}"
        if ext == ".sh":
            bash = bash_exe()
            if not bash:
                return False, "Git bash introuvable : impossible d'exécuter un script .sh sous Windows"
            if not os.path.isfile(path):
                return False, f"Erreur lors du lancement : script introuvable ({path})"
            posix = path.replace("\\", "/")
            script = (f"'{posix}'; echo; read -rp 'Appuyez sur Entrée pour fermer cette fenêtre'"
                      if "'" not in posix else f'"{posix}"')
            popen_detached([bash, "-lc", script], **console)
            record_recent_launch(nom)
            return True, f"Lancé dans Git bash : {nom}"
        if terminal and exec_cmd:
            ok, msg = open_in_terminal(exec_cmd, title=nom, cwd=dossier)
            if ok:
                record_recent_launch(nom)
            return ok, (f"Lancé dans le terminal : {nom}" if ok else f"Erreur lors du lancement : {msg}")
        if exec_cmd:
            popen_detached(exec_cmd, shell=True, cwd=dossier)
            record_recent_launch(nom)
            return True, f"Processus détaché lancé : {nom}"
        ok, msg = open_path_msg(path)
        if ok:
            record_recent_launch(nom)
        return ok, (f"Ouvert : {nom}" if ok else f"Erreur lors du lancement : {msg}")
    except Exception as e:
        return False, f"Erreur lors du lancement : {e}"


def load_prefs() -> dict:
    if os.path.exists(PREFS_FILE):
        try:
            # encoding explicite : cp1252 par défaut sous Windows (emoji/accents).
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"favorites": [], "recents": []}

def save_prefs(prefs: dict):
    try:
        os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
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
