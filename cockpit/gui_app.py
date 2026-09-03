#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui_app.py — JARVIS MASTER COCKPIT (AAA FUTURISTIC SCALABLE DESKTOP APPLICATION)
100% Native PyQt6 GUI • Modular Architecture • High-Performance Cluster Telemetry • Claude Code First-Class
"""

import sys
import os
from datetime import datetime

# Ajout du répertoire courant au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QProgressBar, QFrame, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut

from core.config import M6_HOST, M6_PORT
from core.telemetry import get_vram_info, get_ram_info, get_cpu_info, is_port_open
from core.mcp_registry import get_all_mcp_servers
from ui.theme import STYLESHEET

# Import des onglets modulaires
from ui.tabs.tab_hud import TabHud
from ui.tabs.tab_avancements import TabAvancements
from ui.tabs.tab_claude import TabClaude
from ui.tabs.tab_apps import TabApps
from ui.tabs.tab_terminal import TabTerminal
from ui.tabs.tab_table_ronde import TabTableRonde
from ui.tabs.tab_plan import TabPlan
from ui.tabs.tab_sql import TabSql
from ui.tabs.tab_studio import TabStudio
from ui.tabs.tab_mcps import TabMcps
from ui.tabs.tab_swarm import TabSwarm
from ui.tabs.tab_cluster import TabCluster
from ui.tabs.tab_moisson import TabMoisson
from ui.tabs.tab_iaweb import TabIaWeb
from ui.tabs.tab_bureau import TabBureau

class JarvisMasterCockpitWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS MASTER COCKPIT — POSTE DE COMMANDE UNIFIÉ M4")
        self.resize(1400, 900)
        self.setMinimumSize(1150, 720)
        self.setStyleSheet(STYLESHEET)
        self.mcp_count = len(get_all_mcp_servers())

        self.init_ui()
        self.setup_shortcuts()

        # Timer de télémétrie non-bloquante (2.5 s)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(2500)
        self.update_telemetry()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ── TOP BAR / TELEMETRY HUD ──
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0a1124, stop:1 #0f1b38);
            border: 1px solid #00f0ff;
            border-radius: 12px;
            padding: 10px 16px;
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 6, 6, 6)

        # Brand Title
        brand_box = QVBoxLayout()
        title_lbl = QLabel("🤖 JARVIS MASTER COCKPIT")
        title_lbl.setFont(QFont("Ubuntu", 15, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1px;")
        brand_box.addWidget(title_lbl)

        sub_lbl = QLabel("POSTE MAÎTRE M4 • SSD M1 (1 To) • M6 GPU RJ45 (1.4 ms) • CLAUDE CODE • 0-TOKEN")
        sub_lbl.setFont(QFont("Ubuntu", 10))
        sub_lbl.setStyleSheet("color: #94a3b8;")
        brand_box.addWidget(sub_lbl)
        top_layout.addLayout(brand_box)

        top_layout.addStretch()

        # Telemetry Live Gauges
        telem_layout = QHBoxLayout()
        telem_layout.setSpacing(16)

        # Gauge VRAM
        vram_box = QVBoxLayout()
        self.lbl_vram = QLabel("VRAM GPU: -- / 4096 MB")
        self.lbl_vram.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        self.lbl_vram.setStyleSheet("color: #38bdf8;")
        self.bar_vram = QProgressBar()
        self.bar_vram.setRange(0, 4096)
        self.bar_vram.setFixedWidth(150)
        vram_box.addWidget(self.lbl_vram)
        vram_box.addWidget(self.bar_vram)
        telem_layout.addLayout(vram_box)

        # Gauge RAM
        ram_box = QVBoxLayout()
        self.lbl_ram = QLabel("RAM: -- / 16 GB")
        self.lbl_ram.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        self.lbl_ram.setStyleSheet("color: #c084fc;")
        self.bar_ram = QProgressBar()
        self.bar_ram.setRange(0, 160)
        self.bar_ram.setFixedWidth(140)
        ram_box.addWidget(self.lbl_ram)
        ram_box.addWidget(self.bar_ram)
        telem_layout.addLayout(ram_box)

        # Status Badges
        badge_box = QVBoxLayout()
        self.badge_m6 = QLabel("🟢 M6 RJ45 : UP (1.4 ms)")
        self.badge_m6.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        self.badge_m6.setStyleSheet("color: #4ade80;")
        
        self.badge_mcp = QLabel(f"📦 MCPs : {self.mcp_count} CONNECTÉS")
        self.badge_mcp.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        self.badge_mcp.setStyleSheet("color: #fbbf24;")
        badge_box.addWidget(self.badge_m6)
        badge_box.addWidget(self.badge_mcp)
        telem_layout.addLayout(badge_box)

        top_layout.addLayout(telem_layout)
        main_layout.addWidget(top_bar)

        # ── TABBED NAVIGATION (12 ONGLETS UNIFIÉS) ──
        self.tabs = QTabWidget()
        
        self.tab_hud = TabHud(self)
        self.tabs.addTab(self.tab_hud, "🎛 Cockpit Exécutif")

        self.tab_avancements = TabAvancements(self)
        self.tabs.addTab(self.tab_avancements, "🚀 Avancements & Sync")

        self.tab_claude = TabClaude(self)
        self.tabs.addTab(self.tab_claude, "👑 Claude Code Suite")

        self.tab_apps = TabApps(self)
        self.tabs.addTab(self.tab_apps, "🚀 Applications Bureau")

        self.tab_term = TabTerminal(self)
        self.tabs.addTab(self.tab_term, "💻 Terminal & TMUX")

        self.tab_tr = TabTableRonde(self)
        self.tabs.addTab(self.tab_tr, "🧠 Table Ronde & Experts")

        self.tab_plan = TabPlan(self)
        self.tabs.addTab(self.tab_plan, "📋 Board Plan & To-Do")

        self.tab_sql = TabSql(self)
        self.tabs.addTab(self.tab_sql, "🗄 Bases SQL (53)")

        self.tab_studio = TabStudio(self)
        self.tabs.addTab(self.tab_studio, "✍️ Studio Création IA")

        self.tab_mcps = TabMcps(self)
        self.tabs.addTab(self.tab_mcps, "📦 48 Serveurs MCP")

        self.tab_swarm = TabSwarm(self)
        self.tabs.addTab(self.tab_swarm, "🐳 Swarm & Services")

        self.tab_cluster = TabCluster(self)
        self.tabs.addTab(self.tab_cluster, "🖥 Cluster & Matériel")

        self.tab_moisson = TabMoisson(self)
        self.tabs.addTab(self.tab_moisson, "🌾 Moissonnage & Vente")

        self.tab_iaweb = TabIaWeb(self)
        self.tabs.addTab(self.tab_iaweb, "🌐 Hub IA Web, CDP 9222 & Notion")

        self.tab_bureau = TabBureau(self)
        self.tabs.addTab(self.tab_bureau, "🖥 Bureau GNOME & Verrous")

        main_layout.addWidget(self.tabs)
        self.setCentralWidget(main_widget)

        # ── STATUS BAR ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🟢 JARVIS MASTER COCKPIT Prêt • Raccourcis : F5 (Actualiser) • Ctrl+1 à Ctrl+9 (Changer d'onglet)")

    def setup_shortcuts(self):
        # F5 = Refresh current tab
        QShortcut(QKeySequence("F5"), self, self.refresh_current_tab)
        # Ctrl+1 à Ctrl+9 = Basculer vers onglets
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda idx=i-1: self.tabs.setCurrentIndex(idx))

    def refresh_current_tab(self):
        self.update_telemetry()
        cur_w = self.tabs.currentWidget()
        if hasattr(cur_w, "recharger_apps"):
            cur_w.recharger_apps()
        elif hasattr(cur_w, "refresh_sessions"):
            cur_w.refresh_sessions()
        elif hasattr(cur_w, "refresh_tasks"):
            cur_w.refresh_tasks()
        elif hasattr(cur_w, "scan_bases"):
            cur_w.scan_bases()
        elif hasattr(cur_w, "scan_mcps"):
            cur_w.scan_mcps()
        elif hasattr(cur_w, "refresh_services"):
            cur_w.refresh_services()
        elif hasattr(cur_w, "refresh_telemetry"):
            cur_w.refresh_telemetry()
        elif hasattr(cur_w, "refresh_report"):
            cur_w.refresh_report()
        elif hasattr(cur_w, "refresh_bureau"):
            cur_w.refresh_bureau()
        self.status_bar.showMessage(f"🔄 Actualisation effectuée ({datetime.now():%H:%M:%S})", 3000)

    def update_telemetry(self):
        vram = get_vram_info()
        ram = get_ram_info()
        cpu = get_cpu_info()
        m6_up = is_port_open(M6_HOST, M6_PORT, timeout=0.25)

        self.lbl_vram.setText(f"VRAM RTX 3050: {vram['used']} / {vram['total']} MB ({vram['temp']}°C)")
        self.bar_vram.setValue(vram["used"])

        self.lbl_ram.setText(f"RAM: {ram['used_gb']} / {ram['total_gb']} GB ({ram['percent']}%)")
        self.bar_ram.setValue(int(ram["used_gb"] * 10))

        if m6_up:
            self.badge_m6.setText("🟢 M6 Câble direct : UP (1.4 ms)")
            self.badge_m6.setStyleSheet("color: #4ade80;")
        else:
            self.badge_m6.setText("🔴 M6 : INJOIGNABLE")
            self.badge_m6.setStyleSheet("color: #f87171;")

def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = JarvisMasterCockpitWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
