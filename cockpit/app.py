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

# Couche de compatibilité Linux rig ⇄ Windows 11 : terminaux, nvidia-smi,
# interpréteur Python (jamais 'python3' nu sous Windows = alias Store), volumes.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.platform_compat import (
    IS_WINDOWS, run_cmd, nvidia_smi_path, python_exe, open_terminal,
    volume_by_label, unavailable_note, tmux_available, ensure_utf8_stdio,
)
try:
    from core.config import (MASTER_DB, BOARD_DIR, SCRIPTS_DIR,
                             LMSTUDIO_HOST, LMSTUDIO_PORT)
except Exception:  # core.config absent (copie autonome de app.py) : valeurs historiques
    MASTER_DB = os.path.expanduser("~/jarvis/jarvis_master.db")
    BOARD_DIR = os.path.expanduser("~/jarvis/board")
    SCRIPTS_DIR = os.path.expanduser("~/jarvis/scripts")
    LMSTUDIO_HOST, LMSTUDIO_PORT = "192.168.42.241", 1234

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
    """(utilisé, total, temp max) agrégés sur toutes les cartes NVIDIA.
    nvidia-smi résolu par la couche compat (System32 sous Windows), délai 2.5 s
    (1 s était trop court au démarrage à froid de nvidia-smi.exe), jamais
    d'exception ; (0, 4096, 0) si aucune carte/outil."""
    smi = nvidia_smi_path()
    if not smi:
        return 0, 4096, 0
    try:
        r = run_cmd(
            [smi, "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
            timeout=2.5,
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            used = total = temp = 0
            for line in r.stdout.strip().splitlines():
                parts = [int(p.strip()) for p in line.split(",") if p.strip().lstrip("-").isdigit()]
                if len(parts) >= 3:
                    used += parts[0]
                    total += parts[1]
                    temp = max(temp, parts[2])
            if total:
                return used, total, temp
    except Exception:
        pass
    return 0, 4096, 0


def _python_script(dossier: str, nom: str) -> str | None:
    """Chemin du script s'il existe, sinon None (message « indisponible »)."""
    p = os.path.join(dossier, nom)
    return p if os.path.isfile(p) else None

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
                        yield Static(self._topologie_text())
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

    @staticmethod
    def _topologie_text() -> str:
        if IS_WINDOWS:
            return ("• Machine   : PC Windows 11 • LM Studio 127.0.0.1:1234 • Ollama 127.0.0.1:11434\n"
                    "• GPU       : NVIDIA (nvidia-smi.exe) — télémétrie ci-contre\n"
                    "• SSD       : lettres de lecteur (JARVIS-M1 détecté par étiquette de volume)\n"
                    f"• {unavailable_note('Sessions tmux / TTX / bureau GNOME')}\n"
                    "• Terminaux : Windows Terminal (wt.exe) ou cmd.exe")
        return ("• Machine   : mining • i5-3450 4c • 31 Go RAM\n• GPU 0     : RTX 2060 12Go → LM Studio 127.0.0.1:1234 (qwen3-8b)\n"
                "• GPU 1     : RTX 3080 10Go → Ollama 127.0.0.1:11434 (qwen2.5:7b)\n• SSD       : / (systeme) • /mnt/jarvis-m1 • /mnt/jarvis-m6\n"
                "• Moteurs   : DOMINO dual-moteur (board boost)\n• Docker    : 29.1.3 (runtime nvidia)")

    def on_mount(self) -> None:
        self.title = "JARVIS MASTER COCKPIT — M4 NATIVE"
        self.sub_title = "91 MCPs • Table Ronde • Swarm • TTX Workspace"
        self.setup_tables()
        self.update_telemetry()
        self.set_interval(2.0, self.update_telemetry)

    def _notifier(self, message: str, severity: str = "warning") -> None:
        """Affiche un message non bloquant (jamais de traceback plein écran)."""
        try:
            self.notify(message, severity=severity, timeout=6)
        except Exception:
            pass
        try:
            self.query_one("#telemetry-display", Static).update(message)
        except Exception:
            pass

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
        """Collecte (nvidia-smi + 8 sondes TCP) dans un worker thread Textual :
        sur la boucle d'événements elle gelait la TUI jusqu'à ~1 s quand les
        hôtes ne répondent pas. L'UI est mise à jour via call_from_thread."""
        self.run_worker(self._collecter_telemetrie, thread=True, exclusive=True,
                        group="telemetrie", exit_on_error=False)

    def _collecter_telemetrie(self) -> None:
        v_used, v_tot, temp = get_vram_info()
        d = {
            "vram": (v_used, v_tot, temp),
            "pg": is_port_open("127.0.0.1", 5432),
            "rd": is_port_open("127.0.0.1", 6379),
            "n8n": is_port_open("127.0.0.1", 5678),
            "port": is_port_open("127.0.0.1", 9000),
            "reg": is_port_open("127.0.0.1", 5000),
            "ol1": is_port_open("127.0.0.1", 11434),
            # LMSTUDIO_HOST = tether du rig (Linux) ou 127.0.0.1 (Windows), + loopback
            "lms": is_port_open(LMSTUDIO_HOST, LMSTUDIO_PORT) or is_port_open("127.0.0.1", 1234),
            # /media/pamerys/JARVIS-M1 (rig) ou lettre de lecteur (Windows)
            "m1": volume_by_label("JARVIS-M1") is not None,
        }
        try:
            self.call_from_thread(self._appliquer_telemetrie, d)
        except Exception:
            pass

    def _appliquer_telemetrie(self, d: dict) -> None:
        v_used, v_tot, temp = d["vram"]
        pg_up, rd_up, n8n_up, port_up = d["pg"], d["rd"], d["n8n"], d["port"]
        lms_up, ol1_up = d["lms"], d["ol1"]

        telem = (
            f"⚡ GPU RTX 3050 : {v_used} MB / {v_tot} MB ({temp}°C) | "
            f"LM Studio : {'UP (Dual GPU)' if lms_up else 'DOWN'} | "
            f"SSD M1 USB : {'MOUNTED' if d['m1'] else 'NON'}\n"
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
            t_swarm.add_row("Docker Registry", "127.0.0.1:5000", "Registre d'images local", "🟢 UP" if d["reg"] else "🔴 DOWN")
            t_swarm.add_row("Ollama Local (OL1)", "127.0.0.1:11434", "Inférence locale gemma3/llama3", "🟢 UP" if ol1_up else "🔴 DOWN")
            t_swarm.add_row("LM Studio GPU", "127.0.0.1:1234", "Dual GPU (RTX 2060+3080)", "🟢 UP" if lms_up else "🔴 DOWN")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Tout est enveloppé : un FileNotFoundError (gnome-terminal absent, script
        # du rig manquant) faisait afficher une traceback par Textual et quittait.
        try:
            self._bouton(event.button.id)
        except Exception as e:  # noqa: BLE001
            self._notifier(f"Erreur : {type(e).__name__}: {e}", severity="error")

    def _bouton(self, bid: str | None) -> None:
        if bid == "btn-ttx":
            # ttx = multiplexeur tmux 14 fenêtres : aucun équivalent sans tmux.
            if not tmux_available():
                self._notifier(unavailable_note("TTX / sessions tmux"))
                return
            if not open_terminal("ttx", title="JARVIS TTX", login_shell=True):
                self._notifier("Aucun émulateur de terminal disponible", severity="error")
        elif bid == "btn-claude":
            # Linux : gnome-terminal -- bash -ic claude (inchangé) ; Windows : wt.exe / cmd.exe
            if not open_terminal("claude", title="Claude Code", login_shell=True):
                self._notifier("Aucun émulateur de terminal disponible", severity="error")
        elif bid == "btn-turbo":
            script = _python_script(SCRIPTS_DIR, "start-turbo-m1.sh")
            if not script or IS_WINDOWS:
                self._notifier(unavailable_note("Terminal Turbo M1 (script bash du rig)"))
                return
            if not open_terminal([script], title="Turbo M1", keep_open=False):
                self._notifier("Aucun émulateur de terminal disponible", severity="error")
        elif bid == "btn-plan-regen":
            script = _python_script(SCRIPTS_DIR, "planning_mega_m4.py")
            if not script:
                self._notifier(f"⚠ Script absent : {os.path.join(SCRIPTS_DIR, 'planning_mega_m4.py')}")
                return
            def run_plan():
                run_cmd([python_exe(), script], timeout=120)
                try:
                    self.call_from_thread(self.setup_tables)
                except Exception:
                    pass
            threading.Thread(target=run_plan, daemon=True).start()
        elif bid == "btn-moisson-run":
            # 'moisson' = alias bash du rig (~/.bashrc) : sans bash interactif Linux, indisponible.
            if IS_WINDOWS:
                self._notifier(unavailable_note("Moisson (alias bash du rig)"))
                return
            if not open_terminal("moisson; read -p 'Terminé'", title="Moisson", login_shell=True):
                self._notifier("Aucun émulateur de terminal disponible", severity="error")
        elif bid == "btn-board-ask":
            q = self.query_one("#input-board", Input).value.strip()
            if q:
                out = self.query_one("#board-output", Static)
                script = _python_script(BOARD_DIR, "dispatch_table_ronde.py")
                if not script:
                    out.update(f"⚠ Table Ronde indisponible : {os.path.join(BOARD_DIR, 'dispatch_table_ronde.py')} absent")
                    return
                out.update("🏛 Débat des 7 Experts en cours...\n0 token payant • Analyse FTS5 du corpus & arbitrage...")
                def run_board():
                    try:
                        r = run_cmd([python_exe(), script, "--task", q], timeout=45)
                        res = r.stdout or r.stderr or "Aucune réponse."
                    except Exception as e:
                        res = f"Erreur d'exécution: {e}"
                    try:
                        self.call_from_thread(out.update, res)
                    except Exception:
                        pass
                threading.Thread(target=run_board, daemon=True).start()

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
        # Historiquement /home/pamerys/jarvis/scripts/moisson_reelle.py (autre machine) :
        # on cherche dans SCRIPTS_DIR, sinon message clair au lieu d'un silence.
        script = _python_script(SCRIPTS_DIR, "moisson_reelle.py")
        try:
            if not script:
                self.query_one("#moisson-output", Static).update(
                    f"⚠ Rapport de moisson indisponible : {os.path.join(SCRIPTS_DIR, 'moisson_reelle.py')} absent")
                return
            r = run_cmd([python_exe(), script, "--rapport"], timeout=3)
            self.query_one("#moisson-output", Static).update(r.stdout or r.stderr or "")
        except Exception:
            pass
    def action_refresh_all(self) -> None:
        self.update_telemetry()
        self.setup_tables()

if __name__ == "__main__":
    ensure_utf8_stdio()
    app = JarvisCockpit()
    app.run()
