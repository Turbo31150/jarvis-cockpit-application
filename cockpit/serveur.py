#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — SERVEUR D'APPLICATION DESKTOP & API UNIFIÉE SCALABLE
====================================================================
Architecture unifiée :
  • Dashboard Télémétrie Cluster M4 + M6 GPU (10.42.0.230 RJ45 direct)
  • Gestionnaire de Tâches & To-Do List Maître (jarvis_master.db)
  • Suite Claude Code CLI (Presets, Diagnostics, Exécution)
  • Explorateur interactif des 53 Bases SQL vivantes
  • Matrice des 48 Serveurs MCP connectés
  • Supervision Docker Swarm & Services
  • Délibération Table Ronde Multi-Agents (Omega, Shield, Turbo)
  • Studio de Création IA (LinkedIn, Article, PRD, Code)
  • Ingestion Vectorielle SWAN / CLAIRE (768D Nomic)
  • Moisson Locomotive & Bibliothèque Vivante Board (528k chunks FTS5)
  • Moteur PTY / xterm.js interactif
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RACINE)

import terminaux
from core.config import (M6_HOST, M6_PORT, MASTER_DB, BOARD_DB,
                         CONTENT_DIR, JARVIS_DIR)
from core.database import (
    get_board_stats, search_board_fts, get_master_tasks, add_master_task,
    update_master_task_status, delete_master_task, scan_all_sqlite_databases,
    execute_safe_query
)
from core.mcp_registry import get_all_mcp_servers
from core.swarm_manager import get_swarm_services_status
from core.apps_registry import scan_all_applications
from core.telemetry import get_vram_info
from core.claude_engine import (
    get_claude_info, run_claude_prompt, launch_claude_interactive, CLAUDE_PRESETS
)
from core.sync_engine import (
    get_avancements_data, trigger_synchronisation, creer_nouveau_chantier, update_tache_production
)
from core.cdp_engine import get_cdp_status, start_cdp, stop_cdp, verify_cdp
from core.notion_engine import get_notion_stats, read_notion_file, run_notion_backup_snapshot
from core.bureau_engine import get_bureau_etat, run_bureau_action
from core.inventaire import (get_postgres, get_tailscale,
                             get_peripheriques, get_inventaire_complet)
from core.settings_engine import get_cockpit_settings, save_cockpit_settings
from core.table_ronde_engine import (
    run_table_ronde_deliberation, check_agent_status, get_browser_os_context
)

PORT = int(os.environ.get("COCKPIT_PORT", "8600"))
M6_URL = f"http://{M6_HOST}:{M6_PORT}"
OL_URL = "http://127.0.0.1:11434"
WEB_DIR = os.path.join(RACINE, "web")


def run_inference_engine(prompt, sys_prompt="Tu es l'assistant IA JARVIS.", max_tokens=1000):
    """Inférence cockpit — délègue à la cascade 3-GPU locale (rig 'mining').

    Câblée sur core.inference.generate_completion :
      RTX 3080 (:11434, qwen3:8b) → délestage RTX 2060 (:11435, qwen2.5:7b) → Chat Proxy.
    (L'ancien tier LM Studio M6 est obsolète : M6 injoignable.)
    """
    from core.inference import generate_completion
    r = generate_completion(prompt, sys_prompt=sys_prompt, max_tokens=max_tokens)
    return {
        "content": r.get("content", ""),
        "source": r.get("source", "NONE"),
        "latency": r.get("latency", 0.0),
        "success": r.get("success", False),
    }


