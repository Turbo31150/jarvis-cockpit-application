#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB : TABLE RONDE DU CONSEIL DES EXPERTS
Délibération de consensus interactive, ancrée dans le corpus vivant BOARD-A (FTS5),
l'état machine BOARD-B, et la bibliothèque de Prompts Dual-Disque (M1/M6).
Matérialisation directe des décisions en objectifs & chaînes DOMINO sur BOARD-B.
"""

import os
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QCheckBox, QProgressBar, QDialog, QListWidget, QListWidgetItem,
    QMessageBox, QApplication, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.table_ronde_engine import run_table_ronde_deliberation, EXPERTS
from core.database import get_board_stats
from core.config import JARVIS_DIR


class PromptSelectorDialog(QDialog):
    """Dialogue de sélection rapide de directives et prompts souverains moissonnés."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Directives & Prompts Souverains (M1 SSD & M6 Local)")
        self.resize(750, 520)
        self.selected_prompt_text = ""
        self.master_db = os.path.join(JARVIS_DIR, "jarvis_master.db")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # En-tête
        lbl_info = QLabel("Sélectionnez une directive experte issue des disques M1/M6 pour la soumettre à la Table Ronde :")
        lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_info)

        # Boutons rapides prédéfinis
        quick_box = QHBoxLayout()
        quick_presets = [
            ("🏛️ Cluster M1/M4/M6", "Comment garantir la haute disponibilité et la tolérance aux pannes du cluster distribué M1/M4/M6 ?"),
            ("⚡ Inférence 0-Token", "Quelle stratégie adopter pour maximiser l'inférence locale 0-token sans latence excessive ?"),
            ("🛡️ Sécurité & Non-Régression", "Quels verrous de sécurité et d'audit souverain appliquer avant toute action autonome ?"),
            ("📈 Trading & Arbitrage", "Comment orchestrer les agents d'arbitrage et de scalping sur signaux crypto ?")
        ]
        for title, q_text in quick_presets:
            btn = QPushButton(title)
            btn.setStyleSheet("""
                QPushButton {
                    background: #0f172a;
                    border: 1px solid #334155;
                    color: #38bdf8;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover { background: #1e293b; color: #ffffff; }
            """)
            btn.clicked.connect(lambda checked, t=q_text: self.select_text(t))
            quick_box.addWidget(btn)
        layout.addLayout(quick_box)

        # Recherche FTS5
        search_box = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filtrer parmi les 834 prompts moissonnés (ex: architecte, trading, domino, gpu)...")
        self.txt_search.setStyleSheet("background: #030712; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 6px;")
        self.txt_search.textChanged.connect(self.load_prompts)
        search_box.addWidget(self.txt_search)
        layout.addLayout(search_box)

        # Liste des prompts
        self.list_prompts = QListWidget()
        self.list_prompts.setStyleSheet("""
            QListWidget {
                background-color: #030712;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #0f172a; }
            QListWidget::item:selected { background-color: #1e1b4b; color: #c084fc; font-weight: bold; }
        """)
        self.list_prompts.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_prompts)

        # Actions
        btn_box = QHBoxLayout()
        btn_inject = QPushButton("✅ Injecter dans la Table Ronde")
        btn_inject.setStyleSheet("""
            QPushButton {
                background: #581c87;
                color: #ffffff;
                border: 1px solid #a855f7;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #7e22ce; }
        """)
        btn_inject.clicked.connect(self.on_inject_clicked)
        btn_box.addWidget(btn_inject)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        self.prompts_cache = []
        self.load_prompts()

    def load_prompts(self):
        self.list_prompts.clear()
        self.prompts_cache = []
        if not os.path.exists(self.master_db):
            return

        q = self.txt_search.text().strip()
        try:
            conn = sqlite3.connect(f"file:{self.master_db}?mode=ro&immutable=1", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            if q:
                clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in q).strip()
                words = [w for w in clean_q.split() if len(w) > 2][:3]
                if words:
                    fts_term = " OR ".join(words)
                    rows = cur.execute("""
                        SELECT p.id, p.filename, p.category, p.origin_disk, substr(p.content, 1, 200) as snippet, p.content
                        FROM system_prompts_library p
                        JOIN system_prompts_fts f ON p.id = f.rowid
                        WHERE system_prompts_fts MATCH ?
                        LIMIT 40
                    """, (fts_term,)).fetchall()
                else:
                    rows = cur.execute("SELECT id, filename, category, origin_disk, substr(content, 1, 200) as snippet, content FROM system_prompts_library LIMIT 40").fetchall()
            else:
                rows = cur.execute("SELECT id, filename, category, origin_disk, substr(content, 1, 200) as snippet, content FROM system_prompts_library ORDER BY id DESC LIMIT 40").fetchall()

            conn.close()

            for r in rows:
                self.prompts_cache.append(dict(r))
                tag = "🏷️ M1" if r["origin_disk"] == "M1_SSD" else "🖥️ M6"
                item_text = f"[{tag}] {r['filename']} ({r['category']})\n   {r['snippet'].strip().replace(chr(10), ' ')[:100]}..."
                self.list_prompts.addItem(item_text)

        except Exception as e:
            self.list_prompts.addItem(f"Erreur chargement prompts : {e}")

    def select_text(self, text):
        self.selected_prompt_text = text
        self.accept()

    def on_item_double_clicked(self, item):
        self.on_inject_clicked()

    def on_inject_clicked(self):
        row = self.list_prompts.currentRow()
        if 0 <= row < len(self.prompts_cache):
            p = self.prompts_cache[row]
            first_line = p["content"].split("\n")[0].strip("# \t")
            if not first_line or len(first_line) < 5:
                first_line = p["filename"]
            self.selected_prompt_text = f"Comment arbitrer et implémenter la directive suivante ({p['filename']}) : « {first_line} » ?"
            self.accept()


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
        self.last_res = None
        self.last_question = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # En-tête : titre + stats corpus & sources
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🏛 TABLE RONDE DU CONSEIL DES EXPERTS (0-TOKEN FACTURÉ)")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #c084fc;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        stats = get_board_stats()
        self.lbl_stats = QLabel(f"📚 {stats.get('summary', 'Corpus FTS5')} · 🌾 834 Prompts Dual-Disque")
        self.lbl_stats.setStyleSheet("color: #94a3b8; font-size: 11px;")
        top_h.addWidget(self.lbl_stats)
        layout.addLayout(top_h)

        # Barre d'état des ancrages cognitifs (BOARD-A, BOARD-B, Prompts)
        anchors_box = QHBoxLayout()
        anchors_box.setSpacing(6)
        b_a = QLabel("📚 BOARD-A : 183k Chunks RAG")
        b_a.setStyleSheet("background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        anchors_box.addWidget(b_a)

        b_b = QLabel("📋 BOARD-B : Machine d'États & Dominos")
        b_b.setStyleSheet("background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.4); color: #c084fc; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        anchors_box.addWidget(b_b)

        b_p = QLabel("🌾 Dual-Disk : 834 Prompts Moissonnés (M1/M6)")
        b_p.setStyleSheet("background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        anchors_box.addWidget(b_p)
        anchors_box.addStretch()

        btn_prompt_picker = QPushButton("📖 Directives & Prompts Souverains...")
        btn_prompt_picker.setStyleSheet("""
            QPushButton {
                background: rgba(88, 28, 135, 0.4);
                border: 1px solid #a855f7;
                color: #e9d5ff;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(88, 28, 135, 0.7); color: #ffffff; }
        """)
        btn_prompt_picker.clicked.connect(self.open_prompt_picker)
        anchors_box.addWidget(btn_prompt_picker)

        layout.addLayout(anchors_box)

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
        self.input_query.setStyleSheet("""
            QLineEdit {
                background: #030712;
                border: 1px solid rgba(192, 132, 252, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
                color: #f8fafc;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #c084fc; background: #060e22; }
        """)
        self.input_query.returnPressed.connect(self.lancer_deliberation)
        inp_h.addWidget(self.input_query)

        self.btn_delib = QPushButton("⚖️ Lancer Débat & Consensus")
        self.btn_delib.setStyleSheet("""
            QPushButton {
                background: #6b21a8;
                border: 1px solid #c084fc;
                border-radius: 6px;
                padding: 6px 14px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover { background: #7e22ce; }
        """)
        self.btn_delib.clicked.connect(self.lancer_deliberation)
        inp_h.addWidget(self.btn_delib)
        layout.addLayout(inp_h)

        # Barre de progression indéterminée
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Bandeau de confiance
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
            "délibération, avec extraction temps réel de BOARD-A (FTS5), BOARD-B (Dominos), "
            "et la bibliothèque de Prompts Dual-Disque (M1/M6)."
        )
        layout.addWidget(self.output_text)

        # Actions post-délibération : Matérialisation sur BOARD-B & Export
        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(10)

        self.btn_materialiser_bb = QPushButton("🧭 Matérialiser la Décision sur BOARD-B (Chaîne DOMINO)")
        self.btn_materialiser_bb.setStyleSheet("""
            QPushButton {
                background: rgba(14, 116, 144, 0.85);
                border: 1px solid #00f0ff;
                border-radius: 6px;
                padding: 6px 14px;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #0284c7; }
        """)
        self.btn_materialiser_bb.setToolTip("Transforme la décision de consensus en objectif exécutable sur BOARD-B")
        self.btn_materialiser_bb.setVisible(False)
        self.btn_materialiser_bb.clicked.connect(self.materialiser_sur_board_b)
        bottom_actions.addWidget(self.btn_materialiser_bb)

        self.btn_copy = QPushButton("📋 Copier Consensus")
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f1f5f9;
                font-size: 11px;
            }
            QPushButton:hover { background: #334155; }
        """)
        self.btn_copy.clicked.connect(self.copier_resultat)
        bottom_actions.addWidget(self.btn_copy)
        bottom_actions.addStretch()

        layout.addLayout(bottom_actions)

    def open_prompt_picker(self):
        dlg = PromptSelectorDialog(self)
        if dlg.exec():
            if dlg.selected_prompt_text:
                self.input_query.setText(dlg.selected_prompt_text)

    def _agents_selectionnes(self):
        ids = [eid for eid, chk in self.expert_checks.items() if chk.isChecked()]
        return ids or None

    def lancer_deliberation(self):
        q = self.input_query.text().strip()
        if not q:
            return
        self.last_question = q
        agents = self._agents_selectionnes()
        nb = len(agents) if agents else len(EXPERTS)
        self.btn_delib.setEnabled(False)
        self.btn_materialiser_bb.setVisible(False)
        self.progress.setVisible(True)
        self.lbl_confiance.setVisible(False)
        self.output_text.setText(
            f"⏳ Consultation de {nb} expert(s) en cours...\n"
            "• Ancrage croisé : BOARD-A (FTS5) + BOARD-B (Dominos) + Prompts Dual-Disque (M1/M6)\n"
            "• Routage d'inférence 0-token (M6 GPU → Ollama M4 → Chat Proxy)\n"
            "• Délibération parallèle puis synthèse du consensus...\n\n"
            "ℹ️ Sur inférence CPU locale, comptez quelques secondes/minutes."
        )

        self.worker = TableRondeWorker(q, agents)
        self.worker.finished_signal.connect(self.afficher_resultat)
        self.worker.start()

    def afficher_resultat(self, res):
        self.last_res = res
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
            f"🔍 {res.get('sources_count', 0)} sources souveraines (BOARD-A, BOARD-B, Prompts) · "
            f"Moteur : {res.get('source', 'Local')}"
        )
        self.lbl_confiance.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_confiance.setVisible(True)
        self.output_text.setText(res.get("content", ""))

        # Activer le bouton de matérialisation sur BOARD-B
        self.btn_materialiser_bb.setVisible(True)

    def materialiser_sur_board_b(self):
        if not self.last_res or not self.last_question:
            return

        consensus_text = self.last_res.get("consensus", "")
        # Extraire la décision
        decision_line = "Appliquer recommandations de la Table Ronde"
        for line in consensus_text.split("\n"):
            if "DÉCISION" in line or line.strip().startswith("1)") or line.strip().startswith("-"):
                decision_line = line.replace("DÉCISION :", "").strip()
                break

        try:
            rdir = os.path.join(JARVIS_DIR, "omega", "engine")
            if rdir not in sys.path:
                sys.path.insert(0, rdir)
            from router import OmegaCognitiveRouter
            router = OmegaCognitiveRouter()

            dominos = [
                {"label": "1. Valider consensus et arbitrages des 7 experts", "kind": "read", "action_class": "READ"},
                {"label": f"2. Exécuter action arbitrée : {decision_line[:40]}...", "kind": "execute", "action_class": "GENERATE"},
                {"label": "3. Auditer non-régression et enregistrer preuve OMEGA", "kind": "verify", "action_class": "READ"}
            ]

            obj_id = router.create_objective(
                title=f"Arbitrage Table Ronde : {self.last_question[:45]}...",
                description=f"Décision consensus : {consensus_text[:300]}",
                intent="TABLE_RONDE_CONSENSUS",
                family="ORCHESTRATION",
                dominos=dominos
            )

            # Proposer de basculer vers l'onglet OMEGA
            rep = QMessageBox.question(
                self,
                "Décision Matérialisée sur BOARD-B",
                f"✅ Objectif créé avec succès sur BOARD-B !\n\n"
                f"ID Objectif : {obj_id}\n"
                f"3 Dominos ont été enchaînés pour l'exécution.\n\n"
                "Souhaitez-vous basculer vers l'onglet OMEGA pour suivre l'état de la machine d'états ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if rep == QMessageBox.StandardButton.Yes:
                win = self.window()
                if hasattr(win, "tab_omega") and hasattr(win, "tabs"):
                    win.tabs.setCurrentWidget(win.tab_omega)
                    win.tab_omega.refresh_data()

        except Exception as e:
            QMessageBox.critical(self, "Erreur Matérialisation", f"Échec de création sur BOARD-B : {e}")

    def copier_resultat(self):
        text = self.output_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                QMessageBox.information(self, "Presse-papier", "Compte-rendu et consensus copiés !")
