#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 6 : EXPLORATEUR SQL & VECTOR STORE
Browse 229 SQLite databases, table schemas, live SQL query runner, and vector store metrics.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QTextEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.database import scan_all_sqlite_databases, execute_safe_query, get_vector_store_stats

class TabSql(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_bases = []
        self.selected_db = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🗄 EXPLORATEUR DE BASES SQL & VECTOR STORE")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #38bdf8;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        vstats = get_vector_store_stats()
        self.lbl_vecto = QLabel(f"🧠 Vector Store : {vstats.get('vectors', 0)} vecteurs 768D")
        self.lbl_vecto.setStyleSheet("color: #c084fc; font-weight: bold; font-size: 11px;")
        top_h.addWidget(self.lbl_vecto)

        btn_rescan = QPushButton("🔄 Scanner Bases")
        btn_rescan.clicked.connect(self.scan_bases)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Splitter: Left = Bases List, Right = Query Runner & Results
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Widget: Bases Table
        left_w = QWidget()
        left_layout = QVBoxLayout(left_w)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.db_search = QLineEdit()
        self.db_search.setPlaceholderText("🔍 Filtrer les bases...")
        self.db_search.textChanged.connect(self.filter_bases)
        left_layout.addWidget(self.db_search)

        self.db_table = QTableWidget()
        self.db_table.setColumnCount(3)
        self.db_table.setHorizontalHeaderLabels(["Base", "Taille", "Tables"])
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.db_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.db_table.itemSelectionChanged.connect(self.select_db)
        left_layout.addWidget(self.db_table)
        splitter.addWidget(left_w)

        # Right Widget: SQL Query & Results Table
        right_w = QWidget()
        right_layout = QVBoxLayout(right_w)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_db_info = QLabel("Sélectionnez une base à gauche pour inspecter ses tables.")
        self.lbl_db_info.setStyleSheet("color: #fbbf24; font-weight: bold;")
        right_layout.addWidget(self.lbl_db_info)

        query_h = QHBoxLayout()
        self.sql_input = QLineEdit()
        self.sql_input.setPlaceholderText("SELECT * FROM sqlite_master WHERE type='table';")
        self.sql_input.returnPressed.connect(self.run_query)
        query_h.addWidget(self.sql_input)

        btn_run = QPushButton("▶ Exécuter SQL")
        btn_run.setProperty("class", "green")
        btn_run.clicked.connect(self.run_query)
        query_h.addWidget(btn_run)
        right_layout.addLayout(query_h)

        self.result_table = QTableWidget()
        right_layout.addWidget(self.result_table)
        splitter.addWidget(right_w)

        splitter.setSizes([380, 720])
        layout.addWidget(splitter)

        self.scan_bases()

    def scan_bases(self):
        self.all_bases = scan_all_sqlite_databases()
        self.lbl_title.setText(f"🗄 EXPLORATEUR DE BASES SQL ({len(self.all_bases)} bases vivantes)")
        self.populate_bases(self.all_bases)

    def populate_bases(self, bases):
        self.bases_visibles = bases
        self.db_table.setRowCount(len(bases))
        for row, b in enumerate(bases):
            self.db_table.setItem(row, 0, QTableWidgetItem(b["name"]))
            self.db_table.setItem(row, 1, QTableWidgetItem(b["size_str"]))
            self.db_table.setItem(row, 2, QTableWidgetItem(str(b["table_count"])))

    def filter_bases(self):
        q = self.db_search.text().lower().strip()
        filtered = [b for b in self.all_bases if q in b["name"].lower() or q in b["rel_path"].lower()] if q else self.all_bases
        self.populate_bases(filtered)

    def select_db(self):
        row = self.db_table.currentRow()
        if 0 <= row < len(self.bases_visibles):
            b = self.bases_visibles[row]
            self.selected_db = b["path"]
            tbl_str = ", ".join(b.get("tables", [])[:8])
            self.lbl_db_info.setText(f"Base : {b['name']} ({b['size_str']}) · Tables : {tbl_str}")
            if b.get("tables"):
                self.sql_input.setText(f"SELECT * FROM {b['tables'][0]} LIMIT 20;")
                self.run_query()

    def run_query(self):
        if not self.selected_db:
            return
        sql = self.sql_input.text().strip()
        if not sql:
            return
        res = execute_safe_query(self.selected_db, sql)
        if res.get("error"):
            self.lbl_db_info.setText(f"❌ Erreur SQL: {res['error']}")
            return

        cols = res.get("columns", [])
        rows = res.get("rows", [])
        self.result_table.setColumnCount(len(cols))
        self.result_table.setHorizontalHeaderLabels(cols)
        self.result_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                self.result_table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
