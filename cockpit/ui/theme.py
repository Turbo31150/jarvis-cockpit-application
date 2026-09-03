#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CYBERPUNK & GLASSMORPHISM UI THEME
High-DPI stylesheet, custom components styling, and color constants.
"""

STYLESHEET = """
QMainWindow {
    background-color: #050814;
}
QWidget {
    color: #e2e8f0;
    font-family: 'Ubuntu', 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0a0f1d;
    border-radius: 12px;
    padding: 10px;
}
QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 11px 22px;
    margin-right: 6px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    border: 1px solid #1e293b;
    border-bottom: none;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
    color: #ffffff;
    border: 1px solid #38bdf8;
    border-bottom: none;
}
QTabBar::tab:hover:!selected {
    background-color: #1e293b;
    color: #f8fafc;
}
QFrame.cyber-card {
    background-color: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 14px;
}
QFrame.cyber-card:hover {
    border: 1px solid #00f0ff;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0284c7);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    padding: 10px 18px;
    border: 1px solid #38bdf8;
    font-size: 13px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
    border: 1px solid #7dd3fc;
}
QPushButton:pressed {
    background-color: #075985;
}
QPushButton.purple {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #9333ea);
    border: 1px solid #c084fc;
}
QPushButton.purple:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #7e22ce);
}
QPushButton.green {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    border: 1px solid #34d399;
}
QPushButton.green:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
}
QPushButton.amber {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
    border: 1px solid #fcd34d;
}
QPushButton.amber:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #d97706);
}
QPushButton.red {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ef4444);
    border: 1px solid #fca5a5;
}
QPushButton.red:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #dc2626);
}
QLineEdit, QTextEdit, QComboBox {
    background-color: #030712;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-family: 'Fira Code', 'Monospace', monospace;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #00f0ff;
    background-color: #050b18;
}
QComboBox QAbstractItemView {
    background-color: #030712;
    border: 1px solid #1e293b;
    selection-background-color: #0284c7;
    color: #f8fafc;
}
QTableWidget {
    background-color: #030712;
    border: 1px solid #1e293b;
    border-radius: 10px;
    gridline-color: #111c33;
    color: #e2e8f0;
    font-family: 'Fira Code', 'Monospace', monospace;
    font-size: 12px;
    selection-background-color: #0369a1;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #00f0ff;
    font-weight: 700;
    padding: 8px;
    border: 1px solid #1e293b;
}
QProgressBar {
    background-color: #030712;
    border: 1px solid #1e293b;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 10px;
    font-weight: bold;
    color: #ffffff;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #00f0ff);
    border-radius: 5px;
}
QScrollBar:vertical {
    border: none;
    background: #030712;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #1e293b;
    min-height: 20px;
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
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #00f0ff;
}
QStatusBar {
    background-color: #050814;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
    font-size: 11px;
}
"""
