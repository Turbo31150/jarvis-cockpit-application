#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 4 : TABLE RONDE & 7 EXPERTS
Interactive consensus deliberation grounded in board.db FTS5 living corpus.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QFrame, QSplitter, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.table_ronde_engine import run_table_ronde_deliberation, EXPERTS
from core.database import get_board_stats

class TableRondeWorker(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, question):
        super().__init__()
        self.question = question
    def run(self):
        res = run_table_ronde_deliberation(self.question)
        self.finished_signal.emit(res)

class TabTableRonde(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header : Stats & Experts Badges
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🏛 TABLE RONDE DU CONSEIL DES 7 EXPERTS (0-TOKEN FACTURÉ)")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #c084fc;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        stats = get_board_stats()
        self.lbl_stats = QLabel("📚 " + str(stats.get('summary', 'Corpus FTS5')))
        self.lbl_stats.setStyleSheet("color: #94a3b8; font-size: 11px;")
        top_h.addWidget(self.lbl_stats)
        layout.addLayout(top_h)

        # Experts Pills Bar
        exp_bar = QHBoxLayout()
        exp_bar.setSpacing(6)
        for exp in EXPERTS:
            lbl_exp = QLabel(exp["name"])
            lbl_exp.setStyleSheet(f"background-color: #0d1527; color: {exp['color']}; border: 1px solid #1e293b; border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: bold;")
            exp_bar.addWidget(lbl_exp)
        exp_bar.addStretch()
        layout.addLayout(exp_bar)

        # Input & Trigger
        inp_h = QHBoxLayout()
        self.input_query = QLineEdit()
        self.input_query.setPlaceholderText("Posez une question technique, une problématique d'architecture ou un arbitrage...")
        self.input_query.returnPressed.connect(self.lancer_deliberation)
        inp_h.addWidget(self.input_query)

        self.btn_delib = QPushButton("⚖️ Lancer Débat & Consensus")
        self.btn_delib.setProperty("class", "purple")
        self.btn_delib.clicked.connect(self.lancer_deliberation)
        inp_h.addWidget(self.btn_delib)
        layout.addLayout(inp_h)

        # Loading / Progress Bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Output Area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("background-color: #030712; color: #f8fafc; font-family: 'Fira Code', monospace; line-height: 1.4;")
        self.output_text.setText("Posez une question ci-dessus pour engager la délibération des 7 experts avec extraction FTS5 en temps réel.")
        layout.addWidget(self.output_text)

    def lancer_deliberation(self):
        q = self.input_query.text().strip()
        if not q:
            return
        self.btn_delib.setEnabled(False)
        self.progress.setVisible(True)
        self.output_text.setText("⏳ Consultation du Conseil des 7 Experts en cours...\n• Recherche FTS5 dans board.db (87k chunks)\n• Routage d'inférence 0-token (M6 GPU / Ollama M4)\n• Synthèse et consensus en cours de rédaction...\n")
        
        self.worker = TableRondeWorker(q)
        self.worker.finished_signal.connect(self.afficher_resultat)
        self.worker.start()

    def afficher_resultat(self, res):
        self.btn_delib.setEnabled(True)
        self.progress.setVisible(False)
        
        src_info = "🔍 " + str(res.get('sources_count', 0)) + " sources FTS5 trouvées · Moteur : " + str(res.get('source', 'Local')) + "\n\n"
        self.output_text.setText(src_info + res.get("content", ""))
