#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB : TABLE RONDE & 7 EXPERTS
Délibération de consensus interactive, ancrée dans le corpus vivant board.db (FTS5),
avec sélection des experts et indicateur de confiance (part d'avis réellement produits
par un LLM local, hors repli heuristique).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from core.table_ronde_engine import run_table_ronde_deliberation, EXPERTS
from core.database import get_board_stats


class TableRondeWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, question, agents=None):
        super().__init__()
        self.question = question
        self.agents = agents

    def run(self):
        try:
            res = run_table_ronde_deliberation(self.question, agents_selectionnes=self.agents)
        except Exception as e:
            res = {"success": False, "content": f"Erreur moteur : {e}",
                   "sources_count": 0, "source": "Exception", "confidence": 0}
        self.finished_signal.emit(res)


class TabTableRonde(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.expert_checks = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # En-tête : titre + stats corpus
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🏛 TABLE RONDE DU CONSEIL DES EXPERTS (0-TOKEN FACTURÉ)")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #c084fc;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        stats = get_board_stats()
        self.lbl_stats = QLabel("📚 " + str(stats.get("summary", "Corpus FTS5")))
        self.lbl_stats.setStyleSheet("color: #94a3b8; font-size: 11px;")
        top_h.addWidget(self.lbl_stats)
        layout.addLayout(top_h)

        # Barre de sélection des experts (cases à cocher, tous actifs par défaut)
        exp_bar = QHBoxLayout()
        exp_bar.setSpacing(6)
        lbl_sel = QLabel("Sièges :")
        lbl_sel.setStyleSheet("color: #64748b; font-size: 11px;")
        exp_bar.addWidget(lbl_sel)
        for exp in EXPERTS:
            chk = QCheckBox(exp["name"])
            chk.setChecked(True)
            chk.setStyleSheet(
                f"QCheckBox {{ color: {exp['color']}; font-size: 11px; font-weight: bold; "
                f"background-color: #0d1527; border: 1px solid #1e293b; border-radius: 6px; "
                f"padding: 3px 7px; }}"
                f"QCheckBox::indicator {{ width: 11px; height: 11px; }}"
            )
            self.expert_checks[exp["id"]] = chk
            exp_bar.addWidget(chk)
        exp_bar.addStretch()
        layout.addLayout(exp_bar)

        # Saisie + déclenchement
        inp_h = QHBoxLayout()
        self.input_query = QLineEdit()
        self.input_query.setPlaceholderText(
            "Posez une question technique, une problématique d'architecture ou un arbitrage..."
        )
        self.input_query.returnPressed.connect(self.lancer_deliberation)
        inp_h.addWidget(self.input_query)

        self.btn_delib = QPushButton("⚖️ Lancer Débat & Consensus")
        self.btn_delib.setProperty("class", "purple")
        self.btn_delib.clicked.connect(self.lancer_deliberation)
        inp_h.addWidget(self.btn_delib)
        layout.addLayout(inp_h)

        # Barre de progression indéterminée
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Bandeau de confiance (masqué tant qu'aucun résultat)
        self.lbl_confiance = QLabel("")
        self.lbl_confiance.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 2px;")
        self.lbl_confiance.setVisible(False)
        layout.addWidget(self.lbl_confiance)

        # Zone de sortie
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(
            "background-color: #030712; color: #f8fafc; "
            "font-family: 'Fira Code', monospace; line-height: 1.4;"
        )
        self.output_text.setText(
            "Sélectionnez les sièges et posez une question ci-dessus pour engager la "
            "délibération, avec extraction FTS5 du corpus en temps réel."
        )
        layout.addWidget(self.output_text)

    def _agents_selectionnes(self):
        ids = [eid for eid, chk in self.expert_checks.items() if chk.isChecked()]
        # Aucun coché => None (le moteur convoque alors tout le Conseil)
        return ids or None

    def lancer_deliberation(self):
        q = self.input_query.text().strip()
        if not q:
            return
        agents = self._agents_selectionnes()
        nb = len(agents) if agents else len(EXPERTS)
        self.btn_delib.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_confiance.setVisible(False)
        self.output_text.setText(
            f"⏳ Consultation de {nb} expert(s) en cours...\n"
            "• Recherche FTS5 dans board.db\n"
            "• Routage d'inférence 0-token (M6 GPU → Ollama M4 → Chat Proxy)\n"
            "• Délibération parallèle puis synthèse du consensus...\n\n"
            "ℹ️ Sur inférence CPU locale, comptez quelques minutes."
        )

        self.worker = TableRondeWorker(q, agents)
        self.worker.finished_signal.connect(self.afficher_resultat)
        self.worker.start()

    def afficher_resultat(self, res):
        self.btn_delib.setEnabled(True)
        self.progress.setVisible(False)

        if not res.get("success", False):
            self.lbl_confiance.setVisible(False)
            self.output_text.setText("⚠️ " + str(res.get("content", "Échec de la délibération.")))
            return

        conf = int(res.get("confidence", 0))
        couleur = "#34d399" if conf >= 70 else ("#fbbf24" if conf >= 30 else "#f87171")
        jauge = "█" * (conf // 10) + "░" * (10 - conf // 10)
        self.lbl_confiance.setText(
            f"Confiance : <span style='color:{couleur};'>{jauge} {conf}%</span> d'avis réels · "
            f"🔍 {res.get('sources_count', 0)} sources FTS5 · Moteur : {res.get('source', 'Local')}"
        )
        self.lbl_confiance.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_confiance.setVisible(True)
        self.output_text.setText(res.get("content", ""))
