#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 16 : PARAMÈTRES & MOTEURS IA (WHISPER, FLO & LUMEN)
Centre de configuration unifié, persistance JSON/SQLite et lanceurs opérationnels.
"""

import os
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QSpinBox, QGroupBox, QSplitter, QTextEdit, QFrame,
    QMessageBox, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.settings_engine import get_cockpit_settings, save_cockpit_settings, DEFAULT_SETTINGS
from core.voice_flow_engine import (
    get_whisper_status, record_and_transcribe,
    get_flo_status, launch_whisperflow_ui, run_n8n_workflow_file,
    get_lumen_status, toggle_lumen_mic, lumen_summarize_clipboard, lumen_inject_cursor
)


class VoiceFlowWorker(QThread):
    """Thread d'exécution non-bloquant pour les tâches audio et workflows."""
    finished_signal = pyqtSignal(dict)

    def __init__(self, task_name, params=None):
        super().__init__()
        self.task_name = task_name
        self.params = params or {}

    def run(self):
        res = {"success": False, "task": self.task_name}
        try:
            if self.task_name == "whisper_record":
                duration = self.params.get("duration", 5)
                model = self.params.get("model", "distil-large-v3")
                lang = self.params.get("lang", "fr")
                res = record_and_transcribe(duration=duration, model_size=model, lang=lang)
                res["task"] = self.task_name
            elif self.task_name == "flo_launch":
                res = launch_whisperflow_ui()
                res["task"] = self.task_name
            elif self.task_name == "flo_run_workflow":
                wf = self.params.get("workflow", "jarvis_system_health.json")
                res = run_n8n_workflow_file(wf)
                res["task"] = self.task_name
            elif self.task_name == "lumen_mic":
                res = toggle_lumen_mic()
                res["task"] = self.task_name
            elif self.task_name == "lumen_summarize":
                res = lumen_summarize_clipboard()
                res["task"] = self.task_name
            elif self.task_name == "lumen_inject":
                res = lumen_inject_cursor()
                res["task"] = self.task_name
            else:
                res = {"success": False, "error": f"Action inconnue: {self.task_name}"}
        except Exception as e:
            res = {"success": False, "error": str(e), "task": self.task_name}

        self.finished_signal.emit(res)


class TabSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.init_ui()
        self.charger_parametres()
        self.actualiser_statuts_moteurs()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ── TOP BAR / EN-TÊTE ──
        top_h = QHBoxLayout()
        lbl_title = QLabel("⚙️ CENTRE DE CONTRÔLE & PARAMÈTRES — MOTEURS WHISPER · FLO · LUMEN")
        lbl_title.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #00f0ff;")
        top_h.addWidget(lbl_title)
        top_h.addStretch()

        self.lbl_sync_status = QLabel("● Synchronisé")
        self.lbl_sync_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        top_h.addWidget(self.lbl_sync_status)

        btn_save = QPushButton("💾 Enregistrer")
        btn_save.setProperty("class", "green")
        btn_save.clicked.connect(self.sauvegarder_parametres)
        top_h.addWidget(btn_save)

        btn_reload = QPushButton("🔄 Recharger")
        btn_reload.clicked.connect(self.charger_parametres)
        top_h.addWidget(btn_reload)

        btn_default = QPushButton("⚡ Défaut")
        btn_default.clicked.connect(self.restaurer_defaut)
        top_h.addWidget(btn_default)

        main_layout.addLayout(top_h)

        # ── SÉLECTEUR DE MODE D'INTERFACE ── (Simple / Médium / Dev)
        mode_frame = QFrame()
        mode_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(5, 12, 28, 0.95), stop:1 rgba(8, 20, 45, 0.92));
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        mode_row = QHBoxLayout(mode_frame)
        mode_row.setContentsMargins(12, 8, 12, 8)
        mode_row.setSpacing(10)

        ico_mode = QLabel("🖥️")
        ico_mode.setFont(QFont("Ubuntu", 14))
        ico_mode.setStyleSheet("background: transparent; border: none;")
        mode_row.addWidget(ico_mode)

        lbl_mode_title = QLabel("MODE D'INTERFACE :")
        lbl_mode_title.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        lbl_mode_title.setStyleSheet("color: #00f0ff; background: transparent; border: none; letter-spacing: 0.8px;")
        mode_row.addWidget(lbl_mode_title)

        mode_row.addStretch()

        self.current_mode = "dev"  # mode par défaut

        # Mode SIMPLE
        self.btn_mode_simple = QPushButton("📱  SIMPLE")
        self.btn_mode_simple.setCheckable(True)
        self.btn_mode_simple.setFixedHeight(36)
        self.btn_mode_simple.setMinimumWidth(120)
        self.btn_mode_simple.setStyleSheet("""
            QPushButton {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(74, 222, 128, 0.4);
                color: #4ade80;
                font-size: 11px;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 14px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: rgba(5, 150, 105, 0.3);
                border-color: #34d399;
                color: #ffffff;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
                border: 1px solid #34d399;
                color: #ffffff;
                font-weight: 900;
            }
        """)
        self.btn_mode_simple.clicked.connect(lambda: self.appliquer_mode_interface("simple"))
        mode_row.addWidget(self.btn_mode_simple)

        # Séparateur visuel
        sep1 = QLabel("·")
        sep1.setStyleSheet("color: #334155; font-size: 18px; background: transparent; border: none;")
        mode_row.addWidget(sep1)

        # Mode MÉDIUM
        self.btn_mode_medium = QPushButton("💼  MÉDIUM")
        self.btn_mode_medium.setCheckable(True)
        self.btn_mode_medium.setFixedHeight(36)
        self.btn_mode_medium.setMinimumWidth(120)
        self.btn_mode_medium.setStyleSheet("""
            QPushButton {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(251, 191, 36, 0.4);
                color: #fbbf24;
                font-size: 11px;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 14px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: rgba(217, 119, 6, 0.3);
                border-color: #f59e0b;
                color: #ffffff;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d97706, stop:1 #f59e0b);
                border: 1px solid #fcd34d;
                color: #ffffff;
                font-weight: 900;
            }
        """)
        self.btn_mode_medium.clicked.connect(lambda: self.appliquer_mode_interface("medium"))
        mode_row.addWidget(self.btn_mode_medium)

        # Séparateur visuel
        sep2 = QLabel("·")
        sep2.setStyleSheet("color: #334155; font-size: 18px; background: transparent; border: none;")
        mode_row.addWidget(sep2)

        # Mode DEV (plein cockpit)
        self.btn_mode_dev = QPushButton("⚡  DEV / COCKPIT")
        self.btn_mode_dev.setCheckable(True)
        self.btn_mode_dev.setChecked(True)
        self.btn_mode_dev.setFixedHeight(36)
        self.btn_mode_dev.setMinimumWidth(150)
        self.btn_mode_dev.setStyleSheet("""
            QPushButton {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(0, 240, 255, 0.4);
                color: #00f0ff;
                font-size: 11px;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 14px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: rgba(2, 132, 199, 0.3);
                border-color: #38bdf8;
                color: #ffffff;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0284c7, stop:1 #00f0ff);
                border: 1px solid #38bdf8;
                color: #040817;
                font-weight: 900;
            }
        """)
        self.btn_mode_dev.clicked.connect(lambda: self.appliquer_mode_interface("dev"))
        mode_row.addWidget(self.btn_mode_dev)

        mode_row.addStretch()

        # Badge descriptif du mode actif
        self.lbl_mode_desc = QLabel("⚡ Cockpit complet • 16 modules • Toutes fonctionnalités développeur actives")
        self.lbl_mode_desc.setStyleSheet("""
            color: #64748b;
            font-size: 10px;
            font-style: italic;
            background: transparent;
            border: none;
        """)
        self.lbl_mode_desc.setAlignment(Qt.AlignmentFlag.AlignRight)
        mode_row.addWidget(self.lbl_mode_desc)

        main_layout.addWidget(mode_frame)

        # ── SPLITTER HORIZONTAL ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─────────────────────────────────────────────────────────────
        # COLONNE GAUCHE : PARAMÈTRES GÉNÉRAUX & SYSTÈME (SCROLLABLE)
        # ─────────────────────────────────────────────────────────────
        scroll_left = QScrollArea()
        scroll_left.setWidgetResizable(True)
        scroll_left.setFrameShape(QFrame.Shape.NoFrame)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 8, 4)
        left_layout.setSpacing(12)

        # 1. GROUPE INTERFACE & THÈME
        grp_ui = QGroupBox("🎨 Interface, Thème & Ergonomie")
        gl_ui = QGridLayout(grp_ui)

        gl_ui.addWidget(QLabel("Thème Visuel :"), 0, 0)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Cyan Néon (Cockpit Standard)", "Émeraude Cluster M4", "Synthwave Violet", "Ambre Cyberpunk"])
        gl_ui.addWidget(self.combo_theme, 0, 1)

        gl_ui.addWidget(QLabel("Échelle de l'Interface :"), 1, 0)
        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["Compact (90%)", "Normal (100%)", "Grand (115%)"])
        gl_ui.addWidget(self.combo_scale, 1, 1)

        self.chk_grid = QCheckBox("Grille Cybernétique & Bordures Néon")
        self.chk_grid.setChecked(True)
        gl_ui.addWidget(self.chk_grid, 2, 0, 1, 2)

        self.chk_sound = QCheckBox("Effets Sonores & Confirmations Vocales")
        self.chk_sound.setChecked(True)
        gl_ui.addWidget(self.chk_sound, 3, 0, 1, 2)

        left_layout.addWidget(grp_ui)

        # 2. GROUPE TÉLÉMÉTRIE & PERFORMANCES
        grp_perf = QGroupBox("⚡ Télémétrie, Matériel & Alertes")
        gl_perf = QGridLayout(grp_perf)

        gl_perf.addWidget(QLabel("Fréquence Télémétrie :"), 0, 0)
        self.combo_telemetry = QComboBox()
        self.combo_telemetry.addItems(["1.5 s (Temps Réel Rapide)", "2.5 s (Standard Équilibré)", "5.0 s (Basse Consommation)"])
        gl_perf.addWidget(self.combo_telemetry, 0, 1)

        gl_perf.addWidget(QLabel("Alerte Température VRAM GPU (°C) :"), 1, 0)
        self.spin_temp = QSpinBox()
        self.spin_temp.setRange(60, 100)
        self.spin_temp.setValue(85)
        gl_perf.addWidget(self.spin_temp, 1, 1)

        gl_perf.addWidget(QLabel("Modèle d'Inférence Local :"), 2, 0)
        self.combo_ai = QComboBox()
        self.combo_ai.addItems(["gemma3:4b (Polyvalent)", "gemma4 (Ultra Rapide)", "gemma3.5 (Polyvalent)", "qwen3:8b (Analyse)", "qwen2.5:7b (Inférence)", "qwen2.5:1.5b (Rapide)", "mistral:7b (Expert M4)", "deepseek-r1:14b (Raisonnement)"])
        gl_perf.addWidget(self.combo_ai, 2, 1)

        left_layout.addWidget(grp_perf)

        # 3. GROUPE IDENTITÉ & PERSISTANCE
        grp_db = QGroupBox("🗄 Persistance & Stockage")
        gl_db = QGridLayout(grp_db)

        lbl_paths = QLabel(
            "• Fichier JSON : ~/jarvis/data/cockpit_settings.json\n"
            "• Table SQLite : ~/jarvis/jarvis_master.db (cockpit_settings)\n"
            "• Architecture : 100% Découplée & Synchronisée Web / Desktop"
        )
        lbl_paths.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        gl_db.addWidget(lbl_paths, 0, 0)

        left_layout.addWidget(grp_db)
        left_layout.addStretch()

        scroll_left.setWidget(left_widget)
        splitter.addWidget(scroll_left)

        # ─────────────────────────────────────────────────────────────
        # COLONNE DROITE : LANCEURS & MOTEURS (WHISPER, FLO & LUMEN)
        # ─────────────────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 4, 4, 4)
        right_layout.setSpacing(12)

        # 1. SECTION WHISPER
        grp_whisper = QGroupBox("🎙️ Moteur Whisper — Transcription Vocale Locale")
        gl_w = QGridLayout(grp_whisper)

        self.lbl_whisper_stat = QLabel("Statut : Calcul en cours...")
        self.lbl_whisper_stat.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        gl_w.addWidget(self.lbl_whisper_stat, 0, 0, 1, 2)

        gl_w.addWidget(QLabel("Modèle Whisper :"), 1, 0)
        self.combo_w_model = QComboBox()
        self.combo_w_model.addItems(["distil-large-v3 (Recommandé CUDA)", "large-v3-turbo", "medium", "small", "base", "tiny"])
        gl_w.addWidget(self.combo_w_model, 1, 1)

        gl_w.addWidget(QLabel("Accélération :"), 2, 0)
        self.combo_w_device = QComboBox()
        self.combo_w_device.addItems(["CUDA GPU (float16)", "CPU (int8)"])
        gl_w.addWidget(self.combo_w_device, 2, 1)

        # Lanceurs Whisper
        w_actions = QHBoxLayout()
        btn_rec = QPushButton("⏺ Enregistrer 5s & Transcrire")
        btn_rec.setProperty("class", "green")
        btn_rec.clicked.connect(self.lancer_enregistrement_whisper)
        w_actions.addWidget(btn_rec)

        btn_w_test = QPushButton("⟳ Test Rapide Micro")
        btn_w_test.clicked.connect(lambda: self.lancer_enregistrement_whisper(duration=3))
        w_actions.addWidget(btn_w_test)
        gl_w.addLayout(w_actions, 3, 0, 1, 2)

        right_layout.addWidget(grp_whisper)

        # 2. SECTION FLO (WHISPERFLOW & WORKFLOWS)
        grp_flo = QGroupBox("🌊 Moteur Flo — WhisperFlow & Orchestration Workflows")
        gl_f = QGridLayout(grp_flo)

        self.lbl_flo_stat = QLabel("Statut : Calcul en cours...")
        self.lbl_flo_stat.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        gl_f.addWidget(self.lbl_flo_stat, 0, 0, 1, 2)

        gl_f.addWidget(QLabel("Workflow Actif :"), 1, 0)
        self.combo_flo_wf = QComboBox()
        self.combo_flo_wf.addItems([
            "jarvis_system_health.json",
            "jarvis_cluster_monitor.json",
            "jarvis_daily_report.json",
            "jarvis_git_auto_backup.json",
            "jarvis_brain_learning.json",
            "jarvis_trading_pipeline.json"
        ])
        gl_f.addWidget(self.combo_flo_wf, 1, 1)

        # Lanceurs Flo
        flo_actions = QHBoxLayout()
        btn_flo_ui = QPushButton("🚀 Ouvrir WhisperFlow UI")
        btn_flo_ui.setProperty("class", "purple")
        btn_flo_ui.clicked.connect(self.lancer_flo_ui)
        flo_actions.addWidget(btn_flo_ui)

        btn_run_wf = QPushButton("⚡ Exécuter Workflow")
        btn_run_wf.setProperty("class", "green")
        btn_run_wf.clicked.connect(self.lancer_workflow_flo)
        flo_actions.addWidget(btn_run_wf)
        gl_f.addLayout(flo_actions, 2, 0, 1, 2)

        right_layout.addWidget(grp_flo)

        # 3. SECTION LUMEN
        grp_lumen = QGroupBox("💡 Moteur Lumen — Assistant Visuel & Synthèse Contextuelle")
        gl_l = QGridLayout(grp_lumen)

        self.lbl_lumen_stat = QLabel("Statut : Calcul en cours...")
        self.lbl_lumen_stat.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        gl_l.addWidget(self.lbl_lumen_stat, 0, 0, 1, 2)

        gl_l.addWidget(QLabel("Mode Tâche Actif :"), 1, 0)
        self.combo_l_mode = QComboBox()
        self.combo_l_mode.addItems(["auto (Détection intelligente)", "research (Recherche & Synthèse)", "translation (Traducteur)", "document (Analyse doc)", "meeting (Réunion & Prise de note)"])
        gl_l.addWidget(self.combo_l_mode, 1, 1)

        # Lanceurs Lumen
        lumen_actions = QHBoxLayout()
        btn_mic = QPushButton("🎤 Basculer Micro")
        btn_mic.setProperty("class", "cyan")
        btn_mic.clicked.connect(self.lancer_lumen_mic)
        lumen_actions.addWidget(btn_mic)

        btn_sum = QPushButton("📋 Résumer Presse-papiers")
        btn_sum.clicked.connect(self.lancer_lumen_summarize)
        lumen_actions.addWidget(btn_sum)

        btn_inj = QPushButton("📝 Injecter au Curseur")
        btn_inj.clicked.connect(self.lancer_lumen_inject)
        lumen_actions.addWidget(btn_inj)
        gl_l.addLayout(lumen_actions, 2, 0, 1, 2)

        right_layout.addWidget(grp_lumen)

        # 4. CONSOLE DE RETOUR EN DIRECT
        right_layout.addWidget(QLabel("📋 Console d'Exécution des Moteurs (Sortie en direct) :"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumHeight(140)
        self.console_output.setStyleSheet(
            "background-color: #030712; color: #4ade80; font-family: 'Fira Code', monospace; font-size: 11px;"
        )
        self.console_output.setPlaceholderText("Les résultats d'exécution de Whisper, Flo et Lumen apparaîtront ici...")
        right_layout.addWidget(self.console_output)

        splitter.addWidget(right_widget)
        splitter.setSizes([500, 700])
        main_layout.addWidget(splitter)

    # ── SÉLECTEUR DE MODE D'INTERFACE ────────────────────────────────
    def appliquer_mode_interface(self, mode: str):
        """Bascule entre les 3 modes d'interface: simple, medium, dev."""
        self.current_mode = mode

        # Décocher tous les boutons puis cocher le bon
        self.btn_mode_simple.setChecked(mode == "simple")
        self.btn_mode_medium.setChecked(mode == "medium")
        self.btn_mode_dev.setChecked(mode == "dev")

        # Description et couleur selon le mode
        descriptions = {
            "simple": "📱 Vue simplifiée • Fonctions essentielles • Idéal utilisation quotidienne",
            "medium": "💼 Vue intermédiaire • Moteurs IA + Télémétrie • Pour supervision productive",
            "dev":    "⚡ Cockpit complet • 16 modules • Toutes fonctionnalités développeur actives",
        }
        self.lbl_mode_desc.setText(descriptions.get(mode, ""))

        # Obtenir la fenêtre principale via le parent
        parent_win = self.parent()
        if parent_win is None:
            return

        # Correspondance mode → onglets visibles (indices dans tab_list)
        MODES_TABS = {
            "simple": [0, 1, 2, 4, 14, 15],    # HUD, Avancements, Claude, Terminal, Bureau, Paramètres
            "medium": [0, 1, 2, 3, 4, 5, 9, 11, 14, 15],  # + Apps, Table Ronde, MCPs, Cluster
            "dev":    list(range(16)),            # Tous les 16 modules
        }

        visible_indices = MODES_TABS.get(mode, list(range(16)))

        # Montrer / Cacher les éléments dans la sidebar
        if hasattr(parent_win, "sidebar"):
            for idx in range(parent_win.sidebar.count()):
                item = parent_win.sidebar.item(idx)
                item.setHidden(idx not in visible_indices)

        # Si l'onglet courant est masqué, basculer sur le premier visible
        if hasattr(parent_win, "pages"):
            cur_idx = parent_win.pages.currentIndex()
            if cur_idx not in visible_indices and visible_indices:
                parent_win.tabs.setCurrentIndex(visible_indices[0])

        # Confirmation dans le log de console
        noms_modes = {"simple": "SIMPLE", "medium": "MÉDIUM", "dev": "DEV / COCKPIT COMPLET"}
        self.log(f"🖥️ Mode d'interface basculé → {noms_modes.get(mode, mode)} ({len(visible_indices)} modules actifs)", "#00f0ff")

    def log(self, message: str, color: str = "#38bdf8"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_output.append(f"<span style='color:#64748b;'>[{timestamp}]</span> <span style='color:{color};'>{message}</span>")

    def actualiser_statuts_moteurs(self):
        # 1. Whisper
        w_stat = get_whisper_status()
        self.lbl_whisper_stat.setText(f"Statut : {w_stat['status_text']} • Mode: {w_stat['mode']}")
        self.lbl_whisper_stat.setStyleSheet(f"color: {'#4ade80' if w_stat['active'] else '#94a3b8'}; font-weight: bold;")

        # 2. Flo
        f_stat = get_flo_status()
        self.lbl_flo_stat.setText(f"Statut : {f_stat['status_text']} • Workflows dispo: {f_stat['workflows_count']}")
        self.lbl_flo_stat.setStyleSheet(f"color: {'#4ade80' if f_stat['is_running'] else '#38bdf8'}; font-weight: bold;")

        # 3. Lumen
        l_stat = get_lumen_status()
        self.lbl_lumen_stat.setText(f"Statut : {l_stat['status_text']}")
        self.lbl_lumen_stat.setStyleSheet(f"color: {'#4ade80' if l_stat['active'] else '#94a3b8'}; font-weight: bold;")

    def charger_parametres(self):
        res = get_cockpit_settings()
        s = res.get("settings", DEFAULT_SETTINGS)
        self.log("Paramètres rechargés avec succès depuis la configuration.", "#38bdf8")
        self.lbl_sync_status.setText("● Synchronisé")
        self.lbl_sync_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        self.actualiser_statuts_moteurs()

    def sauvegarder_parametres(self):
        theme_map = {
            0: "cyan", 1: "emerald", 2: "synthwave", 3: "amber"
        }
        scale_map = {0: "compact", 1: "normal", 2: "large"}
        telem_map = {0: 1500, 1: 2500, 2: 5000}

        nouveaux = {
            "theme": theme_map.get(self.combo_theme.currentIndex(), "cyan"),
            "ui_scale": scale_map.get(self.combo_scale.currentIndex(), "normal"),
            "grid_overlay": self.chk_grid.isChecked(),
            "sound_enabled": self.chk_sound.isChecked(),
            "telemetry_interval": telem_map.get(self.combo_telemetry.currentIndex(), 2500),
            "cpu_temp_alert": self.spin_temp.value(),
            "ai_engine": self.combo_ai.currentText().split(" ")[0],
            "whisper_model": self.combo_w_model.currentText().split(" ")[0],
            "whisper_device": "cuda" if self.combo_w_device.currentIndex() == 0 else "cpu",
            "flo_active_workflow": self.combo_flo_wf.currentText(),
            "lumen_mode": self.combo_l_mode.currentText().split(" ")[0]
        }
        res = save_cockpit_settings(nouveaux)
        if res.get("success"):
            self.log("✅ Tous les paramètres ont été persistés (JSON & SQLite).", "#4ade80")
            self.lbl_sync_status.setText("● Enregistré")
            self.lbl_sync_status.setStyleSheet("color: #4ade80; font-weight: bold;")
            QMessageBox.information(self, "Paramètres Sauvegardés", "Les paramètres du Cockpit ont été sauvegardés avec succès.")
        else:
            self.log(f"❌ Erreur sauvegarde: {res.get('error')}", "#f87171")
            QMessageBox.warning(self, "Erreur", f"Impossible de sauvegarder : {res.get('error')}")

    def restaurer_defaut(self):
        rep = QMessageBox.question(self, "Restaurer les valeurs par défaut", "Voulez-vous réinitialiser tous les paramètres aux valeurs d'usine ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if rep == QMessageBox.StandardButton.Yes:
            res = save_cockpit_settings(dict(DEFAULT_SETTINGS))
            self.charger_parametres()
            self.log("⚡ Paramètres réinitialisés aux valeurs par défaut.", "#fbbf24")

    # ── ACTIONS DES LANCEURS WHISPER ──
    def lancer_enregistrement_whisper(self, duration=5):
        model = self.combo_w_model.currentText().split(" ")[0]
        device = "cuda" if self.combo_w_device.currentIndex() == 0 else "cpu"
        self.log(f"🎙️ Enregistrement micro en cours ({duration}s)... Parlez maintenant.", "#fbbf24")
        self.worker = VoiceFlowWorker("whisper_record", {"duration": duration, "model": model, "lang": "fr"})
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    # ── ACTIONS DES LANCEURS FLO ──
    def lancer_flo_ui(self):
        self.log("🌊 Lancement de l'interface WhisperFlow Overlay...", "#c084fc")
        self.worker = VoiceFlowWorker("flo_launch")
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def lancer_workflow_flo(self):
        wf = self.combo_flo_wf.currentText()
        self.log(f"⚡ Exécution du workflow Flo : {wf}...", "#00f0ff")
        self.worker = VoiceFlowWorker("flo_run_workflow", {"workflow": wf})
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    # ── ACTIONS DES LANCEURS LUMEN ──
    def lancer_lumen_mic(self):
        self.log("🎤 Bascule de l'état du microphone Lumen...", "#38bdf8")
        self.worker = VoiceFlowWorker("lumen_mic")
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def lancer_lumen_summarize(self):
        self.log("📋 Résumé contextuel du presse-papiers par Lumen...", "#38bdf8")
        self.worker = VoiceFlowWorker("lumen_summarize")
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def lancer_lumen_inject(self):
        self.log("📝 Injection du dernier transcript au curseur actif...", "#38bdf8")
        self.worker = VoiceFlowWorker("lumen_inject")
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self, res: dict):
        task = res.get("task", "")
        if not res.get("success"):
            err = res.get("error", "Échec d execution")
            self.log(f"⚠️ Résultat [{task}] : {err}", "#f87171")
            return

        if task == "whisper_record":
            txt = res.get("text", "")
            self.log(f"🎙️ TRANSCRIPTION WHISPER ({res.get('duration')}s) : \"{txt}\"", "#4ade80")
        elif task == "flo_launch":
            self.log(f"🌊 WhisperFlow UI démarré (PID: {res.get('pid')})", "#4ade80")
        elif task == "flo_run_workflow":
            self.log(f"⚡ Workflow [{res.get('workflow')}] exécuté avec succès ({res.get('nodes')} nœuds validés).", "#4ade80")
        elif task == "lumen_mic":
            self.log(f"🎤 {res.get('message')} — Réponse: {res.get('output', 'OK')}", "#4ade80")
        elif task == "lumen_summarize":
            self.log(f"📋 Résumé Lumen : {res.get('summary')}", "#4ade80")
        elif task == "lumen_inject":
            self.log(f"📝 {res.get('message')}", "#4ade80")

        self.actualiser_statuts_moteurs()
