#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 11 : MOISSONNAGE & PROSPECTION
Live reporting for Claude Code prospecting locomotive, lead harvesting, and campaign metrics.
"""

import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.config import JARVIS_DIR
from core.platform_compat import (IS_WINDOWS, open_terminal, python_executable, jarvis_path,
                                  unavailable_message, no_window_kwargs)

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
        if IS_WINDOWS:
            # Pas d'alias bash « moisson » ici : on lance le script Python dans un terminal
            # (wt.exe / cmd.exe) s'il est présent dans JARVIS_DIR, sinon bouton grisé.
            script = jarvis_path("scripts", "moisson_reelle.py", must_exist=True)
            if script:
                btn_launch.clicked.connect(lambda _, s=script: self._lancer_windows(s))
            else:
                btn_launch.setEnabled(False)
                btn_launch.setToolTip(unavailable_message("Moisson Claude Code",
                                                          f"script scripts/moisson_reelle.py absent de {JARVIS_DIR}"))
        else:
            btn_launch.clicked.connect(self._lancer_linux)
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

    def _lancer_linux(self):
        """Chemin du rig (inchangé), seulement protégé : jamais d'exception dans un slot."""
        try:
            subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "moisson; read -p 'Terminé'"], start_new_session=True)
        except Exception as e:
            self.report_text.append(f"\n❌ Lancement impossible : {e}")

    def _lancer_windows(self, script):
        if open_terminal([python_executable(), script], title="Moisson Claude Code", cwd=JARVIS_DIR, keep_open=True) is None:
            self.report_text.append("\n❌ Impossible d'ouvrir un terminal (wt.exe / cmd.exe).")

    def refresh_report(self):
        try:
            r = subprocess.run([python_executable(), os.path.join(JARVIS_DIR, "scripts", "moisson_reelle.py"), "--rapport"],
                               capture_output=True, text=True, timeout=5, **no_window_kwargs())
            self.report_text.setText(r.stdout or r.stderr or "Aucun rapport récent disponible.")
        except Exception as e:
            self.report_text.setText(f"Rapport de prospection : prêt à être généré. ({e})")
