#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 10 : CLUSTER & MATÉRIEL
Deep telemetry inspection for M4 Laptop, M6 Tour (Direct USB-C ASIX), GPU, zRAM, and 16 Core Organs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.telemetry import get_full_telemetry

class TabCluster(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("🖥 DIAGNOSTIC APPROFONDI DU CLUSTER (M4 + M6 CÂBLE DIRECT)")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #00f0ff;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_rescan = QPushButton("🔄 Re-sonder Cluster")
        btn_rescan.clicked.connect(self.refresh_telemetry)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Grid of Info Cards
        grid = QGridLayout()
        grid.setSpacing(10)

        # M4 Card
        card_m4 = QFrame()
        card_m4.setProperty("class", "cyber-card")
        c_m4 = QVBoxLayout(card_m4)
        l_m4_t = QLabel("💻 M4 (Poste Maître Local)")
        l_m4_t.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        l_m4_t.setStyleSheet("color: #38bdf8;")
        c_m4.addWidget(l_m4_t)
        self.lbl_m4_details = QLabel("Chargement métriques...")
        self.lbl_m4_details.setStyleSheet("color: #94a3b8; font-family: monospace;")
        c_m4.addWidget(self.lbl_m4_details)
        grid.addWidget(card_m4, 0, 0)

        # M6 Card
        card_m6 = QFrame()
        card_m6.setProperty("class", "cyber-card")
        c_m6 = QVBoxLayout(card_m6)
        l_m6_t = QLabel("🏢 M6 (Tour Inférence 4 GPU · 10.42.0.230)")
        l_m6_t.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        l_m6_t.setStyleSheet("color: #c084fc;")
        c_m6.addWidget(l_m6_t)
        self.lbl_m6_details = QLabel("Sondage en cours...")
        self.lbl_m6_details.setStyleSheet("color: #94a3b8; font-family: monospace;")
        c_m6.addWidget(self.lbl_m6_details)
        grid.addWidget(card_m6, 0, 1)

        layout.addLayout(grid)

        # Organs Table
        lbl_org = QLabel("🩺 ÉTAT DES 16 ORGANES DU NOYAU")
        lbl_org.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_org.setStyleSheet("color: #4ade80; margin-top: 6px;")
        layout.addWidget(lbl_org)

        self.table_organs = QTableWidget()
        self.table_organs.setColumnCount(4)
        self.table_organs.setHorizontalHeaderLabels(["Organe du Noyau", "Hôte : Port", "Rôle Système", "État Réel"])
        self.table_organs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_organs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_organs)

        self.refresh_telemetry()

    def refresh_telemetry(self):
        telem = get_full_telemetry()
        m4 = telem.get("m4", {})
        vram = m4.get("vram", {})
        ram = m4.get("ram", {})
        cpu = m4.get("cpu", {})
        m6 = telem.get("m6", {})

        m4_txt = (
            "• CPU Charge : " + str(cpu.get('load_1m')) + " / " + str(cpu.get('load_5m')) + " / " + str(cpu.get('load_15m')) + " (Temp: " + str(cpu.get('temp_c')) + "°C)\n" +
            "• RAM Utilisée : " + str(ram.get('used_gb')) + " / " + str(ram.get('total_gb')) + " Go (" + str(ram.get('percent')) + "%)\n" +
            "• zRAM / Swap : " + str(cpu.get('zram_percent')) + "% utilisé (" + str(cpu.get('zram_used_mb')) + " Mo)\n" +
            "• GPU RTX 3050 Laptop : " + str(vram.get('used')) + " / " + str(vram.get('total')) + " Mo (" + str(vram.get('temp')) + "°C - " + str(vram.get('util')) + "%)"
        )
        self.lbl_m4_details.setText(m4_txt)

        m6_status = "🟢 EN LIGNE (UP)" if m6.get("online") else "🔴 INJOIGNABLE (DOWN)"
        models_str = ", ".join(m6.get("loaded_models", [])) or "Aucun modèle chargé"
        m6_txt = (
            "• Statut Câble Direct : " + m6_status + "\n" +
            "• Latence Réseau ASIX : " + str(m6.get('latency_ms')) + " ms (Lien direct 1.4 ms)\n" +
            "• Modèles Inférence Actifs : " + models_str + "\n" +
            "• Accès Inférence : http://" + str(m6.get('host')) + ":" + str(m6.get('port'))
        )
        self.lbl_m6_details.setText(m6_txt)

        # Organes Table
        organs = telem.get("organes", [])
        self.table_organs.setRowCount(len(organs))
        for row, o in enumerate(organs):
            self.table_organs.setItem(row, 0, QTableWidgetItem(o["nom"]))
            self.table_organs.setItem(row, 1, QTableWidgetItem(str(o['host']) + ":" + str(o['port'])))
            self.table_organs.setItem(row, 2, QTableWidgetItem(o["role"]))

            is_up = o.get("online", False)
            it_st = QTableWidgetItem("🟢 RÉPOND" if is_up else "✖ MUET")
            it_st.setForeground(QColor("#4ade80" if is_up else "#f87171"))
            self.table_organs.setItem(row, 3, it_st)
