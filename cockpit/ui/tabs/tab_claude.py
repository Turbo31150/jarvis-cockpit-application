#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB : CLAUDE CODE CLI & STUDIO
Integrated Claude Code launcher, preset prompt executor, MCP inspector, and session supervisor.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QProgressBar, QGridLayout, QFrame, QSplitter, QApplication, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.claude_engine import (
    get_claude_info, run_claude_prompt, launch_claude_interactive, CLAUDE_PRESETS
)

class ClaudePromptWorker(QThread):
    finished_signal = pyqtSignal(dict)
    def __init__(self, prompt, cwd=None):
        super().__init__()
        self.prompt = prompt
        self.cwd = cwd
    def run(self):
        res = run_claude_prompt(self.prompt, cwd=self.cwd)
        self.finished_signal.emit(res)

class TabClaude(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ── TOP BAR : INFO & QUICK LAUNCHERS ──
        top_h = QHBoxLayout()
        self.lbl_title = QLabel("👑 CLAUDE CODE — SUITE CLI & AGENTIC WORKSPACE")
        self.lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #c084fc;")
        top_h.addWidget(self.lbl_title)
        top_h.addStretch()

        info = get_claude_info()
        self.lbl_info = QLabel("Version : " + str(info.get('version', 'OK')) + " • MCPs : " + str(info.get('mcp_count', '40+')))
        self.lbl_info.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold;")
        top_h.addWidget(self.lbl_info)
        layout.addLayout(top_h)

        # Dedicated Launchers Row
        launch_h = QHBoxLayout()
        launch_h.setSpacing(8)

        btn_interact = QPushButton("👑 Session Interactive")
        btn_interact.setProperty("class", "purple")
        btn_interact.clicked.connect(lambda: launch_claude_interactive("default"))
        launch_h.addWidget(btn_interact)

        btn_tmux = QPushButton("🪟 Session Tmux H24")
        btn_tmux.clicked.connect(lambda: launch_claude_interactive("tmux"))
        launch_h.addWidget(btn_tmux)

        btn_resume = QPushButton("🔄 Reprendre (-r)")
        btn_resume.clicked.connect(lambda: launch_claude_interactive("resume"))
        launch_h.addWidget(btn_resume)

        btn_doc = QPushButton("🩺 Claude Doctor")
        btn_doc.setProperty("class", "green")
        btn_doc.clicked.connect(lambda: launch_claude_interactive("doctor"))
        launch_h.addWidget(btn_doc)

        btn_mcps = QPushButton("📦 MCP List")
        btn_mcps.setProperty("class", "amber")
        btn_mcps.clicked.connect(lambda: launch_claude_interactive("mcp_list"))
        launch_h.addWidget(btn_mcps)

        layout.addLayout(launch_h)

        # ── PRESET PROMPTS MATRIX (5 PRESETS) ──
        lbl_presets = QLabel("⚡ BIBLIOTHÈQUE DE PROMPTS EXPERTS (1-CLIC)")
        lbl_presets.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        lbl_presets.setStyleSheet("color: #38bdf8; margin-top: 4px;")
        layout.addWidget(lbl_presets)

        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        for idx, p in enumerate(CLAUDE_PRESETS):
            display_title = p["title"].replace("&", "&&")
            b = QPushButton(display_title)
            b.setProperty("class", "ghost")
            b.clicked.connect(lambda _, prompt_text=p["prompt"]: self.load_preset_prompt(prompt_text))
            r, col = divmod(idx, 3)
            preset_grid.addWidget(b, r, col)
        layout.addLayout(preset_grid)

        # ── DIRECT PROMPT RUNNER (claude -p "<prompt>") ──
        lbl_direct = QLabel("💬 EXÉCUTEUR DIRECT DE PROMPTS (claude -p)")
        lbl_direct.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        lbl_direct.setStyleSheet("color: #4ade80; margin-top: 6px;")
        layout.addWidget(lbl_direct)

        prompt_h = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Entrez une instruction ou choisissez un preset ci-dessus (ex: Analyse et optimise le module X)...")
        self.prompt_input.returnPressed.connect(self.run_prompt)
        prompt_h.addWidget(self.prompt_input)

        self.btn_run = QPushButton("⚡ Lancer (Monopasse)")
        self.btn_run.setProperty("class", "green")
        self.btn_run.clicked.connect(self.run_prompt)
        prompt_h.addWidget(self.btn_run)
        layout.addLayout(prompt_h)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Cyber Terminal Container
        term_frame = QFrame()
        term_frame.setStyleSheet("""
            background-color: #030712;
            border: 1px solid rgba(192, 132, 252, 0.3);
            border-radius: 10px;
        """)
        tf_layout = QVBoxLayout(term_frame)
        tf_layout.setContentsMargins(0, 0, 0, 0)
        tf_layout.setSpacing(0)

        # Terminal Title Bar
        title_bar = QFrame()
        title_bar.setStyleSheet("background: rgba(15, 23, 42, 0.8); border-bottom: 1px solid rgba(192, 132, 252, 0.2); border-top-left-radius: 9px; border-top-right-radius: 9px; padding: 4px 10px;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(6)

        dots = QLabel("🔴  🟡  🟢")
        dots.setFont(QFont("Ubuntu", 8))
        tb_layout.addWidget(dots)

        term_title = QLabel("CLAUDE CODE CONSOLE • MONOPASSE / EXECUTION")
        term_title.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Bold))
        term_title.setStyleSheet("color: #c084fc;")
        tb_layout.addWidget(term_title)
        tb_layout.addStretch()

        tf_layout.addWidget(title_bar)

        # Output Console
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setStyleSheet("background-color: transparent; border: none; color: #f8fafc; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 8px; line-height: 1.4;")
        self.output_console.setPlaceholderText("La sortie textuelle de Claude Code s'affichera ici en temps réel...")
        tf_layout.addWidget(self.output_console)

        layout.addWidget(term_frame)

        # Bottom Bar: Copy & Clear
        bot_h = QHBoxLayout()
        btn_copy = QPushButton("📋 Copier la Sortie")
        btn_copy.clicked.connect(self.copy_output)
        bot_h.addWidget(btn_copy)

        btn_clear = QPushButton("🗑 Effacer Console")
        btn_clear.clicked.connect(self.output_console.clear)
        bot_h.addWidget(btn_clear)

        self.lbl_exec_status = QLabel("Prêt.")
        self.lbl_exec_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        bot_h.addWidget(self.lbl_exec_status)
        bot_h.addStretch()
        layout.addLayout(bot_h)

    def load_preset_prompt(self, text):
        self.prompt_input.setText(text)
        self.prompt_input.setFocus()

    def run_prompt(self):
        txt = self.prompt_input.text().strip()
        if not txt:
            return
        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_exec_status.setText("⏳ Claude Code en cours d'exécution (mode monopasse)...")
        self.output_console.setText("$ claude -p \"" + txt + "\"\n\nExécution en cours...")

        self.worker = ClaudePromptWorker(txt)
        self.worker.finished_signal.connect(self.show_prompt_result)
        self.worker.start()

    def show_prompt_result(self, res):
        self.btn_run.setEnabled(True)
        self.progress.setVisible(False)
        self.output_console.setText(res.get("output", ""))
        if res.get("success"):
            self.lbl_exec_status.setText("✅ Exécution Claude Code réussie.")
            self.lbl_exec_status.setStyleSheet("color: #4ade80;")
        else:
            self.lbl_exec_status.setText("❌ Code sortie: " + str(res.get('returncode')))
            self.lbl_exec_status.setStyleSheet("color: #f87171;")

    def copy_output(self):
        t = self.output_console.toPlainText()
        if t:
            QApplication.clipboard().setText(t)
            self.lbl_exec_status.setText("📋 Sortie copiée dans le presse-papier !")
