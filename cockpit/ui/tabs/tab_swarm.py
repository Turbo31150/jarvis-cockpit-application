#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 9 : SWARM DOCKER & SERVICES
Live infrastructure supervisor for PostgreSQL, Redis, n8n, Portainer, Ollama, Whisper, and CDP.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.swarm_manager import get_swarm_services_status
import subprocess

class TabSwarm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("🐳 INFRASTRUCTURE DOCKER SWARM & MICROSERVICES")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #4ade80;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_rescan = QPushButton("🔄 Actualiser Sondes")
        btn_rescan.clicked.connect(self.refresh_services)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Services Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Microservice / Conteneur", "Endpoint Réseau", "Rôle Système", "Statut Temps Réel"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Quick Web Openers
        bot_h = QHBoxLayout()
        for title, url in [
            ("⚡ n8n (:5678)", "http://127.0.0.1:5678"),
            ("🐳 Portainer (:9000)", "http://127.0.0.1:9000"),
            ("🌐 Cockpit Web (:8600)", "http://127.0.0.1:8600"),
            ("🎤 Whisper Voice (:9742)", "http://127.0.0.1:9742"),
        ]:
            b = QPushButton(title)
            b.clicked.connect(lambda _, u=url: subprocess.Popen(["xdg-open", u], start_new_session=True))
            bot_h.addWidget(b)
        bot_h.addStretch()
        layout.addLayout(bot_h)

        self.refresh_services()

    def refresh_services(self):
        services = get_swarm_services_status()
        self.table.setRowCount(len(services))
        for row, s in enumerate(services):
            it_name = QTableWidgetItem(s["name"])
            it_name.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
            self.table.setItem(row, 0, it_name)

            self.table.setItem(row, 1, QTableWidgetItem(s["endpoint"]))
            self.table.setItem(row, 2, QTableWidgetItem(s["role"]))

            is_up = s.get("online", False)
            it_st = QTableWidgetItem("🟢 ACTIF (UP)" if is_up else "🔴 INACTIF (DOWN)")
            it_st.setForeground(QColor("#4ade80" if is_up else "#f87171"))
            self.table.setItem(row, 3, it_st)
