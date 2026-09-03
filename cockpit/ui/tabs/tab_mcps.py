#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 8 : MATRICE DES SERVEURS MCP
Inspects 91+ active Model Context Protocol (MCP) servers, tools, and configurations.
"""

import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.mcp_registry import get_all_mcp_servers

class TabMcps(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_mcps = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("📦 MATRICE DES SERVEURS MCP CONNECTÉS")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #fbbf24;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrer les serveurs MCP...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.filter_mcps)
        top_h.addWidget(self.search_input)

        btn_rescan = QPushButton("🔄 Actualiser")
        btn_rescan.clicked.connect(self.scan_mcps)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Splitter: Table left, Config inspector right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Serveur MCP", "Transport", "Commande / Endpoint"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.show_details)
        splitter.addWidget(self.table)

        self.details_json = QTextEdit()
        self.details_json.setReadOnly(True)
        self.details_json.setStyleSheet("background-color: #030712; color: #38bdf8; font-family: monospace;")
        self.details_json.setPlaceholderText("Sélectionnez un serveur MCP pour inspecter sa configuration JSON...")
        splitter.addWidget(self.details_json)

        splitter.setSizes([650, 450])
        layout.addWidget(splitter)

        self.scan_mcps()

    def scan_mcps(self):
        self.all_mcps = get_all_mcp_servers()
        self.lbl_title.setText(f"📦 MATRICE DES SERVEURS MCP ({len(self.all_mcps)} serveurs connectés)")
        self.filter_mcps()

    def filter_mcps(self):
        q = self.search_input.text().lower().strip()
        filtered = [m for m in self.all_mcps if q in m["name"].lower() or q in m["endpoint"].lower()] if q else self.all_mcps
        self.table.setRowCount(len(filtered))
        self.filtered_mcps = filtered
        for row, m in enumerate(filtered):
            it_name = QTableWidgetItem(f"🟢 {m['name']}")
            it_name.setForeground(QColor("#4ade80"))
            it_name.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
            self.table.setItem(row, 0, it_name)

            it_tr = QTableWidgetItem(m["transport"])
            it_tr.setForeground(QColor("#fbbf24"))
            self.table.setItem(row, 1, it_tr)

            self.table.setItem(row, 2, QTableWidgetItem(m["endpoint"]))

    def show_details(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.filtered_mcps):
            m = self.filtered_mcps[row]
            cfg = m.get("raw_config", {})
            self.details_json.setText(json.dumps(cfg, indent=2))
