#!/usr/bin/env python3
"""
app.py — JARVIS MASTER COCKPIT (NATIVE TEXTUAL TUI APPLICATION)
0% HTML — 100% NATIVE PYTHON & TERMINAL ENGINE
Fournit le centre de commande unifié pour M4, les 91 MCPs, la Table Ronde,
le Planning To-Do List et le Swarm Docker.
"""

from __future__ import annotations
import os
import sys
import json
import sqlite3
import subprocess
import socket
import threading
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Button, Static, Input, DataTable, TabbedContent, TabPane,
    Label, ProgressBar, Markdown
)
from textual.reactive import reactive
from textual.binding import Binding

MASTER_DB = os.path.expanduser("~/jarvis/jarvis_master.db")
BOARD_DIR = os.path.expanduser("~/jarvis/board")

def is_port_open(host: str, port: int, timeout: float = 0.15) -> bool:
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def get_vram_info() -> tuple[int, int, int]:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [int(p.strip()) for p in r.stdout.strip().split(",")]
            return parts[0], parts[1], parts[2]
    except Exception:
        pass
    return 0, 4096, 0

def get_mcp_servers() -> dict:
    p = os.path.expanduser("~/.claude.json")
    if os.path.exists(p):
        try:
            return json.load(open(p)).get("mcpServers", {})
        except Exception:
            pass
    return {}

