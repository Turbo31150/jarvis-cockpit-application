#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 2 : APPLICATIONS DU BUREAU
Comprehensive Hub scanning 100+ desktop applications and scripts with real-time search & filters.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QIcon
from core.config import APP_CATEGORIES
from core.apps_registry import scan_all_applications, launch_application

class TabApps(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apps_all = []
        self.apps_visibles = []
        self.selected_category = "TOUTES"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top Bar : Title, Search, Rescan
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("🚀 OUTILS & APPLICATIONS DU BUREAU")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #00f0ff;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filtrer les applications (nom, description, commande)...")
        self.search_input.setFixedWidth(340)
        self.search_input.textChanged.connect(self.filtrer_apps)
        top_h.addWidget(self.search_input)

        btn_rescan = QPushButton("🔄 Réinventorier")
        btn_rescan.clicked.connect(self.recharger_apps)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Categories Filter Pills Bar
        cat_bar = QHBoxLayout()
        cat_bar.setSpacing(6)
        self.cat_buttons = {}
        for cat in APP_CATEGORIES:
            b = QPushButton(cat)
            b.setCheckable(True)
            if cat == "TOUTES":
                b.setChecked(True)
            b.clicked.connect(lambda _, c=cat: self.select_category(c))
            cat_bar.addWidget(b)
            self.cat_buttons[cat] = b
        cat_bar.addStretch()
        layout.addLayout(cat_bar)

        # Applications Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Catégorie", "Nom de l'Outil", "Description / Commande", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.lancer_selection)
        layout.addWidget(self.table)

        # Bottom Action Bar
        bot_h = QHBoxLayout()
        btn_launch = QPushButton("▶ Lancer l'outil sélectionné")
        btn_launch.setProperty("class", "green")
        btn_launch.clicked.connect(self.lancer_selection)
        bot_h.addWidget(btn_launch)

        self.lbl_status = QLabel("💡 Double-clic sur une ligne = Lancement immédiat.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        bot_h.addWidget(self.lbl_status)
        bot_h.addStretch()
        layout.addLayout(bot_h)

        self.recharger_apps()

    def select_category(self, cat):
        self.selected_category = cat
        for c, b in self.cat_buttons.items():
            b.setChecked(c == cat)
        self.filtrer_apps()

    def recharger_apps(self):
        self.apps_all = scan_all_applications()
        morts = sum(1 for a in self.apps_all if not a.get("dispo", True))
        dossiers = sum(1 for a in self.apps_all if a.get("type") == "dossier")
        self.lbl_title.setText(
            f"🚀 OUTILS & APPLICATIONS DU BUREAU — {len(self.apps_all)} entrées "
            f"· 📁 {dossiers} dossiers · ⚠ {morts} cibles introuvables")
        self.filtrer_apps()

    def peupler_table(self, apps):
        self.apps_visibles = apps
        self.table.setRowCount(len(apps))
        for row, app in enumerate(apps):
            # Catégorie
            it_cat = QTableWidgetItem(app.get("category", ""))
            it_cat.setForeground(QColor("#fbbf24"))
            self.table.setItem(row, 0, it_cat)

            # Nom — les entrees dont la cible est absente sont signalees.
            # Ajoute le 2026-09-03 : 18 lanceurs pointent dans le vide (surtout
            # vers /home/rempc, l'utilisateur d'une autre machine). Ils etaient
            # affiches comme les autres ; la panne n'apparaissait qu'au clic.
            vivante = app.get("dispo", True)
            it_name = QTableWidgetItem(app.get("name", "") if vivante
                                       else "⚠ " + app.get("name", ""))
            it_name.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
            if not vivante:
                it_name.setForeground(QColor("#ef4444"))
                it_name.setToolTip("Cible introuvable sur cette machine : "
                                   + (app.get("exec") or app.get("path", "")))
            self.table.setItem(row, 1, it_name)

            # Commande
            cmd_txt = app.get("comment") or app.get("exec") or app.get("path", "")
            it_cmd = QTableWidgetItem(cmd_txt)
            it_cmd.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 2, it_cmd)

            # Type
            typ = app.get("type", "desktop")
            it_type = QTableWidgetItem(("📁 " if typ == "dossier" else "") + typ.upper())
            it_type.setForeground(QColor("#a78bfa" if typ == "dossier" else "#38bdf8"))
            self.table.setItem(row, 3, it_type)

    def filtrer_apps(self):
        query = self.search_input.text().lower().strip()
        filtered = self.apps_all
        if self.selected_category != "TOUTES":
            filtered = [a for a in filtered if a.get("category") == self.selected_category]
        if query:
            filtered = [
                a for a in filtered
                if query in a.get("name", "").lower()
                or query in a.get("comment", "").lower()
                or query in a.get("exec", "").lower()
                or query in a.get("category", "").lower()
            ]
        self.peupler_table(filtered)

    def lancer_selection(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.apps_visibles):
            app = self.apps_visibles[row]
            ok, msg = launch_application(app)
            self.lbl_status.setText(f"▶ {msg}")
            self.lbl_status.setStyleSheet("color: #4ade80;" if ok else "color: #f87171;")
