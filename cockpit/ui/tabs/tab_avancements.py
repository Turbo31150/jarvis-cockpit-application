#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB AVANCEMENTS & SYNCHRONISATION (NATIVE PYQT6)
================================================================
Supervision des chantiers de production (production.db), dépôts Git, timers systemd et sync 1-clic.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar,
    QFrame, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.sync_engine import get_avancements_data, trigger_synchronisation, creer_nouveau_chantier, update_tache_production

class SyncWorker(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, auto_git=False):
        super().__init__()
        self.auto_git = auto_git
    def run(self):
        res = trigger_synchronisation(auto_git_commit=self.auto_git)
        self.finished_signal.emit(res)

class TabAvancements(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(10000)
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── TOP BAR HEADER ──
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🚀 AVANCEMENTS DE PRODUCTION & SYNCHRONISATION (production.db)")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #10b981;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        self.btn_sync = QPushButton("⚡ Synchroniser Tout (1-Clic)")
        self.btn_sync.setProperty("class", "green")
        self.btn_sync.setStyleSheet("background: #059669; color: white; font-weight: bold; padding: 6px 14px; border-radius: 8px;")
        self.btn_sync.clicked.connect(self.run_sync)
        top_h.addWidget(self.btn_sync)

        self.btn_new_run = QPushButton("➕ Nouveau Chantier")
        self.btn_new_run.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 8px;")
        self.btn_new_run.clicked.connect(self.nouveau_chantier_dialog)
        top_h.addWidget(self.btn_new_run)

        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.clicked.connect(self.refresh_data)
        top_h.addWidget(btn_refresh)
        layout.addLayout(top_h)

        # ── KPI CARDS ──
        kpi_h = QHBoxLayout()
        kpi_h.setSpacing(10)

        self.card_runs = self.create_kpi_card("CHANTIERS PROD", "--", "#10b981")
        self.card_taches = self.create_kpi_card("SOUS-TÂCHES", "--", "#06b6d4")
        self.card_git = self.create_kpi_card("DÉPÔTS GIT", "--", "#f59e0b")
        self.card_timers = self.create_kpi_card("TIMERS SYSTEMD", "--", "#8b5cf6")

        kpi_h.addWidget(self.card_runs)
        kpi_h.addWidget(self.card_taches)
        kpi_h.addWidget(self.card_git)
        kpi_h.addWidget(self.card_timers)
        layout.addLayout(kpi_h)

        # ── TABLE DES CHANTIERS DE PRODUCTION ──
        lbl_sec = QLabel("📌 Chantiers de Production & Étapes Actives")
        lbl_sec.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        lbl_sec.setStyleSheet("color: #e2e8f0; margin-top: 4px;")
        layout.addWidget(lbl_sec)

        self.table_runs = QTableWidget()
        self.table_runs.setColumnCount(6)
        self.table_runs.setHorizontalHeaderLabels(["Run ID", "État", "Étape", "Besoin du Chantier", "Avancement", "Tâches"])
        self.table_runs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_runs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_runs.setStyleSheet("background: #0b0f17; border: 1px solid #1e293b; color: #e2e8f0;")
        layout.addWidget(self.table_runs)

        # ── JOURNAL DES DERNIERS GESTES ──
        lbl_j = QLabel("📜 Journal Unique des Derniers Gestes (LOI 3)")
        lbl_j.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        lbl_j.setStyleSheet("color: #cbd5e1; margin-top: 4px;")
        layout.addWidget(lbl_j)

        self.table_journal = QTableWidget()
        self.table_journal.setColumnCount(4)
        self.table_journal.setHorizontalHeaderLabels(["Horodate", "Brique", "Message", "Run ID"])
        self.table_journal.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_journal.setMaximumHeight(160)
        self.table_journal.setStyleSheet("background: #0b0f17; border: 1px solid #1e293b; color: #cbd5e1; font-size: 11px;")
        layout.addWidget(self.table_journal)

    def create_kpi_card(self, title, default_val, color_hex):
        frame = QFrame()
        frame.setStyleSheet(f"""
            background: #0f172a;
            border: 1px solid #1e293b;
            border-left: 4px solid {color_hex};
            border-radius: 10px;
            padding: 8px 12px;
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(4, 4, 4, 4)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
        v.addWidget(lbl_t)

        lbl_v = QLabel(default_val)
        lbl_v.setObjectName("val")
        lbl_v.setFont(QFont("Monospace", 14, QFont.Weight.Bold))
        lbl_v.setStyleSheet(f"color: {color_hex};")
        v.addWidget(lbl_v)
        return frame

    def refresh_data(self):
        try:
            data = get_avancements_data()
            if not data.get("success"):
                return
            k = data["kpis"]
            self.card_runs.findChild(QLabel, "val").setText(f"{k['runs_ouverts']} ouverts · {k['runs_livres']} livrés")
            self.card_taches.findChild(QLabel, "val").setText(f"{k['fait_taches']}/{k['total_taches']} ({k['global_progress']}%)")
            
            git_synced = sum(1 for g in data["git_repos"] if g["synced"])
            self.card_git.findChild(QLabel, "val").setText(f"{git_synced}/{len(data['git_repos'])} dépôts à jour")
            self.card_timers.findChild(QLabel, "val").setText(f"{len(data['timers'])} timers actifs")

            # Table Chantiers
            runs = data.get("runs", [])
            self.table_runs.setRowCount(len(runs))
            for i, r in enumerate(runs):
                self.table_runs.setItem(i, 0, QTableWidgetItem(r["run_id"]))
                
                it_etat = QTableWidgetItem(r["etat"].upper())
                it_etat.setForeground(QColor("#10b981" if r["etat"] == "livre" else "#38bdf8"))
                self.table_runs.setItem(i, 1, it_etat)
                
                self.table_runs.setItem(i, 2, QTableWidgetItem(r.get("etape", "").upper()))
                self.table_runs.setItem(i, 3, QTableWidgetItem(r.get("besoin", "")))
                self.table_runs.setItem(i, 4, QTableWidgetItem(f"{r.get('progress_pct', 0)}%"))
                self.table_runs.setItem(i, 5, QTableWidgetItem(f"{r.get('fait_taches', 0)}/{r.get('total_taches', 0)}"))

            # Table Journal
            journal = data.get("journal", [])
            self.table_journal.setRowCount(len(journal))
            for i, j in enumerate(journal):
                self.table_journal.setItem(i, 0, QTableWidgetItem(j.get("horodate", "")))
                self.table_journal.setItem(i, 1, QTableWidgetItem(j.get("brique", "")))
                self.table_journal.setItem(i, 2, QTableWidgetItem(j.get("message", "")))
                self.table_journal.setItem(i, 3, QTableWidgetItem(j.get("run_id", "")))
        except Exception:
            pass

    def run_sync(self):
        self.btn_sync.setText("⏳ Synchronisation…")
        self.btn_sync.setEnabled(False)
        self.worker = SyncWorker(auto_git=False)
        self.worker.finished_signal.connect(self.on_sync_done)
        self.worker.start()

    def on_sync_done(self, res):
        self.btn_sync.setText("⚡ Synchroniser Tout (1-Clic)")
        self.btn_sync.setEnabled(True)
        self.refresh_data()
        QMessageBox.information(self, "Synchronisation JARVIS", res.get("summary", "Synchronisation terminée avec succès."))

    def nouveau_chantier_dialog(self):
        text, ok = QInputDialog.getText(self, "Nouveau Chantier", "Besoin / Objectif du chantier de production :")
        if ok and text.strip():
            res = creer_nouveau_chantier(text.strip())
            if res.get("success"):
                self.refresh_data()
                QMessageBox.information(self, "Chantier Ouvert", f"Chantier #{res.get('run_id')} créé avec succès.")
            else:
                QMessageBox.warning(self, "Erreur", res.get("error", "Échec création chantier"))
