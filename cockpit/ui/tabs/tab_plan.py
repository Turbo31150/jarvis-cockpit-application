#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 5 : PLANNING & TO-DO MASTER
Interactive Task CRUD, Priority Filtering, and Autonomous Planning synchronization.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QAbstractItemView, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.database import get_master_tasks, add_master_task, update_master_task_status, delete_master_task
from core.config import JARVIS_DIR
import subprocess

class PlanRegenWorker(QThread):
    done_signal = pyqtSignal()
    def run(self):
        try:
            subprocess.run(["python3", f"{JARVIS_DIR}/scripts/planning_mega_m4.py"], timeout=45)
        except Exception:
            pass
        self.done_signal.emit()

class TabPlan(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("📋 TO-DO LIST UNIFIÉE DU PLANNING MASTER (jarvis_master.db)")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #38bdf8;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        self.btn_regen = QPushButton("🔄 Scanner & Régénérer Tâches")
        self.btn_regen.setProperty("class", "amber")
        self.btn_regen.clicked.connect(self.run_plan_regen)
        top_h.addWidget(self.btn_regen)
        layout.addLayout(top_h)

        # Add Task Bar
        add_h = QHBoxLayout()
        self.new_task_title = QLineEdit()
        self.new_task_title.setPlaceholderText("Ajouter une nouvelle tâche au planning...")
        add_h.addWidget(self.new_task_title)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["GÉNÉRAL", "INGÉNIERIE", "CLUSTER", "PROSPECTION", "SÉCURITÉ", "URGENT"])
        add_h.addWidget(self.cat_combo)

        btn_add = QPushButton("➕ Ajouter")
        btn_add.setProperty("class", "green")
        btn_add.clicked.connect(self.add_task)
        add_h.addWidget(btn_add)
        layout.addLayout(add_h)

        # Tasks Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Catégorie", "Titre de la Tâche", "Statut"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self.toggle_task_status)
        layout.addWidget(self.table)

        # Bottom Actions Bar
        bot_h = QHBoxLayout()
        btn_done = QPushButton("✅ Basculer Statut (TODO ⇄ DONE)")
        btn_done.clicked.connect(self.toggle_task_status)
        bot_h.addWidget(btn_done)

        btn_del = QPushButton("🗑 Supprimer la Tâche")
        btn_del.setProperty("class", "red")
        btn_del.clicked.connect(self.delete_task)
        bot_h.addWidget(btn_del)

        self.lbl_info = QLabel("Double-clic sur une ligne = Changer le statut.")
        self.lbl_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        bot_h.addWidget(self.lbl_info)
        bot_h.addStretch()
        layout.addLayout(bot_h)

        self.refresh_tasks()

    def refresh_tasks(self):
        tasks = get_master_tasks(250)
        self.tasks_list = tasks
        self.table.setRowCount(len(tasks))
        for row, t in enumerate(tasks):
            self.table.setItem(row, 0, QTableWidgetItem(str(t.get("id"))))
            
            it_cat = QTableWidgetItem(str(t.get("category", "")))
            it_cat.setForeground(QColor("#fbbf24"))
            self.table.setItem(row, 1, it_cat)

            it_title = QTableWidgetItem(str(t.get("title", "")))
            it_title.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
            self.table.setItem(row, 2, it_title)

            st = t.get("status", "TODO")
            it_st = QTableWidgetItem(f"✅ {st}" if st == "DONE" else f"⏳ {st}")
            it_st.setForeground(QColor("#4ade80" if st == "DONE" else "#38bdf8"))
            self.table.setItem(row, 3, it_st)

    def add_task(self):
        title = self.new_task_title.text().strip()
        if not title:
            return
        cat = self.cat_combo.currentText()
        add_master_task(title, category=cat)
        self.new_task_title.clear()
        self.refresh_tasks()

    def toggle_task_status(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.tasks_list):
            t = self.tasks_list[row]
            new_st = "TODO" if t.get("status") == "DONE" else "DONE"
            update_master_task_status(t["id"], new_st)
            self.refresh_tasks()

    def delete_task(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.tasks_list):
            t = self.tasks_list[row]
            delete_master_task(t["id"])
            self.refresh_tasks()

    def run_plan_regen(self):
        self.btn_regen.setEnabled(False)
        self.worker = PlanRegenWorker()
        self.worker.done_signal.connect(lambda: [self.btn_regen.setEnabled(True), self.refresh_tasks()])
        self.worker.start()
