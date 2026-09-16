#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CYBERPUNK & HIGH-TECH GLASSMORPHISM UI THEME (AAA EDITION)
High-DPI stylesheet, modern typography, glowing accents, and micro-interactions.
"""

STYLESHEET = """
/* Polices : Ubuntu / JetBrains Mono sur le rig Linux ; Segoe UI, Cascadia Mono et
   Consolas servent de repli natif sous Windows (Qt retombe sur la 1re police installée). */
/* ── FENÊTRE & FOND PRINCIPAL ── */
QMainWindow {
    background-color: #030712;
}

QWidget {
    color: #e2e8f0;
    font-family: 'JetBrains Mono', 'Ubuntu', 'Inter', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* Élimination absolue des fonds blancs/gris par défaut */
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget,
QScrollArea QWidget#qt_scrollarea_viewport {
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
}

/* ── TOP BAR HUD & CAPSULES ── */
QFrame#topBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #050b18, stop:0.5 #091733, stop:1 #050a17);
    border: 1px solid rgba(0, 240, 255, 0.35);
    border-radius: 14px;
}

QFrame.hud-chip {
    background: rgba(8, 17, 36, 0.85);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 8px;
}

/* ── SIDEBAR NAVIGATION CYBER-DECK ── */
QFrame#sidebarFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #050b18, stop:1 #071226);
    border: 1px solid rgba(0, 240, 255, 0.28);
    border-radius: 14px;
}

QListWidget#sidebarNav {
    background: transparent;
    border: none;
    outline: none;
    padding: 4px 2px;
}

QListWidget#sidebarNav::item {
    color: #94a3b8;
    padding: 8px 12px;
    margin-bottom: 2px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 12px;
    border-left: 3px solid transparent;
}

QListWidget#sidebarNav::item:hover {
    background: rgba(2, 132, 199, 0.2);
    color: #38bdf8;
    border-left: 3px solid #38bdf8;
}

QListWidget#sidebarNav::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(2, 132, 199, 0.45), stop:1 rgba(6, 182, 212, 0.12));
    color: #00f0ff;
    font-weight: 800;
    border-left: 3px solid #00f0ff;
}

/* ── CONTENEUR CENTRAL DES PAGES (STACKED WIDGET) ── */
QStackedWidget#centralPages {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #050b18, stop:0.5 #071226, stop:1 #050a17);
    border: 1px solid rgba(0, 240, 255, 0.28);
    border-radius: 14px;
    padding: 12px;
}

/* ── COMPATIBILITÉ TAB WIDGET ── */
QTabWidget::pane {
    border: 1px solid rgba(0, 240, 255, 0.28);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #050b18, stop:0.5 #071226, stop:1 #050a17);
    border-radius: 14px;
    padding: 10px;
    margin-top: 2px;
}

QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0d1a33, stop:1 #081124);
    color: #94a3b8;
    padding: 10px 18px;
    margin-right: 5px;
    margin-bottom: 2px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    font-size: 12px;
    border: 1px solid rgba(30, 41, 59, 0.9);
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00f0ff, stop:0.15 #0369a1, stop:1 #091a38);
    color: #ffffff;
    font-weight: 800;
    border: 1px solid #38bdf8;
    border-bottom: 3px solid #00f0ff;
}

QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #132447, stop:1 #0a172e);
    color: #38bdf8;
    border-color: rgba(0, 240, 255, 0.5);
}

/* ── CARTES HOLOGRAPHIQUES & HERO CARDS ── */
QFrame.cyber-card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(10, 22, 44, 0.9), stop:1 rgba(5, 12, 24, 0.95));
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 14px;
    padding: 16px;
}

QFrame.cyber-card:hover {
    border: 1px solid #00f0ff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(14, 28, 56, 0.95), stop:1 rgba(8, 16, 32, 0.98));
}

/* ── BOUTONS HAUTE PRÉCISION (AAA NEON BUTTONS) ── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    padding: 9px 16px;
    border: 1px solid #38bdf8;
    font-size: 12px;
    letter-spacing: 0.3px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #00f0ff);
    border: 1px solid #7dd3fc;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #075985;
}

QPushButton:disabled {
    background-color: #0f172a;
    color: #475569;
    border: 1px solid #1e293b;
}

/* Variantes de couleurs pour boutons */
QPushButton.purple {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #9333ea);
    border: 1px solid #c084fc;
}

