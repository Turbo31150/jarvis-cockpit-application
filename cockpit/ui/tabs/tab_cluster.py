#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 10 : CLUSTER & MATÉRIEL
Deep telemetry inspection for M4 Laptop, M6 Tour (Direct USB-C ASIX), GPU, zRAM, and 16 Core Organs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QGridLayout, QFrame,
    QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.telemetry import get_full_telemetry
from core.config import MACHINE_NAME, HOSTNAME

class TabCluster(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("🖥 DIAGNOSTIC APPROFONDI DU CLUSTER (M4 + M6 CÂBLE DIRECT)")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #00f0ff; letter-spacing: 0.5px;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_rescan = QPushButton("🔄 Re-sonder Cluster")
        btn_rescan.setProperty("class", "cyan")
        btn_rescan.clicked.connect(self.refresh_telemetry)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Grid of Info Cards
        grid = QGridLayout()
        grid.setSpacing(12)

        # ── M4 Card ──
        card_m4 = QFrame()
        card_m4.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(8, 20, 42, 0.9), stop:1 rgba(4, 10, 22, 0.95));
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 12px;
            padding: 10px;
        """)
        c_m4 = QVBoxLayout(card_m4)
        c_m4.setSpacing(6)

        h_m4 = QHBoxLayout()
        l_m4_t = QLabel(f"💻 {MACHINE_NAME} (Poste Maître Local)")
        l_m4_t.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        l_m4_t.setStyleSheet("color: #38bdf8;")
        h_m4.addWidget(l_m4_t)
        h_m4.addStretch()
        b_m4 = QLabel(f"HOST: {HOSTNAME}")
        b_m4.setStyleSheet("color: #38bdf8; background: rgba(56, 189, 248, 0.15); border: 1px solid #38bdf8; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h_m4.addWidget(b_m4)
        c_m4.addLayout(h_m4)

        # M4 CPU
        self.lbl_m4_cpu = QLabel("CPU: --")
        self.lbl_m4_cpu.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m4_cpu.setStyleSheet("color: #94a3b8;")
        self.bar_m4_cpu = QProgressBar()
        self.bar_m4_cpu.setRange(0, 100)
        self.bar_m4_cpu.setFixedHeight(10)
        c_m4.addWidget(self.lbl_m4_cpu)
        c_m4.addWidget(self.bar_m4_cpu)

        # M4 RAM
        self.lbl_m4_ram = QLabel("RAM: --")
        self.lbl_m4_ram.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m4_ram.setStyleSheet("color: #c084fc;")
        self.bar_m4_ram = QProgressBar()
        self.bar_m4_ram.setRange(0, 100)
        self.bar_m4_ram.setFixedHeight(10)
        c_m4.addWidget(self.lbl_m4_ram)
        c_m4.addWidget(self.bar_m4_ram)

        # M4 GPU
        self.lbl_m4_gpu = QLabel("GPU: Détection...")
        self.lbl_m4_gpu.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m4_gpu.setStyleSheet("color: #38bdf8;")
        self.bar_m4_gpu = QProgressBar()
        self.bar_m4_gpu.setRange(0, 4096)
        self.bar_m4_gpu.setFixedHeight(10)
        c_m4.addWidget(self.lbl_m4_gpu)
        c_m4.addWidget(self.bar_m4_gpu)

        # M4 zRAM
        self.lbl_m4_zram = QLabel("zRAM / Swap: --")
        self.lbl_m4_zram.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m4_zram.setStyleSheet("color: #f59e0b;")
        c_m4.addWidget(self.lbl_m4_zram)

        grid.addWidget(card_m4, 0, 0)

        # ── M6 Card ──
        card_m6 = QFrame()
        card_m6.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(22, 11, 40, 0.9), stop:1 rgba(9, 4, 18, 0.95));
            border: 1px solid rgba(192, 132, 252, 0.35);
            border-radius: 12px;
            padding: 10px;
        """)
        c_m6 = QVBoxLayout(card_m6)
        c_m6.setSpacing(6)

        h_m6 = QHBoxLayout()
        l_m6_t = QLabel("🏢 M6 (Tour Inférence 4 GPU)")
        l_m6_t.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        l_m6_t.setStyleSheet("color: #c084fc;")
        h_m6.addWidget(l_m6_t)
        h_m6.addStretch()
        self.badge_m6_status = QLabel("SONDAGE...")
        self.badge_m6_status.setStyleSheet("color: #fbbf24; background: rgba(251, 191, 36, 0.15); border: 1px solid #fbbf24; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h_m6.addWidget(self.badge_m6_status)
        c_m6.addLayout(h_m6)

        self.lbl_m6_net = QLabel("• Lien Réseau Direct : ASIX USB-C (1.4 ms)")
        self.lbl_m6_net.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m6_net.setStyleSheet("color: #94a3b8;")
        c_m6.addWidget(self.lbl_m6_net)

        self.lbl_m6_models = QLabel("• Modèles Inférence : Aucun modèle chargé")
        self.lbl_m6_models.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m6_models.setStyleSheet("color: #c084fc;")
        c_m6.addWidget(self.lbl_m6_models)

        self.lbl_m6_endpoint = QLabel("• Endpoint HTTP : http://10.42.0.230:11434")
        self.lbl_m6_endpoint.setFont(QFont("JetBrains Mono", 9))
        self.lbl_m6_endpoint.setStyleSheet("color: #38bdf8;")
        c_m6.addWidget(self.lbl_m6_endpoint)

        c_m6.addStretch()
        grid.addWidget(card_m6, 0, 1)

        layout.addLayout(grid)

        # Organs Table
        lbl_org = QLabel("🩺 ÉTAT DES 16 ORGANES DU NOYAU")
        lbl_org.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_org.setStyleSheet("color: #4ade80; margin-top: 4px; letter-spacing: 0.5px;")
        layout.addWidget(lbl_org)

        self.table_organs = QTableWidget()
        self.table_organs.setColumnCount(4)
        self.table_organs.setHorizontalHeaderLabels(["Organe du Noyau", "Hôte : Port", "Rôle Système", "État Réel"])
        self.table_organs.setColumnWidth(0, 220)
        self.table_organs.setColumnWidth(1, 140)
        self.table_organs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_organs.setColumnWidth(3, 110)
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

        # M4 Update
        cpu_load1 = cpu.get('load_1m', 0)
        try:
            load_val = float(cpu_load1)
            cpu_pct = min(100, int(load_val * 12.5))
        except (ValueError, TypeError):
            cpu_pct = 0
        self.lbl_m4_cpu.setText(f"• CPU Charge : {cpu.get('load_1m')} / {cpu.get('load_5m')} / {cpu.get('load_15m')} (Temp: {cpu.get('temp_c')}°C)")
        self.bar_m4_cpu.setValue(cpu_pct)

        ram_pct = int(ram.get('percent', 0))
        self.lbl_m4_ram.setText(f"• RAM Utilisée : {ram.get('used_gb')} / {ram.get('total_gb')} Go ({ram_pct}%)")
        self.bar_m4_ram.setValue(ram_pct)

        vram_used = int(vram.get('used', 0))
        vram_tot = int(vram.get('total', 4096))
        vram_name = vram.get('name', 'GPU NVIDIA')
        self.lbl_m4_gpu.setText(f"• {vram_name} : {vram_used} / {vram_tot} Mo ({vram.get('temp')}°C • Utilisation {vram.get('util')}%)")
        self.bar_m4_gpu.setRange(0, max(vram_tot, 1))
        self.bar_m4_gpu.setValue(vram_used)
        if vram.get("gpus"):
            gpu_tt = "Détail GPU :\n" + "\n".join([f"• {g['name']}: {g['used']}/{g['total']} Mo ({g['temp']}°C, util {g['util']}%)" for g in vram["gpus"]])
            self.lbl_m4_gpu.setToolTip(gpu_tt)

        self.lbl_m4_zram.setText(f"• zRAM / Swap : {cpu.get('zram_percent')}% utilisé ({cpu.get('zram_used_mb')} Mo)")

        # M6 Update
        if m6.get("online"):
            self.badge_m6_status.setText("🟢 EN LIGNE (UP)")
            self.badge_m6_status.setStyleSheet("color: #4ade80; background: rgba(74, 222, 128, 0.15); border: 1px solid #4ade80; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        else:
            self.badge_m6_status.setText("🔴 INJOIGNABLE (DOWN)")
            self.badge_m6_status.setStyleSheet("color: #f87171; background: rgba(248, 113, 113, 0.15); border: 1px solid #f87171; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")

        self.lbl_m6_net.setText(f"• Latence ASIX USB-C : {m6.get('latency_ms', '--')} ms (Lien direct 1.4 ms)")
        models_str = ", ".join(m6.get("loaded_models", [])) or "Aucun modèle chargé"
        self.lbl_m6_models.setText(f"• Modèles Inférence Actifs : {models_str}")
        self.lbl_m6_endpoint.setText(f"• Inférence Directe : http://{m6.get('host', '10.42.0.230')}:{m6.get('port', 11434)}")

        # Organes Table
        organs = telem.get("organes", [])
        self.table_organs.setRowCount(len(organs))
        for row, o in enumerate(organs):
            self.table_organs.setItem(row, 0, QTableWidgetItem(o["nom"]))
            self.table_organs.setItem(row, 1, QTableWidgetItem(str(o['host']) + ":" + str(o['port'])))
            self.table_organs.setItem(row, 2, QTableWidgetItem(o["role"]))

            is_up = o.get("online", False)
            it_st = QTableWidgetItem("🟢 ACTIF" if is_up else "✖ MUET")
            it_st.setForeground(QColor("#4ade80" if is_up else "#f87171"))
            self.table_organs.setItem(row, 3, it_st)
