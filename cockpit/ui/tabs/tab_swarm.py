#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TAB 9 : SWARM DOCKER & SERVICES
Live infrastructure supervisor for PostgreSQL, Redis, n8n, Portainer, Ollama, Whisper, and CDP.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from core.swarm_manager import get_swarm_services_status
from core.config import JARVIS_DIR
from core.platform_compat import (IS_WINDOWS, open_terminal, python_executable, jarvis_path,
                                  find_app, unavailable_message)
import subprocess
import sys


def _actions_linux():
    """Actions du rig (inchangées) : (titre, classe, argv gnome-terminal, raison=None)."""
    return [
        ("⚡ Journal des Services", "cyan", ["gnome-terminal", "--title=Journal des Services JARVIS", "--", "bash", "-lc", "journalctl --user -u 'jarvis*' -n 50 -f"], None),
        ("🐳 Conteneurs Docker", "", ["gnome-terminal", "--title=Docker Conteneurs Swarm", "--", "bash", "-lc", "docker ps -a 2>/dev/null || echo 'Docker non démarré'; exec bash"], None),
        ("🎤 Pilote Vocal Whisper", "green", ["gnome-terminal", "--title=JARVIS Whisper Voice", "--", "bash", "-lc", "python3 /home/turbo/jarvis/scripts/voice_pilot.py 2>/dev/null || bash"], None),
        ("🔍 Audit Santé Système", "amber", ["gnome-terminal", "--title=Audit Santé Système", "--", "bash", "-lc", "/home/turbo/jarvis/scripts/quick_health.sh 2>/dev/null || echo 'Diagnostic terminé'; read -p 'Entrée pour fermer'"], None),
    ]


def _actions_windows():
    """Mêmes actions pour ce poste : callable (terminal wt.exe/cmd via open_terminal)
    ou None + raison → bouton grisé. journalctl et les scripts bash n'existent pas ici."""
    docker = find_app("docker")
    voice = jarvis_path("scripts", "voice_pilot.py", must_exist=True)

    def _terminal(titre, cmd):
        return lambda: open_terminal(cmd, title=titre, cwd=JARVIS_DIR, keep_open=True)

    return [
        ("⚡ Journal des Services", "cyan", None, "journalctl (systemd) du rig Linux"),
        ("🐳 Conteneurs Docker", "", _terminal("Docker Conteneurs Swarm", "docker ps -a") if docker else None,
         "docker.exe introuvable (Docker Desktop)"),
        ("🎤 Pilote Vocal Whisper", "green", _terminal("JARVIS Whisper Voice", [python_executable(), voice]) if voice else None,
         f"script scripts/voice_pilot.py absent de {JARVIS_DIR}"),
        ("🔍 Audit Santé Système", "amber", None, "script bash scripts/quick_health.sh du rig Linux"),
    ]

class TabSwarm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        top_h = QHBoxLayout()
        lbl = QLabel("🐳 INFRASTRUCTURE DOCKER SWARM & MICROSERVICES")
        lbl.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #4ade80;")
        top_h.addWidget(lbl)
        top_h.addStretch()

        btn_rescan = QPushButton("🔄 Actualiser Sondes")
        btn_rescan.clicked.connect(self.refresh_services)
        top_h.addWidget(btn_rescan)
        layout.addLayout(top_h)

        # Services Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Microservice / Conteneur", "Endpoint Réseau", "Rôle Système", "Statut Temps Réel"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Actions Bureau & Outils Système
        bot_h = QHBoxLayout()
        bot_h.setSpacing(8)
        for title, cls, cmd, raison in (_actions_windows() if IS_WINDOWS else _actions_linux()):
            b = QPushButton(title)
            if cls:
                b.setProperty("class", cls)
            if cmd is None:
                b.setEnabled(False)
                b.setToolTip(unavailable_message(title.split(" ", 1)[-1], raison or ""))
            else:
                b.clicked.connect(lambda _, c=cmd, t=title: self._lancer(c, t))
            bot_h.addWidget(b)
        bot_h.addStretch()
        layout.addLayout(bot_h)

        self.refresh_services()

    def _lancer(self, cmd, title):
        """Ne lève jamais (PyQt6 abandonne le processus sur une exception dans un slot)."""
        try:
            if callable(cmd):
                cmd()
            else:
                subprocess.Popen(cmd, start_new_session=True)
        except Exception as e:
            print(f"[swarm] {title} : {e}", file=sys.stderr)

    def refresh_services(self):
        services = get_swarm_services_status()
        self.table.setRowCount(len(services))
        for row, s in enumerate(services):
            it_name = QTableWidgetItem(s["name"])
            it_name.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
            self.table.setItem(row, 0, it_name)

            self.table.setItem(row, 1, QTableWidgetItem(s["endpoint"]))
            self.table.setItem(row, 2, QTableWidgetItem(s["role"]))

            is_up = s.get("online", False)
            it_st = QTableWidgetItem("🟢 ACTIF (UP)" if is_up else "🔴 INACTIF (DOWN)")
            it_st.setForeground(QColor("#4ade80" if is_up else "#f87171"))
            self.table.setItem(row, 3, it_st)
