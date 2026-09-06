#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB : HUB IA WEB, CDP 9222 & NOTION VAULT
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from core.cdp_engine import get_cdp_status, start_cdp, stop_cdp, verify_cdp
from core.notion_engine import get_notion_stats, run_notion_backup_snapshot


class CdpWorker(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, action):
        super().__init__()
        self.action = action
    def run(self):
        if self.action == "start":
            res = start_cdp()
        elif self.action == "stop":
            res = stop_cdp()
        elif self.action == "verify":
            res = verify_cdp()
        else:
            res = get_cdp_status()
        self.finished_signal.emit(res)


class TabIaWeb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ── ENTÊTE ──
        lbl_title = QLabel("🌐 HUB IA WEB, CDP AUTHENTIFIÉ (PORT 9222) & NOTION VAULT")
        lbl_title.setFont(QFont("Ubuntu", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #38bdf8;")
        layout.addWidget(lbl_title)

        # ── APPLICATIONS IA DE BUREAU ──
        row_apps = QHBoxLayout()
        row_apps.setSpacing(8)
        apps_list = [
            ("👑 Claude Desktop", "purple", ["/usr/bin/claude-desktop"]),
            ("⚡ Claude Code CLI", "", ["gnome-terminal", "--title=Claude Code CLI", "--", "claude"]),
            ("🛰 Antigravity IDE", "purple", ["gnome-terminal", "--title=Google Antigravity", "--", "agy"]),
            ("🌐 BrowserOS App", "cyan", ["/home/turbo/Téléchargements/BrowserOS.AppImage"]),
            ("🤖 Chat Local Ollama", "amber", ["gnome-terminal", "--title=Inférence Locale Ollama", "--", "ollama", "run", "qwen2.5:1.5b"]),
        ]
        for name, cls, cmd in apps_list:
            b = QPushButton(name)
            if cls:
                b.setProperty("class", cls)
            b.clicked.connect(lambda _, c=cmd: subprocess.Popen(c, start_new_session=True))
            row_apps.addWidget(b)
        layout.addLayout(row_apps)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── PANNEAU GAUCHE : CDP 9222 ──
        w_left = QWidget()
        v_left = QVBoxLayout(w_left)
        v_left.setContentsMargins(0, 0, 0, 0)
        
        lbl_cdp = QLabel("⚡ CDP AUTHENTIFIÉ · PORT 9222 (LinkedIn)")
        lbl_cdp.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        lbl_cdp.setStyleSheet("color: #22d3ee;")
        v_left.addWidget(lbl_cdp)

        self.lbl_cdp_status = QLabel("Statut : Chargement…")
        self.lbl_cdp_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v_left.addWidget(self.lbl_cdp_status)

        h_cdp_btn = QHBoxLayout()
        btn_start = QPushButton("🚀 Démarrer :9222")
        btn_start.setProperty("class", "green")
        btn_start.clicked.connect(lambda: self.run_cdp_action("start"))
        h_cdp_btn.addWidget(btn_start)

        btn_verify = QPushButton("🔍 Tester Session")
        btn_verify.clicked.connect(lambda: self.run_cdp_action("verify"))
        h_cdp_btn.addWidget(btn_verify)

        btn_stop = QPushButton("🛑 Arrêter")
        btn_stop.setProperty("class", "red")
        btn_stop.clicked.connect(lambda: self.run_cdp_action("stop"))
        h_cdp_btn.addWidget(btn_stop)
        v_left.addLayout(h_cdp_btn)

        self.cdp_log = QTextEdit()
        self.cdp_log.setReadOnly(True)
        self.cdp_log.setStyleSheet("background-color: #020617; color: #a5f3fc; font-family: monospace; font-size: 11px;")
        v_left.addWidget(self.cdp_log)
        splitter.addWidget(w_left)

        # ── PANNEAU DROIT : NOTION VAULT ──
        w_right = QWidget()
        v_right = QVBoxLayout(w_right)
        v_right.setContentsMargins(0, 0, 0, 0)

        lbl_notion = QLabel("📦 NOTION JARVIS BACKUP & VAULT")
        lbl_notion.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        lbl_notion.setStyleSheet("color: #818cf8;")
        v_right.addWidget(lbl_notion)

        self.lbl_notion_stats = QLabel("Statistiques : Chargement…")
        self.lbl_notion_stats.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v_right.addWidget(self.lbl_notion_stats)

        btn_snap = QPushButton("⚡ Snapshot Notion Immédiat")
        btn_snap.setProperty("class", "purple")
        btn_snap.clicked.connect(self.trigger_notion_snap)
        v_right.addWidget(btn_snap)

        self.notion_table = QTableWidget()
        self.notion_table.setColumnCount(3)
        self.notion_table.setHorizontalHeaderLabels(["Fichier", "Taille (Ko)", "Date"])
        self.notion_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.notion_table.setStyleSheet("background-color: #020617; color: #cbd5e1; font-size: 11px;")
        v_right.addWidget(self.notion_table)
        splitter.addWidget(w_right)

        layout.addWidget(splitter)
        self.refresh_data()

    def refresh_data(self):
        # 1. CDP Status
        st = get_cdp_status()
        if st.get("alive"):
            self.lbl_cdp_status.setText(f"✅ CDP ACTIF sur port 9222 ({st.get('tabs_count', 0)} onglet(s))")
            self.lbl_cdp_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.lbl_cdp_status.setText("🛑 CDP Inactif sur :9222")
            self.lbl_cdp_status.setStyleSheet("color: #f87171;")

        # 2. Notion Stats
        ns = get_notion_stats()
        self.lbl_notion_stats.setText(f"📑 {ns.get('pages_count', 0)} Pages MD • 📊 {ns.get('csv_count', 0)} CSV • 🗄️ {ns.get('schemas_count', 0)} Schémas SQL")
        
        all_f = (ns.get("pages", []) + ns.get("csvs", []))
        self.notion_table.setRowCount(len(all_f))
        for row, f in enumerate(all_f):
            self.notion_table.setItem(row, 0, QTableWidgetItem(f.get("name", "")))
            self.notion_table.setItem(row, 1, QTableWidgetItem(str(f.get("size_kb", ""))))
            self.notion_table.setItem(row, 2, QTableWidgetItem(f.get("mtime", "")))

    def run_cdp_action(self, act):
        self.cdp_log.append(f"⏳ Exécution action CDP : {act}…")
        self.worker = CdpWorker(act)
        self.worker.finished_signal.connect(self.on_cdp_finished)
        self.worker.start()

    def on_cdp_finished(self, res):
        out = res.get("output") or res.get("message") or str(res)
        self.cdp_log.append(f"✨ Résultat :\n{out}\n")
        self.refresh_data()

    def trigger_notion_snap(self):
        self.cdp_log.append("⏳ Snapshot Notion en cours…")
        res = run_notion_backup_snapshot()
        self.cdp_log.append(f"✅ {res.get('summary')}\n")
        self.refresh_data()
