#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 1 : HUD & COCKPIT EXÉCUTIF (AAA DESIGN)
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
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        # ── HERO CARDS (3 COLONNES HOLOGRAPHIQUES) ──
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(14)

        # CARD 1: TTX WORKSPACE
        card1 = QFrame()
        card1.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #091733, stop:1 #040b17);
            border: 1px solid rgba(0, 240, 255, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c1 = QVBoxLayout(card1)
        c1.setSpacing(8)

        h1 = QHBoxLayout()
        l1_title = QLabel("🚀 WORKSPACE MULTIPLEXER")
        l1_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l1_title.setStyleSheet("color: #00f0ff; letter-spacing: 0.5px;")
        h1.addWidget(l1_title)
        h1.addStretch()
        b1 = QLabel("14 FENÊTRES")
        b1.setStyleSheet("color: #00f0ff; background: rgba(0, 240, 255, 0.15); border: 1px solid #00f0ff; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h1.addWidget(b1)
        c1.addLayout(h1)
        
        l1_desc = QLabel("Centre de commandement 14 fenêtres TMUX unifiées :\n• Claude Code Orfèvre + 48 MCPs connectés\n• Table Ronde 7 Experts en direct\n• Planning To-Do List unifié & Supervision")
        l1_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c1.addWidget(l1_desc)
        
        btn_ttx = QPushButton("🚀 Lancer Multiplexeur TTX")
        btn_ttx.setProperty("class", "cyan")
        btn_ttx.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "ttx"], start_new_session=True))
        c1.addWidget(btn_ttx)
        hero_layout.addWidget(card1)

        # CARD 2: CLAUDE CODE
        card2 = QFrame()
        card2.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a0f33, stop:1 #080514);
            border: 1px solid rgba(192, 132, 252, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c2 = QVBoxLayout(card2)
        c2.setSpacing(8)

        h2 = QHBoxLayout()
        l2_title = QLabel("👑 CLAUDE CODE ORFÈVRE")
        l2_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l2_title.setStyleSheet("color: #c084fc; letter-spacing: 0.5px;")
        h2.addWidget(l2_title)
        h2.addStretch()
        b2 = QLabel("0-TOKEN M6")
        b2.setStyleSheet("color: #c084fc; background: rgba(192, 132, 252, 0.15); border: 1px solid #c084fc; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h2.addWidget(b2)
        c2.addLayout(h2)
        
        l2_desc = QLabel("Agent d'ingénierie suprême en autonomie 100% :\n• Inférence prioritaire M6 RJ45 (1.4 ms)\n• Accès complet SSD M1 (1 To) & Git unifié\n• Mode non-stop ininterruptible")
        l2_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c2.addWidget(l2_desc)
        
        btn_claude = QPushButton("👑 Ouvrir Claude Code")
        btn_claude.setProperty("class", "purple")
        btn_claude.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "claude"], start_new_session=True))
        c2.addWidget(btn_claude)
        hero_layout.addWidget(card2)

        # CARD 3: TERMINAL TURBO
        card3 = QFrame()
        card3.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #091a18, stop:1 #030d0b);
            border: 1px solid rgba(74, 222, 128, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c3 = QVBoxLayout(card3)
        c3.setSpacing(8)

        h3 = QHBoxLayout()
        l3_title = QLabel("💻 TERMINAL & SWARM")
        l3_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        l3_title.setStyleSheet("color: #4ade80; letter-spacing: 0.5px;")
        h3.addWidget(l3_title)
        h3.addStretch()
        b3 = QLabel("NOEUD M4")
        b3.setStyleSheet("color: #4ade80; background: rgba(74, 222, 128, 0.15); border: 1px solid #4ade80; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h3.addWidget(b3)
        c3.addLayout(h3)
        
        l3_desc = QLabel("Accès direct au terminal & conteneurs :\n• Session native Turbo M4\n• Base PostgreSQL 15 & Redis 7\n• Workflows n8n (:5678) & Portainer (:9000)")
        l3_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c3.addWidget(l3_desc)
        
        btn_turbo = QPushButton("💻 Terminal Turbo M4")
        btn_turbo.setProperty("class", "green")
        btn_turbo.clicked.connect(lambda: subprocess.Popen(["gnome-terminal", "--title=Terminal Turbo M4", "--", "/home/turbo/bin/ttx"], start_new_session=True))
        c3.addWidget(btn_turbo)
        hero_layout.addWidget(card3)

        layout.addLayout(hero_layout)

        # ── MATRICE D'ACTIONS RAPIDES ET DÉCLENCHEURS (3 LIGNES x 4 BOUTONS) ──
        lbl_matrix = QLabel("⚡ MATRICE D'ACTIONS RAPIDES & MOTEURS OPÉRATIONNELS")
        lbl_matrix.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_matrix.setStyleSheet("color: #00f0ff; margin-top: 6px; letter-spacing: 0.5px;")
        layout.addWidget(lbl_matrix)

        grid = QGridLayout()
        grid.setSpacing(10)

        actions = [
            ("🛰 Antigravity IDE (agy)", "purple", "agy"),
            ("🌪 Mistral Vibe Coding", "amber", "vibe"),
            ("🌐 Chrome CDP Authentifié 9222", "cyan", f"{JARVIS_DIR}/bin/browseros-cdp-authentifie demarrer"),
            ("🌾 Moisson Claude Code", "green", "moisson"),
            ("⏰ Minuteur Réveil JARVIS", "ghost", f"{JARVIS_DIR}/bin/jarvis-reveil"),
            ("🎤 Whisper Voice Pilote", "green", f"python3 {JARVIS_DIR}/scripts/voice_pilot.py"),
            ("🔄 Rescan Planning Master", "amber", f"python3 {JARVIS_DIR}/board/dispatch_table_ronde.py"),
            ("💾 Sauvegarde Système Disque", "green", f"python3 {JARVIS_DIR}/scripts/save_full_config.py"),
            ("🎙️ Dictée Whisper (5s)", "green", f"{JARVIS_DIR}/scripts/lumen/lumen-cli.sh record 5"),
            ("🌊 WhisperFlow Overlay (Alt+X)", "purple", "google-chrome --app=file:///home/turbo/jarvis/whisperflow/widget.html --window-size=450,600"),
            ("💡 Toggle Micro Lumen", "cyan", f"{JARVIS_DIR}/scripts/lumen/lumen-toggle-mic.sh"),
            ("📋 Résumé Presse-Papiers Lumen", "cyan", f"{JARVIS_DIR}/scripts/lumen/lumen-cli.sh summarize"),
        ]

        for idx, (title, color_cls, cmd) in enumerate(actions):
            btn = QPushButton(title)
            if color_cls:
                btn.setProperty("class", color_cls)
            btn.clicked.connect(lambda _, c=cmd, t=title: self.execute_action(c, t))
            r, col = divmod(idx, 4)
            grid.addWidget(btn, r, col)

        layout.addLayout(grid)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def execute_action(self, cmd, title):
        if "google-chrome" in cmd or "toggle-mic" in cmd or "summarize" in cmd:
            subprocess.Popen(f"{cmd} &", shell=True, start_new_session=True)
        else:
            subprocess.Popen(["gnome-terminal", f"--title={title}", "--", "bash", "-lc", f"{cmd}; read -p 'Appuyez sur Entrée pour fermer...'"], start_new_session=True)