def get_cluster_telemetry():
    """Télémétrie complète temps réel du cluster M4 + M6."""
    # 1. Matériel M4 (CPU / RAM / VRAM)
    temp_c = subprocess.getoutput("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -rn | head -1").strip()
    temp_val = int(temp_c) // 1000 if temp_c.isdigit() else 0

    mem_info = subprocess.getoutput("free -m").splitlines()
    mem_used, mem_total, mem_free = 0, 16000, 0
    for l in mem_info:
        if l.startswith("Mem:"):
            parts = l.split()
            mem_total = int(parts[1])
            mem_used = int(parts[2])
            mem_free = int(parts[6])

    # VRAM agrégée sur les 4 GPU du rig via get_vram_info() (multi-GPU correct +
    # garde thermique doctrine excluant la 1660S). L'ancien parse inline supposait
    # 1 seul GPU : sur 4 cartes nvidia-smi rend 4 lignes → split(',') plantait
    # (ValueError) et retombait sur 0/4096 ; timeout=1 s trop court sous charge.
    vram_used, vram_total, vram_temp = 0, 4096, 0
    try:
        _v = get_vram_info()
        if _v.get("available"):
            vram_used, vram_total, vram_temp = _v["used"], _v["total"], _v["temp"]
    except Exception:
        pass

    # 2. Nœud M6 GPU
    m6_online = False
    m6_latency = 0.0
    m6_models = []
    try:
        t0 = time.time()
        req = urllib.request.Request(f"{M6_URL}/api/v0/models")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            m6_latency = round((time.time() - t0) * 1000, 1)
            data = json.loads(resp.read().decode())
            m6_models = [m["id"] for m in data.get("data", []) if m.get("state") == "loaded"]
            m6_online = True
    except Exception:
        pass

    # 3. Matrice des 12 services
    ports_map = [
        ("Cockpit Web", "127.0.0.1", 8600),
        ("Planning Widget", "127.0.0.1", 8899),
        ("Board Serveur", "127.0.0.1", 8795),
        ("S8 Voice", "127.0.0.1", 8799),
        ("Chat Proxy LLM", "127.0.0.1", 18800),
        ("Whisper Bridge", "127.0.0.1", 9742),
        ("Ollama M4", "127.0.0.1", 11434),
        ("Monitor Cluster", "127.0.0.1", 8420),
        ("Espace Prof", "127.0.0.1", 7777),
        ("PostgreSQL", "127.0.0.1", 5432),
        ("Redis Local", "127.0.0.1", 6379),
        ("BrowserOS CDP", "127.0.0.1", 9108)
    ]
    services_status = []
    import socket
    for name, host, port in ports_map:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            res = s.connect_ex((host, port))
            s.close()
            services_status.append({"name": name, "port": port, "up": (res == 0)})
        except Exception:
            services_status.append({"name": name, "port": port, "up": False})

    return {
        "m4": {
            "temp_c": temp_val,
            "mem_used_mb": mem_used,
            "mem_total_mb": mem_total,
            "mem_free_mb": mem_free,
            "vram_used_mb": vram_used,
            "vram_total_mb": vram_total,
            "vram_temp_c": vram_temp,
            "governor": "performance"
        },
        "m6": {
            "online": m6_online,
            "latency_ms": m6_latency,
            "models": m6_models,
            "ip": M6_HOST
        },
        "services": services_status,
        "timestamp": datetime.now().isoformat()
    }


class CockpitHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def local_seulement(self):
        """Terminal/PTY accessible depuis la machine + réseaux de confiance.

        Étendu pour l'app mobile JARVIS Cockpit OS : autorise le loopback,
        le tether USB du téléphone (192.168.42.0/24) et Tailscale (100.64.0.0/10).
        ⚠️ Expose l'accès shell à ces réseaux privés (téléphone direct + tailnet chiffré).
        """
        pair = (self.client_address[0] or "").replace("::ffff:", "")
        def _tailscale(ip):
            try:
                a, b = ip.split(".")[:2]
                return a == "100" and 64 <= int(b) <= 127   # CGNAT 100.64.0.0/10
            except Exception:
                return False
        if (pair in ("127.0.0.1", "::1")
                or pair.startswith("127.")
                or pair.startswith("192.168.42.")   # tether USB téléphone
                or _tailscale(pair)):                # Tailscale
            return True
        self.respond_json({"success": False, "error": "Accès restreint : loopback, tether (192.168.42.x) ou Tailscale (100.64/10) uniquement"}, 403)
        return False

    def respond_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def router_terminal(self, path, req_data=None, params=None):
        """Routes /api/term/* pour PTY et TMUX."""
        if not path.startswith("/api/term"):
            return False
        if not self.local_seulement():
            return True
        try:
            if path == "/api/term/apps":
                self.respond_json(terminaux.api_apps())
            elif path == "/api/term/sessions":
                self.respond_json(terminaux.api_sessions())
            elif path == "/api/term/tmux":
                self.respond_json(terminaux.api_tmux())
            elif path == "/api/term/output":
                sid = (params or {}).get("id", [""])[0]
                offset = int((params or {}).get("offset", ["0"])[0])
                attente = float((params or {}).get("attente", ["20"])[0])
                self.respond_json(terminaux.api_lire(sid, offset, min(attente, 30.0)))
            elif path == "/api/term/open":
                self.respond_json(terminaux.api_ouvrir(req_data or {}))
            elif path == "/api/term/input":
                self.respond_json(terminaux.api_ecrire(req_data or {}))
            elif path == "/api/term/resize":
                self.respond_json(terminaux.api_redimensionner(req_data or {}))
            elif path == "/api/term/signal":
                self.respond_json(terminaux.api_signal(req_data or {}))
            elif path == "/api/term/close":
                self.respond_json(terminaux.api_fermer(req_data or {}))
            elif path == "/api/term/tmux-tout-ouvrir":
                self.respond_json(terminaux.api_tmux_tout_ouvrir())
            else:
                self.respond_json({"success": False, "error": "route terminal inconnue"}, 404)
        except Exception as e:
            self.respond_json({"success": False, "error": f"{type(e).__name__}: {e}"}, 500)
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if self.router_terminal(path, params=params):
            return

        # ── TÉLÉMÉTRIE CLUSTER ──
        if path == "/api/status":
            self.respond_json(get_cluster_telemetry())
            return

        # ── AVANCEMENTS & SYNCHRONISATION ──
        elif path == "/api/avancements":
            self.respond_json(get_avancements_data())
            return

        # ── CDP AUTHENTIFIÉ (PORT 9222) ──
        elif path == "/api/cdp/status":
            self.respond_json(get_cdp_status())
            return

        # ── BUREAU GNOME (BARRE / ICONES / VERROUS / ECRANS) ──
        # Lecture seule : c'est un CONSTAT, il n'écrit rien nulle part.
        elif path == "/api/bureau/etat":
            try:
                self.respond_json(get_bureau_etat())
            except Exception as e:
                self.respond_json({"success": False, "error": f"{type(e).__name__}: {e}"}, 500)
            return

        # ── NOTION BACKUP & VAULT ──
        elif path == "/api/notion/stats":
            self.respond_json(get_notion_stats())
            return
        elif path == "/api/notion/file":
            rel_t = params.get("type", ["page"])[0]
            fname = params.get("file", [""])[0]
            self.respond_json(read_notion_file(rel_t, fname))
            return

        # ── TÂCHES & PLANNING ──
        elif path == "/api/tasks":
            limit = int(params.get("limit", [50])[0])
            tasks = get_master_tasks(limit=limit)
            self.respond_json({"success": True, "tasks": tasks, "count": len(tasks)})
            return

        # ── BASES SQL VIVANTES ──
        elif path == "/api/databases":
            bases = scan_all_sqlite_databases()
            self.respond_json({"success": True, "databases": bases, "count": len(bases)})
            return

        # ── POSTGRESQL, TAILSCALE, PERIPHERIQUES ──
        # Ajoutes le 2026-09-03 : ces trois familles existaient sur la machine
        # (2 conteneurs pg16 portant 7 bases, 9 pairs tailnet, 13 disques /
        # 7 USB / 1 GPU / 5 interfaces) sans aucune vue dans l'application.
        elif path == "/api/postgres":
            self.respond_json({"success": True, "postgres": get_postgres()})
            return

        elif path == "/api/tailscale":
            self.respond_json({"success": True, "tailscale": get_tailscale()})
            return

        elif path == "/api/peripheriques":
            self.respond_json({"success": True, "peripheriques": get_peripheriques()})
            return

        elif path == "/api/inventaire":
            self.respond_json({"success": True, "inventaire": get_inventaire_complet()})
            return

        # ── PARAMÈTRES & CONFIGURATION ──
        elif path == "/api/settings":
            self.respond_json(get_cockpit_settings())
            return

        # ── STATUT DES AGENTS TABLE RONDE & BROWSER OS ──
        elif path == "/api/table-ronde/status":
            self.respond_json({
                "success": True,
                "agents": check_agent_status(),
                "browser_context": get_browser_os_context()
            })
            return

        # ── SERVEURS MCP ──
        elif path == "/api/mcps":
            mcps = get_all_mcp_servers()
            self.respond_json({"success": True, "mcps": mcps, "count": len(mcps)})
            return

        # ── DOCKER SWARM & SERVICES ──
        elif path == "/api/swarm":
            services = get_swarm_services_status()
            self.respond_json({"success": True, "services": services, "count": len(services)})
            return

        # ── APPLICATIONS BUREAU ──
        elif path == "/api/apps/all":
            apps = scan_all_applications()
            self.respond_json({"success": True, "apps": apps, "count": len(apps)})
            return

        # ── CLAUDE CODE SUITE ──
        elif path == "/api/claude":
            info = get_claude_info()
            self.respond_json({"success": True, "info": info, "presets": CLAUDE_PRESETS})
            return

        # ── BIBLIOTHÈQUE VIVANTE BOARD ──
        elif path == "/api/board/stats":
            stats = get_board_stats()
            self.respond_json({"success": True, "stats": stats})
            return

        # ── MOISSON LOCOMOTIVE ──
        elif path == "/api/locomotive":
            try:
                conn = sqlite3.connect(os.path.join(JARVIS_DIR, "databases",
                                                "locomotive_moisson.db"))
                c = conn.cursor()
                c.execute("SELECT id, titre, url, taille_octets, date_moisson FROM pages_moissonnees ORDER BY id DESC LIMIT 100;")
                rows = [{"id": r[0], "titre": r[1], "url": r[2], "taille": r[3], "date": r[4]} for r in c.fetchall()]
                conn.close()
                self.respond_json({"success": True, "pages": rows})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "pages": []})
            return

        # ── FICHIERS STATIQUES WEB & PWA ──
        if path == "/" or path == "":
            path = "/index.html"

        file_path = os.path.join(WEB_DIR, path.lstrip("/"))
        if os.path.exists(file_path) and os.path.isfile(file_path):
            ctype = "text/html; charset=utf-8"
            if file_path.endswith(".js"): ctype = "application/javascript"
            elif file_path.endswith(".css"): ctype = "text/css"
            elif file_path.endswith(".png"): ctype = "image/png"
            elif file_path.endswith(".json"): ctype = "application/json"
            elif file_path.endswith(".svg"): ctype = "image/svg+xml"

            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            if "/vendor/" in path:
                self.send_header("Cache-Control", "public, max-age=604800")
            else:
                self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        if self.router_terminal(path, req_data=req_data):
            return

        # ── SYNCHRONISATION 1-CLIC ──
        if path == "/api/sync/run":
            auto_git = bool(req_data.get("auto_git", False))
            msg_commit = req_data.get("commit_message", "")
            res = trigger_synchronisation(auto_git_commit=auto_git, message_commit=msg_commit)
            self.respond_json(res)
            return

        # ── CRÉATION CHANTIER PRODUCTION ──
        elif path == "/api/chantiers/nouveau":
            besoin = req_data.get("besoin", "").strip()
            famille = req_data.get("famille", "GENERAL")
            domaine = req_data.get("domaine", "SYSTEM")
            res = creer_nouveau_chantier(besoin, famille=famille, domaine=domaine)
            self.respond_json(res)
            return

        # ── MISE À JOUR TÂCHE CHANTIER ──
        elif path == "/api/chantiers/tache":
            tache_id = int(req_data.get("id", 0))
            status = req_data.get("status", "fait")
            res = update_tache_production(tache_id, status)
            self.respond_json(res)
            return

        # ── ACTION CHANTIER PRODUCTION (PROD-*) ──
        elif path == "/api/chantiers/action":
            action = req_data.get("action", "avancement")
            run_id = req_data.get("run_id", "")
            cmd_map = {
                "detecter": f"~/jarvis/prod/bin/prod-detecter '{req_data.get('besoin', '')}'",
                "souvenir": f"~/jarvis/prod/bin/prod-souvenir '{run_id}'",
                "specialiser": f"~/jarvis/prod/bin/prod-specialiser '{run_id}'",
                "nourrir": f"~/jarvis/prod/bin/prod-nourrir '{run_id}'",
                "eclater": f"~/jarvis/prod/bin/prod-eclater '{run_id}'",
                "debattre": f"~/jarvis/prod/bin/prod-debattre '{run_id}'",
                "realiser": f"~/jarvis/prod/bin/prod-realiser '{run_id}'",
                "verifier": f"~/jarvis/prod/bin/prod-verifier '{run_id}'",
                "persister": f"~/jarvis/prod/bin/prod-persister '{run_id}'",
                "rappeler": f"~/jarvis/prod/bin/prod-rappeler '{run_id}'",
                "avancement": "~/jarvis/prod/bin/prod-avancement",
                "etat": "~/jarvis/prod/bin/prod-etat",
                "suggerer": "~/jarvis/prod/bin/prod-suggerer",
                "doctor": "~/jarvis/prod/bin/prod-doctor"
            }
            exec_cmd = cmd_map.get(action)
            if not exec_cmd:
                self.respond_json({"success": False, "error": f"Action inconnue: {action}"}, 400)
                return
            p = subprocess.run(["bash", "-lc", exec_cmd], capture_output=True, text=True, timeout=30)
            self.respond_json({
                "success": (p.returncode == 0),
                "stdout": p.stdout,
                "stderr": p.stderr,
                "code": p.returncode,
                "action": action,
                "run_id": run_id
            })
            return

        # ── CRÉATION DE TÂCHE ──
        elif path == "/api/tasks":
            title = req_data.get("title", "").strip()
            cat = req_data.get("category", "GÉNÉRAL")
            prio = int(req_data.get("priority", 1))
            if not title:
                self.respond_json({"success": False, "error": "Titre requis"}, 400)
                return
            ok = add_master_task(title, category=cat, priority=prio)
            self.respond_json({"success": ok})
            return

        # ── MISE À JOUR DE TÂCHE ──
        elif path == "/api/tasks/status":
            task_id = int(req_data.get("id", 0))
            status = req_data.get("status", "DONE")
            ok = update_master_task_status(task_id, status)
            self.respond_json({"success": ok})
            return

        # ── REQUÊTE SQL SÉCURISÉE ──
        elif path == "/api/sql/query":
            db_path = req_data.get("db_path", "")
            sql = req_data.get("sql", "")
            limit = int(req_data.get("limit", 50))
            res = execute_safe_query(db_path, sql, limit=limit)
            self.respond_json(res)
            return

        # ── RECHERCHE FTS5 BOARD ──
        elif path == "/api/board/search":
            query = req_data.get("query", "")
            limit = int(req_data.get("limit", 10))
            results = search_board_fts(query, limit=limit)
            self.respond_json({"success": True, "results": results, "count": len(results)})
            return

        # ── BUREAU GNOME — ACTION TRACÉE (LOOPBACK UNIQUEMENT) ──
        # Le serveur écoute sur 0.0.0.0 : piloter le bureau depuis le LAN serait un trou béant.
        # local_seulement() émet DÉJÀ le 403 — ne jamais répondre une seconde fois.
        elif path == "/api/bureau/action":
            if not self.local_seulement():
                return
            try:
                self.respond_json(run_bureau_action(
                    req_data.get("action", "constat"),
                    req_data.get("params", {}) or {}))
            except Exception as e:
                self.respond_json({"success": False, "error": f"{type(e).__name__}: {e}"}, 500)
            return

        # ── CDP ACTION (PORT 9222) ──
        elif path == "/api/cdp/action":
            action = req_data.get("action", "status")
            if action == "start":
                self.respond_json(start_cdp())
            elif action == "stop":
                self.respond_json(stop_cdp())
            elif action == "verify":
                self.respond_json(verify_cdp())
            else:
                self.respond_json(get_cdp_status())
            return

        # ── NOTION BACKUP SNAPSHOT ──
        elif path == "/api/notion/backup":
            self.respond_json(run_notion_backup_snapshot())
            return

        # ── CLAUDE PROMPT EXÉCUTION (AVEC FALLBACK SOUVERAIN 529) ──
        elif path == "/api/claude/run":
            prompt = req_data.get("prompt", "")
            force_local = bool(req_data.get("force_local", False))
            if not prompt:
                self.respond_json({"success": False, "error": "Prompt vide"}, 400)
                return
            res = run_claude_prompt(prompt, force_local=force_local)
            self.respond_json(res)
            return

        # ── LANCEMENT D'APPLICATION BUREAU ──
        elif path == "/api/apps/launch":
            exec_cmd = req_data.get("exec", "")
            if not exec_cmd:
                self.respond_json({"success": False, "error": "Commande vide"}, 400)
                return
            try:
                subprocess.Popen(["bash", "-lc", exec_cmd], start_new_session=True)
                self.respond_json({"success": True, "message": f"Lancé: {exec_cmd}"})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── STUDIO CRÉATION ──
        elif path == "/api/create":
            ctype = req_data.get("type", "linkedin")
            sujet = req_data.get("sujet", "Architecture IA Souveraine")

            prompts = {
                "linkedin": ("Tu es un expert en branding technologique et leadership IA. Rédige un post LinkedIn percutant avec accroches et puces concrètes.", f"Sujet: {sujet}"),
                "article": ("Tu es rédacteur en chef et architecte IA. Rédige un article technique structuré avec titres clairs.", f"Thème: {sujet}"),
                "prd": ("Tu es Lead Product Manager. Rédige un PRD exhaustif.", f"Spécification pour: {sujet}"),
                "code": ("Tu es Staff Software Engineer Python/Rust. Produis du code de production propre et typé.", f"Code demandé: {sujet}")
            }
            sys_p, u_p = prompts.get(ctype, ("Assistant IA", sujet))
            res = run_inference_engine(u_p, sys_prompt=sys_p, max_tokens=1200)

            if res.get("success"):
                os.makedirs(CONTENT_DIR, exist_ok=True)
                fn = f"{CONTENT_DIR}/{ctype}_{datetime.now():%Y%m%d_%H%M%S}.md"
                try:
                    with open(fn, "w", encoding="utf-8") as f:
                        f.write(f"# Création Cockpit — {ctype.upper()}\n\n{res['content']}")
                    res["saved_to"] = fn
                except Exception:
                    pass
            self.respond_json(res)
            return

        # ── PARAMÈTRES & CONFIGURATION ──
        elif path == "/api/settings":
            res = save_cockpit_settings(req_data)
            self.respond_json(res)
            return

        # ── TABLE RONDE SOUVERAINE & BROWSER OS ──
        elif path == "/api/table-ronde":
            question = req_data.get("question", "Stratégie opérationnelle globale du cluster.")
            inject_browser = bool(req_data.get("injecter_browser", True))
            inject_board = bool(req_data.get("injecter_board", True))
            selected_agents = req_data.get("agents", None)
            res = run_table_ronde_deliberation(
                question=question,
                injecter_browser=inject_browser,
                injecter_board=inject_board,
                agents_selectionnes=selected_agents
            )
            self.respond_json(res)
            return

        # ── SWAN STREAM ──
        elif path == "/api/swan":
            titre = req_data.get("titre", "Signal Cockpit")
            contenu = req_data.get("contenu", "Flux émis depuis le Cockpit Desktop.")
            script_path = os.path.expanduser("~/jarvis/scripts/swan_stream_engine.py")
            if os.path.exists(script_path):
                r = subprocess.run(["python3", script_path, titre, contenu], capture_output=True, text=True)
                self.respond_json({"success": (r.returncode == 0), "output": r.stdout or r.stderr})
            else:
                self.respond_json({"success": True, "output": f"Signal '{titre}' enregistré."})
            return

        # ── REPLAY & GUÉRISON ──
        elif path == "/api/replay":
            script = os.path.expanduser("~/jarvis/scripts/jarvis_full_session_replay.sh")
            if os.path.exists(script):
                subprocess.Popen(["bash", script])
            self.respond_json({"success": True, "message": "Rejeu complet 1-clic initié en arrière-plan."})
            return

        # ── CMD SHELL (LOCAL UNIQUEMENT) ──
        elif path == "/api/cmd":
            if not self.local_seulement():
                return
            cmd = req_data.get("cmd", "echo OK")
            res = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=25)
            self.respond_json({"stdout": res.stdout, "stderr": res.stderr, "code": res.returncode})
            return

        self.send_response(404)
        self.end_headers()


def main():
    os.makedirs(WEB_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CockpitHandler)
    print(f"🚀 JARVIS COCKPIT DESKTOP SERVER démarré sur http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
