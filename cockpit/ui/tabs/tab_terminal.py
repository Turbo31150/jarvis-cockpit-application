#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 3 : TERMINAL & TMUX HUB
Interactive console runner, TMUX session manager, and quick agent attachments.

Sous Windows : lanceurs rapides adaptés (PowerShell, Claude Code, WSL, Ollama,
LM Studio) ouverts dans Windows Terminal, table tmux remplacée par une ligne
« indisponible », commandes directes exécutées via platform_compat.run_shell
(UTF-8, sans fenêtre console).
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QLineEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.terminal_manager import (
    get_active_tmux_sessions, launch_terminal_command, launch_shell, command_available,
    tmux_unavailable_note, TMUX,
)
from core.platform_compat import IS_WINDOWS, run_shell, ui_font, unavailable_note, win_shell_kind

# Polices : inchangées sous Linux ("Ubuntu" / "Monospace"), Segoe UI / Consolas sous Windows.
FONT_UI = ui_font() if IS_WINDOWS else "Ubuntu"
FONT_MONO = ui_font(mono=True) if IS_WINDOWS else "Monospace"

# Lanceurs rapides : (titre, classe CSS, commande). Commande None = shell nu.
QUICK_LAUNCHERS_LINUX = [
    ("🚀 TTX Multiplexeur (14 Fenêtres)", "", "ttx"),
    ("👑 Claude Code (tmux)", "purple", "claude"),
    ("🛰 Antigravity IDE (agy)", "purple", "agy"),
    ("🏛 Board OS Console", "", "/home/turbo/jarvis/board/launch_table_ronde_terminal.sh"),
    ("💻 Shell Turbo M4", "green", "bash"),
]
QUICK_LAUNCHERS_WINDOWS = [
    ("💻 PowerShell", "green", None),
    ("👑 Claude Code", "purple", "claude"),
    ("🐧 WSL Ubuntu", "", "wsl.exe"),
    ("🦙 Ollama (modèles)", "", "ollama list"),
    ("🧠 LM Studio (lms ps)", "", "lms ps"),
]
QUICK_LAUNCHERS = QUICK_LAUNCHERS_WINDOWS if IS_WINDOWS else QUICK_LAUNCHERS_LINUX


def _shell_label() -> str:
    """Nom du shell qui exécute les commandes directes (pour le placeholder)."""
    if not IS_WINDOWS:
        return "bash"
    return {"powershell": "PowerShell", "pwsh": "PowerShell 7", "gitbash": "Git Bash"}.get(
        win_shell_kind(), "cmd.exe")


class TabTerminal(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title & Launchers
        top_h = QHBoxLayout()
        lbl = QLabel("💻 TERMINAUX INTERACTIFS & SESSIONS TMUX")
        lbl.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #4ade80;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_refresh = QPushButton("🔄 Actualiser Sessions")
        btn_refresh.clicked.connect(self.refresh_sessions)
        top_h.addWidget(btn_refresh)
        layout.addLayout(top_h)

        # Quick Dedicated Session Starters
        quick_h = QHBoxLayout()
        for title, cls, cmd in QUICK_LAUNCHERS:
            b = QPushButton(title)
            if cls:
                b.setProperty("class", cls)
            if IS_WINDOWS and cmd is not None and not command_available(cmd):
                # Outil absent de cette machine : bouton grisé plutôt qu'un clic muet.
                b.setEnabled(False)
                b.setToolTip(unavailable_note(f"{cmd.split(' ')[0]} (non installé)"))
            b.clicked.connect(lambda _, t=title, c=cmd: self.launch_quick(t, c))
            quick_h.addWidget(b)
        layout.addLayout(quick_h)

        # Active TMUX Sessions Table
        self.tmux_table = QTableWidget()
        self.tmux_table.setColumnCount(3)
        self.tmux_table.setHorizontalHeaderLabels(["Nom de Session TMUX", "Fenêtres Actives", "Statut Attach"])
        self.tmux_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tmux_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tmux_table)

        # Direct Command Runner
        cmd_h = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText(f"Exécuter une commande {_shell_label()} directe...")
        self.cmd_input.returnPressed.connect(self.exec_command)
        cmd_h.addWidget(self.cmd_input)

        btn_exec = QPushButton("⚡ Exécuter")
        btn_exec.setProperty("class", "green")
        btn_exec.clicked.connect(self.exec_command)
        cmd_h.addWidget(btn_exec)
        layout.addLayout(cmd_h)

        # Output console
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setStyleSheet("background-color: #030712; color: #4ade80; font-family: monospace;")
        self.output_console.setPlaceholderText("Sortie des commandes exécutées en direct...")
        layout.addWidget(self.output_console)

        self.refresh_sessions()

    def launch_quick(self, title: str, cmd):
        """Ouvre un terminal graphique pour un lanceur rapide ; signale l'échec dans la console."""
        ok = launch_shell(title) if cmd is None else launch_terminal_command(title, cmd)
        if not ok:
            self.output_console.append(
                f"Impossible d'ouvrir un terminal pour « {title} » "
                f"(aucun émulateur trouvé : {'wt.exe / cmd.exe' if IS_WINDOWS else 'gnome-terminal / xterm'}).\n")

    def refresh_sessions(self):
        sessions = get_active_tmux_sessions()
        self.tmux_table.clearSpans()
        if IS_WINDOWS and not TMUX and not sessions:
            # Ligne unique explicative : la table garde sa place dans la mise en page.
            self.tmux_table.setRowCount(1)
            it = QTableWidgetItem(f"{tmux_unavailable_note()} — utilisez Windows Terminal (wt.exe) ou WSL")
            it.setForeground(QColor("#94a3b8"))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tmux_table.setItem(0, 0, it)
            self.tmux_table.setSpan(0, 0, 1, 3)
            return
        self.tmux_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            it_name = QTableWidgetItem(s["name"])
            it_name.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
            self.tmux_table.setItem(row, 0, it_name)

            it_win = QTableWidgetItem(f"{s['windows']} fenêtres")
            self.tmux_table.setItem(row, 1, it_win)

            it_att = QTableWidgetItem("🟢 ATTACHÉE" if s["attached"] else "⚪ EN FOND")
            it_att.setForeground(QColor("#4ade80" if s["attached"] else "#94a3b8"))
            self.tmux_table.setItem(row, 2, it_att)

    def exec_command(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.output_console.append(f"$ {cmd}")
        try:
            if IS_WINDOWS:
                # cmd.exe / PowerShell sans fenêtre, sortie UTF-8 (errors='replace') :
                # pas de mojibake sur les accents, jamais d'exception.
                r = run_shell(cmd, timeout=15)
            else:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            out = r.stdout or r.stderr or "[Code sortie: 0 - Sortie vide]"
            if IS_WINDOWS and r.returncode != 0 and not (r.stdout or r.stderr):
                out = f"[Code sortie: {r.returncode} - Sortie vide]"
            self.output_console.append(out + "\n")
        except Exception as e:
            self.output_console.append(f"Erreur d'exécution: {e}\n")
        self.cmd_input.clear()
