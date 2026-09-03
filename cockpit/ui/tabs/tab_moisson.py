#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 11 : MOISSONNAGE & PROSPECTION
Live reporting for Claude Code prospecting locomotive, lead harvesting, and campaign metrics.
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.config import JARVIS_DIR

class TabMoisson(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("🌾 RAPPORT DE PROSPECTION RÉELLE & MOISSON CLAUDE CODE")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #facc15;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_launch = QPushButton("🚀 Lancer Moisson Claude Code")
        btn_launch.setProperty("class", "green")
        btn_launch.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "moisson; read -p 'Terminé'"], start_new_session=True))
        top_h.addWidget(btn_launch)

        btn_refresh = QPushButton("🔄 Actualiser Rapport")
        btn_refresh.clicked.connect(self.refresh_report)
        top_h.addWidget(btn_refresh)
        layout.addLayout(top_h)

        # Report Viewer
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("background-color: #030712; color: #f8fafc; font-family: 'Fira Code', monospace;")
        layout.addWidget(self.report_text)

        self.refresh_report()

    def refresh_report(self):
        try:
            r = subprocess.run(["python3", f"{JARVIS_DIR}/scripts/moisson_reelle.py", "--rapport"], capture_output=True, text=True, timeout=5)
            self.report_text.setText(r.stdout or r.stderr or "Aucun rapport récent disponible.")
        except Exception as e:
            self.report_text.setText(f"Rapport de prospection : prêt à être généré. ({e})")