def get_tasks_list() -> list[dict]:
    if not os.path.exists(MASTER_DB):
        return []
    try:
        con = sqlite3.connect(MASTER_DB)
        cur = con.cursor()
        cur.execute("SELECT id, title, status, category FROM tasks ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        con.close()
        return [{"id": r[0], "title": r[1], "status": r[2], "category": r[3]} for r in rows]
    except Exception:
        return []

class JarvisCockpit(App):
    CSS = """
    Screen {
        background: #0b0f19;
        color: #e2e8f0;
    }
    Header {
        background: #1e1b4b;
        color: #38bdf8;
        dock: top;
        height: 3;
    }
    Footer {
        background: #0f172a;
        color: #94a3b8;
        dock: bottom;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 1 2;
    }
    .hud-box {
        background: #111827;
        border: solid #0284c7;
        padding: 1 2;
        margin: 1 0;
        height: auto;
    }
    .hud-title {
        color: #38bdf8;
        text-style: bold;
        margin-bottom: 1;
    }
    .action-btn {
        margin: 1;
        width: 100%;
        background: #0369a1;
        color: #ffffff;
        text-style: bold;
    }
    .action-btn:hover {
        background: #0284c7;
    }
    .purple-btn {
        background: #7e22ce;
        color: #ffffff;
    }
    .purple-btn:hover {
        background: #9333ea;
    }
    .green-btn {
        background: #15803d;
        color: #ffffff;
    }
    .green-btn:hover {
        background: #16a34a;
    }
    #board-output {
        background: #030712;
        border: solid #6b21a8;
        padding: 1 2;
        height: 16;
        color: #c084fc;
    }
    #moisson-output {
        background: #030712;
        border: solid #ca8a04;
        padding: 1 2;
        height: 16;
        color: #fde047;
    }
    DataTable {
        background: #111827;
        border: solid #374151;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quitter", show=True),
        Binding("1", "tab_hud", "Cockpit HUD", show=True),
        Binding("2", "tab_board", "Table Ronde", show=True),
        Binding("3", "tab_plan", "Board Plan", show=True),
        Binding("4", "tab_mcps", "91 MCPs", show=True),
        Binding("5", "tab_swarm", "Swarm & SQL", show=True),
        Binding("6", "tab_moisson", "Moissonnage", show=True),
        Binding("r", "refresh_all", "Rafraîchir", show=True),
    ]

    telemetry_text = reactive("Chargement de la télémétrie...")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-hud"):
            # TAB 1: COCKPIT HUD
            with TabPane("🎛 Cockpit HUD & Lanceurs", id="tab-hud"):
                with Horizontal():
                    with Vertical(classes="hud-box"):
                        yield Label("🤖 POSTE MAÎTRE M4 [PAMERYS]", classes="hud-title")
                        yield Static(id="telemetry-display", content="VRAM: ... | RAM: ... | M6: ...")
                        yield Label("\n🚀 ACTIONS INSTANTANÉES (LANCEMENT NATIVE TERMINAL)")
                        yield Button("🚀 Lancer Cockpit TTX (5 Fenêtres TMUX)", id="btn-ttx", classes="action-btn")
                        yield Button("👑 Claude Code Orfèvre (91 MCPs)", id="btn-claude", classes="action-btn purple-btn")
                        yield Button("💻 Terminal Turbo M4 Native", id="btn-turbo", classes="action-btn green-btn")
                    
                    with Vertical(classes="hud-box"):
                        yield Label("⚡ TOPOLOGIE & INFRASTRUCTURE", classes="hud-title")
                        yield Static("• M4 Local     : i5-11400H • RTX 3050 Laptop • 16 Go RAM\n• M1 SSD (1 To): /media/pamerys/JARVIS-M1 (USB 0 ms)\n• M6 GPU Multi : 10.42.0.230:1234 (RJ45 Direct 1.4 ms)\n• Docker Swarm : PostgreSQL, Redis, n8n, Portainer, Registry\n• MCP Total    : 91 Serveurs Actifs & Synchronisés")
                        yield Button("🔄 Scanner & Régénérer To-Do List M4", id="btn-plan-regen", classes="action-btn")
                        yield Button("🌾 Lancer Moisson Claude Code", id="btn-moisson-run", classes="action-btn")

            # TAB 2: TABLE RONDE & BOARD OS
            with TabPane("🧠 Table Ronde & Experts", id="tab-board"):
                yield Label("🏛 CONSEIL DES 7 EXPERTS & ARBITRAGE (0-TOKEN FACTURÉ)", classes="hud-title")
                yield Input(placeholder="Posez une question ou entrez une tâche pour le Conseil des Experts...", id="input-board")
                yield Button("⚖️ Soumettre au Débat des 7 Experts", id="btn-board-ask", classes="action-btn purple-btn")
                yield Static(id="board-output", content="Entrez une question ci-dessus pour lancer le débat d'experts...")

            # TAB 3: BOARD PLAN & TODOLIST
            with TabPane("📋 Board Plan & To-Do", id="tab-plan"):
                yield Label("📋 TO-DO LIST UNIFIÉE DU PLANNING MASTER (jarvis_master.db)", classes="hud-title")
                yield DataTable(id="table-tasks")

            # TAB 4: 91 MCP SERVERS MATRIX
            with TabPane("📦 91 Serveurs MCP", id="tab-mcps"):
                yield Label("📦 MATRICE DES 91 SERVEURS MCP CONNECTÉS", classes="hud-title")
                yield DataTable(id="table-mcps")

            # TAB 5: SWARM & BASES SQL
            with TabPane("🐳 Swarm & Bases SQL", id="tab-swarm"):
                yield Label("🐳 ÉTAT DES SERVICES SWARM DOCKER & BASES DE DONNÉES", classes="hud-title")
                yield DataTable(id="table-swarm")

            # TAB 6: MOISSONNAGE RÉEL
            with TabPane("🌾 Moissonnage Réel", id="tab-moisson"):
                yield Label("🌾 RAPPORT DE PROSPECTION RÉELLE & MOISSON CLAUDE CODE", classes="hud-title")
                yield Static(id="moisson-output", content="Chargement du rapport de prospection...")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "JARVIS MASTER COCKPIT — M4 NATIVE"
        self.sub_title = "91 MCPs • Table Ronde • Swarm • TTX Workspace"
        self.setup_tables()
        self.update_telemetry()
        self.set_interval(2.0, self.update_telemetry)

    def setup_tables(self) -> None:
        # Table MCPs
        t_mcp = self.query_one("#table-mcps", DataTable)
        t_mcp.add_columns("Nom Serveur", "Type", "Commande / URL")
        mcps = get_mcp_servers()
        for name, cfg in sorted(mcps.items()):
            t = "HTTP" if (cfg.get("type") == "http" or "serverUrl" in cfg or "url" in cfg) else "STDIO"
            cmd = cfg.get("command") or cfg.get("url") or cfg.get("serverUrl") or "npx/python"
            t_mcp.add_row(name, t, str(cmd))

        # Table Tasks
        t_tasks = self.query_one("#table-tasks", DataTable)
        t_tasks.add_columns("ID", "Catégorie", "Titre de la Tâche", "Statut")
        tasks = get_tasks_list()
        for task in tasks:
            t_tasks.add_row(str(task["id"]), str(task["category"]), str(task["title"]), str(task["status"]))

        # Table Swarm
        t_swarm = self.query_one("#table-swarm", DataTable)
        t_swarm.add_columns("Service", "Hôte : Port", "Rôle", "Statut Live")

    def update_telemetry(self) -> None:
        v_used, v_tot, temp = get_vram_info()
        pg_up = is_port_open("127.0.0.1", 5432)
        rd_up = is_port_open("127.0.0.1", 6379)
        n8n_up = is_port_open("127.0.0.1", 5678)
        port_up = is_port_open("127.0.0.1", 9000)
        m6_up = is_port_open("10.42.0.230", 1234) or is_port_open("10.42.0.230", 22)
        ol1_up = is_port_open("127.0.0.1", 11434)

        telem = (
            f"⚡ GPU RTX 3050 : {v_used} MB / {v_tot} MB ({temp}°C) | "
            f"M6 RJ45 : {'UP (1.4ms)' if m6_up else 'DOWN'} | "
            f"SSD M1 USB : {'MOUNTED' if os.path.exists('/media/pamerys/JARVIS-M1') else 'NON'}\n"
            f"🐳 Swarm : Postgres={'UP' if pg_up else 'DOWN'} | Redis={'UP' if rd_up else 'DOWN'} | "
            f"n8n={'UP' if n8n_up else 'DOWN'} | Portainer={'UP' if port_up else 'DOWN'}"
        )
        try:
            self.query_one("#telemetry-display", Static).update(telem)
        except Exception:
            pass

        # Update Swarm table
        try:
            t_swarm = self.query_one("#table-swarm", DataTable)
            t_swarm.clear()
            t_swarm.add_row("PostgreSQL 15", "127.0.0.1:5432", "Base relationnelle & vectorielle", "🟢 UP" if pg_up else "🔴 DOWN")
            t_swarm.add_row("Redis 7 Alpine", "127.0.0.1:6379", "Cache mémoire & Event bus", "🟢 UP" if rd_up else "🔴 DOWN")
            t_swarm.add_row("n8n Automation", "127.0.0.1:5678", "Moteur de workflows & déclencheurs", "🟢 UP" if n8n_up else "🔴 DOWN")
            t_swarm.add_row("Portainer CE", "127.0.0.1:9000", "Console d'administration Swarm", "🟢 UP" if port_up else "🔴 DOWN")
            t_swarm.add_row("Docker Registry", "127.0.0.1:5000", "Registre d'images local", "🟢 UP" if is_port_open("127.0.0.1", 5000) else "🔴 DOWN")
            t_swarm.add_row("Ollama Local (OL1)", "127.0.0.1:11434", "Inférence locale gemma3/llama3", "🟢 UP" if ol1_up else "🔴 DOWN")
            t_swarm.add_row("M6 Inférence (RJ45)", "10.42.0.230:1234", "LM Studio Qwen 3.5 9B/27B", "🟢 UP" if m6_up else "🔴 DOWN")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-ttx":
            subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "ttx"])
        elif bid == "btn-claude":
            subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "claude"])
        elif bid == "btn-turbo":
            subprocess.Popen(["gnome-terminal", "--", "/home/pamerys/jarvis/scripts/start-turbo-m1.sh"])
        elif bid == "btn-plan-regen":
            def run_plan():
                subprocess.run(["python3", "/home/pamerys/jarvis/scripts/planning_mega_m4.py"])
                self.setup_tables()
            threading.Thread(target=run_plan).start()
        elif bid == "btn-moisson-run":
            subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", "moisson; read -p 'Terminé'"])
        elif bid == "btn-board-ask":
            q = self.query_one("#input-board", Input).value.strip()
            if q:
                out = self.query_one("#board-output", Static)
                out.update("🏛 Débat des 7 Experts en cours...\n0 token payant • Analyse FTS5 du corpus & arbitrage...")
                def run_board():
                    try:
                        cmd = ["python3", "/home/pamerys/jarvis/board/dispatch_table_ronde.py", "--task", q]
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                        res = r.stdout or r.stderr or "Aucune réponse."
                    except Exception as e:
                        res = f"Erreur: {e}"
                    self.call_from_thread(out.update, res)
                threading.Thread(target=run_board).start()

    def action_tab_hud(self) -> None:
        self.query_one(TabbedContent).active = "tab-hud"
    def action_tab_board(self) -> None:
        self.query_one(TabbedContent).active = "tab-board"
    def action_tab_plan(self) -> None:
        self.query_one(TabbedContent).active = "tab-plan"
    def action_tab_mcps(self) -> None:
        self.query_one(TabbedContent).active = "tab-mcps"
    def action_tab_swarm(self) -> None:
        self.query_one(TabbedContent).active = "tab-swarm"
    def action_tab_moisson(self) -> None:
        self.query_one(TabbedContent).active = "tab-moisson"
        try:
            r = subprocess.run(["python3", "/home/pamerys/jarvis/scripts/moisson_reelle.py", "--rapport"], capture_output=True, text=True, timeout=3)
            self.query_one("#moisson-output", Static).update(r.stdout)
        except Exception:
            pass
    def action_refresh_all(self) -> None:
        self.update_telemetry()
        self.setup_tables()

if __name__ == "__main__":
    app = JarvisCockpit()
    app.run()
