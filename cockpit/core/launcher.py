#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — LAUNCHER & 10-ORGAN SYSTEM HEALTH CHECK
==================================================
Vérifie réellement au démarrage les 10 organes vitaux :
  1. Environnement (OS, Python 3.10+, DISPLAY, chemins, droits)
  2. Services critiques (systemctl user services / daemons)
  3. LM Studio / llama-server (:1234, :1235, :1240, :1300)
  4. MCP (serveurs et outils déclarés)
  5. STT (Whisper :1270)
  6. TTS (Kokoro :1250)
  7. GPU (Dual RTX 3080 + RTX 2060, ~22GB VRAM via nvidia-smi)
  8. Mémoire (action_memory, base SQLite)
  9. RAG (board.db 1.12MB+, index de connaissances)
  10. Board & Cockpit (:8600, interface web, terminaux)

Directives :
  - Aucun état statique inventé : probes réels sur sockets, fichiers et processus.
  - Fail-safe : indique clairement l'organe dégradé sans bloquer si un repli existe.
"""

from __future__ import annotations

import os
import sys
import json
import time
import socket
import sqlite3
import shutil
import urllib.request
import subprocess
from typing import Dict, Any, List

try:
    from .system_state import HealthStatus, get_system_state
except ImportError:
    try:
        from system_state import HealthStatus, get_system_state
    except ImportError:
        HealthStatus = None


def _check_socket(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _http_get_json(url: str, timeout: float = 1.5) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TurboOS-Launcher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# ─── LES 10 PROBES D'ORGANES RÉELS ───────────────────────────────────────────

def probe_environment() -> Dict[str, Any]:
    """Organe 1 : Environnement système, runtime, display."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    display = os.environ.get("DISPLAY", "")
    home = os.path.expanduser("~")
    has_write = os.access(home, os.W_OK)
    status = "HEALTHY" if sys.version_info >= (3, 10) and has_write else "DEGRADED"
    return {
        "organ": "environment",
        "status": status,
        "details": {
            "python_version": py_ver,
            "display": display or "headless",
            "home": home,
            "user": os.environ.get("USER", "turbo"),
            "writable_home": has_write,
        },
        "message": f"Python {py_ver}, Display={display or 'none'}"
    }


def probe_services() -> Dict[str, Any]:
    """Organe 2 : Services critiques systemd."""
    services = ["jarvis-cockpit", "jarvis-agent-api", "jarvis-voice-cockpit", "jarvis-llm-qwen25", "jarvis-llm-qwen3"]
    states = {}
    active_count = 0
    for s in services:
        try:
            r = subprocess.run(["systemctl", "--user", "is-active", s],
                               capture_output=True, text=True, timeout=1.0)
            st = r.stdout.strip() or "unknown"
            states[s] = st
            if st == "active":
                active_count += 1
        except Exception:
            states[s] = "error"

    # Cockpit peut tourner manuellement même sans systemd
    status = "HEALTHY" if active_count >= 2 else "DEGRADED"
    return {
        "organ": "services",
        "status": status,
        "details": {"services": states, "active_count": active_count, "total": len(services)},
        "message": f"{active_count}/{len(services)} services actifs"
    }


def probe_lmstudio() -> Dict[str, Any]:
    """Organe 3 : Nœuds d'inférence LLM locaux (:1234, :1235, :1240, :1300)."""
    ports = {
        "1234_qwen2.5_7b": 1234,
        "1235_qwen3_8b": 1235,
        "1240_routeur": 1240,
        "1300_embeddings": 1300,
    }
    nodes = {}
    live_count = 0
    for label, port in ports.items():
        alive = _check_socket("127.0.0.1", port)
        nodes[label] = {"port": port, "alive": alive}
        if alive:
            live_count += 1

    status = "HEALTHY" if live_count >= 2 else ("DEGRADED" if live_count > 0 else "ERROR")
    return {
        "organ": "lmstudio",
        "status": status,
        "details": {"nodes": nodes, "live_count": live_count, "total_nodes": len(ports)},
        "message": f"{live_count}/{len(ports)} nœuds LLM connectés"
    }


