#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 7 : STUDIO DE CRÉATION IA
High-speed generator for LinkedIn posts, Technical Articles, PRDs, Code Modules, and Outreach.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.content_engine import generate_content, CONTENT_TEMPLATES

class ContentWorker(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, content_type, topic):
        super().__init__()
        self.content_type = content_type
        self.topic = topic
    def run(self):
        res = generate_content(self.content_type, self.topic)
        self.finished_signal.emit(res)

class TabStudio(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("✍️ STUDIO DE CRÉATION & GÉNÉRATEUR IA UNIFIÉ")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #f472b6;")
        top_h.addWidget(lbl)
        top_h.addStretch()
        layout.addLayout(top_h)

        # Controls Row
        ctrl_h = QHBoxLayout()
        self.type_combo = QComboBox()
        for k, v in CONTENT_TEMPLATES.items():
            self.type_combo.addItem(v["title"], k)
        ctrl_h.addWidget(self.type_combo)

        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Sujet, technologie, concept ou problématique...")
        self.topic_input.returnPressed.connect(self.generate)
        ctrl_h.addWidget(self.topic_input)

        self.btn_gen = QPushButton("⚡ Générer")
        self.btn_gen.setProperty("class", "purple")
        self.btn_gen.clicked.connect(self.generate)
        ctrl_h.addWidget(self.btn_gen)
        layout.addLayout(ctrl_h)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Output text
        self.output_text = QTextEdit()
        self.output_text.setStyleSheet("background-color: #030712; color: #f8fafc; font-family: 'Fira Code', monospace;")
        self.output_text.setPlaceholderText("Le contenu généré apparaîtra ici avec sauvegarde automatique dans /storage/content/...")
        layout.addWidget(self.output_text)

        # Bottom Bar: Copy & File info
        bot_h = QHBoxLayout()
        btn_copy = QPushButton("📋 Copier dans le Presse-Papier")
        btn_copy.setProperty("class", "green")
        btn_copy.clicked.connect(self.copy_clipboard)
        bot_h.addWidget(btn_copy)

        self.lbl_saved = QLabel("")
        self.lbl_saved.setStyleSheet("color: #4ade80; font-size: 11px;")
        bot_h.addWidget(self.lbl_saved)
        bot_h.addStretch()
        layout.addLayout(bot_h)

    def generate(self):
        topic = self.topic_input.text().strip()
        if not topic:
            return
        c_type = self.type_combo.currentData()
        self.btn_gen.setEnabled(False)
        self.progress.setVisible(True)
        self.output_text.setText("⏳ Génération en cours via la cascade LLM (0-token M6/M4)...")
        
        self.worker = ContentWorker(c_type, topic)
        self.worker.finished_signal.connect(self.show_result)
        self.worker.start()

    def show_result(self, res):
        self.btn_gen.setEnabled(True)
        self.progress.setVisible(False)
        self.output_text.setText(res.get("content", ""))
        saved = res.get("saved_file")
        if saved:
            self.lbl_saved.setText(f"💾 Sauvegardé : {saved}")
        else:
            self.lbl_saved.setText("Génération terminée.")

    def copy_clipboard(self):
        txt = self.output_text.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            self.lbl_saved.setText("📋 Copié dans le presse-papier !")