QPushButton.purple:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #a855f7);
    border-color: #e9d5ff;
}

QPushButton.green {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    border: 1px solid #34d399;
}

QPushButton.green:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #34d399);
    border-color: #a7f3d0;
}

QPushButton.amber {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
    border: 1px solid #fcd34d;
}

QPushButton.amber:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #fbbf24);
    border-color: #fef08a;
}

QPushButton.red {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ef4444);
    border: 1px solid #fca5a5;
}

QPushButton.red:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #f87171);
    border-color: #fecaca;
}

QPushButton.cyan {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0891b2, stop:1 #06b6d4);
    color: #ffffff;
    font-weight: 800;
    border: 1px solid #38bdf8;
}

QPushButton.cyan:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #22d3ee);
    color: #ffffff;
}

QPushButton.ghost {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(56, 189, 248, 0.35);
    color: #38bdf8;
}

QPushButton.ghost:hover {
    background: rgba(2, 132, 199, 0.3);
    border-color: #00f0ff;
    color: #ffffff;
}

/* ── CHAMPS DE TEXTE & ENTRÉES ── */
QLineEdit, QTextEdit, QComboBox {
    background-color: #040814;
    border: 1px solid rgba(0, 240, 255, 0.24);
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 12px;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #00f0ff;
    background-color: #060d20;
}

QComboBox QAbstractItemView {
    background-color: #050b18;
    border: 1px solid #0284c7;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    color: #f8fafc;
    padding: 4px;
}

/* ── TABLEAUX & LISTES ── */
QTableWidget, QTreeWidget {
    background-color: #030612;
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 10px;
    gridline-color: #0d1b38;
    color: #e2e8f0;
    font-family: 'JetBrains Mono', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 12px;
}

QTableWidget::item {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(14, 27, 56, 0.6);
}

QTableWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
    color: #ffffff;
    font-weight: bold;
}

QTableWidget::item:hover {
    background-color: rgba(2, 132, 199, 0.15);
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a152e, stop:1 #071024);
    color: #00f0ff;
    font-weight: 800;
    padding: 8px 12px;
    border: 1px solid #102144;
    border-top: none;
    letter-spacing: 0.5px;
    font-size: 11px;
}

/* ── BARRES DE PROGRESSION ── */
QProgressBar {
    background-color: #040917;
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 6px;
    height: 14px;
    text-align: center;
    font-size: 10px;
    font-weight: 800;
    color: #ffffff;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.7 #00f0ff, stop:1 #38bdf8);
    border-radius: 5px;
}

/* ── GROUPBOX CYBERNÉTIQUES ── */
QGroupBox {
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 12px;
    margin-top: 22px;
    padding-top: 18px;
    padding-bottom: 10px;
    padding-left: 10px;
    padding-right: 10px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(8, 16, 32, 0.85), stop:1 rgba(4, 9, 18, 0.95));
    font-weight: bold;
    color: #00f0ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 14px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0c1c3d, stop:1 #061126);
    border: 1px solid #00f0ff;
    border-radius: 6px;
    color: #00f0ff;
    font-size: 11px;
    letter-spacing: 0.6px;
}

/* ── CHECKBOX & SPINBOX ── */
QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #38bdf8;
    border-radius: 5px;
    background: #030612;
}

QCheckBox::indicator:hover {
    border-color: #00f0ff;
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #00f0ff);
    border: 1px solid #00f0ff;
}

QSpinBox {
    background-color: #030714;
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 6px;
    padding: 6px 10px;
    color: #ffffff;
    font-family: 'JetBrains Mono', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 12px;
}

QSpinBox:focus {
    border: 1px solid #00f0ff;
    background-color: #060d20;
}

/* ── SCROLLBARS ULTRA-FINES ── */
QScrollBar:vertical {
    border: none;
    background: #030712;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #1e293b;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #00f0ff;
}

QScrollBar:horizontal {
    border: none;
    background: #030712;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #1e293b;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #00f0ff;
}

/* ── BARRE DE STATUT BASSE (BOTTOM HUD) ── */
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #030714, stop:0.5 #061024, stop:1 #030714);
    color: #94a3b8;
    border-top: 1px solid rgba(0, 240, 255, 0.22);
    font-size: 11px;
    padding: 4px 10px;
}
"""
