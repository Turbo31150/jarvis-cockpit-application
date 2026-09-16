#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 1 : HUD & COCKPIT EXÉCUTIF (AAA DESIGN)
Executive dashboard with hero launchers, quick action matrix, and instant triggers.

Portage Windows : chaque lanceur passe par core.platform_compat (open_terminal /
safe_popen / open_chrome_app) qui ne lève jamais — PyQt6 appelle qFatal() sur
toute exception non gérée dans un slot. Les actions sans équivalent Windows
(tmux/ttx, alias bash « moisson », scripts Lumen, jarvis-reveil…) sont grisées
avec une infobulle « indisponible sous Windows ». Le chemin Linux (rig) garde
exactement les mêmes commandes gnome-terminal/bash qu'avant.
"""

import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor
from core.config import JARVIS_DIR
from core.platform_compat import (
    IS_WINDOWS, open_terminal, safe_popen, open_chrome_app, python_executable,
    jarvis_path, find_app, which, feature_available, unavailable_message, ui_font_family,
)

# Police de titre : 'Ubuntu' sur le rig, 'Segoe UI' sous Windows (repli Qt sinon)
_UI_FONT = ui_font_family()


class AsyncCommandWorker(QThread):
    finished_signal = pyqtSignal(str)
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
    def run(self):
        try:
            r = subprocess.run(self.cmd, capture_output=True, text=True, timeout=60)
            self.finished_signal.emit(r.stdout or r.stderr or "Terminé.")
        except Exception as e:
            self.finished_signal.emit(f"Erreur: {e}")


class CdpStartWorker(QThread):
    """Windows : remplace le script bash `browseros-cdp-authentifie demarrer`
    par core.cdp_engine.start_cdp() hors du thread GUI."""
    finished_signal = pyqtSignal(dict)
    def run(self):
        try:
            from core.cdp_engine import start_cdp
            res = start_cdp()
            if not isinstance(res, dict):
                res = {"success": bool(res), "output": str(res)}
        except Exception as e:
            res = {"success": False, "error": str(e)}
        self.finished_signal.emit(res)


class TabHud(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self.init_ui()

    # ── Lancement sûr (ne lève jamais) ───────────────────────────────
    def _popen(self, argv):
        """Chemin Linux d'origine (Popen brut, start_new_session) protégé par un
        try/except : une FileNotFoundError dans un slot tuerait le cockpit."""
        try:
            subprocess.Popen(argv, start_new_session=True)
            self._status("🚀 Lancé : " + str(argv[-1]), ok=True)
        except Exception as e:
            self._status(f"❌ Lancement impossible ({e})", ok=False)

    def _status(self, text, ok=True):
        lbl = getattr(self, "lbl_hud_status", None)
        if lbl is not None:
            lbl.setText(text)
            lbl.setStyleSheet(f"color: {'#4ade80' if ok else '#f87171'}; font-size: 11px;")

    def _disable(self, btn, feature, detail=""):
        """Grise un bouton sans équivalent Windows + infobulle homogène."""
        btn.setEnabled(False)
        btn.setToolTip(unavailable_message(feature, detail))

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        # ── HERO CARDS (3 COLONNES HOLOGRAPHIQUES) ──
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(14)

        # CARD 1: TTX WORKSPACE
        card1 = QFrame()
        card1.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #091733, stop:1 #040b17);
            border: 1px solid rgba(0, 240, 255, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c1 = QVBoxLayout(card1)
        c1.setSpacing(8)

        h1 = QHBoxLayout()
        l1_title = QLabel("🚀 WORKSPACE MULTIPLEXER")
        l1_title.setFont(QFont(_UI_FONT, 13, QFont.Weight.Bold))
        l1_title.setStyleSheet("color: #00f0ff; letter-spacing: 0.5px;")
        h1.addWidget(l1_title)
        h1.addStretch()
        b1 = QLabel("14 FENÊTRES")
        b1.setStyleSheet("color: #00f0ff; background: rgba(0, 240, 255, 0.15); border: 1px solid #00f0ff; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h1.addWidget(b1)
        c1.addLayout(h1)

        l1_desc = QLabel("Centre de commandement 14 fenêtres TMUX unifiées :\n• Claude Code Orfèvre + 48 MCPs connectés\n• Table Ronde 7 Experts en direct\n• Planning To-Do List unifié & Supervision")
        l1_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c1.addWidget(l1_desc)

        btn_ttx = QPushButton("🚀 Lancer Multiplexeur TTX")
        btn_ttx.setProperty("class", "cyan")
        if IS_WINDOWS or not feature_available("tmux"):
            # ttx = multiplexeur tmux 14 fenêtres du rig : aucun équivalent Windows
            self._disable(btn_ttx, "Multiplexeur TTX (tmux)", "sessions tmux du rig Linux uniquement")
        else:
            btn_ttx.clicked.connect(lambda: self._popen(["gnome-terminal", "--", "bash", "-ic", "ttx"]))
        c1.addWidget(btn_ttx)
        hero_layout.addWidget(card1)

        # CARD 2: CLAUDE CODE
        card2 = QFrame()
        card2.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a0f33, stop:1 #080514);
            border: 1px solid rgba(192, 132, 252, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c2 = QVBoxLayout(card2)
        c2.setSpacing(8)

        h2 = QHBoxLayout()
        l2_title = QLabel("👑 CLAUDE CODE ORFÈVRE")
        l2_title.setFont(QFont(_UI_FONT, 13, QFont.Weight.Bold))
        l2_title.setStyleSheet("color: #c084fc; letter-spacing: 0.5px;")
        h2.addWidget(l2_title)
        h2.addStretch()
        b2 = QLabel("0-TOKEN M6")
        b2.setStyleSheet("color: #c084fc; background: rgba(192, 132, 252, 0.15); border: 1px solid #c084fc; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h2.addWidget(b2)
        c2.addLayout(h2)

        l2_desc = QLabel("Agent d'ingénierie suprême en autonomie 100% :\n• Inférence prioritaire M6 RJ45 (1.4 ms)\n• Accès complet SSD M1 (1 To) & Git unifié\n• Mode non-stop ininterruptible")
        l2_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c2.addWidget(l2_desc)

        btn_claude = QPushButton("👑 Ouvrir Claude Code")
        btn_claude.setProperty("class", "purple")
        if IS_WINDOWS:
            claude_exe = find_app("claude")
            if claude_exe:
                btn_claude.clicked.connect(
                    lambda _, exe=claude_exe: self._open_terminal([exe], "Claude Code", cwd=JARVIS_DIR))
            else:
                self._disable(btn_claude, "Claude Code CLI", "claude.exe introuvable (npm i -g @anthropic-ai/claude-code)")
        else:
            btn_claude.clicked.connect(lambda: self._popen(["gnome-terminal", "--", "bash", "-ic", "claude"]))
        c2.addWidget(btn_claude)
        hero_layout.addWidget(card2)

        # CARD 3: TERMINAL TURBO
        card3 = QFrame()
        card3.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #091a18, stop:1 #030d0b);
            border: 1px solid rgba(74, 222, 128, 0.45);
            border-radius: 14px;
            padding: 14px;
        """)
        c3 = QVBoxLayout(card3)
        c3.setSpacing(8)

        h3 = QHBoxLayout()
        l3_title = QLabel("💻 TERMINAL & SWARM")
        l3_title.setFont(QFont(_UI_FONT, 13, QFont.Weight.Bold))
        l3_title.setStyleSheet("color: #4ade80; letter-spacing: 0.5px;")
        h3.addWidget(l3_title)
        h3.addStretch()
        b3 = QLabel("NOEUD M4")
        b3.setStyleSheet("color: #4ade80; background: rgba(74, 222, 128, 0.15); border: 1px solid #4ade80; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        h3.addWidget(b3)
        c3.addLayout(h3)

        l3_desc = QLabel("Accès direct au terminal & conteneurs :\n• Session native Turbo M4\n• Base PostgreSQL 15 & Redis 7\n• Workflows n8n (:5678) & Portainer (:9000)")
        l3_desc.setStyleSheet("color: #94a3b8; font-size: 11.5px; line-height: 1.4;")
        c3.addWidget(l3_desc)

        btn_turbo = QPushButton("💻 Terminal Turbo M4")
        btn_turbo.setProperty("class", "green")
        if IS_WINDOWS:
            # Sous Windows : simple terminal local (wt.exe / cmd) ouvert dans JARVIS_DIR
            btn_turbo.setText("💻 Terminal JARVIS (local)")
            btn_turbo.setToolTip("Ouvre Windows Terminal (ou cmd.exe) dans " + JARVIS_DIR)
            btn_turbo.clicked.connect(lambda: self._open_terminal(None, "Terminal JARVIS", cwd=JARVIS_DIR))
        else:
            btn_turbo.clicked.connect(lambda: self._popen(["gnome-terminal", "--title=Terminal Turbo M4", "--", "/home/turbo/bin/ttx"]))
        c3.addWidget(btn_turbo)
        hero_layout.addWidget(card3)

        layout.addLayout(hero_layout)

        # ── MATRICE D'ACTIONS RAPIDES ET DÉCLENCHEURS (3 LIGNES x 4 BOUTONS) ──
        lbl_matrix = QLabel("⚡ MATRICE D'ACTIONS RAPIDES & MOTEURS OPÉRATIONNELS")
        lbl_matrix.setFont(QFont(_UI_FONT, 12, QFont.Weight.Bold))
        lbl_matrix.setStyleSheet("color: #00f0ff; margin-top: 6px; letter-spacing: 0.5px;")
        layout.addWidget(lbl_matrix)

        grid = QGridLayout()
        grid.setSpacing(10)

        # (titre, classe CSS, commande shell Linux — inchangée —, clé de résolution Windows)
        actions = [
            ("🛰 Antigravity IDE (agy)", "purple", "agy", "agy"),
            ("🌪 Mistral Vibe Coding", "amber", "vibe", "vibe"),
            ("🌐 Chrome CDP Authentifié 9222", "cyan", f"{JARVIS_DIR}/bin/browseros-cdp-authentifie demarrer", "cdp"),
            ("🌾 Moisson Claude Code", "green", "moisson", "moisson"),
            ("⏰ Minuteur Réveil JARVIS", "ghost", f"{JARVIS_DIR}/bin/jarvis-reveil", "reveil"),
            ("🎤 Whisper Voice Pilote", "green", f"python3 {JARVIS_DIR}/scripts/voice_pilot.py", "voice_pilot"),
            ("🔄 Rescan Planning Master", "amber", f"python3 {JARVIS_DIR}/board/dispatch_table_ronde.py", "dispatch"),
            ("💾 Sauvegarde Système Disque", "green", f"python3 {JARVIS_DIR}/scripts/save_full_config.py", "save_config"),
            ("🎙️ Dictée Whisper (5s)", "green", f"{JARVIS_DIR}/scripts/lumen/lumen-cli.sh record 5", "lumen"),
            ("🌊 WhisperFlow Overlay (Alt+X)", "purple", "google-chrome --app=file:///home/turbo/jarvis/whisperflow/widget.html --window-size=450,600", "whisperflow"),
            ("💡 Toggle Micro Lumen", "cyan", f"{JARVIS_DIR}/scripts/lumen/lumen-toggle-mic.sh", "lumen"),
            ("📋 Résumé Presse-Papiers Lumen", "cyan", f"{JARVIS_DIR}/scripts/lumen/lumen-cli.sh summarize", "lumen"),
        ]

        for idx, (title, color_cls, cmd, win_key) in enumerate(actions):
            btn = QPushButton(title)
            if color_cls:
                btn.setProperty("class", color_cls)
            if IS_WINDOWS:
                callback, reason = self._windows_action(win_key, title)
                if callback is None:
                    self._disable(btn, title.split(" ", 1)[-1], reason)
                else:
                    btn.clicked.connect(lambda _, cb=callback, t=title: self._run_windows_action(cb, t))
            else:
                btn.clicked.connect(lambda _, c=cmd, t=title: self.execute_action(c, t))
            r, col = divmod(idx, 4)
            grid.addWidget(btn, r, col)

        layout.addLayout(grid)

        # Retour visuel du dernier lancement (utile surtout sous Windows où il n'y a
        # ni console ni gnome-terminal pour voir l'erreur)
        self.lbl_hud_status = QLabel("Prêt.")
        self.lbl_hud_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.lbl_hud_status)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # ── Chemin Linux (rig) : inchangé, seulement protégé ─────────────
    def execute_action(self, cmd, title):
        try:
            if "google-chrome" in cmd or "toggle-mic" in cmd or "summarize" in cmd:
                subprocess.Popen(f"{cmd} &", shell=True, start_new_session=True)
            else:
                subprocess.Popen(["gnome-terminal", f"--title={title}", "--", "bash", "-lc", f"{cmd}; read -p 'Appuyez sur Entrée pour fermer...'"], start_new_session=True)
            self._status(f"🚀 {title} lancé.", ok=True)
        except Exception as e:
            self._status(f"❌ {title} : {e}", ok=False)

    # ── Chemin Windows ───────────────────────────────────────────────
    def _open_terminal(self, argv, title, cwd=None):
        """open_terminal() ne lève jamais ; None = aucun émulateur (wt.exe/cmd)."""
        proc = open_terminal(argv, title=title, cwd=cwd, keep_open=True)
        if proc is None:
            self._status(f"❌ {title} : impossible d'ouvrir un terminal (wt.exe / cmd.exe).", ok=False)
        else:
            self._status(f"🚀 {title} ouvert dans un terminal.", ok=True)
        return proc

    def _windows_action(self, key, title):
        """Résout une action de la matrice pour Windows.
        Retourne (callable, '') si disponible, sinon (None, raison)."""
        if key == "agy":
            exe = find_app("agy")
            if exe:
                return (lambda: self._open_terminal([exe], title, cwd=JARVIS_DIR), "")
            return (None, "commande « agy » (Google Antigravity) introuvable")
        if key == "vibe":
            exe = which("vibe")
            if exe:
                return (lambda: self._open_terminal([exe], title, cwd=JARVIS_DIR), "")
            return (None, "commande « vibe » (Mistral Vibe) introuvable")
        if key == "cdp":
            if find_app("chrome"):
                return (self._start_cdp_windows, "")
            return (None, "aucun navigateur Chrome/Edge trouvé pour le port 9222")
        if key == "moisson":
            return (None, "alias bash « moisson » du rig Linux (voir onglet Moisson)")
        if key == "reveil":
            return (None, "script shell bin/jarvis-reveil du rig Linux")
        if key in ("voice_pilot", "dispatch", "save_config"):
            rel = {"voice_pilot": ("scripts", "voice_pilot.py"),
                   "dispatch": ("board", "dispatch_table_ronde.py"),
                   "save_config": ("scripts", "save_full_config.py")}[key]
            script = jarvis_path(*rel, must_exist=True)
            if script:
                return (lambda: self._open_terminal([python_executable(), script], title, cwd=JARVIS_DIR), "")
            return (None, f"script {'/'.join(rel)} absent de {JARVIS_DIR}")
        if key == "lumen":
            return (None, "moteur Lumen (scripts bash + arecord/xdotool)")
        if key == "whisperflow":
            widget = jarvis_path("whisperflow", "widget.html", must_exist=True)
            if widget and find_app("chrome"):
                return (lambda: self._open_chrome(widget, title), "")
            if not widget:
                return (None, "fichier whisperflow/widget.html absent")
            return (None, "aucun navigateur Chrome/Edge trouvé")
        return (None, "sans équivalent Windows")

    def _run_windows_action(self, callback, title):
        try:
            callback()
        except Exception as e:  # ceinture et bretelles : jamais d'exception dans un slot
            self._status(f"❌ {title} : {e}", ok=False)

    def _open_chrome(self, target, title):
        proc = open_chrome_app(target, 450, 600)
        if proc is None:
            self._status(f"❌ {title} : lancement du navigateur impossible.", ok=False)
        else:
            self._status(f"🌊 {title} ouvert.", ok=True)

    def _start_cdp_windows(self):
        self._status("⏳ Démarrage du navigateur CDP :9222…", ok=True)
        w = CdpStartWorker()
        w.finished_signal.connect(self._on_cdp_started)
        self._workers.append(w)
        w.start()

    def _on_cdp_started(self, res):
        msg = res.get("output") or res.get("message") or res.get("error") or ""
        if res.get("success"):
            self._status(f"✅ CDP :9222 démarré. {msg}".strip(), ok=True)
        else:
            self._status(f"❌ CDP :9222 : {msg or 'échec'}", ok=False)
        self._workers = [x for x in self._workers if x.isRunning()]
