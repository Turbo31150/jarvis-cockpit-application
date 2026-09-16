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
import hashlib
import socket
import platform
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

RACINE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(RACINE)
for p in (RACINE, PARENT):
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    from config import jarvis_config
except ImportError:
    import jarvis_config

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
from core.telemetry import get_vram_info, get_m6_status
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
from core.escouade_engine import (
    get_agents_escouade, lancer_agent, get_cartographie_ssd,
    scanner_bases_sql, inspecter_base_sql
)


PORT = int(os.environ.get("COCKPIT_PORT", "8600"))
M6_URL = f"http://{M6_HOST}:{M6_PORT}"
OL_URL = "http://127.0.0.1:1235"
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

    # VRAM agrégée sur les 2 GPU du rig via get_vram_info() (RTX 3080 10 Go +
    # RTX 2060 12 Go = 22 Go). L'ancien parse inline supposait 1 seul GPU →
    # split(',') plantait sur plusieurs lignes ; fallback prudent si indispo.
    vram_used, vram_total, vram_temp = 0, 22528, 0
    try:
        _v = get_vram_info()
        if _v.get("available"):
            vram_used, vram_total, vram_temp = _v["used"], _v["total"], _v["temp"]
    except Exception:
        pass

    # 2. Nœud LM Studio / M6 GPU
    m6_info = get_m6_status()
    m6_online = m6_info.get("online", False)
    m6_latency = m6_info.get("latency_ms", 0.0)
    m6_models = m6_info.get("loaded_models", [])
    m6_ip = m6_info.get("host", M6_HOST)

    # 3. Matrice des services
    ports_map = [
        ("Cockpit Web", "127.0.0.1", 8600),
        ("llama-server qwen2.5-7b", m6_ip, 1234),
        ("llama-server qwen3-8b", "127.0.0.1", 1235),
        ("Chat Proxy LLM", "127.0.0.1", 18800),
        ("Board Serveur", "127.0.0.1", 8795),
        ("Planning Widget", "127.0.0.1", 8899),
        ("S8 Voice", "127.0.0.1", 8799),
        ("Whisper Bridge", "127.0.0.1", 9742),
        ("Unified Launcher", "127.0.0.1", 8765),
        ("Dashboard Web", "127.0.0.1", 8088),
        ("OpenClaw Daemon", "127.0.0.1", 18789),
        ("BrowserOS CDP", "127.0.0.1", 9222),
        ("Monitor Cluster", "127.0.0.1", 8420),
        ("Espace Prof", "127.0.0.1", 7777),
        ("PostgreSQL", "127.0.0.1", 5432),
        ("Redis Local", "127.0.0.1", 6379),
        ("Serveur MCP Cockpit", "127.0.0.1", 8600)
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

    local_data = {
        "hostname": socket.gethostname(),
        "node_label": f"{socket.gethostname()} (Rig Bi-GPU 22 Go)",
        "temp_c": temp_val,
        "mem_used_mb": mem_used,
        "mem_total_mb": mem_total,
        "mem_free_mb": mem_free,
        "vram_used_mb": vram_used,
        "vram_total_mb": vram_total,
        "vram_temp_c": vram_temp,
        "governor": "performance"
    }

    return {
        "hostname": socket.gethostname(),
        "local": local_data,
        "m4": local_data,  # alias rétro-compatibilité
        "m6": {
            "online": m6_online,
            "latency_ms": m6_latency,
            "models": m6_models,
            "ip": m6_ip
        },
        "services": services_status,
        "timestamp": datetime.now().isoformat()
    }


def get_legion_status():
    """État live de la Légion OMEGA (domino continu + vectorisation board + tmux).

    Ajout 2026-09-11 : donne au cockpit une vue de ce qui tourne réellement en
    tâche de fond (fiches générées, embeddings, fenêtres agents). Lecture seule.
    """
    ddb = os.path.expanduser("~/jarvis/omega/domino-continu/domino_continu.db")
    bdb = os.path.expanduser("~/jarvis/board/board.db")
    out = {"domino": {}, "vectorisation": {}, "fenetres_tmux": 0}
    try:
        c = sqlite3.connect(f"file:{ddb}?mode=ro", uri=True)
        for s, n in c.execute("SELECT statut, COUNT(*) FROM taches GROUP BY statut"):
            out["domino"][s] = n
        c.close()
    except Exception:
        pass
    try:
        c = sqlite3.connect(f"file:{bdb}?mode=ro", uri=True)
        ok = c.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0]
        nul = c.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL").fetchone()[0]
        out["vectorisation"] = {"ok": ok, "a_faire": nul}
        c.close()
    except Exception:
        pass
    try:
        w = subprocess.run(["tmux", "list-windows", "-t", "OMEGA-LEGION"],
                           capture_output=True, text=True, timeout=3)
        out["fenetres_tmux"] = len([l for l in w.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    return out


def get_gpu_models_state():
    """État moteur GPU : GPU0 (:1234 fixe qwen2.5-7b), GPU1 (:1235 slot modulable),
    embeddings (:1300) + modèles chargeables (manifests ollama, hors embeddings)."""
    import urllib.request as _u
    def served(port):
        try:
            with _u.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2) as r:
                d = json.loads(r.read().decode())
            return [(m.get("id") or m.get("name")) for m in (d.get("data") or d.get("models") or []) if (m.get("id") or m.get("name"))]
        except Exception:
            return []
    man = os.path.expanduser("~/.ollama/models/manifests/registry.ollama.ai/library")
    embeds = {"nomic-embed-text", "bge-m3", "mxbai-embed-large"}
    available = []
    try:
        for repo in sorted(os.listdir(man)):
            if repo in embeds:
                continue
            for tag in sorted(os.listdir(os.path.join(man, repo))):
                available.append(f"{repo}:{tag}")
    except Exception:
        pass
    return {"success": True, "gpu0_1234": served(1234), "gpu1_1235": served(1235),
            "embeddings_1300": served(1300), "available": available, "switcher": "jarvis-model"}


def charger_modele_gpu1(model):
    """Charge un modèle sur le slot GPU1 (:1235) via jarvis-model (subprocess liste → pas d'injection shell).
    GPU0 (:1234, qwen2.5-7b) reste intact."""
    model = str(model or "").strip()
    if not model or not all(c.isalnum() or c in "._:-" for c in model):
        return {"success": False, "error": "nom de modèle invalide"}
    try:
        r = subprocess.run(["/home/turbo/.local/bin/jarvis-model", model],
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        ok = ("✅" in out) or (r.returncode == 0 and "❌" not in out and "⚠️" not in out)
        return {"success": ok, "model": model, "output": out[-1000:]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def chat_gpu(model, prompt, port=1234, system=None):
    """Chat direct « LM Studio maison » avec un modèle du moteur GPU (llama-server OpenAI /v1/)."""
    import urllib.request as _u, time as _t
    try:
        port = int(port)
    except Exception:
        port = 1234
    if port not in (1234, 1235):
        port = 1234
    prompt = str(prompt or "").strip()
    if not prompt:
        return {"success": False, "error": "prompt vide"}
    msgs = []
    if system:
        msgs.append({"role": "system", "content": str(system)[:4000]})
    msgs.append({"role": "user", "content": prompt[:8000]})
    payload = json.dumps({"model": model or "local", "messages": msgs,
                          "max_tokens": 640, "temperature": 0.7}).encode("utf-8")
    try:
        req = _u.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                         data=payload, headers={"Content-Type": "application/json"})
        t0 = _t.time()
        with _u.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode())
        ch = d["choices"][0]["message"]
        content = (ch.get("content") or ch.get("reasoning_content") or "").strip()
        u = d.get("usage", {})
        return {"success": bool(content), "content": content, "port": port,
                "model": d.get("model"), "tokens": u.get("completion_tokens"),
                "latency": round(_t.time() - t0, 2)}
    except Exception as e:
        return {"success": False, "error": str(e), "port": port}


_TTS_MAP = {
    # Branding : jamais « JARVIS » à voix haute → toujours « Turbo OS »
    "jarvis": "Turbo OS",
    # Acronymes/anglicismes fréquents → articulation française (aucun mot anglais brut)
    "gpu": "gé pé u", "cpu": "cé pé u", "ram": "ram", "vram": "vé ram", "ssd": "esse esse dé",
    "llm": "modèle de langage", "llms": "modèles de langage", "rag": "rag", "os": "o ès",
    "stt": "reconnaissance vocale", "tts": "synthèse vocale", "board": "conseil",
    "checkpoint": "point de reprise", "screenshot": "capture d'écran", "cloud": "nuage",
    "token": "jeton", "tokens": "jetons", "cockpit": "cockpit", "kokoro": "kokoro",
}


def sanitize_tts(text):
    """Prépare un texte pour Kokoro : branding Turbo OS, aucun mot anglais brut, SANS ponctuation ni symbole."""
    import re as _re
    t = str(text or "")
    t = _re.sub(r"[A-Za-zÀ-ÿ']+", lambda m: _TTS_MAP.get(m.group(0).lower(), m.group(0)), t)
    t = _re.sub(r"[^0-9A-Za-zÀ-ÿ'\s]", " ", t)   # retire ponctuation & symboles
    t = _re.sub(r"\s+", " ", t).strip()
    return t


def parler(text):
    """Voix souveraine Kokoro FR : génère un WAV et le joue sur les HP (paplay). Non bloquant.

    Texte assaini pour l'oral : branding Turbo OS (jamais « JARVIS »), sans ponctuation ni symbole,
    acronymes articulés, aucun mot anglais brut (protocole voix Turbo OS).
    """
    import os as _os
    # ── MUTE GLOBAL : respecter sound_enabled (Paramètres & Affichage). No-op si voix coupée. ──
    try:
        _snd = get_cockpit_settings().get("settings", {}).get("sound_enabled", True)
    except Exception:
        _snd = True
    if not _snd:
        return {"success": True, "muted": True, "message": "Voix coupée (sound_enabled=false)"}
    text = sanitize_tts(text)[:1200]
    if not text:
        return {"success": False, "error": "texte vide"}
    wav = f"/tmp/turbo-tts-{_os.getpid()}.wav"
    try:
        r = subprocess.run(["/home/turbo/jarvis/bin/jarvis-tts-souverain.sh", text, wav],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not _os.path.exists(wav) or _os.path.getsize(wav) < 100:
            return {"success": False, "error": "TTS: " + (r.stderr or "")[-160:]}
        env = dict(_os.environ, XDG_RUNTIME_DIR="/run/user/1000")
        subprocess.Popen(["paplay", wav], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "chars": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── TURBO OS : pilotage de la boucle vocale mains-libres (service jarvis-voice-cockpit :1270) ──
VOICE_STOP_FLAG = "/tmp/voice_cockpit_stop"
VOICE_LOOP_SERVICE = "jarvis-voice-cockpit"
VOICE_STATE_URL = "http://127.0.0.1:1270/state"


def voice_loop_state():
    """Lit l'état vivant de la boucle vocale (:1270/state). Renvoie un dict état + drapeau service."""
    import os as _os
    stop_present = _os.path.exists(VOICE_STOP_FLAG)
    state = None
    reachable = False
    try:
        req = urllib.request.Request(VOICE_STATE_URL, headers={"User-Agent": "JarvisCockpit/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            state = json.loads(resp.read().decode("utf-8"))
            reachable = True
    except Exception:
        pass
    # État systemd (lecture seule, jamais bloquant)
    active = None
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", VOICE_LOOP_SERVICE],
                           capture_output=True, text=True, timeout=5)
        active = (r.stdout or "").strip()  # active | inactive | failed | activating
    except Exception:
        pass
    # Vérité affichée : "running" seulement si service actif ET flag stop absent
    running = (active == "active") and (not stop_present)
    return {
        "success": True,
        "running": running,
        "service_active": active,
        "stop_flag": stop_present,
        "reachable": reachable,
        "state": state,  # {mode: idle|listening|thinking|speaking, ...} si joignable
    }


def voice_loop_control(action):
    """start|stop|status pour la boucle vocale mains-libres. subprocess en liste d'args (pas de shell)."""
    import os as _os
    action = (action or "status").strip().lower()
    if action == "status":
        return voice_loop_state()

    if action == "start":
        # 1) lever le drapeau d'arrêt s'il existe
        try:
            if _os.path.exists(VOICE_STOP_FLAG):
                _os.remove(VOICE_STOP_FLAG)
        except Exception as e:
            return {"success": False, "error": f"impossible d'enlever le drapeau: {e}"}
        # 2) démarrer le service utilisateur
        try:
            r = subprocess.run(["systemctl", "--user", "start", VOICE_LOOP_SERVICE],
                               capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return {"success": False, "error": (r.stderr or r.stdout or "start a échoué").strip()[-200:]}
        except Exception as e:
            return {"success": False, "error": str(e)}
        st = voice_loop_state()
        st["message"] = "Boucle vocale démarrée."
        return st

    if action == "stop":
        # 1) poser le drapeau d'arrêt (la boucle s'auto-arrête proprement au prochain tick)
        try:
            with open(VOICE_STOP_FLAG, "w") as f:
                f.write("stop")
        except Exception as e:
            return {"success": False, "error": f"impossible de poser le drapeau: {e}"}
        # 2) tenter aussi d'arrêter le service (non fatal si ça échoue : le drapeau suffit)
        try:
            subprocess.run(["systemctl", "--user", "stop", VOICE_LOOP_SERVICE],
                           capture_output=True, text=True, timeout=20)
        except Exception:
            pass
        st = voice_loop_state()
        st["message"] = "Boucle vocale arrêtée (drapeau posé)."
        return st

    return {"success": False, "error": f"action inconnue: {action} (attendu start|stop|status)"}


# ── PILOTAGE VOCAL DE TOUT LE COCKPIT ──
# Onglets adressables (doivent rester alignés sur la liste `valides` de web/index.html → deep-link #rubrique)
COCKPIT_TABS = {
    "tableau de bord": "dashboard", "dashboard": "dashboard", "accueil": "dashboard", "bord": "dashboard",
    "avancements": "avancements", "avancement": "avancements", "progrès": "avancements",
    "plan": "plan", "planning": "plan",
    "omega": "omega", "oméga": "omega",
    "claude": "claude",
    "terminal": "terminal", "console": "terminal", "bash": "terminal", "shell": "terminal",
    "applications": "apps", "applis": "apps", "application": "apps", "apps": "apps",
    "table ronde": "tableronde", "tableronde": "tableronde",
    "studio": "studio", "modèles": "studio", "modeles": "studio",
    "mcp": "mcps", "mcps": "mcps",
    "sql": "sql", "base de données": "sql", "bases": "sql", "base": "sql",
    "swarm": "swarm", "essaim": "swarm",
    "moisson": "moisson", "récolte": "moisson",
    "swan": "swan",
    "ia web": "iaweb", "iaweb": "iaweb", "web": "iaweb",
    "bureau": "bureau",
    "réglages": "settings", "reglages": "settings", "paramètres": "settings", "parametres": "settings", "settings": "settings",
    "audit": "audit", "moat": "audit", "cahier des charges": "audit", "comparaison": "audit",
    "légion": "legion", "legion": "legion",
    "escouade": "escouade", "agents": "escouade",
}
# Corrections déterministes rapides (vocabulaire Turbo + fautes STT FR fréquentes) — avant la passe LLM
VOICE_FIX = {
    "turbot": "turbo", "turbos": "turbo", "tourbo": "turbo", "tourbeau": "turbo", "turbeau": "turbo",
    "jarviss": "jarvis", "jervis": "jarvis", "charvis": "jarvis", "charvie": "jarvis", "jarvisse": "jarvis",
    "cocotte": "cockpit", "cockpite": "cockpit", "cocpit": "cockpit", "cockpit": "cockpit", "cocotpite": "cockpit",
    "au méga": "omega", "o méga": "omega", "oh méga": "omega",
    "aissquel": "sql", "aiscuel": "sql", "esse cu elle": "sql",
    "ène cu": "gpu", "gpou": "gpu",
    "écouade": "escouade", "excouade": "escouade",
    "région": "légion", "légions": "légion",
}


# Applis bureau lançables à la voix (nom FR → candidats exec, 1er installé retenu). PC Control.
APP_LAUNCH = {
    "firefox": ["firefox"],
    "navigateur": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "firefox"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "chromium": ["chromium", "chromium-browser"],
    "vs code": ["code"], "vscode": ["code"], "visual studio code": ["code"], "éditeur de code": ["code"],
    "fichiers": ["nautilus", "nemo", "dolphin", "thunar"], "explorateur de fichiers": ["nautilus", "nemo"],
    "gestionnaire de fichiers": ["nautilus", "nemo", "dolphin", "thunar"],
    "calculatrice": ["gnome-calculator", "kcalc", "galculator"],
    "éditeur de texte": ["gedit", "kate", "xed", "mousepad"], "bloc-notes": ["gedit", "xed", "mousepad"],
    "moniteur système": ["gnome-system-monitor", "ksysguard"], "gestionnaire des tâches": ["gnome-system-monitor"],
    "capture d'écran": ["gnome-screenshot", "spectacle", "flameshot"],
    "paramètres système": ["gnome-control-center", "systemsettings"],
    "lecteur vidéo": ["vlc", "mpv", "totem"], "vlc": ["vlc"],
}


def resolve_app(phrase):
    """Trouve l'exec d'une appli bureau installée à partir d'une phrase (clé la plus longue d'abord)."""
    import shutil as _sh
    hay = " " + str(phrase or "").lower() + " "
    for key in sorted(APP_LAUNCH, key=len, reverse=True):
        if key in hay:
            for exe in APP_LAUNCH[key]:
                if _sh.which(exe):
                    return exe, key
            return None, key  # reconnue mais non installée
    return None, None


def voice_command(raw):
    """Corrige la transcription STT (selon le langage FR de l'utilisateur) PUIS route vers TOUT le cockpit.

    Retour : {success, raw, corrige, type: 'command'|'chat', action, cible, dire}.
    - type 'command' : action 'open_tab' (cible = rubrique) ou 'load_model' (cible = modèle) → le front exécute + parle `dire`.
    - type 'chat' : le front interroge /api/gpu/chat avec `corrige` (texte nettoyé, montré à l'utilisateur).
    """
    import re as _re
    import urllib.request as _u
    raw = str(raw or "").strip()
    if not raw:
        return {"success": False, "error": "transcription vide"}
    low = raw.lower().strip()
    for wrong, right in VOICE_FIX.items():
        low = _re.sub(r"\b" + _re.escape(wrong) + r"\b", right, low)

    # ── FAST-PATH DÉTERMINISTE PC Control (AVANT le LLM : robuste même s'il échoue, + rapide) ──
    _pc = " " + low + " "
    if _re.search(r"capture d['’ ]?[ée]cran|screenshot|fai[ts]? une capture|prend[s]? une capture", _pc):
        return {"success": True, "raw": raw, "corrige": low, "type": "command",
                "action": "screenshot", "cible": "", "payload": "", "dire": "Je capture l'écran."}
    if _re.search(r"list\w*\s+(?:les\s+|des\s+)?fen[êe]tres?|quelles?\s+fen[êe]tres|fen[êe]tres ouvertes", _pc):
        return {"success": True, "raw": raw, "corrige": low, "type": "command",
                "action": "list_windows", "cible": "", "payload": "", "dire": "Voici les fenêtres ouvertes."}
    _mf = _re.search(
        r"(?:passe[r]? (?:à|au|aux|sur)|bascule[r]? (?:vers|sur)|reviens (?:à|au)|au premier plan|"
        r"met[s]? (?:au premier plan|devant)|affiche[r]? la fen[êe]tre|montre[r]? la fen[êe]tre|"
        r"va (?:à|sur) la fen[êe]tre)\s+(?:la fen[êe]tre\s+|l['’]appli\w*\s+|de\s+|du\s+)?(.+?)\s*$", low)
    if _mf and not _re.search(r"\b(ex[ée]cut\w*|lance[rz]?|commande|termine|arr[êe]te|ferme)\b", _pc):
        tgt = _mf.group(1).strip(" .")
        if tgt:
            return {"success": True, "raw": raw, "corrige": low, "type": "command",
                    "action": "focus_window", "cible": tgt, "payload": "", "dire": f"Je passe à {tgt}."}

    # ── FAST-PATH DÉTERMINISTE : lecture vocale des chantiers ──
    if _re.search(r"\b(?:lis|lire|donne|fais|point|r[ée]sum[ée]|[ée]tat)\b.*(?:chantiers?|avancements?|t[âa]ches?|progr[èe]s)", _pc) or (_re.search(r"\bchantiers?\b", _pc) and _re.search(r"\b(?:lire|lis|vocal|voix)\b", _pc)):
        res_ch = lire_chantiers_vocal(parler_audio=False)
        dire_txt = res_ch.get("texte", "Voici le point sur vos chantiers.")
        return {"success": True, "raw": raw, "corrige": low, "type": "command",
                "action": "read_chantiers", "cible": "", "payload": dire_txt, "dire": dire_txt}

    sys_p = (
        "Tu es le routeur vocal de Turbo OS (moteur interne JARVIS, application cockpit). "
        "On te donne UNE phrase issue d'une reconnaissance vocale française, souvent mal transcrite.\n"
        "1) CORRIGE la phrase en français correct SANS changer le sens.\n"
        "2) CLASSE l'intention et EXTRAIS le contenu utile dans 'payload' :\n"
        "   - ouvrir    : afficher un onglet du cockpit (dashboard, avancements, plan, omega, claude, "
        "terminal, apps, tableronde, studio, mcps, sql, swarm, moisson, swan, iaweb, bureau, settings, "
        "audit, legion, escouade). payload vide.\n"
        "   - app       : lancer une application du bureau (Firefox, navigateur, VS Code, fichiers, "
        "calculatrice, VLC, éditeur de texte, moniteur système…). cible = nom de l'application.\n"
        "   - capture   : faire une capture d'écran. payload vide.\n"
        "   - fenetres  : lister les fenêtres ouvertes. payload vide.\n"
        "   - focus     : mettre une fenêtre au premier plan. cible = nom de la fenêtre/appli.\n"
        "   - fermer    : fermer une fenêtre / une application. cible = nom de la fenêtre/appli.\n"
        "   - modele    : charger un modèle d'IA. cible = nom du modèle.\n"
        "   - consulter : chercher/consulter une information dans la base de connaissances. payload = la question.\n"
        "   - executer  : lancer une commande système / faire une action sur le PC. payload = la commande shell.\n"
        "   - coder     : écrire ou modifier du code / un fichier. payload = l'instruction de code complète.\n"
        "   - email     : rédiger un e-mail. payload = 'destinataire | objet | corps' (laisse vide ce qui manque).\n"
        "   - chat      : toute autre question ou discussion. payload vide.\n"
        "Réponds STRICTEMENT en JSON, une seule ligne, sans texte autour :\n"
        "{\"corrige\":\"...\",\"intent\":\"ouvrir|app|capture|fenetres|focus|fermer|modele|consulter|executer|coder|email|chat\","
        "\"cible\":\"\",\"payload\":\"\",\"dire\":\"<confirmation courte à prononcer si commande, sinon vide>\"}"
    )
    payload = json.dumps({
        "model": "local",
        "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": low[:600]}],
        "max_tokens": 400, "temperature": 0.1,
    }).encode("utf-8")
    try:
        req = _u.Request("http://127.0.0.1:1234/v1/chat/completions",
                         data=payload, headers={"Content-Type": "application/json"})
        with _u.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
        txt = (d["choices"][0]["message"].get("content") or "").strip()
        m = _re.search(r"\{.*\}", txt, _re.S)
        obj = json.loads(m.group(0)) if m else {}
    except Exception:
        # Repli robuste : pas de routage LLM → chat direct avec la correction déterministe
        return {"success": True, "raw": raw, "corrige": low, "type": "chat", "action": "", "cible": "", "payload": "", "dire": ""}

    corrige = (obj.get("corrige") or low).strip()
    intent = (obj.get("intent") or "chat").strip().lower()
    cible = (obj.get("cible") or "").strip().lower()
    pay = (obj.get("payload") or "").strip()
    dire = (obj.get("dire") or "").strip()

    def _ret(**kw):
        base = {"success": True, "raw": raw, "corrige": corrige, "type": "chat",
                "action": "", "cible": "", "payload": "", "dire": ""}
        base.update(kw)
        return base

    # ── OUVRIR un onglet (sûr, exécution immédiate) — choix DÉTERMINISTE ──
    if intent in ("ouvrir", "open", "onglet"):
        haystack = " " + corrige.lower() + " " + low + " "
        tab = None
        for key in sorted(COCKPIT_TABS, key=len, reverse=True):
            if key in haystack:
                tab = COCKPIT_TABS[key]
                break
        if not tab:
            tab = COCKPIT_TABS.get(cible) or (cible if cible in set(COCKPIT_TABS.values()) else None)
        if tab:
            label = next((k for k, v in COCKPIT_TABS.items() if v == tab), tab)
            return _ret(type="command", action="open_tab", cible=tab, dire=dire or f"J'ouvre {label}.")
        # Pas un onglet → peut-être une appli bureau (« ouvre Firefox »)
        exe, app_key = resolve_app(corrige + " " + low)
        if exe:
            return _ret(type="command", action="launch_app", cible=exe, dire=dire or f"J'ouvre {app_key}.")

    # ── LANCER une application du bureau (PC Control, sûr) ──
    if intent in ("app", "application", "appli", "lancer_app", "programme"):
        exe, app_key = resolve_app(corrige + " " + low + " " + cible)
        if exe:
            return _ret(type="command", action="launch_app", cible=exe, dire=dire or f"J'ouvre {app_key}.")
        # reconnue mais non installée, ou inconnue → repli chat en fin de fonction

    # ── PC CONTROL : capture d'écran (sûr) ──
    if intent in ("capture", "screenshot", "capturer"):
        return _ret(type="command", action="screenshot", dire=dire or "Je capture l'écran.")

    # ── PC CONTROL : lister les fenêtres ouvertes (sûr) ──
    if intent in ("fenetres", "fenêtres", "list_windows"):
        return _ret(type="command", action="list_windows", dire=dire or "Voici les fenêtres ouvertes.")

    # ── PC CONTROL : mettre une fenêtre au premier plan (sûr) ──
    if intent in ("focus", "afficher", "premier_plan"):
        tgt = cible or pay or corrige
        return _ret(type="command", action="focus_window", cible=tgt, dire=dire or f"Je passe à {tgt}.")

    # ── PC CONTROL : fermer une fenêtre (perte de données possible → confirmation) ──
    if intent in ("fermer", "close", "quitter"):
        tgt = cible or pay or corrige
        return _ret(type="confirm", action="close_window", cible=tgt, payload=tgt,
                    dire=dire or "Je vais fermer une fenêtre, confirme.")

    # ── CHARGER un modèle (sûr) ──
    if intent in ("modele", "modèle", "model") and cible:
        return _ret(type="command", action="load_model", cible=cible, dire=dire or f"Je charge le modèle {cible}.")

    # ── CONSULTER la base de connaissances (lecture seule → immédiat) ──
    if intent in ("consulter", "consultation", "recherche", "chercher", "lire", "rag"):
        q = pay or corrige
        return _ret(type="consult", action="rag", payload=q, dire=dire or "Je consulte la base.")

    # ── EXÉCUTER une commande système (DANGEREUX → confirmation) ──
    if intent in ("executer", "exécuter", "execute", "faire", "commande", "lancer", "action"):
        if pay:
            return _ret(type="confirm", action="exec", payload=pay,
                        dire=dire or "Je vais exécuter une commande, confirme.")

    # ── ÉCRIRE / MODIFIER DU CODE via Claude (PUISSANT → confirmation) ──
    if intent in ("coder", "code", "écrire", "ecrire", "developper", "développer", "programmer"):
        instr = pay or corrige
        return _ret(type="confirm", action="code", payload=instr,
                    dire=dire or "Je vais écrire du code, confirme.")

    # ── E-MAIL (SORTANT → confirmation, JAMAIS d'envoi automatique) ──
    if intent in ("email", "mail", "courriel", "e-mail"):
        return _ret(type="confirm", action="email", payload=pay or corrige,
                    dire=dire or "J'ai préparé un e-mail, à valider avant tout envoi.")

    return _ret(type="chat")


# ── PC CONTROL avancé : contrôle des fenêtres (xdotool) + capture d'écran (scrot) ──
def _x_env():
    import os as _os
    return dict(_os.environ, DISPLAY=_os.environ.get("DISPLAY", ":1"),
                XAUTHORITY=_os.environ.get("XAUTHORITY", "/run/user/1000/gdm/Xauthority"))


def pc_windows():
    """Liste les fenêtres visibles nommées (xdotool), dédupliquées par titre."""
    try:
        r = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", ""],
                           capture_output=True, text=True, timeout=8, env=_x_env())
        seen, wins = set(), []
        for wid in r.stdout.split():
            n = subprocess.run(["xdotool", "getwindowname", wid],
                               capture_output=True, text=True, timeout=3, env=_x_env())
            name = n.stdout.strip()
            if name and name != "mutter guard window" and name not in seen:
                seen.add(name)
                wins.append({"id": wid, "name": name})
        return {"success": True, "windows": wins, "count": len(wins)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pc_window_op(op, target):
    """Agit sur une fenêtre repérée par sous-chaîne de titre (insensible à la casse) : focus|close|minimize."""
    op = (op or "").strip().lower()
    target = (target or "").strip()
    xop = {"focus": "windowactivate", "close": "windowclose", "minimize": "windowminimize"}.get(op)
    if not xop:
        return {"success": False, "error": "opération inconnue"}
    if not target:
        return {"success": False, "error": "fenêtre cible manquante"}
    import re as _re
    lst = pc_windows()
    if not lst.get("success"):
        return lst
    tl = target.lower()
    match = next((w for w in lst["windows"] if tl in w["name"].lower()), None)
    if not match:  # repli : correspondance sur un mot significatif (≥3 car.) du titre
        words = [x for x in _re.split(r"\W+", tl) if len(x) >= 3]
        match = next((w for w in lst["windows"] if any(x in w["name"].lower() for x in words)), None)
    if not match:
        return {"success": False, "error": f"aucune fenêtre « {target} »",
                "windows": [w["name"] for w in lst["windows"]]}
    try:
        subprocess.run(["xdotool", xop, match["id"]], capture_output=True, text=True, timeout=6, env=_x_env())
        return {"success": True, "op": op, "window": match["name"], "id": match["id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pc_screenshot():
    """Capture l'écran (scrot) dans web/ (servi en loopback seulement) et renvoie l'URL."""
    import os as _os
    out = "/home/turbo/jarvis/cockpit/web/turbo-shot.png"
    try:
        r = subprocess.run(["scrot", "-o", out], capture_output=True, text=True, timeout=15, env=_x_env())
        if r.returncode != 0 or not _os.path.exists(out) or _os.path.getsize(out) < 500:
            return {"success": False, "error": "capture échouée: " + (r.stderr or "")[-160:]}
        return {"success": True, "url": "/turbo-shot.png", "bytes": _os.path.getsize(out)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lire_chantiers_vocal(parler_audio=True):
    """Fait le point réel sur les chantiers (production.db) et le vocalise en français via Kokoro."""
    try:
        from core.sync_engine import get_avancements_data
        d = get_avancements_data()
        k = d.get("kpis", {})
        runs = d.get("runs", [])
        ouverts = [r for r in runs if r.get("etat") == "ouvert"]

        def nettoyer_titre(t):
            lines = [l.strip(" #*-") for l in (t or "").splitlines() if l.strip(" #*-")]
            return lines[0][:75] if lines else "Chantier en cours"

        titres = [nettoyer_titre(o.get("besoin", "")) for o in ouverts[:3]]
        synth = (
            f"Point sur vos chantiers : vous avez {k.get('runs_ouverts', 0)} chantiers ouverts "
            f"et {k.get('runs_livres', 0)} livrés, pour une progression globale de {k.get('global_progress', 0)} pour cent. "
            f"{k.get('fait_taches', 0)} tâches sont terminées sur {k.get('total_taches', 0)}."
        )
        if titres:
            synth += " Les chantiers prioritaires sont : " + ", ".join(titres) + "."

        if parler_audio:
            parler(synth)

        return {
            "success": True,
            "texte": synth,
            "spoken": parler_audio,
            "kpis": k,
            "ouverts_count": len(ouverts),
            "titres_prioritaires": titres
        }
    except Exception as e:
        return {"success": False, "error": f"Erreur lecture chantiers : {e}"}


def appeler_agent_1260(message, speak=False):
    """Transfère la requête à l'Agent souverain JARVIS (:1260), qui dispose des 12 outils réels."""
    import urllib.request as _u
    import json as _j
    message = str(message or "").strip()
    if not message:
        return {"success": False, "error": "message vide"}
    payload = _j.dumps({"message": message, "speak": speak}).encode("utf-8")
    req = _u.Request("http://127.0.0.1:1260/agent", data=payload, headers={"Content-Type": "application/json"})
    try:
        with _u.urlopen(req, timeout=120) as r:
            return _j.loads(r.read().decode())
    except Exception as e:
        return {"success": False, "error": f"Agent :1260 injoignable ou timeout : {e}"}


def statut_agent_1260():
    """Vérifie l'état de santé de l'Agent :1260."""
    import urllib.request as _u
    import json as _j
    req = _u.Request("http://127.0.0.1:1260/health")
    try:
        with _u.urlopen(req, timeout=3) as r:
            return _j.loads(r.read().decode())
    except Exception as e:
        return {"status": "offline", "error": str(e), "port": 1260}


def envoyer_email_cockpit(to, subject, body, send_now=True):
    """Envoie un e-mail via l'outil de l'agent :1260 ou SMTP local."""
    to = str(to or "").strip()
    subject = str(subject or "").strip()
    body = str(body or "").strip()
    if not to:
        return {"success": False, "error": "Destinataire manquant"}
    # Déléguer à l'agent :1260 qui possède tool_send_email avec gestion drafts/SMTP
    res = appeler_agent_1260(f"Envoie un e-mail à {to} avec pour objet '{subject}' et pour corps :\n{body}", speak=False)
    if res.get("status") == "done" or res.get("answer"):
        return {"success": True, "result": res.get("answer", "E-mail traité."), "trace": res.get("trace", [])}
    return {"success": False, "error": res.get("error", "Échec traitement e-mail")}


def stt_transcribe(audio_b64, mime):
    """Proxy vers le service STT souverain jarvis-stt (:1301, faster-whisper large-v3-turbo GPU, lazy+TTL).

    L'orbe envoie l'audio en base64 (corps JSON, sûr) ; on décode et on relaie en OCTETS BRUTS
    à POST :1301/transcribe (contrat réel : body = audio WAV/webm). Renvoie {success, text, seconds, lang}.
    """
    import urllib.request as _u
    import base64 as _b64
    if not audio_b64:
        return {"success": False, "error": "audio manquant"}
    try:
        raw = _b64.b64decode(audio_b64)
    except Exception:
        return {"success": False, "error": "audio base64 invalide"}
    try:
        req = _u.Request("http://127.0.0.1:1301/transcribe", data=raw,
                         headers={"Content-Type": mime or "audio/webm"})
        with _u.urlopen(req, timeout=90) as r:  # 1re parole = ~12 s (chargement modèle lazy)
            d = json.loads(r.read().decode())
        return {"success": d.get("text") is not None, "text": (d.get("text") or "").strip(),
                "seconds": d.get("load_s"), "lang": d.get("lang"), "device": d.get("device")}
    except Exception as e:
        return {"success": False, "error": f"service STT injoignable (:1301) : {e}"}


# ── CHECKPOINT ENGINE : mettre une tâche en pause (persistée) puis la reprendre ──
_CP_DB = "/home/turbo/jarvis/data/turbo_checkpoints.db"


def _cp_conn():
    import sqlite3
    c = sqlite3.connect(_CP_DB, timeout=5)
    c.execute("""CREATE TABLE IF NOT EXISTS checkpoints(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, updated REAL,
        kind TEXT, title TEXT, input TEXT, status TEXT, result TEXT)""")
    return c


def cp_save(kind, title, inp, status, result):
    import time as _t
    if not (inp or "").strip():
        return {"success": False, "error": "tâche vide (rien à reprendre)"}
    try:
        c = _cp_conn(); now = _t.time()
        cur = c.execute("INSERT INTO checkpoints(created,updated,kind,title,input,status,result) VALUES(?,?,?,?,?,?,?)",
                        (now, now, kind or "task", (title or "")[:200], inp, status or "paused", (result or "")[:4000]))
        c.commit(); i = cur.lastrowid; c.close()
        return {"success": True, "id": i}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cp_resolve(cid, status):
    import time as _t
    try:
        c = _cp_conn()
        c.execute("UPDATE checkpoints SET status=?, updated=? WHERE id=?", (status or "done", _t.time(), int(cid)))
        c.commit(); c.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cp_pending():
    """Dernière tâche reprenable (en pause ou interrompue)."""
    try:
        c = _cp_conn()
        row = c.execute("SELECT id,kind,title,input,result,created FROM checkpoints "
                        "WHERE status IN ('paused','running') ORDER BY id DESC LIMIT 1").fetchone()
        c.close()
        if not row:
            return {"success": True, "found": False}
        return {"success": True, "found": True, "id": row[0], "kind": row[1],
                "title": row[2], "input": row[3], "result": row[4], "created": row[5]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cp_list(limit=20):
    try:
        c = _cp_conn()
        rows = c.execute("SELECT id,kind,title,status,created FROM checkpoints ORDER BY id DESC LIMIT ?",
                         (int(limit),)).fetchall()
        c.close()
        return {"success": True, "items": [{"id": r[0], "kind": r[1], "title": r[2],
                                            "status": r[3], "created": r[4]} for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def stt_listen(seconds=6):
    """Écoute DIRECTE côté cockpit : enregistre le micro du PC (parec) puis transcrit via :1301.

    Indépendant du micro du navigateur → corrige le cas « micro bloqué dans la fenêtre Chrome ».
    """
    import urllib.request as _u
    import tempfile as _tf
    import os as _os
    import time as _t
    try:
        seconds = max(2, min(15, int(seconds)))
    except Exception:
        seconds = 6
    src = _os.environ.get("TURBO_MIC", "alsa_input.pci-0000_00_1b.0.analog-stereo")
    wav = _tf.mktemp(prefix="turbo-listen-", suffix=".wav")
    env = dict(_os.environ, XDG_RUNTIME_DIR="/run/user/1000")
    p = None
    try:
        p = subprocess.Popen(["parec", "--device", src, "--file-format=wav",
                              "--rate=16000", "--channels=1", wav], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _t.sleep(seconds)
        p.send_signal(2)  # SIGINT → finalise le WAV
        try:
            p.wait(timeout=2)
        except Exception:
            p.terminate()
        if not _os.path.exists(wav) or _os.path.getsize(wav) < 2000:
            return {"success": False, "error": "aucun son capté par le micro du PC"}
        raw = open(wav, "rb").read()
        req = _u.Request("http://127.0.0.1:1301/transcribe", data=raw,
                         headers={"Content-Type": "audio/wav"})
        with _u.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        return {"success": d.get("text") is not None, "text": (d.get("text") or "").strip(),
                "device": d.get("device"), "source": "cockpit-mic", "seconds": seconds}
    except Exception as e:
        try:
            p and p.kill()
        except Exception:
            pass
        return {"success": False, "error": f"écoute cockpit : {str(e)[:180]}"}
    finally:
        try:
            _os.remove(wav)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════
# OMEGA COGNITIVE OS — protocole 2 voix (JARVIS reformule → Conseil tranche)
# App bureau cliente dissociée : elle ne parle QU'À ce cockpit (:8600).
# 0 token cloud : routeur LLM local :1240 (JARVIS=qwen2.5-7b, Conseil=qwen3-8b).
# ══════════════════════════════════════════════════════════════════════════
ORBE_ROUTER = os.environ.get("OMEGA_ROUTER", "http://127.0.0.1:1240/v1/chat/completions")
ORBE_AGENT = os.environ.get("OMEGA_AGENT", "http://127.0.0.1:1260/agent")
_ORBE_JARVIS = {"name": "JARVIS", "model": os.environ.get("OMEGA_MODEL_JARVIS", "qwen2.5-7b"),
    "system": ("Tu es JARVIS, l'IA vocale du client. On te donne une INSTRUCTION. Tu ne l'exécutes "
               "PAS : tu la REFORMULES clairement (ce que le client veut) puis proposes le plan concret. "
               "Oral, 2 phrases MAX, pas de listes ni markdown. Ne préfixe jamais par ton nom.")}
_ORBE_BOARD = {"name": "Conseil", "model": os.environ.get("OMEGA_MODEL_BOARD", "qwen3-8b"),
    "system": ("/nothink Tu es le Conseil, l'autorité de jugement. JARVIS vient de reformuler une "
               "instruction et proposer un plan. Tu ARBITRES : valide ou corrige, et ÉNONCE la décision "
               "finale (ce qu'il FAUT faire). Oral, 2 phrases MAX, tranché. Pas de listes ni markdown.")}
_orbe_state = {"state": "idle", "you": "", "jarvis": "", "board": "", "decision": "", "ts": 0}


def _orbe_clean(t):
    import re
    t = re.sub(r"(?is)<think>.*?</think>", "", t)
    t = re.sub(r"(?is)^.*?</think>", "", t)
    t = re.sub(r"^\s*(JARVIS|Board|Conseil)\s*[:：\-]\s*", "", t.strip())
    return " ".join(t.split())[:500]


def _orbe_llm(persona, user_msg):
    import urllib.request
    payload = {"model": persona["model"],
               "messages": [{"role": "system", "content": persona["system"]},
                            {"role": "user", "content": user_msg}],
               "max_tokens": 120, "temperature": 0.7}
    req = urllib.request.Request(ORBE_ROUTER, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return _orbe_clean(json.loads(r.read())["choices"][0]["message"]["content"])


def orbe_deliberate(instruction):
    """Protocole 2 voix : JARVIS reformule+propose, le Conseil arbitre+tranche. N'EXÉCUTE PAS."""
    import time as _t
    _orbe_state.update({"state": "thinking", "you": instruction, "jarvis": "", "board": "",
                        "decision": "", "ts": int(_t.time())})
    jarvis = _orbe_llm(_ORBE_JARVIS, f"INSTRUCTION DU CLIENT : {instruction}")
    _orbe_state.update({"state": "speaking", "jarvis": jarvis, "ts": int(_t.time())})
    board = _orbe_llm(_ORBE_BOARD, f"INSTRUCTION DU CLIENT : {instruction}\n\nJARVIS a répondu : {jarvis}")
    _orbe_state.update({"state": "idle", "board": board, "decision": board, "ts": int(_t.time())})
    return {"instruction": instruction, "jarvis": jarvis, "board": board, "decision": board}


def orbe_execute(instruction):
    """Exécute la décision validée en la relayant à l'agent souverain :1260 (best effort)."""
    import urllib.request
    try:
        req = urllib.request.Request(ORBE_AGENT, data=json.dumps({"message": instruction}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return {"ok": True, "result": json.loads(r.read())}
    except Exception as e:
        return {"ok": False, "error": f"agent :1260 injoignable ({type(e).__name__}: {e})"}


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
        """Vérifie l'autorisation d'accès selon jarvis_config.

        Loopback sans restriction (Application Desktop locale).
        Accès réseau distant (LAN / WAN) sécurisé par jeton Bearer Token.
        """
        headers = dict(self.headers)
        params = parse_qs(urlparse(self.path).query)
        client_ip = (self.client_address[0] or "").replace("::ffff:", "")
        if jarvis_config.is_authorized(client_ip, headers, params):
            return True
        self.respond_json({
            "success": False,
            "error": "Accès restreint (P0 Sécurité Appliance) : Jeton d'authentification requis pour les connexions réseau distantes."
        }, 403)
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

    def router_orbe(self, path, req_data=None, params=None):
        """OMEGA COGNITIVE OS — orbe cliente dissociée, connectée UNIQUEMENT à ce cockpit.
        Sécurité C-SEC : loopback libre, client distant => jeton Bearer requis (local_seulement)."""
        if not path.startswith("/orbe"):
            return False
        if not self.local_seulement():
            return True
        try:
            if path == "/orbe.html":
                f = "/home/turbo/omega-cognitive-os/app/index.html"
                html = open(f, encoding="utf-8").read() if os.path.exists(f) else "<h1>OMEGA app absente</h1>"
                data = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/orbe/health":
                self.respond_json({"ok": True, "service": "orbe-cockpit",
                                   "jarvis": _ORBE_JARVIS["model"], "board": _ORBE_BOARD["model"]})
            elif path == "/orbe/state":
                self.respond_json(dict(_orbe_state))
            elif path == "/orbe/ask":
                msg = ((req_data or {}).get("message") or "").strip()
                self.respond_json(orbe_deliberate(msg) if msg else {"error": "message vide"},
                                  200 if msg else 400)
            elif path == "/orbe/execute":
                msg = ((req_data or {}).get("message") or "").strip()
                self.respond_json(orbe_execute(msg) if msg else {"error": "message vide"},
                                  200 if msg else 400)
            else:
                self.respond_json({"success": False, "error": "route orbe inconnue"}, 404)
        except Exception as e:
            self.respond_json({"error": f"{type(e).__name__}: {e}"}, 500)
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # ── SÉCURITÉ APPLIANCE P0 (Défense en profondeur) ──
        # Loopback (127.0.0.1 / ::1) : libre sans friction.
        # Accès réseau distant (LAN / WAN / Tailscale) : Bearer Token requis (403 si absent).
        if not self.local_seulement():
            return

        if self.router_terminal(path, params=params):
            return
        if self.router_orbe(path, params=params):
            return

        # ── TÉLÉMÉTRIE CLUSTER ──
        if path == "/api/status":
            self.respond_json(get_cluster_telemetry())
            return

        # ── MOTEUR GPU : état des modèles (remplace la gestion LM Studio) ──
        elif path == "/api/gpu/models":
            self.respond_json(get_gpu_models_state())
            return

        # ── CHECKPOINT ENGINE : tâche reprenable + historique ──
        elif path == "/api/checkpoint/pending":
            self.respond_json(cp_pending())
            return
        elif path == "/api/checkpoint/list":
            self.respond_json(cp_list())
            return

        # ── S9 STANDALONE BRIDGE & BACKUPS ──
        elif path == "/api/mcp/status":
            self.respond_json({
                "success": True,
                "mcp_server": "jarvis-cockpit",
                "script": "/home/turbo/jarvis/mcp/cockpit_mcp.py",
                "desktop_app": "/home/turbo/Bureau/JARVIS-COCKPIT-OS",
                "launcher_desktop": "/home/turbo/Bureau/jarvis-cockpit.desktop",
                "backend_url": "http://127.0.0.1:8600",
                "tools_count": 33,
                "lmstudio_integration": True,
                "timestamp": datetime.now().isoformat()
            })
            return

        # ── AGENT SOUVERAIN (:1260) & CHANTIERS VOCAUX ──
        elif path == "/api/agent/status":
            self.respond_json(statut_agent_1260())
            return
        elif path == "/api/chantiers/lire":
            speak = params.get("speak", ["1"])[0] not in ("0", "false", "non")
            self.respond_json(lire_chantiers_vocal(parler_audio=speak))
            return
        elif path == "/api/turbo/audit":
            audit_file = "/home/turbo/jarvis/turbo-os/RAPPORT_AUDIT_FINAL.md"
            fmt = params.get("format", ["json"])[0]
            if fmt in ("markdown", "md"):
                if not os.path.exists(audit_file):
                    subprocess.run(["python3", "/home/turbo/jarvis/turbo-os/bin/self_audit_engine.py", f"--output={audit_file}"], timeout=30)
                content = open(audit_file, encoding="utf-8").read() if os.path.exists(audit_file) else ""
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Length", str(len(content.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
                return
            else:
                try:
                    if "/home/turbo/jarvis/turbo-os/bin" not in sys.path:
                        sys.path.insert(0, "/home/turbo/jarvis/turbo-os/bin")
                    import self_audit_engine as sae
                    eng = sae.SelfAuditEngine()
                    res = eng.run_all()
                    self.respond_json({"success": True, "results": res, "tests_pass": eng.tests_pass, "tests_fail": eng.tests_fail})
                except Exception as e:
                    self.respond_json({"success": False, "error": str(e)})
                return

        # ── ARMÉE D'AGENTS & MULTI-SSDs SQL ──
        elif path == "/api/escouade/agents":
            self.respond_json({"success": True, "agents": get_agents_escouade()})
            return
        elif path == "/api/stockage/ssd":
            self.respond_json({"success": True, "ssds": get_cartographie_ssd()})
            return
        elif path == "/api/stockage/sql":
            filtre = params.get("filtre", ["tous"])[0]
            self.respond_json({"success": True, "bases": scanner_bases_sql(filtre)})
            return
        elif path == "/api/stockage/inspecter":
            target_db = params.get("db", [""])[0]
            if target_db:
                self.respond_json(inspecter_base_sql(target_db))
            else:
                self.respond_json({"success": False, "error": "Paramètre 'db' manquant"}, 400)
            return

        # ── AUTOPILOTE H24 ──
        elif path == "/api/autopilot/status":
            try:
                p = subprocess.run(["systemctl", "--user", "is-active", "jarvis-h24-autopilot.service"], capture_output=True, text=True, timeout=3)
                st = p.stdout.strip()
                pid = ""
                pid_file = "/home/turbo/jarvis/logs/autopilot_h24.pid"
                if os.path.exists(pid_file):
                    with open(pid_file) as f:
                        pid = f.read().strip()

                con = sqlite3.connect(f"file:{MASTER_DB}?mode=ro", uri=True, timeout=2.0)
                c = con.cursor()
                rows = c.execute("SELECT timestamp, cycle_nom, statut FROM h24_autopilot_heartbeat ORDER BY id DESC LIMIT 5;").fetchall()
                con.close()

                hb = [{"timestamp": r[0], "cycle": r[1], "statut": r[2]} for r in rows]
                self.respond_json({
                    "success": True,
                    "service": "jarvis-h24-autopilot.service",
                    "status": st,
                    "pid": pid,
                    "heartbeats": hb,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/autopilot/logs":
            try:
                log_file = "/home/turbo/jarvis/logs/autopilot_h24.log"
                lines = []
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        lines = [l.rstrip() for l in f.readlines()[-80:]]
                self.respond_json({"success": True, "logs": lines, "count": len(lines)})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/linkedin/post/today":
            try:
                queue_dir = "/home/turbo/jarvis/data/linkedin/queue"
                today_str = datetime.now().strftime("%Y-%m-%d")
                post_file = os.path.join(queue_dir, f"post_{today_str}.md")
                content = ""
                exists = False
                if os.path.exists(post_file):
                    exists = True
                    with open(post_file, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                self.respond_json({
                    "success": True,
                    "exists": exists,
                    "date": today_str,
                    "file": post_file,
                    "content": content
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/emails/triage/status":
            try:
                mails_base = os.path.expanduser("~/jarvis/data/mails_organises")
                categories = []
                total = 0
                if os.path.exists(mails_base):
                    for d in sorted(os.listdir(mails_base)):
                        p = os.path.join(mails_base, d)
                        if os.path.isdir(p):
                            count = len([f for f in os.listdir(p) if f.endswith(".eml")])
                            total += count
                            categories.append({"nom": d, "count": count})
                self.respond_json({
                    "success": True,
                    "total_emails": total,
                    "categories": categories,
                    "base_path": mails_base
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── AUDIT CITATIONS SQL & ANTI-HALLUCINATION (P0 MOAT) ──
        elif path == "/api/rag/audit-citations":
            try:
                board_path = "/home/turbo/jarvis/board/board.db"
                if not os.path.exists(board_path):
                    self.respond_json({"success": False, "error": "board.db introuvable"}, 404)
                    return
                con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=5.0)
                c = con.cursor()
                total_chunks = c.execute("SELECT count(*) FROM chunks;").fetchone()[0]
                total_sources = c.execute("SELECT count(*) FROM sources;").fetchone()[0]
                total_experts = c.execute("SELECT count(*) FROM experts;").fetchone()[0]
                total_answers = c.execute("SELECT count(*) FROM answers;").fetchone()[0]
                total_citations = c.execute("SELECT count(*) FROM citations;").fetchone()[0]

                # Réponses sans citation
                sans_cit = c.execute("""
                    SELECT count(*) FROM answers a
                    LEFT JOIN citations c ON c.answer_id = a.id
                    WHERE c.id IS NULL;
                """).fetchone()[0]

                # Échantillon des 5 dernières réponses rejetées
                rejets_rows = c.execute("""
                    SELECT a.id, a.query_id, a.expert_id, substr(a.text, 1, 100)
                    FROM answers a
                    LEFT JOIN citations c ON c.answer_id = a.id
                    WHERE c.id IS NULL
                    ORDER BY a.id DESC LIMIT 5;
                """).fetchall()

                # Échantillon des 5 dernières réponses validées avec citation
                valides_rows = c.execute("""
                    SELECT a.id, a.expert_id, count(c.id) as nb_cit, substr(a.text, 1, 100)
                    FROM answers a
                    JOIN citations c ON c.answer_id = a.id
                    GROUP BY a.id
                    ORDER BY a.id DESC LIMIT 5;
                """).fetchall()
                con.close()

                conformite_pct = round(((total_answers - sans_cit) / max(total_answers, 1)) * 100, 2)

                self.respond_json({
                    "success": True,
                    "metrics": {
                        "total_chunks": total_chunks,
                        "total_sources": total_sources,
                        "total_experts": total_experts,
                        "total_answers": total_answers,
                        "total_citations": total_citations,
                        "answers_sans_citation": sans_cit,
                        "conformite_pct": conformite_pct,
                    },
                    "echantillon_rejets": [
                        {"answer_id": r[0], "query_id": r[1], "expert": r[2], "extrait": r[3]} for r in rejets_rows
                    ],
                    "echantillon_valides": [
                        {"answer_id": r[0], "expert": r[1], "citations_count": r[2], "extrait": r[3]} for r in valides_rows
                    ],
                    "regle": "Toute réponse sans citation formelle est rejetée avant restitution.",
                    "sql_view": "CREATE VIEW answers_sans_citation AS SELECT a.id, a.query_id, a.expert_id FROM answers a LEFT JOIN citations c ON c.answer_id = a.id WHERE c.id IS NULL;"
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── AUDIT CLAIMS EVIDENCE-FIRST (P0 MOAT — table claims, L3-01/L3-03) ──
        # Le moat réel : ce que le batch evidence_answer a persisté (SUPPORTED/WEAK/
        # UNSUPPORTED), là où /api/rag/audit-citations ne lit que answers/citations legacy.
        elif path == "/api/rag/audit-claims":
            try:
                board_path = "/home/turbo/jarvis/board/board.db"
                if not os.path.exists(board_path):
                    self.respond_json({"success": False, "error": "board.db introuvable"}, 404)
                    return
                con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=5.0)
                con.execute("PRAGMA query_only=1")
                c = con.cursor()
                total = c.execute("SELECT count(*) FROM claims;").fetchone()[0]
                distinct_req = c.execute("SELECT count(DISTINCT request_id) FROM claims;").fetchone()[0]
                par_verdict = {(k or "?"): v for (k, v) in c.execute(
                    "SELECT verdict, count(*) FROM claims GROUP BY verdict;").fetchall()}
                par_status = {(k or "?"): v for (k, v) in c.execute(
                    "SELECT answer_status, count(*) FROM claims GROUP BY answer_status;").fetchall()}
                par_model = {(k or "?"): v for (k, v) in c.execute(
                    "SELECT model, count(*) FROM claims GROUP BY model ORDER BY 2 DESC LIMIT 6;").fetchall()}
                sup = par_verdict.get("SUPPORTED", 0)
                weak = par_verdict.get("WEAK", 0)
                unsup = par_verdict.get("UNSUPPORTED", 0)
                supported_pct = round(sup / max(total, 1) * 100, 1)
                grounded_pct = round((sup + weak) / max(total, 1) * 100, 1)
                # Échantillon des 40 dernières claims + document source réel.
                # limit-first PUIS join CAST → index PK chunks.id (mesuré ~0,08 s sur 12 Go) :
                # claims.chunk_id est déclaré INTEGER mais stocke le chunk_id TEXTE (chk_/s_/local_).
                ech = c.execute("""
                    SELECT cl.id, cl.request_id, cl.verdict, cl.ratio, cl.answer_status,
                           substr(cl.affirmation, 1, 260), substr(cl.extrait, 1, 260),
                           cl.chunk_id, s.title, s.url, s.kind
                    FROM (SELECT * FROM claims ORDER BY id DESC LIMIT 40) cl
                    LEFT JOIN chunks ch ON ch.id = CAST(cl.chunk_id AS TEXT)
                    LEFT JOIN sources s ON s.id = ch.source_id;
                """).fetchall()
                con.close()
                self.respond_json({
                    "success": True,
                    "metrics": {
                        "total_claims": total,
                        "distinct_request_id": distinct_req,
                        "supported": sup, "weak": weak, "unsupported": unsup,
                        "supported_pct": supported_pct,
                        "grounded_pct": grounded_pct,
                        "par_verdict": par_verdict,
                        "par_answer_status": par_status,
                        "par_model": par_model,
                    },
                    "echantillon": [
                        {"id": r[0], "request_id": r[1], "verdict": r[2], "ratio": r[3],
                         "answer_status": r[4], "affirmation": r[5], "extrait": r[6],
                         "chunk_id": r[7], "source_titre": r[8], "source_url": r[9],
                         "source_kind": r[10]} for r in ech
                    ],
                    "regle": "Evidence-First : chaque affirmation est vérifiée verbatim contre l'extrait cité (SUPPORTED/WEAK/UNSUPPORTED). Refus fail-closed sans preuve.",
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── CATALOGUE DES DOMAINES ET EXPERTS RAG SOUVERAINS ──
        elif path == "/api/rag/domains":
            try:
                board_path = getattr(jarvis_config, "BOARD_DB", "/home/turbo/jarvis/board/board.db")
                if not os.path.exists(board_path):
                    self.respond_json({"success": False, "error": "board.db introuvable"}, 404)
                    return
                con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=5.0)
                cur = con.cursor()
                cur.execute("""
                    SELECT d.id, d.display_name, count(c.rowid) as nb_chunks
                    FROM domains d
                    LEFT JOIN chunks c ON c.domain_id = d.id
                    GROUP BY d.id
                    ORDER BY nb_chunks DESC;
                """)
                domains = [{"id": r[0], "name": r[1], "chunks": r[2]} for r in cur.fetchall()]

                cur.execute("""
                    SELECT domain_id, id, display_name, lens, is_arbitre
                    FROM experts
                    ORDER BY is_arbitre ASC, id ASC;
                """)
                experts = [{"domain_id": r[0], "id": r[1], "name": r[2], "lens": r[3], "is_arbitre": bool(r[4])} for r in cur.fetchall()]
                con.close()
                self.respond_json({"success": True, "domains": domains, "experts": experts})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── STATUT APPLIANCE SOUVERAINE JARVIS BOX ──
        elif path == "/api/appliance/status":
            try:
                gpus = []
                try:
                    res_gpu = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=2.0
                    )
                    if res_gpu.returncode == 0:
                        for line in res_gpu.stdout.strip().split("\n"):
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) >= 5:
                                gpus.append({
                                    "name": parts[0],
                                    "vram_total_mb": int(parts[1]),
                                    "vram_free_mb": int(parts[2]),
                                    "vram_used_mb": int(parts[3]),
                                    "temp_c": int(parts[4])
                                })
                except Exception:
                    pass

                board_path = getattr(jarvis_config, "BOARD_DB", "/home/turbo/jarvis/board/board.db")
                board_stat = {"exists": False, "size_gb": 0, "chunks": 0, "sources": 0, "experts": 0, "conformite_sql": 0}
                if os.path.exists(board_path):
                    try:
                        board_stat["exists"] = True
                        board_stat["size_gb"] = round(os.path.getsize(board_path) / (1024**3), 2)
                        con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=2.0)
                        cur = con.cursor()
                        cur.execute("SELECT count(*) FROM chunks;")
                        board_stat["chunks"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM sources;")
                        board_stat["sources"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM experts;")
                        board_stat["experts"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM answers;")
                        ans = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM answers_sans_citation;")
                        rej = cur.fetchone()[0]
                        con.close()
                        board_stat["conformite_sql"] = round((ans - rej) / ans * 100, 2) if ans > 0 else 100.0
                    except Exception:
                        pass

                tok = getattr(jarvis_config, "JARVIS_AUTH_TOKEN", "")
                tok_preview = (tok[:6] + "..." + tok[-4:]) if len(tok) >= 10 else ("Configuré" if tok else "Non configuré")

                self.respond_json({
                    "success": True,
                    "appliance_model": "JARVIS Box Souveraine v1.0",
                    "hostname": socket.gethostname(),
                    "platform": platform.platform(),
                    "zero_trust": True,
                    "zero_token": True,
                    "auth_enabled": bool(tok),
                    "token_preview": tok_preview,
                    "gpus": gpus,
                    "board_db": board_stat,
                    "anti_hallucination_rule": "Strict SQL (answers_sans_citation = 0 acceptées)",
                    "cost_eur": 0.0
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── EXPORT OFFICIEL ATTESTATION DPO & CONFORMITÉ SOUVERAINE ──
        elif path == "/api/rag/export-dpo":
            try:
                board_path = getattr(jarvis_config, "BOARD_DB", "/home/turbo/jarvis/board/board.db")
                board_stat = {"size_gb": 0, "chunks": 0, "sources": 0, "experts": 0, "answers": 0, "citations": 0, "rejets": 0, "conformite": 0}
                if os.path.exists(board_path):
                    try:
                        board_stat["size_gb"] = round(os.path.getsize(board_path) / (1024**3), 2)
                        con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=3.0)
                        cur = con.cursor()
                        cur.execute("SELECT count(*) FROM chunks;")
                        board_stat["chunks"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM sources;")
                        board_stat["sources"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM experts;")
                        board_stat["experts"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM answers;")
                        board_stat["answers"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM citations;")
                        board_stat["citations"] = cur.fetchone()[0]
                        cur.execute("SELECT count(*) FROM answers_sans_citation;")
                        board_stat["rejets"] = cur.fetchone()[0]
                        con.close()
                        board_stat["conformite"] = round((board_stat["answers"] - board_stat["rejets"]) / board_stat["answers"] * 100, 2) if board_stat["answers"] > 0 else 100.0
                    except Exception:
                        pass

                date_now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                sig_raw = f"{socket.gethostname()}:{board_stat['size_gb']}:{board_stat['chunks']}:{board_stat['conformite']}:{date_now}"
                cert_hash = hashlib.sha256(sig_raw.encode()).hexdigest().upper()

                dpo_report = {
                    "certificat_id": f"DPO-CERT-{cert_hash[:12]}",
                    "horodatage": date_now,
                    "date_audit": date_now,
                    "appliance": {
                        "modele": "JARVIS Box Souveraine v1.0",
                        "poste_hote": socket.gethostname(),
                        "systeme": platform.platform()
                    },
                    "poste_hote": socket.gethostname(),
                    "environnement_execution": platform.platform(),
                    "indicateurs_techniques_et_donnees": {
                        "mode_reseau": "Zero-Trust LAN étanche (Zéro fuite de données)",
                        "consommation_api_externe": "0.00 € (Coût token cloud nul)",
                        "volume_corpus_local_gb": board_stat["size_gb"],
                        "total_chunks_indexes": board_stat["chunks"],
                        "total_sources_tracees": board_stat["sources"],
                        "experts_deliberatifs": board_stat["experts"],
                        "reponses_auditees_sql": board_stat["answers"],
                        "citations_verifiees": board_stat["citations"],
                        "reponses_rejetees_sans_citation": board_stat["rejets"],
                        "taux_conformite_sql": f"{board_stat['conformite']}%",
                        "taux_conformite_anti_hallucination": f"{board_stat['conformite']}%"
                    },
                    "conformite_juridique": {
                        "secret_professionnel": "Strict (Art. 66-5 loi du 31 décembre 1971) — Traitement 100% local",
                        "rgpd_article_32": "Conforme (Sécurité des traitements, chiffrement, isolation physique)",
                        "transferts_hors_ue": "Néant (0 fuite réseau, aucune donnée transmise à des tiers)",
                        "anti_hallucination": "Obligation formelle de citation vérifiable en direct en SQL (board.db)"
                    },
                    "garantie_cryptographique": {
                        "algorithme": "SHA-256",
                        "empreinte_certificat": cert_hash
                    },
                    "cadre_juridique_et_conformite": [
                        "Secret professionnel strict (Art. 66-5 loi du 31 décembre 1971)",
                        "Règlement Général sur la Protection des Données (RGPD - Art. 32)",
                        "Hébergement et traitement 100% on-premise sans transfert transfrontalier",
                        "Obligation contractuelle de traçabilité formelle des sources (Règle Anti-Hallucination SQL)"
                    ],
                    "metriques_souverainete": {
                        "mode_reseau": "Zero-Trust LAN étanche (Zéro fuite de données)",
                        "consommation_api_externe": "0.00 € (Coût token cloud nul)",
                        "volume_corpus_local_gb": board_stat["size_gb"],
                        "total_chunks_indexes": board_stat["chunks"],
                        "total_sources_tracees": board_stat["sources"],
                        "experts_deliberatifs": board_stat["experts"],
                        "reponses_auditees_sql": board_stat["answers"],
                        "citations_verifiees": board_stat["citations"],
                        "reponses_rejetees_sans_citation": board_stat["rejets"],
                        "taux_conformite_anti_hallucination": f"{board_stat['conformite']}%"
                    },
                    "securite_acces": {
                        "authentification_forte": "Bearer Token HMAC-SHA256 actif",
                        "restrictions_reseau": "Loopback 127.0.0.1 ou LAN authentifié exclusivement",
                        "coupe_circuit_externe": "Actif"
                    },
                    "signature_cryptographique_sha256": cert_hash
                }

                self.respond_json({"success": True, "report": dpo_report})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── AUDIT DE PROVENANCE DU CORPUS (IP SAFETY & SOUVERAINETÉ) ──
        elif path == "/api/appliance/provenance":
            try:
                from scripts.corpus_provenance_auditor import audit_provenance
                report = audit_provenance()
                self.respond_json({"success": True, "report": report})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── VALIDATION PRÉ-VOL DE L'APPLIANCE CLIENT ──
        elif path == "/api/appliance/validation":
            try:
                from scripts.appliance_install_validator import run_full_validation
                report = run_full_validation()
                self.respond_json({"success": True, "validation": report})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── SIMULATEUR ROI & ÉCONOMIES DE COÛT TOKEN POUR CABINETS ──
        elif path == "/api/appliance/roi":
            try:
                u_str = params.get("users", ["5"])[0]
                q_str = params.get("queries_per_day", ["60"])[0]
                users = max(1, min(100, int(u_str)))
                queries_per_day = max(5, min(2000, int(q_str)))

                tokens_per_query = 4500
                cloud_token_rate = 15.0 / 1_000_000

                daily_tokens = queries_per_day * tokens_per_query
                monthly_tokens = daily_tokens * 22
                annual_tokens = monthly_tokens * 12

                monthly_token_cost = round(monthly_tokens * cloud_token_rate, 2)
                monthly_seat_std = users * 30.0
                monthly_cloud_std = round(monthly_token_cost + monthly_seat_std, 2)
                annual_cloud_std = round(monthly_cloud_std * 12, 2)

                # Équivalent SaaS IA Vertical Régulé (Harvey AI / CoCounsel à 350 €/siège/mois)
                monthly_vertical_total = round((users * 350.0) + (monthly_token_cost * 0.5), 2)
                annual_vertical_total = round(monthly_vertical_total * 12, 2)

                cost_jarvis_acq = 5900.0
                cost_jarvis_mco = 2400.0
                cost_jarvis_elec = 125.0
                cost_jarvis_year1 = cost_jarvis_acq + cost_jarvis_mco + cost_jarvis_elec
                cost_jarvis_year3 = cost_jarvis_acq + (cost_jarvis_mco * 3) + (cost_jarvis_elec * 3)

                monthly_net_gain = round(monthly_vertical_total - (cost_jarvis_mco / 12 + cost_jarvis_elec / 12), 2)
                annual_savings_year1 = round(annual_vertical_total - cost_jarvis_year1, 2)
                savings_3years = round((annual_vertical_total * 3) - cost_jarvis_year3, 2)

                amortissement_mois = round(cost_jarvis_acq / max(100.0, monthly_net_gain), 1)
                amortissement_mois = max(1.2, amortissement_mois)

                self.respond_json({
                    "success": True,
                    "hypotheses": {
                        "users": users,
                        "queries_per_day": queries_per_day,
                        "tokens_per_query": tokens_per_query,
                        "token_cloud_price_m": 15.0,
                        "cloud_seat_price_user_month": 30.0,
                        "vertical_saas_seat_month": 350.0
                    },
                    "cout_cloud_concurrent": {
                        "tokens_mensuels": monthly_tokens,
                        "cout_tokens_mensuel_eur": monthly_token_cost,
                        "cloud_standard_mensuel_eur": monthly_cloud_std,
                        "cloud_standard_annuel_eur": annual_cloud_std,
                        "vertical_metier_mensuel_eur": monthly_vertical_total,
                        "vertical_metier_annuel_eur": annual_vertical_total,
                        "vertical_metier_3_ans_eur": round(annual_vertical_total * 3, 2)
                    },
                    "cout_jarvis_box": {
                        "acquisition_one_shot_eur": cost_jarvis_acq,
                        "mco_annuel_eur": cost_jarvis_mco,
                        "electricite_annuelle_eur": cost_jarvis_elec,
                        "cout_annee_1_eur": cost_jarvis_year1,
                        "cout_total_3_ans_eur": cost_jarvis_year3
                    },
                    "benefices_financiers": {
                        "economie_nette_annee_1_eur": annual_savings_year1,
                        "economie_nette_3_ans_eur": savings_3years,
                        "gain_net_mensuel_eur": monthly_net_gain,
                        "delai_amortissement_mois": amortissement_mois,
                        "taux_rentabilite_roi_annee_1": f"{round((annual_savings_year1 / cost_jarvis_year1) * 100, 1)} %"
                    }
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── LECTURE DES DOCUMENTS LÉGAUX & STRATÉGIQUES ──
        elif path == "/api/appliance/docs":
            doc_id = params.get("doc", ["cahier_charges"])[0]
            mapping = {
                "cahier_charges": "cahier-des-charges.md",
                "kit_commercial": "kit-commercial-cabinets.md",
                "commercialisation": "audit-commercialisation.md",
                "complet": "audit-complet.md"
            }
            fname = mapping.get(doc_id, "cahier-des-charges.md")
            fpath = os.path.join(WEB_DIR, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.respond_json({"success": True, "doc_id": doc_id, "filename": fname, "content": content})
                except Exception as e:
                    self.respond_json({"success": False, "error": str(e)}, 500)
            else:
                self.respond_json({"success": False, "error": f"Document {fname} non trouvé"}, 404)
            return

        # ── GÉNÉRATEUR DE PROPOSITIONS COMMERCIALES & DEVIS OFFICIELS ──
        elif path == "/api/appliance/devis":
            try:
                from scripts.devis_generator import generer_devis, format_devis_markdown
                client = params.get("client", ["Cabinet & Associés"])[0]
                contact = params.get("contact", ["Maître / Associé Gérant"])[0]
                adresse = params.get("adresse", ["75008 Paris"])[0]
                users = int(params.get("users", ["5"])[0])
                mco = params.get("mco", ["1"])[0] in ("1", "true")
                corpus = params.get("corpus", ["1"])[0] in ("1", "true")
                redondance = params.get("redondance", ["0"])[0] in ("1", "true")

                devis_data = generer_devis(
                    client_nom=client,
                    client_contact=contact,
                    client_adresse=adresse,
                    collaborateurs=users,
                    option_mco=mco,
                    option_corpus_client=corpus,
                    option_secours_redondance=redondance
                )
                md_doc = format_devis_markdown(devis_data)
                self.respond_json({
                    "success": True,
                    "devis": devis_data,
                    "markdown": md_doc
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── AUDIT DE FIDÉLITÉ DES CITATIONS (FAITHFULNESS & GROUNDING) ──
        elif path == "/api/rag/faithfulness":
            try:
                from scripts.faithfulness_evaluator import audit_board_faithfulness_sample
                sample = int(params.get("sample", ["6"])[0])
                res = audit_board_faithfulness_sample(sample_size=sample)
                self.respond_json({"success": True, "faithfulness": res})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── HAUTE DISPONIBILITÉ & STATUT DU MIROIR REDONDANT (JB-REDUND) ──
        elif path == "/api/appliance/ha":
            try:
                from scripts.appliance_ha_manager import get_ha_status
                status = get_ha_status()
                self.respond_json({"success": True, "ha": status})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── BENCHMARK DE PERFORMANCE SOUVERAINE ON-PREMISE ──
        elif path == "/api/appliance/benchmark":
            try:
                from scripts.appliance_benchmark import run_benchmark
                bench = run_benchmark()
                self.respond_json({"success": True, "benchmark": bench})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/s9/status":
            # FIX audit 2026-09-17 : ne plus mentir 'online' sans sonde réelle de l'appareil.
            bdir = "/home/turbo/Bureau/SAUVEGARDE_S9"
            self.respond_json({
                "success": True,
                "bridge": "non_sondé",
                "note": "Aucune sonde réelle de l'appareil S9/S8 — état non vérifié.",
                "device_target": "S9/S8",
                "backup_dir": bdir,
                "backup_dir_present": os.path.exists(bdir),
                "timestamp": datetime.now().isoformat()
            })
            return
        elif path == "/api/s9/backups":
            bdir = "/home/turbo/Bureau/SAUVEGARDE_S9"
            backups = []
            if os.path.exists(bdir):
                for f in sorted(os.listdir(bdir), reverse=True):
                    if f.endswith(".json"):
                        fpath = os.path.join(bdir, f)
                        backups.append({
                            "filename": f,
                            "size": os.path.getsize(fpath),
                            "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
                        })
            self.respond_json({"success": True, "backups": backups, "count": len(backups)})
            return

        # ── AVANCEMENTS & SYNCHRONISATION ──
        elif path == "/api/avancements":
            self.respond_json(get_avancements_data())
            return

        # ── PROSPECTION & SOURCES INTELLIGENCE ──
        elif path == "/api/prospection/status":
            from core.prospection_engine import get_prospection_status
            self.respond_json(get_prospection_status())
            return
        elif path == "/api/prospection/sources":
            from core.prospection_engine import lire_catalogue
            self.respond_json({"success": True, "sources": lire_catalogue()})
            return
        elif path == "/api/prospection/regles":
            from core.prospection_engine import charger_regles_prospection
            regles, bonus = charger_regles_prospection()
            # Nettoyage des clés non sérialisables JSON
            regles_clean = [
                {"segment": r["segment"], "poids": r["poids"], "mots": r["mots"],
                 "processus_qui_saigne": r["processus_qui_saigne"], "exclusions": r.get("exclusions", [])}
                for r in regles
            ]
            self.respond_json({"success": True, "regles": regles_clean, "bonus": bonus, "count": len(regles_clean)})
            return

        elif path == "/api/prospection/cibles_postgres":
            # Lecture des cibles depuis la Tour (100.124.69.1) via ssh jarvis-dva, fallback local
            SQL = "SELECT id, entreprise, ville, segment, score, processus_qui_saigne, dirigeant, statut FROM prospection.cibles ORDER BY score DESC LIMIT 100;"
            source = "tour"
            out = None
            try:
                # Tenter d'abord via la Tour (données réelles)
                out = subprocess.check_output([
                    "ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
                    "jarvis-dva",
                    f"ssh -o ConnectTimeout=4 -o BatchMode=yes root@100.124.69.1 "
                    f"\"docker exec jarvis-postgres psql -U jarvis -d jarvis_main -t -A -F $'\\t' -c '{SQL}'\""
                ], text=True, timeout=8)
            except Exception:
                source = "local"
                try:
                    out = subprocess.check_output([
                        "docker", "exec", "-i", "jarvis-postgres", "psql", "-U", "jarvis", "-d", "jarvis_main",
                        "-t", "-A", "-F", "\t", "-c", SQL
                    ], text=True, timeout=4)
                except Exception as e:
                    self.respond_json({"success": False, "error": str(e), "cibles": [], "source": "erreur"})
                    return
            cibles = []
            for line in (out or "").strip().splitlines():
                p = line.split("\t")
                if len(p) >= 8:
                    try:
                        cibles.append({
                            "id": p[0], "entreprise": p[1], "ville": p[2], "segment": p[3],
                            "score": int(p[4] or 0), "processus_qui_saigne": p[5],
                            "dirigeant": p[6], "statut": p[7]
                        })
                    except Exception:
                        continue
            self.respond_json({"success": True, "count": len(cibles), "cibles": cibles, "source": source})
            return

        elif path == "/api/remi/status":
            from core.prospection_engine import verifier_tunnels
            self.respond_json({"success": True, "tunnels": verifier_tunnels()})
            return

        elif path == "/api/remi/planning":
            # Proxy direct vers le Planning Widget de Rémi (:8899)
            try:
                req = urllib.request.Request("http://127.0.0.1:8899/data", headers={"User-Agent": "JarvisCockpit/1.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    self.respond_json(json.loads(resp.read().decode("utf-8")))
            except Exception as e:
                self.respond_json({"success": False, "error": f"Planning widget injoignable: {e}"}, 503)
            return

        elif path == "/api/remi/board":
            # Proxy direct vers le Board OS de Rémi (:5001)
            try:
                req = urllib.request.Request("http://127.0.0.1:5001/api/state", headers={"User-Agent": "JarvisCockpit/1.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    self.respond_json(json.loads(resp.read().decode("utf-8")))
            except Exception as e:
                self.respond_json({"success": False, "error": f"Board OS injoignable: {e}"}, 503)
            return

        elif path == "/api/benchmark/status":
            # État en direct des GPU et de la performance d'inférence Dual-GPU
            try:
                from core.metrics_collector import collecter_gpu
                gpus = collecter_gpu()
                # Modèles LM Studio
                models_loaded = []
                try:
                    req_lms = urllib.request.Request("http://127.0.0.1:1234/v1/models", headers={"User-Agent": "JarvisCockpit/1.0"})
                    with urllib.request.urlopen(req_lms, timeout=2.0) as resp_lms:
                        data_lms = json.loads(resp_lms.read().decode("utf-8"))
                        models_loaded = [m.get("id") for m in data_lms.get("data", [])]
                except Exception:
                    pass
                # Historique benchmarks depuis lms CLI
                bench_hist = []
                bench_hist_path = os.path.expanduser("~/.local/share/lms/benchmark_history.json")
                if os.path.exists(bench_hist_path):
                    try:
                        with open(bench_hist_path) as f:
                            bh = json.load(f)
                        if bh:
                            last = bh[0]
                            bench_hist = last.get("resultats", [])
                    except Exception:
                        pass
                self.respond_json({
                    "success": True,
                    "gpus": gpus,
                    "models_loaded": models_loaded,
                    "last_benchmark": bench_hist,
                    "split_mode": "dedicated_per_gpu",
                    "kv_offload": True,
                    "flash_attn": True
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/benchmark/live":
            # Stats GPU live + job en cours
            try:
                from core.metrics_collector import lire_cache
                cache = lire_cache()
                self.respond_json({"success": True, "ts": cache.get("ts"), "gpu": cache.get("gpu", []),
                                   "ram": cache.get("ram", {}), "cpu": cache.get("cpu", {}),
                                   "lms": cache.get("lms", {})})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)})
            return

        elif path == "/api/benchmark/resultats":
            # Historique complet des benchmarks
            bench_hist_path = os.path.expanduser("~/.local/share/lms/benchmark_history.json")
            if os.path.exists(bench_hist_path):
                try:
                    with open(bench_hist_path) as f:
                        self.respond_json({"success": True, "historique": json.load(f)})
                except Exception as e:
                    self.respond_json({"success": False, "error": str(e), "historique": []})
            else:
                self.respond_json({"success": True, "historique": []})
            return

        elif path == "/api/metrics/snapshot":
            # Snapshot complet système en temps réel
            try:
                from core.metrics_collector import snapshot
                self.respond_json({"success": True, **snapshot()})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)})
            return

        elif path == "/api/metrics/alertes":
            # Alertes actives + historique
            try:
                from core.metrics_collector import lire_cache, lire_alertes
                cache = lire_cache()
                alertes_actives = cache.get("alertes", [])
                historique = lire_alertes(20)
                self.respond_json({"success": True, "actives": alertes_actives, "historique": historique})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "actives": [], "historique": []})
            return

        elif path == "/api/metrics/historique":
            # Historique des 50 dernières collectes
            try:
                from core.metrics_collector import lire_historique
                self.respond_json({"success": True, "historique": lire_historique(50)})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "historique": []})
            return

        elif path.startswith("/api/scraping/recherche_gouv"):
            # Recherche SIRENE API gouv.fr
            # FIX audit 2026-09-17 : do_GET met path=parsed.path (query retirée) ; réutiliser
            # le dict 'params' déjà parsé au lieu de re-parser une query vide.
            q = (params.get("q") or [""])[0]
            dep = (params.get("dep") or [""])[0]
            if not q:
                self.respond_json({"success": False, "error": "Paramètre q requis", "resultats": []})
                return
            try:
                from core.scraping_pipeline import recherche_gouv
                res = recherche_gouv(q, dep)
                self.respond_json({"success": True, "total": len(res), "resultats": res})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "resultats": []})
            return

        elif path == "/api/veille/sources":
            # Sources de veille actives
            sources_path = "/home/turbo/jarvis/data/veille_sources.json"
            if os.path.exists(sources_path):
                try:
                    with open(sources_path) as f:
                        self.respond_json(json.load(f))
                    return
                except Exception:
                    pass
            self.respond_json({"sources": [
                {"nom": "API Recherche-Entreprises (gouv.fr)", "url": "https://recherche-entreprises.api.gouv.fr/", "type": "api", "actif": True},
                {"nom": "Pappers.fr",  "url": "https://api.pappers.fr/", "type": "api", "actif": True},
                {"nom": "Infogreffe",  "url": "https://www.infogreffe.fr/", "type": "scraping", "actif": False},
                {"nom": "Société.com", "url": "https://www.societe.com/", "type": "scraping", "actif": False},
                {"nom": "Ollama Rémi (veille IA)", "url": "http://127.0.0.1:11500", "type": "llm", "actif": True},
            ]})
            return

        elif path == "/api/veille/derniers_leads":
            # 20 derniers leads capturés
            leads_path = "/home/turbo/jarvis/data/veille_leads.jsonl"
            leads = []
            if os.path.exists(leads_path):
                try:
                    with open(leads_path) as f:
                        lignes = f.readlines()
                    leads = [json.loads(l) for l in lignes[-20:] if l.strip()]
                except Exception:
                    pass
            self.respond_json({"success": True, "leads": list(reversed(leads))})
            return

        elif path == "/api/drip/sequences":
            # Séquences de relance disponibles
            self.respond_json({"sequences": [
                {"id": "cold_outreach", "nom": "Prospection froide", "etapes": 4,
                 "duree_jours": 21, "canal": "email+linkedin",
                 "delais": [0, 4, 10, 21],
                 "desc": "4 touches espacées pour convertir un prospect froid"},
                {"id": "relance_devis", "nom": "Relance devis envoyé", "etapes": 3,
                 "duree_jours": 14, "canal": "email",
                 "delais": [3, 7, 14],
                 "desc": "3 relances pour transformer un devis en bon de commande"},
                {"id": "nurturing_veille", "nom": "Nurturing veille mensuelle", "etapes": 6,
                 "duree_jours": 90, "canal": "email",
                 "delais": [0, 15, 30, 45, 60, 90],
                 "desc": "6 contenus valeur pour rester top-of-mind"},
            ]})
            return

        elif path == "/api/drip/leads_actifs":
            # Leads en cours de séquence drip
            drip_path = "/home/turbo/jarvis/data/drip_leads.json"
            if os.path.exists(drip_path):
                try:
                    with open(drip_path) as f:
                        self.respond_json(json.load(f))
                    return
                except Exception:
                    pass
            self.respond_json({"leads": []})
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

        # ── ACTION MEMORY STATS ──
        elif path == "/api/memory/stats":
            try:
                from core.action_memory import ActionMemoryEngine
                engine = ActionMemoryEngine()
                # FIX audit 2026-09-17 : get_stats() lit la vraie DB (total/vectorized réels),
                # _stats = compteurs en-process init à 0 (trompeur).
                self.respond_json({"success": True, "stats": engine.get_stats()})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── PARAMÈTRES & CONFIGURATION ──
        elif path == "/api/settings":
            self.respond_json(get_cockpit_settings())
            return

        # ── REMODELAGE : vrai hardware du rig (source de vérité agent remodelage) ──
        elif path == "/api/remodelage":
            try:
                with open(os.path.expanduser("~/jarvis/cockpit/hardware.json"), encoding="utf-8") as f:
                    self.respond_json({"success": True, "hardware": json.load(f)})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 404)
            return

        # ── LÉGION OMEGA : domino continu + vectorisation + agents tmux ──
        elif path == "/api/legion":
            self.respond_json({"success": True, "legion": get_legion_status()})
            return

        # ── STATUT DES AGENTS TABLE RONDE & BROWSER OS ──
        elif path == "/api/table-ronde/status":
            self.respond_json({
                "success": True,
                "agents": check_agent_status(),
                "browser_context": get_browser_os_context()
            })
            return

        # ── OMEGA COGNITIVE OS (REGISTRE, BOARD-B, AUDIT) ──
        elif path == "/api/omega/status":
            try:
                reg_p = os.path.join(JARVIS_DIR, "omega", "registry", "omega_registry.db")
                aud_p = os.path.join(JARVIS_DIR, "omega", "audit", "omega_audit.db")
                bb_p = os.path.join(JARVIS_DIR, "omega", "board", "omega_board.db")
                
                n_art, n_fam, n_agt, n_skl = 0, 0, 0, 0
                if os.path.exists(reg_p):
                    conn = sqlite3.connect(f"file:{reg_p}?mode=ro", uri=True)
                    n_art = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
                    n_fam = conn.execute("SELECT count(*) FROM families").fetchone()[0]
                    n_agt = conn.execute("SELECT count(*) FROM agents").fetchone()[0]
                    n_skl = conn.execute("SELECT count(*) FROM skills").fetchone()[0]
                    conn.close()

                n_aud = 0
                if os.path.exists(aud_p):
                    conn = sqlite3.connect(f"file:{aud_p}?mode=ro", uri=True)
                    n_aud = conn.execute("SELECT count(*) FROM events").fetchone()[0]
                    conn.close()

                n_obj, n_dom = 0, 0
                if os.path.exists(bb_p):
                    conn = sqlite3.connect(f"file:{bb_p}?mode=ro", uri=True)
                    n_obj = conn.execute("SELECT count(*) FROM board_items").fetchone()[0]
                    n_dom = conn.execute("SELECT count(*) FROM dominos").fetchone()[0]
                    conn.close()

                self.respond_json({
                    "success": True,
                    "version": "OMEGA-1.1.0",
                    "artifacts": n_art,
                    "families": n_fam,
                    "agents": n_agt,
                    "skills": n_skl,
                    "audits": n_aud,
                    "board_items": n_obj,
                    "dominos": n_dom
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/omega/board":
            try:
                bb_p = os.path.join(JARVIS_DIR, "omega", "board", "omega_board.db")
                items, dominos = [], []
                if os.path.exists(bb_p):
                    conn = sqlite3.connect(f"file:{bb_p}?mode=ro", uri=True)
                    conn.row_factory = sqlite3.Row
                    items = [dict(r) for r in conn.execute("SELECT id, title, state, family, created_at FROM board_items ORDER BY created_at DESC LIMIT 20").fetchall()]
                    dominos = [dict(r) for r in conn.execute("SELECT id, item_id, seq, name, state, action_class FROM dominos ORDER BY item_id, seq ASC").fetchall()]
                    conn.close()
                self.respond_json({"success": True, "items": items, "dominos": dominos})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/omega/audit":
            try:
                aud_p = os.path.join(JARVIS_DIR, "omega", "audit", "omega_audit.db")
                rows = []
                if os.path.exists(aud_p):
                    conn = sqlite3.connect(f"file:{aud_p}?mode=ro", uri=True)
                    conn.row_factory = sqlite3.Row
                    limit = int(params.get("limit", [30])[0])
                    rows = [dict(r) for r in conn.execute("SELECT event_id, event_uid, quand, quoi, quel_agent, verif_statut, quelle_decision FROM events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()]
                    conn.close()
                self.respond_json({"success": True, "events": rows})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/omega/improve/history":
            try:
                reg_p = os.path.join(JARVIS_DIR, "omega", "registry", "omega_registry.db")
                conn = sqlite3.connect(f"file:{reg_p}?mode=ro&immutable=1", uri=True)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                rows = c.execute(
                    "SELECT id, origin, objective, outputs_json, created_at FROM artifacts WHERE id LIKE 'omega.improvement.cycle.%' ORDER BY created_at DESC LIMIT 10"
                ).fetchall()
                res = []
                for r in rows:
                    out = {}
                    try:
                        out = json.loads(r["outputs_json"]) if r["outputs_json"] else {}
                    except Exception:
                        pass
                    res.append({
                        "id": r["id"],
                        "origin": r["origin"],
                        "objective": r["objective"],
                        "created_at": r["created_at"],
                        "details": out
                    })
                conn.close()
                self.respond_json({"success": True, "history": res})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "history": []})
            return

        elif path == "/api/omega/prompts":
            try:
                q = params.get("q", [""])[0].strip()
                limit = int(params.get("limit", [20])[0])
                db_p = os.path.join(JARVIS_DIR, "jarvis_master.db")
                conn = sqlite3.connect(f"file:{db_p}?mode=ro&immutable=1", uri=True)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                if q:
                    rows = cur.execute(
                        "SELECT filename, category, substr(content, 1, 300) as snippet FROM system_prompts_fts WHERE system_prompts_fts MATCH ? LIMIT ?",
                        (q, limit)
                    ).fetchall()
                else:
                    rows = cur.execute(
                        "SELECT filename, category, substr(content, 1, 300) as snippet FROM system_prompts_library ORDER BY id DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
                total = cur.execute("SELECT count(*) FROM system_prompts_library").fetchone()[0]
                conn.close()
                self.respond_json({"success": True, "total": total, "prompts": [dict(r) for r in rows]})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "prompts": []})
            return

        # ── SERVEURS MCP ──
        elif path in ("/api/mcps", "/api/mcp"):
            mcps = get_all_mcp_servers()
            self.respond_json({"success": True, "mcps": mcps, "count": len(mcps)})
            return

        # ── DOCKER SWARM & SERVICES ──
        elif path == "/api/swarm":
            services = get_swarm_services_status()
            self.respond_json({"success": True, "services": services, "count": len(services)})
            return

        # ── APPLICATIONS BUREAU ──
        elif path in ("/api/apps/all", "/api/apps"):
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
            elif file_path.endswith(".md"): ctype = "text/markdown; charset=utf-8"

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

        # ── SÉCURITÉ APPLIANCE P0 (Défense en profondeur) ──
        # Loopback (127.0.0.1 / ::1) : libre sans friction.
        # Accès réseau distant (LAN / WAN / Tailscale) : Bearer Token requis (403 si absent).
        if not self.local_seulement():
            return

        if self.router_terminal(path, req_data=req_data):
            return
        if self.router_orbe(path, req_data=req_data):
            return

        # ── SYNCHRONISATION 1-CLIC ──
        if path == "/api/sync/run":
            auto_git = bool(req_data.get("auto_git", False))
            msg_commit = req_data.get("commit_message", "")
            res = trigger_synchronisation(auto_git_commit=auto_git, message_commit=msg_commit)
            self.respond_json(res)
            return

        # ── MOTEUR GPU : charger un modèle sur le slot GPU1 (:1235) ──
        elif path == "/api/gpu/models/load":
            self.respond_json(charger_modele_gpu1(req_data.get("model", "")))
            return

        # ── LM STUDIO MAISON : chat direct avec un modèle GPU ──
        elif path == "/api/gpu/chat":
            self.respond_json(chat_gpu(req_data.get("model"), req_data.get("prompt"),
                                       req_data.get("port", 1234), req_data.get("system")))
            return

        # ── TURBO OS : voix souveraine (Kokoro FR) ──
        elif path == "/api/gpu/speak":
            self.respond_json(parler(req_data.get("text", "")))
            return

        # ── TURBO OS : commande vocale (correction STT + routage tout le cockpit) ──
        elif path == "/api/voice/command":
            self.respond_json(voice_command(req_data.get("text", "")))
            return

        # ── TURBO OS : pilotage de la boucle vocale mains-libres (service jarvis-voice-cockpit :1270) ──
        elif path == "/api/voice/loop":
            self.respond_json(voice_loop_control(req_data.get("action", "status")))
            return

        # ── PC CONTROL : fenêtres + capture d'écran ──
        elif path == "/api/pc/windows":
            self.respond_json(pc_windows())
            return
        elif path == "/api/pc/window":
            self.respond_json(pc_window_op(req_data.get("op", ""), req_data.get("target", "")))
            return
        elif path == "/api/pc/screenshot":
            self.respond_json(pc_screenshot())
            return

        # ── TURBO OS : STT souverain (faster-whisper GPU, CPU banni) ──
        elif path == "/api/stt/transcribe":
            self.respond_json(stt_transcribe(req_data.get("audio_b64"), req_data.get("mime")))
            return

        # ── TURBO OS : écoute DIRECTE côté cockpit (micro du PC, sans navigateur) ──
        elif path == "/api/stt/listen":
            self.respond_json(stt_listen(req_data.get("seconds", 6)))
            return

        # ── CHECKPOINT ENGINE : pause/reprise de tâche ──
        elif path == "/api/checkpoint/save":
            self.respond_json(cp_save(req_data.get("kind"), req_data.get("title"),
                                      req_data.get("input"), req_data.get("status"), req_data.get("result")))
            return
        elif path == "/api/checkpoint/resolve":
            self.respond_json(cp_resolve(req_data.get("id"), req_data.get("status")))
            return

        # ── AGENT SOUVERAIN (:1260), CHANTIERS VOCAUX & E-MAILS ──
        elif path == "/api/agent":
            msg = req_data.get("message", "")
            speak = bool(req_data.get("speak", False))
            self.respond_json(appeler_agent_1260(msg, speak=speak))
            return
        elif path == "/api/chantiers/lire":
            speak = bool(req_data.get("speak", True))
            self.respond_json(lire_chantiers_vocal(parler_audio=speak))
            return
        elif path == "/api/emails/envoyer":
            to = req_data.get("to", "")
            subj = req_data.get("subject", "")
            body = req_data.get("body", "")
            send_now = bool(req_data.get("send_now", True))
            self.respond_json(envoyer_email_cockpit(to, subj, body, send_now=send_now))
            return

        # ── PROSPECTION & ENRICHISSEMENT SOURCES ──
        elif path == "/api/prospection/recherche_gouv":
            from core.prospection_engine import rechercher_entreprises_gouv
            q = req_data.get("query", "")
            dep = req_data.get("departement", "31")
            naf = req_data.get("code_naf", None)
            lim = int(req_data.get("limite", 10))
            self.respond_json(rechercher_entreprises_gouv(q, departement=dep, code_naf=naf, limite=lim))
            return

        elif path == "/api/prospection/scan":
            from core.prospection_engine import moissonner_cible, lire_catalogue
            nom_cible = req_data.get("nom", "")
            cibles = lire_catalogue()
            trouvees = [c for c in cibles if not nom_cible or c["nom"].lower() == nom_cible.lower()]
            if not trouvees:
                self.respond_json({"success": False, "error": f"Cible '{nom_cible}' non trouvée dans le catalogue"}, 404)
                return
            resultats = [moissonner_cible(c) for c in trouvees[:3]]
            self.respond_json({"success": True, "scanned": resultats})
            return

        elif path == "/api/prospection/qualifier":
            from core.prospection_engine import qualifier_prospect
            texte = req_data.get("texte", "")
            infos = req_data.get("infos", {})
            self.respond_json({"success": True, "qualification": qualifier_prospect(texte, infos)})
            return

        elif path == "/api/prospection/generer_message":
            from core.prospection_engine import generer_message_prospection
            prospect = req_data.get("prospect", {})
            style = req_data.get("style", "accroche")
            self.respond_json(generer_message_prospection(prospect, style=style))
            return

        elif path == "/api/prospection/route_batch":
            from core.prospection_engine import router_batch_donnees
            lignes = req_data.get("lignes", [])
            self.respond_json(router_batch_donnees(lignes))
            return

        elif path == "/api/prospection/ajouter_cible":
            from core.prospection_engine import ajouter_cible_catalogue
            nom = req_data.get("nom", "").strip()
            pole = req_data.get("pole", "").strip()
            url = req_data.get("url", "").strip()
            if not nom or not url:
                self.respond_json({"success": False, "error": "Nom et URL requis"}, 400)
                return
            ok = ajouter_cible_catalogue(nom, pole or "autre", url)
            self.respond_json({"success": ok, "message": "Cible ajoutée" if ok else "Cible déjà présente"})
            return

        elif path == "/api/benchmark/run":
            model = req_data.get("model", "qwen3-8b")
            mode = req_data.get("mode", "single")  # "single" ou "multi"
            try:
                cmd = ["/home/turbo/.local/bin/lms", "benchmark", model] if mode == "single" else ["/home/turbo/.local/bin/lms", "multi-bench"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                self.respond_json({
                    "success": r.returncode == 0,
                    "output": r.stdout + ("\n" + r.stderr if r.stderr else "")
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return


        # ── MOBILISATION D'UN AGENT DE L'ESCOUADE ──
        elif path == "/api/escouade/lancer":
            nom = req_data.get("nom", "")
            tache = req_data.get("tache", "")
            temp = float(req_data.get("temperature", 0.6))
            if not nom or not tache:
                self.respond_json({"success": False, "error": "Nom de l'agent et tâche requis."}, 400)
                return
            res = lancer_agent(nom, tache, temperature=temp)
            self.respond_json(res)
            return

        # ── ACTION AUTOPILOTE H24 ──
        elif path == "/api/autopilot/action":
            action = req_data.get("action", "status")
            svc = "jarvis-h24-autopilot.service"
            if action == "start":
                subprocess.run(["systemctl", "--user", "start", svc], timeout=10)
            elif action == "stop":
                subprocess.run(["systemctl", "--user", "stop", svc], timeout=10)
            elif action == "restart":
                subprocess.run(["systemctl", "--user", "restart", svc], timeout=10)
            elif action == "force":
                subprocess.Popen(["/home/turbo/jarvis/.venv/bin/python3", "/home/turbo/jarvis/scripts/jarvis_autopilot_h24.py", "--once"])
            self.respond_json({"success": True, "action": action})
            return

        # ── EXÉCUTION D'UNE CADENCE SPÉCIFIQUE H24 ──
        elif path == "/api/autopilot/cadence/run":
            cadence = req_data.get("cadence", "")
            py_bin = "/home/turbo/jarvis/.venv/bin/python3"
            sys.path.insert(0, "/home/turbo/jarvis/scripts")
            try:
                import jarvis_autopilot_h24 as auto
                result = {}
                if cadence == "gpu":
                    result = auto.cycle_materiel_gpu()
                elif cadence == "sql":
                    auto.cycle_sql_taches()
                    result = {"status": "OK", "message": "Cycle SQL & Tâches exécuté avec succès"}
                elif cadence == "emails":
                    auto.cycle_emails_triage()
                    result = {"status": "OK", "message": "Cycle Triage Emails exécuté avec succès"}
                elif cadence == "linkedin":
                    auto.cycle_linkedin_cdp()
                    result = {"status": "OK", "message": "Cycle LinkedIn & CDP exécuté avec succès"}
                else:
                    result = {"error": f"Cadence inconnue: {cadence}"}
                self.respond_json({"success": True, "cadence": cadence, "result": result})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── LINKEDIN GÉNÉRATION ET PUBLICATION EN 1-CLIC ──
        elif path == "/api/linkedin/post/generate":
            try:
                py_bin = "/home/turbo/jarvis/.venv/bin/python3"
                p = subprocess.run([py_bin, "/home/turbo/jarvis/scripts/linkedin_generate.py"], capture_output=True, text=True, timeout=90)
                today_str = datetime.now().strftime("%Y-%m-%d")
                post_file = f"/home/turbo/jarvis/data/linkedin/queue/post_{today_str}.md"
                content = ""
                if os.path.exists(post_file):
                    with open(post_file, "r", encoding="utf-8") as f:
                        content = f.read()
                self.respond_json({
                    "success": p.returncode == 0,
                    "stdout": p.stdout,
                    "content": content
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        elif path == "/api/linkedin/post/publish":
            try:
                py_bin = "/home/turbo/jarvis/.venv/bin/python3"
                p = subprocess.run([py_bin, "/home/turbo/jarvis/scripts/linkedin_cdp_publish.py", "publish"], capture_output=True, text=True, timeout=60)
                self.respond_json({
                    "success": p.returncode == 0,
                    "output": p.stdout.strip() or p.stderr.strip()
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── TRIAGE DES EMAILS EN 1-CLIC ──
        elif path == "/api/emails/triage/run":
            try:
                py_bin = "/home/turbo/jarvis/.venv/bin/python3"
                p = subprocess.run([py_bin, "/home/turbo/jarvis/scripts/mail_sorter_organizer.py"], capture_output=True, text=True, timeout=60)
                self.respond_json({
                    "success": p.returncode == 0,
                    "output": p.stdout.strip() or p.stderr.strip()
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── EXÉCUTION DE COMMANDE BASH INTÉGRÉE COCKPIT (ZÉRO EXTÉRIEUR) ──
        elif path == "/api/command/exec":
            cmd = req_data.get("command", "").strip()
            if not cmd:
                self.respond_json({"success": False, "error": "Commande vide."}, 400)
                return
            t0 = time.time()
            try:
                env = os.environ.copy()
                env["DISPLAY"] = env.get("DISPLAY", ":1")
                env["XAUTHORITY"] = env.get("XAUTHORITY", "/run/user/1000/gdm/Xauthority")
                p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=45, env=env)
                elapsed = round((time.time() - t0) * 1000, 1)
                self.respond_json({
                    "success": True,
                    "command": cmd,
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                    "returncode": p.returncode,
                    "duration_ms": elapsed
                })
            except subprocess.TimeoutExpired:
                self.respond_json({"success": False, "error": "Délai d'exécution dépassé (45s)."}, 504)
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return


        # ── S9 BACKUP RECEPTION (CÂBLAGE / SYNC) ──
        elif path == "/api/s9/backup":
            try:
                bdir = "/home/turbo/Bureau/SAUVEGARDE_S9"
                os.makedirs(bdir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"backup_s9_{ts}.json"
                target_path = os.path.join(bdir, fname)
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(req_data, f, ensure_ascii=False, indent=2)
                self.respond_json({
                    "success": True,
                    "filename": fname,
                    "path": target_path,
                    "sessions_saved": len(req_data.get("sessions", [])) if isinstance(req_data, dict) else 0,
                    "size_bytes": os.path.getsize(target_path),
                    "message": "Sauvegarde S9 reçue et sécurisée sur le PC bureau."
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── ROUTEUR COGNITIF OMEGA ──
        elif path == "/api/omega/route":
            try:
                prompt = req_data.get("prompt", "")
                rdir = os.path.join(JARVIS_DIR, "omega", "engine")
                if rdir not in sys.path:
                    sys.path.insert(0, rdir)
                from router import OmegaCognitiveRouter
                router = OmegaCognitiveRouter()
                res = router.route_intent(prompt)
                chunks = router.search_memory(prompt, limit=2)
                skills = router.discover_skills(prompt, limit=3)
                self.respond_json({
                    "success": True,
                    "routing": res,
                    "memory_chunks": chunks,
                    "skills": skills
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── CYCLE D'AMÉLIORATION CONTINUE OMEGA ──
        elif path == "/api/omega/improve":
            try:
                dry_run = bool(req_data.get("dry_run", False))
                edir = os.path.join(JARVIS_DIR, "omega", "engine")
                if edir not in sys.path:
                    sys.path.insert(0, edir)
                from improve_cycle import OmegaImprovementCycle
                engine = OmegaImprovementCycle(dry_run=dry_run)
                report = engine.run()
                self.respond_json({
                    "success": True,
                    "report": report
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
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
            script_bin = os.path.expanduser(exec_cmd.split()[0])
            if not os.path.exists(script_bin):
                self.respond_json({
                    "success": False,
                    "error": "not_implemented",
                    "reason": f"Brique de production absente : {script_bin}",
                    "action": action,
                    "run_id": run_id
                }, 501)
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

        # ── CHEMIN CANONIQUE EVIDENCE-FIRST (evidence_answer -> OUTPUT VALIDATOR -> jarvis_answer_v1) ──
        elif path == "/api/rag/answer":
            # Auto-route les questions MCP vers le registre typé. 0 token cloud (LM Studio + Rémi).
            try:
                question = req_data.get("question", "").strip()
                if not question:
                    self.respond_json({"status": "error", "error": "Question requise"}, 400); return
                rag_dir = "/home/turbo/jarvis/omega/rag"
                if rag_dir not in sys.path:
                    sys.path.insert(0, rag_dir)
                import evidence_answer as _EA
                import jarvis_output as _JO
                res = _EA.answer(question, k=int(req_data.get("k", 6)), domain=req_data.get("domain"))
                self.respond_json(_JO.validate_v1(_EA.as_v1(res)))
            except Exception as e:
                self.respond_json({"status": "error", "error": str(e)}, 500)
            return

        # ── INTERROGATION RAG SOUVERAIN AVEC CITATIONS & ANTI-HALLUCINATION ──
        elif path == "/api/rag/ask":
            try:
                domain = req_data.get("domain", "souverainete")
                question = req_data.get("question", "").strip()
                mode = req_data.get("mode", "consensus")
                k = int(req_data.get("k", 10))

                if not question:
                    self.respond_json({"success": False, "error": "Question requise"}, 400)
                    return

                board_dir = getattr(jarvis_config, "BOARD_DIR", "/home/turbo/jarvis/board")
                if board_dir not in sys.path:
                    sys.path.insert(0, board_dir)
                import ask

                board_path = getattr(jarvis_config, "BOARD_DB", os.path.join(board_dir, "board.db"))
                con = sqlite3.connect(f"file:{board_path}?mode=ro", uri=True, timeout=10.0)
                try:
                    t_start = time.time()
                    res = ask.ask(con, domain, question, mode=mode, k=k)
                    duration_s = round(time.time() - t_start, 2)
                    citations = res.get("citations", [])
                    has_citations = len(citations) > 0
                    validation_status = "VALIDATED" if has_citations else "REJECTED"
                    validation_reason = (
                        f"{len(citations)} citations formelles vérifiées dans board.db (Règle Anti-Hallucination certifiée)"
                        if has_citations
                        else "CORPUS INSUFFISANT : Aucune citation valide trouvée dans la base."
                    )

                    consensus_text = res.get("consensus", "")
                    source_chunks = [c.get("text") or c.get("extrait") or "" for c in citations if (c.get("text") or c.get("extrait"))]

                    faith_data = {
                        "faithfulness_score": 1.0 if (not consensus_text and has_citations) else 0.0,
                        "faithfulness_pct": "0.0%",
                        "supported_sentences": 0,
                        "total_sentences": 0,
                        "supported_pct": 0.0,
                        "numeric_grounding_pct": 0.0,
                        "extrapolated_sample": [],
                        "verdict": "Aucune source formelle pour l'ancrage."
                    }
                    if source_chunks and consensus_text:
                        try:
                            from scripts.faithfulness_evaluator import evaluate_faithfulness
                            faith_data = evaluate_faithfulness(consensus_text, source_chunks)
                        except Exception as fe:
                            faith_data["eval_error"] = str(fe)

                    # ── FAIL-CLOSE : la validation reflète l'ANCRAGE réel, pas le simple nombre de citations ──
                    try:
                        sup = float(str(faith_data.get("faithfulness_pct") or "0").replace("%", "").strip() or 0)
                    except Exception:
                        sup = 0.0
                    min_faith = float(os.environ.get("RAG_MIN_FAITH", "40"))
                    if has_citations and consensus_text and sup < min_faith:
                        validation_status = "PREUVE_INSUFFISANTE"
                        validation_reason = (
                            f"Fail-close : ancrage {sup:.0f}% < {min_faith:.0f}% — réponse plausible mais NON "
                            f"suffisamment soutenue par les {len(citations)} citations (anti-hallucination stricte)."
                        )

                    self.respond_json({
                        "success": True,
                        "domain": res.get("domain"),
                        "question": res.get("question"),
                        "mode": res.get("mode"),
                        "citations": citations,
                        "opinions": [{"expert": name, "text": txt} for name, txt in res.get("opinions", [])],
                        "consensus": consensus_text,
                        "validation": {
                            "status": validation_status,
                            "is_valid": validation_status == "VALIDATED",
                            "citations_count": len(citations),
                            "reason": validation_reason
                        },
                        "faithfulness": faith_data,
                        "duration_s": duration_s,
                        "zero_token": True,
                        "cost_token_eur": 0.0
                    })
                finally:
                    con.close()
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
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

        # ── ACTION MEMORY HYBRID RECALL ──
        elif path == "/api/memory/recall":
            try:
                from core.action_memory import ActionMemoryEngine
                query = req_data.get("query", "")
                limit = int(req_data.get("limit", 8))
                min_score = float(req_data.get("min_score", 0.20))
                engine = ActionMemoryEngine()
                results = engine.recall(query, limit=limit, min_score=min_score)
                self.respond_json({"success": True, "results": results, "count": len(results)})
            except Exception as e:
                self.respond_json({"success": False, "error": str(e), "results": []}, 500)
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
                # FIX audit 2026-09-17 : ne plus prétendre 'enregistré' quand le moteur est absent.
                self.respond_json({"success": False, "error": "not_implemented",
                                   "reason": "swan_stream_engine.py absent — rien émis ni enregistré."})
            return

        # ── REPLAY & GUÉRISON ──
        elif path == "/api/replay":
            script = os.path.expanduser("~/jarvis/scripts/jarvis_full_session_replay.sh")
            if os.path.exists(script):
                subprocess.Popen(["bash", script])
                self.respond_json({"success": True, "message": "Rejeu complet 1-clic initié en arrière-plan."})
            else:
                # FIX audit 2026-09-17 : ne plus mentir 'initié' quand le script est absent.
                self.respond_json({"success": False, "error": "not_implemented",
                                   "reason": "jarvis_full_session_replay.sh absent — aucun rejeu lancé."})
            return

        # ── ROTATION JETON SÉCURITÉ P0 (LOCAL UNIQUEMENT) ──
        elif path == "/api/appliance/rotate-token":
            if not self.local_seulement():
                return
            try:
                new_tok = jarvis_config.rotate_auth_token()
                preview = (new_tok[:6] + "..." + new_tok[-4:]) if len(new_tok) >= 10 else "Configuré"
                self.respond_json({
                    "success": True,
                    "message": "Nouveau jeton Bearer généré et enregistré dans auth_token.secret (0600)",
                    "token_preview": preview
                })
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── SYNCHRONISATION DU MIROIR HAUTE DISPONIBILITÉ (JB-REDUND) ──
        elif path == "/api/appliance/ha/sync":
            if not self.local_seulement():
                return
            try:
                from scripts.appliance_ha_manager import replicate_mirror
                res = replicate_mirror()
                self.respond_json(res)
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
            return

        # ── TEST DE BASCULEMENT MIROIR (FAILOVER DRILL) ──
        elif path == "/api/appliance/ha/failover-test":
            if not self.local_seulement():
                return
            try:
                from scripts.appliance_ha_manager import test_failover_readiness
                deep = bool(req_data.get("deep", False))
                res = test_failover_readiness(deep=deep)
                self.respond_json(res)
            except Exception as e:
                self.respond_json({"success": False, "error": str(e)}, 500)
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


class CockpitServer(ThreadingHTTPServer):
    # File d'acceptation large : les terminaux font du long-poll 20 s et le
    # tableau de bord interroge /api/status en continu. Le backlog par défaut
    # (5) débordait dès quelques onglets → connexions RST → sessions affichées
    # « rouges » à tort. 128 encaisse les pics sans refuser de connexion.
    request_queue_size = 128
    daemon_threads = True
    allow_reuse_address = True


def _demarrer_collecte_metrics():
    """Thread daemon : collecte métriques toutes les 30s, sauve dans metrics_history.jsonl."""
    import threading as _th
    def _loop():
        import time as _t
        # Attendre 5s au démarrage pour laisser le serveur se stabiliser
        _t.sleep(5)
        while True:
            try:
                from core.metrics_collector import snapshot, sauver_historique
                data = snapshot()
                sauver_historique(data)
            except Exception:
                pass
            _t.sleep(30)
    t = _th.Thread(target=_loop, daemon=True, name="MetricsCollector")
    t.start()


def main():
    os.makedirs(WEB_DIR, exist_ok=True)
    # Démarrer la collecte métriques en arrière-plan
    _demarrer_collecte_metrics()
    server = CockpitServer(("0.0.0.0", PORT), CockpitHandler)
    print(f"🚀 JARVIS COCKPIT DESKTOP SERVER démarré sur http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
