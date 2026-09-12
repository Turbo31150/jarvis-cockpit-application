#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB OMEGA : POSTE DE COMMANDE COGNITIF & ROUTAGE SOUVERAIN
Matérialise l'architecture MEGA PROMPT OMEGA (Ombre × Lumière) au sein du Cockpit natif :
- Registre unifié (523 artefacts, 15 familles, 14 agents, 462 skills)
- Bibliothèque souveraine de Prompts Dual-Disque (M1 SSD + M6 Local, FTS5)
- Routeur cognitif temps réel & RAG souverain BOARD-A
- Machine d'états opératoire BOARD-B & chaînes DOMINO
- Audit souverain avec correlation_id
"""

import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QTextEdit,
    QSplitter, QProgressBar, QFrame, QGroupBox, QTabWidget, QMessageBox,
    QComboBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.config import JARVIS_DIR, MACHINE_NAME


class PromptHarvestWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def run(self):
        try:
            script_path = os.path.join(JARVIS_DIR, "omega", "engine", "harvest_prompts_dual_disk.py")
            res = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=60
            )
            success = res.returncode == 0
            self.finished_signal.emit({
                "success": success,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
        except Exception as e:
            self.finished_signal.emit({"success": False, "stdout": "", "stderr": str(e)})


class TabOmega(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.jarvis_dir = JARVIS_DIR
        self.registry_db = os.path.join(JARVIS_DIR, "omega", "registry", "omega_registry.db")
        self.board_b_db = os.path.join(JARVIS_DIR, "omega", "board", "omega_board.db")
        self.audit_db = os.path.join(JARVIS_DIR, "omega", "audit", "omega_audit.db")
        self.master_db = os.path.join(JARVIS_DIR, "jarvis_master.db")
        self.router_py_dir = os.path.join(JARVIS_DIR, "omega", "engine")
        
        # Router instance
        self.router = None
        self._init_router()

        self.current_prompts_data = []
        self.init_ui()

    def _init_router(self):
        try:
            if self.router_py_dir not in sys.path:
                sys.path.insert(0, self.router_py_dir)
            from router import OmegaCognitiveRouter
            self.router = OmegaCognitiveRouter()
        except Exception:
            self.router = None

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── 1. EN-TÊTE & TÉLÉMÉTRIE COGNITIVE ──
        header_box = QFrame()
        header_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(10, 15, 30, 0.95), stop:1 rgba(15, 23, 42, 0.95));
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 8px;
                padding: 6px;
            }
        """)
        h_layout = QHBoxLayout(header_box)
        h_layout.setContentsMargins(10, 6, 10, 6)

        title_layout = QVBoxLayout()
        lbl_title = QLabel("🌌 JARVIS OMEGA — ARCHITECTURE COGNITIVE SOUVERAINE")
        lbl_title.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #00f0ff; letter-spacing: 1px;")
        title_layout.addWidget(lbl_title)

        self.lbl_subtitle = QLabel("Noyau v1.2.0 • Ombre × Lumière • Dual-Disque M1/M6 • Machine d'États & Audit Actifs")
        self.lbl_subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_layout.addWidget(self.lbl_subtitle)
        h_layout.addLayout(title_layout)
        h_layout.addStretch()

        # Badges télémétrie
        self.badge_art = self._make_badge("📦 523 Artefacts", "#38bdf8")
        self.badge_fam = self._make_badge("🏛️ 15 Familles", "#a855f7")
        self.badge_agt = self._make_badge("🤖 14 Agents", "#4ade80")
        self.badge_skl = self._make_badge("⚡ 462 Skills", "#fbbf24")
        self.badge_prm = self._make_badge("🌾 834 Prompts", "#10b981")
        self.badge_aud = self._make_badge("🛡️ 149+ Audits", "#f43f5e")

        for b in [self.badge_art, self.badge_fam, self.badge_agt, self.badge_skl, self.badge_prm, self.badge_aud]:
            h_layout.addWidget(b)

        btn_refresh_all = QPushButton("🔄")
        btn_refresh_all.setFixedSize(32, 32)
        btn_refresh_all.setToolTip("Actualiser les métriques et bases OMEGA")
        btn_refresh_all.clicked.connect(self.refresh_data)
        h_layout.addWidget(btn_refresh_all)

        btn_improve = QPushButton("⚡ Auto-Amélioration")
        btn_improve.setStyleSheet("""
            QPushButton {
                background: rgba(245, 158, 11, 0.2);
                border: 1px solid rgba(245, 158, 11, 0.6);
                border-radius: 6px;
                color: #fbbf24;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(245, 158, 11, 0.35);
                border-color: #f59e0b;
                color: #ffffff;
            }
        """)
        btn_improve.setToolTip("Lancer un cycle d'auto-amélioration continue OMEGA (§19-§21, §27-§28)")
        btn_improve.clicked.connect(self.trigger_improve_cycle)
        h_layout.addWidget(btn_improve)

        layout.addWidget(header_box)

        # ── 2. CONSOLE DU ROUTEUR COGNITIF ──
        router_group = QGroupBox("⚡ ROUTEUR COGNITIF TEMPS RÉEL (Directive Finale §30 & Boucle §27)")
        router_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 8px;
                margin-top: 8px;
                font-weight: bold;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        rg_layout = QVBoxLayout(router_group)
        rg_layout.setContentsMargins(10, 12, 10, 10)
        rg_layout.setSpacing(8)

        # Barre de commande
        cmd_h = QHBoxLayout()
        self.txt_intent = QLineEdit()
        self.txt_intent.setPlaceholderText("Exprimez une intention cognitive (ex: Optimiser le cluster GPU, Analyser le signal trading BTC, Auditer le code...)")
        self.txt_intent.setStyleSheet("""
            QLineEdit {
                background: #030712;
                border: 1px solid rgba(0, 240, 255, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
                color: #f8fafc;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #00f0ff; background: #060e22; }
        """)
        self.txt_intent.returnPressed.connect(self.exec_route)
        cmd_h.addWidget(self.txt_intent)

        btn_exec = QPushButton("⚡ Analyser & Décomposer (DOMINO)")
        btn_exec.setStyleSheet("""
            QPushButton {
                background: rgba(14, 116, 144, 0.85);
                border: 1px solid #00f0ff;
                border-radius: 6px;
                padding: 6px 14px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover { background: #0284c7; }
        """)
        btn_exec.clicked.connect(self.exec_route)
        cmd_h.addWidget(btn_exec)
        rg_layout.addLayout(cmd_h)

        # Zone d'affichage résultat du routage
        self.router_output = QTextEdit()
        self.router_output.setReadOnly(True)
        self.router_output.setFixedHeight(120)
        self.router_output.setStyleSheet("""
            QTextEdit {
                background: #030712;
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 6px;
                color: #38bdf8;
                font-family: monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        self.router_output.setPlaceholderText("Le résultat de l'analyse sémantique, la mémoire souveraine BOARD-A, les prompts M1/M6, et les compétences apparaîtront ici...")
        rg_layout.addWidget(self.router_output)

        layout.addWidget(router_group)

        # ── 3. SOUS-ONGLETS : BOARD-B, PROMPTS MOISSONNÉS & AUDIT SOUVERAIN ──
        sub_tabs = QTabWidget()
        sub_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid rgba(0, 240, 255, 0.25); border-radius: 6px; background: #080f20; }
            QTabBar::tab { background: #050b16; color: #94a3b8; padding: 6px 14px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #0c1830; color: #00f0ff; border: 1px solid rgba(0, 240, 255, 0.4); border-bottom: none; }
        """)

        # ── Sous-Onglet 1 : BOARD-B ──
        w_board = QWidget()
        w_board_layout = QVBoxLayout(w_board)
        w_board_layout.setContentsMargins(8, 8, 8, 8)

        splitter_board = QSplitter(Qt.Orientation.Horizontal)

        self.tbl_board_items = QTableWidget()
        self.tbl_board_items.setColumnCount(4)
        self.tbl_board_items.setHorizontalHeaderLabels(["ID Objectif", "Titre", "État", "Famille"])
        self.tbl_board_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_board_items.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_board_items.itemSelectionChanged.connect(self.on_board_item_selected)
        splitter_board.addWidget(self.tbl_board_items)

        self.tbl_dominos = QTableWidget()
        self.tbl_dominos.setColumnCount(4)
        self.tbl_dominos.setHorizontalHeaderLabels(["Seq", "Nom du Domino", "État", "Classe Action"])
        self.tbl_dominos.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter_board.addWidget(self.tbl_dominos)

        splitter_board.setSizes([550, 450])
        w_board_layout.addWidget(splitter_board)
        sub_tabs.addTab(w_board, "📋 BOARD-B : Machine d'États & Chaînes DOMINO")

        # ── Sous-Onglet 2 : PROMPTS MOISSONNÉS DUAL-DISQUE ──
        w_prompts = QWidget()
        w_prompts_layout = QVBoxLayout(w_prompts)
        w_prompts_layout.setContentsMargins(8, 8, 8, 8)
        w_prompts_layout.setSpacing(6)

        # Barre de recherche & filtres
        p_filter_h = QHBoxLayout()
        p_filter_h.setSpacing(6)

        self.txt_prompt_search = QLineEdit()
        self.txt_prompt_search.setPlaceholderText("Rechercher dans les 834 prompts moissonnés (FTS5 : nom, contenu, rôle, stratégie)...")
        self.txt_prompt_search.setStyleSheet("""
            QLineEdit {
                background: #030712;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 6px;
                padding: 5px 10px;
                color: #f8fafc;
                font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #10b981; }
        """)
        self.txt_prompt_search.returnPressed.connect(self.search_prompts)
        p_filter_h.addWidget(self.txt_prompt_search, 4)

        self.combo_disk = QComboBox()
        self.combo_disk.addItems([
            "💾 Tous les disques (M1 + M6)",
            "🏷️ M1 SSD (/media/turbo/JARVIS-M1)",
            "🖥️ M6 Local (/home/turbo)"
        ])
        self.combo_disk.setStyleSheet("""
            QComboBox {
                background: #0d1527;
                color: #38bdf8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)
        self.combo_disk.currentIndexChanged.connect(self.search_prompts)
        p_filter_h.addWidget(self.combo_disk, 2)

        btn_p_search = QPushButton("🔍 Filtrer")
        btn_p_search.setStyleSheet("""
            QPushButton {
                background: #065f46;
                color: #ffffff;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #047857; }
        """)
        btn_p_search.clicked.connect(self.search_prompts)
        p_filter_h.addWidget(btn_p_search)

        self.btn_harvest = QPushButton("🌾 Re-Moissonner Dual-Disque")
        self.btn_harvest.setStyleSheet("""
            QPushButton {
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.6);
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(16, 185, 129, 0.3); color: #ffffff; }
        """)
        self.btn_harvest.clicked.connect(self.run_harvest_prompts)
        p_filter_h.addWidget(self.btn_harvest)

        w_prompts_layout.addLayout(p_filter_h)

        # Splitter Prompts : Table à gauche, Aperçu & Actions à droite
        splitter_prompts = QSplitter(Qt.Orientation.Horizontal)

        self.tbl_prompts = QTableWidget()
        self.tbl_prompts.setColumnCount(5)
        self.tbl_prompts.setHorizontalHeaderLabels(["ID", "Fichier", "Catégorie", "Disque", "Taille"])
        self.tbl_prompts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_prompts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_prompts.itemSelectionChanged.connect(self.on_prompt_selected)
        splitter_prompts.addWidget(self.tbl_prompts)

        # Panneau de droite : Détails + Actions
        p_detail_box = QFrame()
        p_detail_box.setStyleSheet("background: #030712; border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 6px;")
        p_detail_layout = QVBoxLayout(p_detail_box)
        p_detail_layout.setContentsMargins(8, 8, 8, 8)
        p_detail_layout.setSpacing(6)

        self.lbl_prompt_header = QLabel("Sélectionnez un prompt dans la liste...")
        self.lbl_prompt_header.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        self.lbl_prompt_header.setStyleSheet("color: #34d399;")
        p_detail_layout.addWidget(self.lbl_prompt_header)

        self.txt_prompt_view = QTextEdit()
        self.txt_prompt_view.setReadOnly(True)
        self.txt_prompt_view.setStyleSheet("""
            QTextEdit {
                background-color: #02040a;
                color: #e2e8f0;
                font-family: 'Fira Code', 'JetBrains Mono', monospace;
                font-size: 11px;
                border: 1px solid #1e293b;
                border-radius: 4px;
                line-height: 1.4;
            }
        """)
        p_detail_layout.addWidget(self.txt_prompt_view)

        # Barre de boutons d'action sur le prompt sélectionné
        p_actions_h = QHBoxLayout()
        p_actions_h.setSpacing(8)

        self.btn_prompt_to_tr = QPushButton("⚖️ Débattre sur Table Ronde")
        self.btn_prompt_to_tr.setStyleSheet("""
            QPushButton {
                background: #581c87;
                color: #e9d5ff;
                border: 1px solid #c084fc;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #6b21a8; color: #ffffff; }
        """)
        self.btn_prompt_to_tr.setToolTip("Envoyer ce prompt à la Table Ronde des 7 experts pour délibération")
        self.btn_prompt_to_tr.clicked.connect(self.send_prompt_to_table_ronde)
        p_actions_h.addWidget(self.btn_prompt_to_tr)

        self.btn_prompt_to_bb = QPushButton("🧭 Router vers BOARD-B")
        self.btn_prompt_to_bb.setStyleSheet("""
            QPushButton {
                background: #0369a1;
                color: #bae6fd;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #0284c7; color: #ffffff; }
        """)
        self.btn_prompt_to_bb.setToolTip("Injecter ce prompt dans le routeur cognitif pour créer une chaîne DOMINO")
        self.btn_prompt_to_bb.clicked.connect(self.send_prompt_to_board_b)
        p_actions_h.addWidget(self.btn_prompt_to_bb)

        self.btn_copy_prompt = QPushButton("📋 Copier")
        self.btn_copy_prompt.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background: #334155; }
        """)
        self.btn_copy_prompt.clicked.connect(self.copy_prompt_content)
        p_actions_h.addWidget(self.btn_copy_prompt)

        p_detail_layout.addLayout(p_actions_h)
        splitter_prompts.addWidget(p_detail_box)

        splitter_prompts.setSizes([500, 500])
        w_prompts_layout.addWidget(splitter_prompts)
        sub_tabs.addTab(w_prompts, "🌾 PROMPTS MOISSONNÉS DUAL-DISQUE (M1 SSD & M6)")

        # ── Sous-Onglet 3 : AUDIT SOUVERAIN ──
        w_audit = QWidget()
        w_audit_layout = QVBoxLayout(w_audit)
        w_audit_layout.setContentsMargins(8, 8, 8, 8)

        self.tbl_audit = QTableWidget()
        self.tbl_audit.setColumnCount(5)
        self.tbl_audit.setHorizontalHeaderLabels(["Horodatage", "Agent", "Vérif", "Action / Quoi", "Décision & Motif"])
        self.tbl_audit.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_audit.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tbl_audit.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        w_audit_layout.addWidget(self.tbl_audit)
        sub_tabs.addTab(w_audit, "🛡️ AUDIT SOUVERAIN (Journal Append-Only)")

        layout.addWidget(sub_tabs)

        # Chargement initial des données
        self.refresh_data()

    def _make_badge(self, text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            QLabel {{
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid {color};
                color: {color};
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 6px;
            }}
        """)
        return lbl

    def refresh_data(self):
        # 1. Mise à jour badges télémétrie
        try:
            if os.path.exists(self.registry_db):
                conn = sqlite3.connect(f"file:{self.registry_db}?mode=ro", uri=True)
                cur = conn.cursor()
                n_art = cur.execute("SELECT count(*) FROM artifacts").fetchone()[0]
                n_fam = cur.execute("SELECT count(*) FROM families").fetchone()[0]
                n_agt = cur.execute("SELECT count(*) FROM agents").fetchone()[0]
                n_skl = cur.execute("SELECT count(*) FROM skills").fetchone()[0]
                conn.close()
                self.badge_art.setText(f"📦 {n_art} Artefacts")
                self.badge_fam.setText(f"🏛️ {n_fam} Familles")
                self.badge_agt.setText(f"🤖 {n_agt} Agents")
                self.badge_skl.setText(f"⚡ {n_skl} Skills")
        except Exception:
            pass

        try:
            if os.path.exists(self.master_db):
                conn = sqlite3.connect(f"file:{self.master_db}?mode=ro", uri=True)
                cur = conn.cursor()
                n_prm = cur.execute("SELECT count(*) FROM system_prompts_library").fetchone()[0]
                conn.close()
                self.badge_prm.setText(f"🌾 {n_prm} Prompts")
        except Exception:
            pass

        try:
            if os.path.exists(self.audit_db):
                conn = sqlite3.connect(f"file:{self.audit_db}?mode=ro", uri=True)
                cur = conn.cursor()
                n_aud = cur.execute("SELECT count(*) FROM events").fetchone()[0]
                conn.close()
                self.badge_aud.setText(f"🛡️ {n_aud} Audits")
        except Exception:
            pass

        # 2. Remplir table BOARD-B
        self.load_board_items()

        # 3. Remplir table Prompts
        self.search_prompts()

        # 4. Remplir table Audit
        self.load_audit_events()

    def load_board_items(self):
        if not os.path.exists(self.board_b_db):
            return
        try:
            conn = sqlite3.connect(f"file:{self.board_b_db}?mode=ro", uri=True)
            cur = conn.cursor()
            rows = cur.execute("SELECT id, title, state, family FROM board_items ORDER BY created_at DESC LIMIT 25").fetchall()
            conn.close()

            self.tbl_board_items.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.tbl_board_items.setItem(i, 0, QTableWidgetItem(r[0]))
                self.tbl_board_items.setItem(i, 1, QTableWidgetItem(r[1]))
                
                # Couleur selon état
                st_item = QTableWidgetItem(f"● {r[2]}")
                if r[2] == "DONE":
                    st_item.setForeground(QColor("#4ade80"))
                elif r[2] == "RUNNING":
                    st_item.setForeground(QColor("#00f0ff"))
                elif r[2] == "FAILED":
                    st_item.setForeground(QColor("#ef4444"))
                else:
                    st_item.setForeground(QColor("#fbbf24"))
                self.tbl_board_items.setItem(i, 2, st_item)
                
                self.tbl_board_items.setItem(i, 3, QTableWidgetItem(r[3]))
        except Exception:
            pass

    def on_board_item_selected(self):
        sel = self.tbl_board_items.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        item_id = self.tbl_board_items.item(row, 0).text()

        try:
            conn = sqlite3.connect(f"file:{self.board_b_db}?mode=ro", uri=True)
            cur = conn.cursor()
            rows = cur.execute("SELECT seq, name, state, action_class FROM dominos WHERE item_id = ? ORDER BY seq ASC", (item_id,)).fetchall()
            conn.close()

            self.tbl_dominos.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.tbl_dominos.setItem(i, 0, QTableWidgetItem(f"D{r[0]:02d}"))
                self.tbl_dominos.setItem(i, 1, QTableWidgetItem(r[1]))
                self.tbl_dominos.setItem(i, 2, QTableWidgetItem(r[2]))
                self.tbl_dominos.setItem(i, 3, QTableWidgetItem(r[3]))
        except Exception:
            pass

    def search_prompts(self):
        if not os.path.exists(self.master_db):
            return
        
        q = self.txt_prompt_search.text().strip()
        disk_filter = self.combo_disk.currentIndex()  # 0=Tous, 1=M1, 2=M6

        try:
            conn = sqlite3.connect(f"file:{self.master_db}?mode=ro&immutable=1", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            query_sql = ""
            params = []

            disk_clause = ""
            if disk_filter == 1:
                disk_clause = " AND p.origin_disk = 'M1_SSD' "
            elif disk_filter == 2:
                disk_clause = " AND p.origin_disk = 'M6_LOCAL' "

            if q:
                clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in q).strip()
                words = [w for w in clean_q.split() if len(w) > 2][:4]
                if words:
                    fts_term = " OR ".join(words)
                    query_sql = f"""
                        SELECT p.id, p.filename, p.category, p.origin_disk, length(p.content) as taille, p.content, p.rel_path
                        FROM system_prompts_library p
                        JOIN system_prompts_fts f ON p.id = f.rowid
                        WHERE system_prompts_fts MATCH ? {disk_clause}
                        ORDER BY rank
                        LIMIT 60
                    """
                    params.append(fts_term)
                else:
                    query_sql = f"""
                        SELECT id, filename, category, origin_disk, length(content) as taille, content, rel_path
                        FROM system_prompts_library p
                        WHERE 1=1 {disk_clause}
                        ORDER BY id DESC LIMIT 60
                    """
            else:
                query_sql = f"""
                    SELECT id, filename, category, origin_disk, length(content) as taille, content, rel_path
                    FROM system_prompts_library p
                    WHERE 1=1 {disk_clause}
                    ORDER BY id DESC LIMIT 60
                """

            rows = cur.execute(query_sql, params).fetchall()
            conn.close()

            self.current_prompts_data = [dict(r) for r in rows]
            self.tbl_prompts.setRowCount(len(self.current_prompts_data))

            for i, p in enumerate(self.current_prompts_data):
                self.tbl_prompts.setItem(i, 0, QTableWidgetItem(str(p["id"])))
                self.tbl_prompts.setItem(i, 1, QTableWidgetItem(p["filename"]))
                self.tbl_prompts.setItem(i, 2, QTableWidgetItem(p["category"]))

                disk_str = "🏷️ M1 SSD" if p["origin_disk"] == "M1_SSD" else "🖥️ M6 Local"
                d_item = QTableWidgetItem(disk_str)
                d_item.setForeground(QColor("#38bdf8") if p["origin_disk"] == "M1_SSD" else QColor("#4ade80"))
                self.tbl_prompts.setItem(i, 3, d_item)

                size_str = f"{p['taille']:,} car".replace(",", " ")
                self.tbl_prompts.setItem(i, 4, QTableWidgetItem(size_str))

            if self.current_prompts_data:
                self.tbl_prompts.selectRow(0)
            else:
                self.lbl_prompt_header.setText("Aucun prompt correspondant trouvé.")
                self.txt_prompt_view.setText("")

        except Exception as e:
            self.lbl_prompt_header.setText(f"Erreur recherche prompts : {e}")

    def on_prompt_selected(self):
        sel = self.tbl_prompts.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        if 0 <= row < len(self.current_prompts_data):
            p = self.current_prompts_data[row]
            disk_tag = "🏷️ M1 SSD" if p["origin_disk"] == "M1_SSD" else "🖥️ M6 Local"
            self.lbl_prompt_header.setText(f"📄 {p['filename']}  [{p['category']} · {disk_tag} · {p['taille']:,} car]")
            self.txt_prompt_view.setText(p["content"])

    def send_prompt_to_table_ronde(self):
        sel = self.tbl_prompts.selectedItems()
        if not sel or not self.current_prompts_data:
            QMessageBox.warning(self, "Table Ronde", "Veuillez d'abord sélectionner un prompt dans la liste.")
            return
        row = sel[0].row()
        p = self.current_prompts_data[row]
        
        first_line = p["content"].split("\n")[0].strip("# \t")
        if not first_line or len(first_line) < 5:
            first_line = p["filename"].replace(".md", "").replace("_", " ")
        
        question = f"Comment adapter et arbitrer la directive suivante ({p['filename']}) : « {first_line} » ?"

        win = self.window()
        if hasattr(win, "tab_tr") and hasattr(win, "tabs"):
            win.tab_tr.input_query.setText(question)
            win.tabs.setCurrentWidget(win.tab_tr)
            QMessageBox.information(
                self, "Table Ronde",
                f"✅ Directive transférée à la Table Ronde :\n« {question} »\n\n"
                "La question a été pré-remplie. Vous pouvez lancer le débat ou l'ajuster."
            )
        else:
            QMessageBox.information(self, "Directive Prête", f"Question préparée :\n\n{question}")

    def send_prompt_to_board_b(self):
        sel = self.tbl_prompts.selectedItems()
        if not sel or not self.current_prompts_data:
            QMessageBox.warning(self, "BOARD-B", "Veuillez d'abord sélectionner un prompt.")
            return
        row = sel[0].row()
        p = self.current_prompts_data[row]

        intent = p["content"].split("\n")[0].strip("# \t")
        if not intent or len(intent) < 5:
            intent = f"Appliquer directive {p['filename']}"
        
        self.txt_intent.setText(intent[:100])
        self.exec_route()

    def copy_prompt_content(self):
        text = self.txt_prompt_view.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                QMessageBox.information(self, "Presse-papier", "Prompt copié dans le presse-papier !")

    def run_harvest_prompts(self):
        self.btn_harvest.setEnabled(False)
        self.btn_harvest.setText("⏳ Moissonnage...")
        self.harvest_worker = PromptHarvestWorker()
        self.harvest_worker.finished_signal.connect(self.on_harvest_finished)
        self.harvest_worker.start()

    def on_harvest_finished(self, res):
        self.btn_harvest.setEnabled(True)
        self.btn_harvest.setText("🌾 Re-Moissonner Dual-Disque")
        if res.get("success"):
            self.refresh_data()
            QMessageBox.information(
                self, "Moissonnage Réussi",
                "✅ Moissonnage dual-disque terminé avec succès !\n"
                "Tous les prompts de M1 SSD et M6 Local sont synchronisés dans jarvis_master.db."
            )
        else:
            QMessageBox.warning(
                self, "Moissonnage",
                f"Résultat du moissonnage :\n{res.get('stderr') or res.get('stdout')}"
            )

    def load_audit_events(self):
        if not os.path.exists(self.audit_db):
            return
        try:
            conn = sqlite3.connect(f"file:{self.audit_db}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rows = cur.execute("SELECT quand, quel_agent, verif_statut, quoi, quelle_decision FROM events ORDER BY event_id DESC LIMIT 30").fetchall()
            conn.close()

            self.tbl_audit.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.tbl_audit.setItem(i, 0, QTableWidgetItem(r["quand"] or ""))
                self.tbl_audit.setItem(i, 1, QTableWidgetItem(r["quel_agent"] or "system"))
                
                v_item = QTableWidgetItem(r["verif_statut"] or "PASSED")
                if r["verif_statut"] == "PASSED":
                    v_item.setForeground(QColor("#4ade80"))
                elif r["verif_statut"] == "FAILED":
                    v_item.setForeground(QColor("#ef4444"))
                else:
                    v_item.setForeground(QColor("#fbbf24"))
                self.tbl_audit.setItem(i, 2, v_item)

                self.tbl_audit.setItem(i, 3, QTableWidgetItem(r["quoi"] or ""))
                self.tbl_audit.setItem(i, 4, QTableWidgetItem(r["quelle_decision"] or ""))
        except Exception:
            pass

    def exec_route(self):
        q = self.txt_intent.text().strip()
        if not q:
            return
        if not self.router:
            self._init_router()
            if not self.router:
                self.router_output.setText("❌ Erreur : Routeur cognitif indisponible.")
                return

        self.router_output.setText(f"⚙️ Analyse de l'intention : '{q}' en cours...")
        try:
            res = self.router.route_intent(q)
            fam = res["family"]
            conf = res["confidence"]
            agt = res["agent"]["name"]
            aid = res["agent"]["id"]

            out = [f"▶ INTENTION RECONNUE : Famille '{fam}' (Confiance: {conf*100:.0f}%)"]
            out.append(f"▶ AGENT EXPERT ASSIGNÉ : {agt} ({aid})")

            # Mémoire BOARD-A
            chunks = self.router.search_memory(q, limit=2)
            if chunks:
                out.append("\n📚 EXTRAITS DE MÉMOIRE SOUVERAINE (BOARD-A) :")
                for c in chunks:
                    out.append(f"   • [Chunk #{c['id']}] {c['text'][:140]}...")

            # Prompts Moissonnés Dual-Disque
            if hasattr(self.router, "search_prompts"):
                prompts = self.router.search_prompts(q, limit=2)
                if prompts:
                    out.append("\n🌾 DIRECTIVES & PROMPTS LIÉS (Dual-Disk Library) :")
                    for p in prompts:
                        out.append(f"   • [{p['origin_disk']}] {p['filename']} ({p['category']}) : {p['snippet'][:120]}...")

            # Skills
            skills = self.router.discover_skills(q, limit=3)
            if skills:
                out.append("\n⚡ SKILLS DÉCOUVERTS & ATTACHÉS DYNAMIQUEMENT :")
                for s in skills:
                    out.append(f"   • {s['name']} : {s['description'][:100]}...")

            # Création automatique de la chaîne DOMINO sur BOARD-B
            dominos = [
                {"label": f"1. Préparer contexte pour {agt}", "kind": "read", "action_class": "READ"},
                {"label": f"2. Exécuter intention via compétences {fam}", "kind": "execute", "action_class": "GENERATE"},
                {"label": "3. Vérifier intégrité et enregistrer trace OMEGA", "kind": "verify", "action_class": "READ"}
            ]
            obj_id = self.router.create_objective(
                title=f"Action : {q[:45]}...",
                description=q,
                intent="COCKPIT_INTENT",
                family=fam,
                dominos=dominos
            )
            out.append(f"\n✅ CHAÎNE DOMINO INSTANCIÉE SUR BOARD-B : Objectif ID = {obj_id}")

            self.router_output.setText("\n".join(out))
            self.refresh_data()

        except Exception as e:
            self.router_output.setText(f"❌ Erreur lors du routage : {e}")

    def trigger_improve_cycle(self):
        try:
            rdir = os.path.join(self.jarvis_dir, "omega", "engine")
            if rdir not in sys.path:
                sys.path.insert(0, rdir)
            from improve_cycle import OmegaImprovementCycle
            engine = OmegaImprovementCycle(dry_run=False)
            rep = engine.run()
            self.refresh_data()
            lessons_txt = "\n• " + "\n• ".join(rep.get("lessons", [])[:3])
            QMessageBox.information(
                self,
                "Cycle d'Auto-Amélioration OMEGA",
                f"✅ Cycle {rep['cycle_id']} complété avec succès en {rep['duration_ms']:.1f} ms !\n\n"
                f"Objectif BOARD-B : {rep['objective_id']}\n"
                f"Audit UID : {rep['audit_uid']}\n"
                f"Non-régression : {rep['benchmark']['verdict']} (Router: {rep['benchmark']['router_ms']:.1f}ms, RAG: {rep['benchmark']['rag_ms']:.1f}ms)\n\n"
                f"💡 Leçons cognitives enregistrées :{lessons_txt}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur Cycle", f"Échec du cycle d'amélioration : {e}")
