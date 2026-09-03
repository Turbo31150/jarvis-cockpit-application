#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TERMINAL & TMUX MANAGER
Manages active TMUX sessions, provides quick attachments, and spawns dedicated CLI agents.
"""

import os
import shutil
import subprocess

TMUX = shutil.which("tmux")

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
    """Lance une commande dans un terminal graphique gnome-terminal ou x-terminal-emulator."""
    term = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator") or "xterm"
    try:
        subprocess.Popen([term, "--title", title, "--", "bash", "-lc", command], start_new_session=True)
        return True
    except Exception:
        return False