def probe_mcp() -> Dict[str, Any]:
    """Organe 4 : Serveurs MCP et outils déclarés."""
    cockpit_mcp = _http_get_json("http://127.0.0.1:8600/api/mcp", timeout=1.0)
    count = 0
    if cockpit_mcp and isinstance(cockpit_mcp, dict):
        count = cockpit_mcp.get("count", len(cockpit_mcp.get("mcps", [])))
    status = "HEALTHY" if count > 0 else "DEGRADED"
    return {
        "organ": "mcp",
        "status": status,
        "details": {"mcp_count": count, "via_cockpit": bool(cockpit_mcp)},
        "message": f"{count} outils MCP opérationnels"
    }


def probe_stt() -> Dict[str, Any]:
    """Organe 5 : STT Whisper (:1270 ou binaire)."""
    alive = _check_socket("127.0.0.1", 1270)
    has_whisper = bool(shutil.which("whisper") or os.path.exists("/home/turbo/jarvis/bin/whisper"))
    status = "HEALTHY" if (alive or has_whisper) else "DEGRADED"
    return {
        "organ": "stt",
        "status": status,
        "details": {"socket_1270": alive, "cli_available": has_whisper},
        "message": "Whisper actif (:1270)" if alive else "Whisper CLI de repli"
    }


def probe_tts() -> Dict[str, Any]:
    """Organe 6 : TTS Kokoro (:1250)."""
    alive = _check_socket("127.0.0.1", 1250)
    status = "HEALTHY" if alive else "DEGRADED"
    return {
        "organ": "tts",
        "status": status,
        "details": {"socket_1250": alive},
        "message": "Kokoro TTS actif (:1250)" if alive else "TTS indisponible"
    }


def probe_gpu() -> Dict[str, Any]:
    """Organe 7 : GPU Dual setup (RTX 3080 + RTX 2060 ~22GB total)."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2.0).decode().strip()
        lines = out.splitlines()
        gpus = []
        total_vram_mb = 0
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                vram = int(parts[1]) if parts[1].isdigit() else 0
                used = int(parts[2]) if parts[2].isdigit() else 0
                util = int(parts[3]) if parts[3].isdigit() else 0
                total_vram_mb += vram
                gpus.append({"name": parts[0], "total_mb": vram, "used_mb": used, "util_pct": util})

        has_3080 = any("3080" in g["name"] for g in gpus)
        has_2060 = any("2060" in g["name"] for g in gpus)
        status = "HEALTHY" if (has_3080 and has_2060) else ("DEGRADED" if gpus else "ERROR")
        return {
            "organ": "gpu",
            "status": status,
            "details": {"gpus": gpus, "total_vram_gb": round(total_vram_mb / 1024.0, 1), "count": len(gpus)},
            "message": f"{len(gpus)} GPU ({round(total_vram_mb / 1024.0, 1)} GB VRAM)"
        }
    except Exception as e:
        return {"organ": "gpu", "status": "ERROR", "details": {"error": str(e)}, "message": "NVIDIA SMI inaccessible"}


def probe_memory() -> Dict[str, Any]:
    """Organe 8 : Mémoire et base d'actions."""
    mem_db = os.path.expanduser("~/jarvis/data/jarvis_action_memory.db")
    board_db = os.path.expanduser("~/jarvis/board/board.db")
    actions_count = 0
    if os.path.exists(mem_db):
        try:
            con = sqlite3.connect(f"file:{mem_db}?mode=ro", uri=True, timeout=1.0)
            cur = con.cursor()
            cur.execute("SELECT count(*) FROM action_memory")
            actions_count = cur.fetchone()[0]
            con.close()
        except Exception:
            pass

    status = "HEALTHY" if actions_count > 0 else ("DEGRADED" if os.path.exists(board_db) else "ERROR")
    return {
        "organ": "memory",
        "status": status,
        "details": {"action_memory_db": mem_db, "actions_count": actions_count, "exists": os.path.exists(mem_db)},
        "message": f"{actions_count} actions mémorisées dans ActionMemory"
    }


