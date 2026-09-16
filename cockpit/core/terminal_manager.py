#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TERMINAL & TMUX MANAGER
Manages active TMUX sessions, provides quick attachments, and spawns dedicated CLI agents.

Sous Windows : pas de tmux (liste vide) et les terminaux s'ouvrent dans
Windows Terminal (wt.exe) ou une console cmd.exe via platform_compat.
"""

import os
import shutil
import subprocess

from .platform_compat import (
    IS_WINDOWS, tmux_path, find_executable, default_shell, open_terminal,
    unavailable_note,
)

# shutil.which('tmux') sous Linux ; toujours None sous Windows.
TMUX = tmux_path()

def get_active_tmux_sessions() -> list[dict]:
    """Liste toutes les sessions TMUX vivantes."""
    if not TMUX:
        return []
    try:
        r = subprocess.run([TMUX, "ls", "-F", "#{session_name}	#{session_windows}	#{session_attached}"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode != 0:
            return []
        sessions = []
        for line in r.stdout.splitlines():
            parts = line.split("	")
            if len(parts) >= 3:
                name = parts[0]
                n_win = int(parts[1]) if parts[1].isdigit() else 1
                attached = parts[2] == "1"
                sessions.append({
                    "name": name,
                    "windows": n_win,
                    "attached": attached
                })
        return sessions
    except Exception:
        return []

def launch_terminal_command(title: str, command: str) -> bool:
    """Lance une commande dans un terminal graphique gnome-terminal ou x-terminal-emulator.

    Windows : Windows Terminal (wt.exe, nouvel onglet) ou, à défaut, une
    nouvelle console cmd.exe ; le shell reste ouvert après la commande.
    Ne lève jamais : False si aucun émulateur n'a pu être lancé.
    """
    if IS_WINDOWS:
        return open_terminal(command, title=title, keep_open=True) is not None
    term = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator") or "xterm"
    try:
        subprocess.Popen([term, "--title", title, "--", "bash", "-lc", command], start_new_session=True)
        return True
    except Exception:
        return False

def launch_shell(title: str = "Shell") -> bool:
    """Ouvre un shell interactif nu (bash de connexion / PowerShell) dans un terminal graphique."""
    if IS_WINDOWS:
        return open_terminal(None, title=title) is not None
    return launch_terminal_command(title, "bash")

def command_available(command: str) -> bool:
    """Vrai si le premier mot de `command` est un exécutable trouvable ici.

    Sert à griser les lanceurs rapides de l'onglet Terminal sous Windows.
    Un chemin de script bash absent ou `bash` nu (= lanceur WSL) → False.
    """
    tete = (command or "").strip().split(" ")[0] if command else ""
    if not tete:
        return False
    if IS_WINDOWS:
        return find_executable(tete) is not None
    # Linux : on ne grise rien (alias bash -lc, scripts, PATH de connexion…).
    return True

def tmux_unavailable_note() -> str:
    """Libellé canonique pour la table des sessions quand tmux n'existe pas ici."""
    return unavailable_note("Sessions tmux")

__all__ = [
    "TMUX", "IS_WINDOWS", "default_shell", "get_active_tmux_sessions",
    "launch_terminal_command", "launch_shell", "command_available", "tmux_unavailable_note",
]
