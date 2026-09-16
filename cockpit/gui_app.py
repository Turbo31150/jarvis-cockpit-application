#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui_app.py — JARVIS MASTER COCKPIT (AAA FUTURISTIC SCALABLE DESKTOP APPLICATION)
100% Native PyQt6 GUI • Modular Architecture • High-Performance Cluster Telemetry • Claude Code First-Class
"""

import sys
import os
from datetime import datetime

# Ajout du répertoire courant au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QProgressBar, QFrame, QStatusBar, QPushButton,
    QListWidget, QStackedWidget, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

IPC_SOCKET_NAME = "jarvis_master_cockpit_os_ipc"

# Couche de compatibilité Linux rig ⇄ Windows 11 (polices, icône barre des
# tâches, flux UTF-8, tmux, dossier du dépôt). Tout le code Linux reste intact.
from core.platform_compat import (
    IS_WINDOWS, cockpit_root, ensure_utf8_stdio, install_excepthook,
    set_windows_app_id, ui_font_family, mono_font_family, tmux_available,
    LOGS_DIR_DEFAULT,
)
from core.config import M6_HOST, M6_PORT, JARVIS_DIR, MACHINE_NAME
from core.telemetry import get_vram_info, get_ram_info, get_cpu_info, is_port_open
from core.mcp_registry import get_all_mcp_servers
from ui.theme import STYLESHEET

# Import des onglets modulaires
from ui.tabs.tab_hud import TabHud
from ui.tabs.tab_avancements import TabAvancements
from ui.tabs.tab_claude import TabClaude
from ui.tabs.tab_apps import TabApps
from ui.tabs.tab_terminal import TabTerminal
from ui.tabs.tab_table_ronde import TabTableRonde
from ui.tabs.tab_plan import TabPlan
from ui.tabs.tab_sql import TabSql
from ui.tabs.tab_studio import TabStudio
from ui.tabs.tab_mcps import TabMcps
from ui.tabs.tab_swarm import TabSwarm
from ui.tabs.tab_cluster import TabCluster
from ui.tabs.tab_moisson import TabMoisson
from ui.tabs.tab_iaweb import TabIaWeb
from ui.tabs.tab_bureau import TabBureau
from ui.tabs.tab_settings import TabSettings
from ui.tabs.tab_omega import TabOmega

# Polices résolues une fois : 'Ubuntu' / 'JetBrains Mono' sur le rig (inchangé),
# 'Segoe UI' / 'Cascadia Mono' (ou Consolas) sous Windows.
FONT_UI = ui_font_family()
FONT_MONO = mono_font_family()


def _trouver_icone():
    """Icône de fenêtre : JARVIS_DIR/icons (rig) puis icons/ du dépôt (Windows :
    le dépôt n'est pas dans ~/jarvis). None si absente."""
    for cand in (os.path.join(JARVIS_DIR, "icons", "1_jarvis_cockpit_os.png"),
                 os.path.join(os.path.dirname(cockpit_root()), "icons", "1_jarvis_cockpit_os.png")):
        if os.path.exists(cand):
            return cand
    return None


class _OngletIndisponible(QWidget):
    """Page de remplacement quand la construction d'un onglet lève : le cockpit
    reste utilisable et affiche l'erreur au lieu de mourir au démarrage."""
    def __init__(self, nom, erreur, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lbl = QLabel(f"⚠ Onglet « {nom} » indisponible\n\n{erreur}")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lbl.setStyleSheet("color: #fbbf24; font-size: 12px; padding: 12px;")
        lay.addWidget(lbl)
        lay.addStretch()


class _TelemetrieWorker(QThread):
    """Collecte VRAM/RAM/CPU/M6 hors du thread GUI : nvidia-smi.exe peut mettre
    1 à 2 s à froid sous Windows et la sonde M6 bloque jusqu'à son timeout."""
    resultat = pyqtSignal(dict)

    def run(self):
        data = {}
        try:
            data["vram"] = get_vram_info()
        except Exception:
            data["vram"] = {}
        try:
            data["ram"] = get_ram_info()
        except Exception:
            data["ram"] = {}
        try:
            data["cpu"] = get_cpu_info()
        except Exception:
            data["cpu"] = {}
        try:
            data["m6_up"] = is_port_open(M6_HOST, M6_PORT, timeout=0.25)
        except Exception:
            data["m6_up"] = False
        self.resultat.emit(data)


class JarvisMasterCockpitWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"JARVIS MASTER COCKPIT — POSTE DE COMMANDE UNIFIÉ ({MACHINE_NAME})")
        # Icône déplaçable (basée sur JARVIS_DIR), posée seulement si présente :
        # un chemin absolu en dur cassait la fenêtre sur toute autre machine/clé USB.
        _icone = _trouver_icone()
        if _icone:
            self.setWindowIcon(QIcon(_icone))
        self.resize(1400, 900)
        self.setMinimumSize(1150, 720)
        self.setStyleSheet(STYLESHEET)
        self.mcp_count = len(get_all_mcp_servers())

        self.init_ui()
        self.setup_shortcuts()

        # Serveur IPC d'instance unique
        self.ipc_server = QLocalServer(self)
        self.ipc_server.removeServer(IPC_SOCKET_NAME)
        self.ipc_server.newConnection.connect(self._handle_ipc_connection)
        self.ipc_server.listen(IPC_SOCKET_NAME)

        # Timer de télémétrie non-bloquante (6.0 s pour préserver le CPU) ;
        # la collecte tourne dans un QThread, seule l'application à l'UI est ici.
        self._telemetrie_worker = None
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(6000)
        self.update_telemetry()

        # Timer d'horloge temps réel (1.0 s)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

    def _handle_ipc_connection(self):
        client = self.ipc_server.nextPendingConnection()
        if client:
            client.readyRead.connect(lambda: self._handle_ipc_message(client))

    def _handle_ipc_message(self, client):
        msg = client.readAll().data().decode("utf-8", errors="ignore")
        if "ACTIVATE" in msg:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.show()
            self.raise_()
            self.activateWindow()
        client.disconnectFromServer()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ── TOP BAR / TELEMETRY HUD CYBER-DECK ──
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("""
            QFrame#topBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #050b18, stop:0.5 #091733, stop:1 #050a17);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 12px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(10)

        # Brand Title & Subtitle Badge
        brand_box = QHBoxLayout()
        brand_box.setSpacing(8)
        brand_badge = QLabel("🤖")
        brand_badge.setFont(QFont(FONT_UI, 16))
        brand_badge.setStyleSheet("""
            background: rgba(0, 240, 255, 0.12);
            border: 1px solid rgba(0, 240, 255, 0.45);
            border-radius: 8px;
            padding: 2px 6px;
        """)
        brand_box.addWidget(brand_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_lbl = QLabel("JARVIS MASTER COCKPIT")
        title_lbl.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1px; font-weight: 900;")
        title_col.addWidget(title_lbl)

        sub_lbl = QLabel(f"{MACHINE_NAME} MAÎTRE • RIG MULTI-GPU • CLAUDE & FLO" if "MINING" in MACHINE_NAME.upper() else f"{MACHINE_NAME} MAÎTRE • DUAL-NODE • CLAUDE & FLO")
        sub_lbl.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        sub_lbl.setStyleSheet("color: #38bdf8;")
        title_col.addWidget(sub_lbl)
        brand_box.addLayout(title_col)
        top_layout.addLayout(brand_box)

        top_layout.addStretch()

        # Telemetry Live Gauges & Stat Capsules
        telem_layout = QHBoxLayout()
        telem_layout.setSpacing(8)

        # Capsule VRAM GPU
        card_vram = QFrame()
        card_vram.setStyleSheet("background: rgba(8, 17, 36, 0.85); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 2px 8px;")
        vram_box = QVBoxLayout(card_vram)
        vram_box.setContentsMargins(2, 2, 2, 2)
        vram_box.setSpacing(2)
        self.lbl_vram = QLabel("🎮 GPU: -- / 4096 MB")
        self.lbl_vram.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        self.lbl_vram.setStyleSheet("color: #38bdf8;")
        self.bar_vram = QProgressBar()
        self.bar_vram.setRange(0, 4096)
        self.bar_vram.setFixedWidth(100)
        self.bar_vram.setFixedHeight(8)
        vram_box.addWidget(self.lbl_vram)
        vram_box.addWidget(self.bar_vram)
        telem_layout.addWidget(card_vram)

        # Capsule RAM Système
        card_ram = QFrame()
        card_ram.setStyleSheet("background: rgba(8, 17, 36, 0.85); border: 1px solid rgba(192, 132, 252, 0.3); border-radius: 8px; padding: 2px 8px;")
        ram_box = QVBoxLayout(card_ram)
        ram_box.setContentsMargins(2, 2, 2, 2)
        ram_box.setSpacing(2)
        self.lbl_ram = QLabel("⚡ RAM: -- GB")
        self.lbl_ram.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        self.lbl_ram.setStyleSheet("color: #c084fc;")
        self.bar_ram = QProgressBar()
        self.bar_ram.setRange(0, 40)
        self.bar_ram.setFixedWidth(100)
        self.bar_ram.setFixedHeight(8)
        ram_box.addWidget(self.lbl_ram)
        ram_box.addWidget(self.bar_ram)
        telem_layout.addWidget(card_ram)

        # Capsule Réseau & MCPs
        card_cluster = QFrame()
        card_cluster.setStyleSheet("background: rgba(8, 17, 36, 0.85); border: 1px solid rgba(74, 222, 128, 0.3); border-radius: 8px; padding: 2px 8px;")
        badge_box = QVBoxLayout(card_cluster)
        badge_box.setContentsMargins(2, 2, 2, 2)
        badge_box.setSpacing(2)
        self.badge_m6 = QLabel(f"🟢 {self._libelle_m6()} : UP (1.4 ms)")
        self.badge_m6.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        self.badge_m6.setStyleSheet("color: #4ade80;")
        
        self.badge_mcp = QLabel(f"📦 MCPs : {self.mcp_count} CONNECTÉS")
        self.badge_mcp.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        self.badge_mcp.setStyleSheet("color: #fbbf24;")
        badge_box.addWidget(self.badge_m6)
        badge_box.addWidget(self.badge_mcp)
        telem_layout.addWidget(card_cluster)

        # Quick Direct Action Buttons in Header
        quick_acts = QHBoxLayout()
        quick_acts.setSpacing(6)

        btn_top_voice = QPushButton("🎙️ Flo / Voix")
        btn_top_voice.setProperty("class", "amber")
        btn_top_voice.setToolTip("Ouvrir l'overlay WhisperFlow & Commandes vocales (Alt+X)")
        btn_top_voice.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_settings))
        quick_acts.addWidget(btn_top_voice)

        btn_top_hud = QPushButton("🎛 HUD")
        btn_top_hud.setProperty("class", "cyan")
        btn_top_hud.setToolTip("Afficher le Cockpit Exécutif (Ctrl+1)")
        btn_top_hud.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_hud))
        quick_acts.addWidget(btn_top_hud)

        btn_top_omega = QPushButton("🌌 OMEGA")
        btn_top_omega.setProperty("class", "cyan")
        btn_top_omega.setToolTip("Afficher l'Architecture Cognitive OMEGA (Ombre × Lumière)")
        btn_top_omega.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_omega))
        quick_acts.addWidget(btn_top_omega)

        btn_top_chantiers = QPushButton("🏗️ Chantiers")
        btn_top_chantiers.setStyleSheet("""
            QPushButton {
                background: rgba(5, 150, 105, 0.25);
                border: 1px solid rgba(16, 185, 129, 0.5);
                color: #10b981;
                font-weight: bold;
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(5, 150, 105, 0.45);
                border-color: #34d399;
                color: #ffffff;
            }
        """)
        btn_top_chantiers.setToolTip("Afficher la Gestion des Chantiers de Production & Sync (Ctrl+3)")
        btn_top_chantiers.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_avancements))
        quick_acts.addWidget(btn_top_chantiers)

        btn_top_settings = QPushButton("⚙️ Config")
        btn_top_settings.setProperty("class", "green")
        btn_top_settings.setToolTip("Paramètres et Moteurs IA (Ctrl+,)")
        btn_top_settings.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_settings))
        quick_acts.addWidget(btn_top_settings)

        btn_top_ref = QPushButton("🔄")
        btn_top_ref.setFixedSize(32, 32)
        btn_top_ref.setStyleSheet("""
            QPushButton {
                background: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(0, 240, 255, 0.45);
                color: #00f0ff;
                font-size: 13px;
                border-radius: 7px;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(2, 132, 199, 0.35);
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        btn_top_ref.setToolTip("Actualiser les données (F5)")
        btn_top_ref.clicked.connect(self.refresh_current_tab)
        quick_acts.addWidget(btn_top_ref)

        btn_top_fs = QPushButton("⛶")
        btn_top_fs.setFixedSize(32, 32)
        btn_top_fs.setStyleSheet("""
            QPushButton {
                background: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(0, 240, 255, 0.45);
                color: #00f0ff;
                font-size: 14px;
                border-radius: 7px;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(2, 132, 199, 0.35);
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        btn_top_fs.setToolTip("Basculer Plein Écran (F11)")
        btn_top_fs.clicked.connect(self.toggle_fullscreen)
        quick_acts.addWidget(btn_top_fs)

        telem_layout.addLayout(quick_acts)

        top_layout.addLayout(telem_layout)
        main_layout.addWidget(top_bar)

        # ── CORPS DE L'APPLICATION (SIDEBAR NAVIGATION + PAGES STACKÉES) ──
        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)

        # ── SIDEBAR FRAME HAUTE PRÉCISION ──
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebarFrame")
        sidebar_frame.setFixedWidth(260)
        sf_layout = QVBoxLayout(sidebar_frame)
        sf_layout.setContentsMargins(6, 8, 6, 8)
        sf_layout.setSpacing(6)

        lbl_nav = QLabel("⚡ NAVIGATION COCKPIT")
        lbl_nav.setFont(QFont(FONT_UI, 10, QFont.Weight.Bold))
        lbl_nav.setStyleSheet("color: #00f0ff; letter-spacing: 1.2px; padding: 2px 6px; font-weight: 900;")
        sf_layout.addWidget(lbl_nav)

        self.sidebar_filter = QLineEdit()
        self.sidebar_filter.setPlaceholderText("🔍 Filtrer onglet...")
        self.sidebar_filter.setStyleSheet("""
            QLineEdit {
                background-color: rgba(4, 8, 20, 0.9);
                border: 1px solid rgba(0, 240, 255, 0.28);
                border-radius: 7px;
                padding: 5px 8px;
                color: #f1f5f9;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #00f0ff;
                background-color: rgba(6, 14, 34, 0.95);
            }
        """)
        self.sidebar_filter.textChanged.connect(self.filter_sidebar_tabs)
        self.sidebar_filter.returnPressed.connect(self.on_filter_enter)
        sf_layout.addWidget(self.sidebar_filter)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebarNav")
        sf_layout.addWidget(self.sidebar)

        # Capsule de statut nœud en bas de sidebar avec horloge
        self.pulse_status = QLabel(f"🕒 --:--:-- • ● {MACHINE_NAME} MAÎTRE")
        self.pulse_status.setStyleSheet("color: #4ade80; font-size: 10.5px; font-weight: bold; padding: 7px 8px; background: rgba(8, 20, 42, 0.9); border: 1px solid rgba(74, 222, 128, 0.35); border-radius: 8px;")
        self.pulse_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf_layout.addWidget(self.pulse_status)

        body_layout.addWidget(sidebar_frame)

        # ── CENTRAL STACKED PAGES ──
        self.pages = QStackedWidget()
        self.pages.setObjectName("centralPages")
        body_layout.addWidget(self.pages)
        main_layout.addLayout(body_layout)

        # Initialisation des 17 pages modulaires. Chaque onglet est construit
        # sous garde : une exception dans un onglet donne une page « indisponible »
        # au lieu de faire mourir tout le cockpit (utile sous Windows où certains
        # onglets dépendent d'outils du rig).
        self.tab_hud = self._construire_onglet(TabHud, "Cockpit Exécutif")
        self.tab_avancements = self._construire_onglet(TabAvancements, "Chantiers & Production")
        self.tab_claude = self._construire_onglet(TabClaude, "Claude Code Suite")
        self.tab_apps = self._construire_onglet(TabApps, "Applications Bureau")
        self.tab_term = self._construire_onglet(TabTerminal, "Terminal & TMUX")
        self.tab_tr = self._construire_onglet(TabTableRonde, "Table Ronde & Experts")
        self.tab_plan = self._construire_onglet(TabPlan, "Board Plan & To-Do")
        self.tab_sql = self._construire_onglet(TabSql, "Bases SQL")
        self.tab_studio = self._construire_onglet(TabStudio, "Studio Création IA")
        self.tab_mcps = self._construire_onglet(TabMcps, "Serveurs MCP")
        self.tab_swarm = self._construire_onglet(TabSwarm, "Swarm & Services")
        self.tab_cluster = self._construire_onglet(TabCluster, "Cluster & Matériel")
        self.tab_moisson = self._construire_onglet(TabMoisson, "Moissonnage & Vente")
        self.tab_iaweb = self._construire_onglet(TabIaWeb, "Hub IA Web & CDP")
        self.tab_bureau = self._construire_onglet(TabBureau, "Bureau GNOME & Verrous")
        self.tab_settings = self._construire_onglet(TabSettings, "Paramètres & Moteurs IA")
        self.tab_omega = self._construire_onglet(TabOmega, "OMEGA Cognitive OS")

        # Libellés dépendants de la plateforme : sur le rig ils sont inchangés ;
        # sous Windows on annonce que tmux et le bureau GNOME n'existent pas.
        titre_term = "💻 Terminal & TMUX" if tmux_available() else "💻 Terminal (TMUX indisponible)"
        titre_bureau = "🖥 Bureau Windows (GNOME indisponible)" if IS_WINDOWS else "🖥 Bureau GNOME & Verrous"

        self.tab_list = [
            (self.tab_hud, "🎛 Cockpit Exécutif"),
            (self.tab_omega, "🌌 OMEGA Cognitive OS"),
            (self.tab_avancements, "🏗️ Chantiers & Production"),
            (self.tab_claude, "👑 Claude Code Suite"),
            (self.tab_apps, "🚀 Applications Bureau"),
            (self.tab_term, titre_term),
            (self.tab_tr, "🧠 Table Ronde & Experts"),
            (self.tab_plan, "📋 Board Plan & To-Do"),
            (self.tab_sql, "🗄 Bases SQL (53)"),
            (self.tab_studio, "✍️ Studio Création IA"),
            (self.tab_mcps, "📦 48 Serveurs MCP"),
            (self.tab_swarm, "🐳 Swarm & Services"),
            (self.tab_cluster, "🖥 Cluster & Matériel"),
            (self.tab_moisson, "🌾 Moissonnage & Vente"),
            (self.tab_iaweb, "🌐 Hub IA Web & CDP"),
            (self.tab_bureau, titre_bureau),
            (self.tab_settings, "⚙️ Paramètres & Moteurs IA")
        ]

        for widget, title in self.tab_list:
            self.pages.addWidget(widget)
            self.sidebar.addItem(title)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # Pont de compatibilité unifié pour self.tabs
        class TabsBridge:
            def __init__(self, win):
                self.win = win
            def setCurrentWidget(self, widget):
                self.win.pages.setCurrentWidget(widget)
                for idx, (w, _) in enumerate(self.win.tab_list):
                    if w == widget:
                        self.win.sidebar.setCurrentRow(idx)
                        break
            def setCurrentIndex(self, index):
                self.win.pages.setCurrentIndex(index)
                self.win.sidebar.setCurrentRow(index)
            def currentWidget(self):
                return self.win.pages.currentWidget()
            def currentIndex(self):
                return self.win.pages.currentIndex()
            def count(self):
                return self.win.pages.count()
            def tabText(self, idx):
                if 0 <= idx < len(self.win.tab_list):
                    return self.win.tab_list[idx][1]
                return ""
            def addTab(self, *a, **k): pass

        self.tabs = TabsBridge(self)

        self.setCentralWidget(main_widget)

        # ── STATUS BAR ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🟢 JARVIS MASTER COCKPIT Prêt • Raccourcis : F5 (Actualiser) • Ctrl+, (Paramètres) • Ctrl+1 à Ctrl+9 (Onglets)")

    def _construire_onglet(self, classe, nom):
        """Instancie un onglet ; en cas d'exception, journalise et rend une page
        de remplacement (le reste du cockpit reste opérationnel)."""
        try:
            return classe(self)
        except Exception as e:  # noqa: BLE001 — on veut TOUT rattraper ici
            import traceback
            msg = f"{type(e).__name__}: {e}"
            try:
                sys.stderr.write(f"[gui_app] onglet {nom} : {msg}\n{traceback.format_exc()}")
            except Exception:
                pass
            return _OngletIndisponible(nom, msg, self)

    @staticmethod
    def _libelle_m6():
        """« M6 Câble direct » sur le rig ; « LM Studio local » quand M6 pointe
        sur le loopback (cas Windows par défaut)."""
        if M6_HOST in ("127.0.0.1", "localhost", "::1"):
            return "LM Studio local"
        return "M6 Câble direct"

    def setup_shortcuts(self):
        # F5 = Refresh current tab
        QShortcut(QKeySequence("F5"), self, self.refresh_current_tab)
        # F11 = Plein écran cyberdeck
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        # Ctrl+, et Ctrl+0 = Paramètres & Moteurs
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self.tabs.setCurrentWidget(self.tab_settings))
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.tabs.setCurrentWidget(self.tab_settings))
        # Ctrl+1 à Ctrl+9 = Basculer vers onglets
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda idx=i-1: self.tabs.setCurrentIndex(idx))

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def filter_sidebar_tabs(self, text):
        query = text.lower().strip()
        for idx in range(self.sidebar.count()):
            item = self.sidebar.item(idx)
            if not query or query in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def on_filter_enter(self):
        for idx in range(self.sidebar.count()):
            item = self.sidebar.item(idx)
            if not item.isHidden():
                self.sidebar.setCurrentRow(idx)
                break

    def update_clock(self):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.pulse_status.setText(f"🕒 {now_str} • ● {MACHINE_NAME} MAÎTRE")

    def refresh_current_tab(self):
        self.update_telemetry()
        cur_w = self.tabs.currentWidget()
        if hasattr(cur_w, "recharger_apps"):
            cur_w.recharger_apps()
        elif hasattr(cur_w, "scan_bases"):
            cur_w.scan_bases()
        elif hasattr(cur_w, "scan_mcps"):
            cur_w.scan_mcps()
        elif hasattr(cur_w, "refresh_services"):
            cur_w.refresh_services()
        elif hasattr(cur_w, "refresh_telemetry"):
            cur_w.refresh_telemetry()
        elif hasattr(cur_w, "refresh_report"):
            cur_w.refresh_report()
        elif hasattr(cur_w, "refresh_bureau"):
            cur_w.refresh_bureau()
        elif hasattr(cur_w, "charger_parametres"):
            cur_w.charger_parametres()
        self.status_bar.showMessage(f"🔄 Actualisation effectuée ({datetime.now():%H:%M:%S})", 3000)

    def update_telemetry(self):
        """Lance la collecte dans un QThread (jamais deux en parallèle) ; le
        résultat arrive dans _appliquer_telemetrie sur le thread GUI."""
        w = self._telemetrie_worker
        if w is not None and w.isRunning():
            return
        # Pas de deleteLater : la référence Python est remplacée seulement une
        # fois le thread terminé (isRunning() ci-dessus), jamais d'objet détruit
        # côté C++ encore référencé ici.
        w = _TelemetrieWorker(self)
        w.resultat.connect(self._appliquer_telemetrie)
        self._telemetrie_worker = w
        w.start()

    def _appliquer_telemetrie(self, data):
        vram = data.get("vram") or {}
        ram = data.get("ram") or {}
        m6_up = bool(data.get("m6_up"))

        tot_vram = max(vram.get("total", 4096), 1)
        self.bar_vram.setRange(0, tot_vram)
        self.bar_vram.setValue(vram.get("used", 0))
        v_used, v_tot, v_temp = vram.get("used", 0), vram.get("total", 4096), vram.get("temp", 0)
        if vram.get("count", 1) > 1:
            self.lbl_vram.setText(f"🎮 {vram['count']} GPUs: {v_used}/{v_tot}MB ({v_temp}°C)")
        elif vram.get("available", True):
            self.lbl_vram.setText(f"🎮 GPU: {v_used}/{v_tot}MB ({v_temp}°C)")
        else:
            self.lbl_vram.setText("🎮 GPU: n/d (nvidia-smi absent)")

        if vram.get("gpus"):
            gpu_tt = "GPU Actifs :\n" + "\n".join([f"• {g['name']}: {g['used']}/{g['total']}MB ({g['temp']}°C, util {g['util']}%)" for g in vram["gpus"]])
            self.lbl_vram.setToolTip(gpu_tt)

        r_used = float(ram.get("used_gb", 0) or 0)
        r_tot = float(ram.get("total_gb", 4) or 4)
        tot_ram_tenth = max(int(r_tot * 10), 1)
        self.bar_ram.setRange(0, tot_ram_tenth)
        self.bar_ram.setValue(int(r_used * 10))
        self.lbl_ram.setText(f"⚡ RAM: {r_used:.1f}/{r_tot:.1f}GB ({ram.get('percent', 0)}%)")

        if m6_up:
            self.badge_m6.setText(f"🟢 {self._libelle_m6()} : UP (1.4 ms)")
            self.badge_m6.setStyleSheet("color: #4ade80;")
        else:
            self.badge_m6.setText(f"🔴 {'LM Studio' if M6_HOST in ('127.0.0.1', 'localhost', '::1') else 'M6'} : INJOIGNABLE")
            self.badge_m6.setStyleSheet("color: #f87171;")

    def closeEvent(self, event):
        # Ne pas laisser un QThread de télémétrie survivre à la fenêtre
        # (QThread détruit en cours d'exécution = avertissement/plantage Qt).
        w = self._telemetrie_worker
        if w is not None and w.isRunning():
            w.wait(3000)
        super().closeEvent(event)


def _rediriger_flux_sans_console():
    """Sous pythonw.exe (lanceur Windows sans console) sys.stdout/stderr valent
    None : tout write()/flush() d'un onglet planterait. On les redirige vers
    JARVIS_DIR/logs/cockpit_gui.log. No-op partout ailleurs."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        os.makedirs(LOGS_DIR_DEFAULT, exist_ok=True)
        fh = open(os.path.join(LOGS_DIR_DEFAULT, "cockpit_gui.log"), "a",
                  encoding="utf-8", errors="replace", buffering=1)
        if sys.stdout is None:
            sys.stdout = fh
        if sys.stderr is None:
            sys.stderr = fh
    except Exception:
        pass

def main():
    # Flux UTF-8 (print avec emoji sous stdout cp1252 redirigé), journal des
    # exceptions non rattrapées (PyQt6 abort sinon), identifiant d'application
    # Windows (icône propre dans la barre des tâches) — no-op sur le rig.
    _rediriger_flux_sans_console()
    ensure_utf8_stdio()
    install_excepthook()
    set_windows_app_id("Jarvis.Cockpit.OS")
    if not IS_WINDOWS:
        # Qt6 gère le DPI Windows nativement ; cette variable reste propre au rig.
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # ── INSTANCE UNIQUE (ACTIVATION IMMÉDIATE DU PREMIER PLAN) ──
    socket = QLocalSocket()
    socket.connectToServer(IPC_SOCKET_NAME)
    if socket.waitForConnected(400):
        socket.write(b"ACTIVATE")
        socket.waitForBytesWritten(400)
        socket.disconnectFromServer()
        sys.exit(0)

    window = JarvisMasterCockpitWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