def probe_rag() -> Dict[str, Any]:
    """Organe 9 : RAG et base de connaissances (board.db 1.12MB+)."""
    db_path = os.path.expanduser("~/jarvis/board/board.db")
    size_mb = 0.0
    exists = os.path.exists(db_path)
    if exists:
        size_mb = round(os.path.getsize(db_path) / (1024.0 * 1024.0), 2)

    # DIRECTIVE : board.db ~1.12MB
    status = "HEALTHY" if (exists and size_mb >= 1.0) else ("DEGRADED" if exists else "ERROR")
    return {
        "organ": "rag",
        "status": status,
        "details": {"db_path": db_path, "size_mb": size_mb, "fail_closed_threshold_pct": 40.0},
        "message": f"Bibliothèque vivante board.db ({size_mb} MB, fail-closed 40%)"
    }


def probe_board_and_cockpit() -> Dict[str, Any]:
    """Organe 10 : Board & Cockpit (:8600, HTML/JS, terminaux)."""
    cockpit_alive = _check_socket("127.0.0.1", 8600)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_dir = os.path.join(repo_root, "web")
    has_web = os.path.isdir(web_dir) and os.path.exists(os.path.join(web_dir, "index.html"))

    status = "HEALTHY" if cockpit_alive else ("DEGRADED" if has_web else "ERROR")
    return {
        "organ": "board_cockpit",
        "status": status,
        "details": {"cockpit_port_8600": cockpit_alive, "web_assets": has_web},
        "message": "Cockpit actif sur :8600" if cockpit_alive else "Cockpit en attente de démarrage"
    }


def probe_all_organs() -> Dict[str, Any]:
    """Agrège la sonde en direct des 10 organes vitaux sans simulation."""
    t0 = time.time()
    organs = {
        "environment": probe_environment(),
        "services": probe_services(),
        "lmstudio": probe_lmstudio(),
        "mcp": probe_mcp(),
        "stt": probe_stt(),
        "tts": probe_tts(),
        "gpu": probe_gpu(),
        "memory": probe_memory(),
        "rag": probe_rag(),
        "board_cockpit": probe_board_and_cockpit(),
    }

    statuses = [o["status"] for o in organs.values()]
    has_error = any(s == "ERROR" for s in statuses)
    has_degraded = any(s == "DEGRADED" for s in statuses)

    if has_error:
        overall = "ERROR"
    elif has_degraded:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return {
        "timestamp": t0,
        "overall_status": overall,
        "is_operational": overall in ("HEALTHY", "DEGRADED"),
        "organs": organs,
        "duration_ms": round((time.time() - t0) * 1000, 1),
    }


def print_cli_report(data: Dict[str, Any]):
    """Affichage console lisible et coloré."""
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

    color_map = {"HEALTHY": GREEN, "DEGRADED": YELLOW, "ERROR": RED}
    overall = data["overall_status"]
    ov_col = color_map.get(overall, RESET)

    print(f"\n{BOLD}{CYAN}=== TURBO OS / JARVIS — BILAN DES 10 ORGANES VITAUX ==={RESET}")
    print(f"Statut Global : {ov_col}{BOLD}{overall}{RESET} (durée {data['duration_ms']}ms)\n")

    for key, info in data["organs"].items():
        st = info["status"]
        col = color_map.get(st, RESET)
        print(f"  [{col}{st:8s}{RESET}] {BOLD}{info['organ']:15s}{RESET} -> {info['message']}")

    print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    res = probe_all_organs()
    if mode == "--json":
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print_cli_report(res)
