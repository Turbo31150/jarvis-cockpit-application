#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 3 : TERMINAL & TMUX HUB
Interactive console runner, TMUX session manager, and quick agent attachments.
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QLineEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.terminal_manager import get_active_tmux_sessions, launch_terminal_command

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
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #4ade80;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_refresh = QPushButton("🔄 Actualiser Sessions")
        btn_refresh.clicked.connect(self.refresh_sessions)
        top_h.addWidget(btn_refresh)
        layout.addLayout(top_h)

        # Quick Dedicated Session Starters
        quick_h = QHBoxLayout()
        for title, cls, cmd in [
            ("🚀 TTX Multiplexeur (14 Fenêtres)", "", "ttx"),
            ("👑 Claude Code (tmux)", "purple", "claude"),
            ("🛰 Antigravity IDE (agy)", "purple", "agy"),
            ("🏛 Board OS Console", "", "python3 ~/jarvis/scripts/jarvis_board_app.py"),
            ("💻 Shell Turbo M4", "green", "~/jarvis/scripts/start-turbo-m1.sh"),
        ]:
            b = QPushButton(title)
            if cls:
                b.setProperty("class", cls)
            b.clicked.connect(lambda _, t=title, c=cmd: launch_terminal_command(t, c))
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
        self.cmd_input.setPlaceholderText("Exécuter une commande bash directe...")
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

    def refresh_sessions(self):
        sessions = get_active_tmux_sessions()
        self.tmux_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            it_name = QTableWidgetItem(s["name"])
            it_name.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
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
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            out = r.stdout or r.stderr or "[Code sortie: 0 - Sortie vide]"
            self.output_console.append(out + "\n")
        except Exception as e:
            self.output_console.append(f"Erreur d'exécution: {e}\n")
        self.cmd_input.clear()
