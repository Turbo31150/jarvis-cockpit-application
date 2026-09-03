#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 1 : HUD & COCKPIT EXÉCUTIF
Executive dashboard with hero launchers, quick action matrix, and instant triggers.
"""

import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor
from core.config import JARVIS_DIR

class AsyncCommandWorker(QThread):
    finished_signal = pyqtSignal(str)
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
    def run(self):
        try:
            r = subprocess.run(self.cmd, capture_output=True, text=True, timeout=60)
            self.finished_signal.emit(r.stdout or r.stderr or "Terminé.")
        except Exception as e:
            self.finished_signal.emit(f"Erreur: {e}")

class TabHud(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # ── HERO CARDS (3 COLONNES) ──
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(14)

        # CARD 1: TTX WORKSPACE
        card1 = QFrame()
        card1.setProperty("class", "cyber-card")
        c1 = QVBoxLayout(card1)
        l1_title = QLabel("🚀 WORKSPACE MULTIPLEXER (TTX)")
        l1_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l1_title.setStyleSheet("color: #00f0ff;")
        c1.addWidget(l1_title)
        
        l1_desc = QLabel("Centre de commandement 14 fenêtres TMUX :\n• Claude Code Orfèvre + 40+ MCPs\n• Table Ronde 7 Experts en direct\n• Planning To-Do List unifié\n• Supervision Swarm & Shell Turbo")
        l1_desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 6px;")
        c1.addWidget(l1_desc)
        
        btn_ttx = QPushButton("🚀 Lancer Cockpit TTX")
        btn_ttx.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "ttx"], start_new_session=True))
        c1.addWidget(btn_ttx)
        hero_layout.addWidget(card1)

        # CARD 2: CLAUDE CODE
        card2 = QFrame()
        card2.setProperty("class", "cyber-card")
        c2 = QVBoxLayout(card2)
        l2_title = QLabel("👑 CLAUDE CODE (MODE ORFÈVRE)")
        l2_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l2_title.setStyleSheet("color: #c084fc;")
        c2.addWidget(l2_title)
        
        l2_desc = QLabel("Agent d'ingénierie suprême en autonomie 100% :\n• 0-Token prioritaire (Inférence M6 RJ45)\n• Tous les serveurs MCP connectés\n• Accès complet SSD M1 (1 To)\n• Protocole ininterruptible")
        l2_desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 6px;")
        c2.addWidget(l2_desc)
        
        btn_claude = QPushButton("👑 Ouvrir Claude Code")
        btn_claude.setProperty("class", "purple")
        btn_claude.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "claude"], start_new_session=True))
        c2.addWidget(btn_claude)
        hero_layout.addWidget(card2)

        # CARD 3: TERMINAL TURBO
        card3 = QFrame()
        card3.setProperty("class", "cyber-card")
        c3 = QVBoxLayout(card3)
        l3_title = QLabel("💻 TERMINAL TURBO & SWARM")
        l3_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l3_title.setStyleSheet("color: #4ade80;")
        c3.addWidget(l3_title)
        
        l3_desc = QLabel("Accès direct au terminal & conteneurs :\n• Session native Turbo M4\n• Base PostgreSQL 15 & Redis 7\n• Workflows n8n (:5678) & Portainer (:9000)\n• Prompt dynamique VRAM")
        l3_desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 6px;")
        c3.addWidget(l3_desc)
        
        btn_turbo = QPushButton("💻 Terminal Turbo M4")
        btn_turbo.setProperty("class", "green")
        btn_turbo.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", f"{JARVIS_DIR}/scripts/start-turbo-m1.sh"], start_new_session=True))
        c3.addWidget(btn_turbo)
        hero_layout.addWidget(card3)

        layout.addLayout(hero_layout)

        # ── MATRICE D'ACTIONS RAPIDES (2 LIGNES x 4 BOUTONS) ──
        lbl_matrix = QLabel("⚡ MATRICE D'ACTIONS RAPIDES ET DÉCLENCHEURS")
        lbl_matrix.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_matrix.setStyleSheet("color: #fbbf24; margin-top: 8px;")
        layout.addWidget(lbl_matrix)

        grid = QGridLayout()
        grid.setSpacing(10)

        actions = [
            ("🛰 Antigravity IDE (agy)", "purple", "agy"),
            ("🌪 Mistral Vibe Coding", "amber", "vibe"),
            ("🌐 CDP Authentifié 9222", "cyan", f"{JARVIS_DIR}/bin/browseros-cdp-authentifie demarrer"),
            ("🌾 Moisson Claude Code", "green", "moisson"),
            ("⏰ Minuteur Réveil JARVIS", "", f"{JARVIS_DIR}/bin/jarvis-reveil"),
            ("🎤 Whisper Voice UI (9742)", "cyan", f"xdg-open http://127.0.0.1:9742"),
            ("🔄 Rescan Planning Master", "amber", f"python3 {JARVIS_DIR}/scripts/planning_mega_m4.py"),
            ("💾 Sauvegarde SQL Complète", "green", f"python3 {JARVIS_DIR}/scripts/sauvegarde_complete_sql.py"),
        ]

        for idx, (title, color_cls, cmd) in enumerate(actions):
            btn = QPushButton(title)
            if color_cls:
                btn.setProperty("class", color_cls)
            btn.clicked.connect(lambda _=False, c=cmd: subprocess.Popen(["gnome-terminal", "--", "bash", "-lc", f"{c}; read -p 'Entrée pour fermer'"], start_new_session=True))
            r, col = divmod(idx, 4)
            grid.addWidget(btn, r, col)

        layout.addLayout(grid)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)
