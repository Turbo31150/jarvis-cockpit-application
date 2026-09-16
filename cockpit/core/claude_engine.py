#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CLAUDE CODE CLI & AGENTIC SUITE ENGINE
========================================================
Interface pour Claude Code CLI, détection ultra-rapide des incidents (529 Overloaded),
et repli automatique transparent vers la cascade souveraine M4 Ollama / M6 GPU.
"""

import os
import json
import time
import shutil
import urllib.request
import subprocess
from .config import HOME, JARVIS_DIR, M6_URL, OLLAMA_URL
from .platform_compat import IS_WINDOWS, which, run_cmd, open_terminal

if IS_WINDOWS:
    # claude.exe / claude.cmd (npm) : which() connaît %USERPROFILE%\.local\bin et npm
    CLAUDE_BIN = which("claude") or os.path.join(HOME, ".local", "bin", "claude.exe")
else:
    CLAUDE_BIN = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude") or "/usr/local/bin/claude"

CLAUDE_PRESETS = [
    {
        "id": "audit",
        "title": "🔍 Audit de Code & Sécurité Avancé",
        "prompt": "Analyse le code du projet courant, identifie les goulots d'étranglement, les risques de sécurité (injections, fuites mémoires) et propose un plan de refactorisation immédiat.",
        "category": "QUALITÉ & AUDIT"
    },
    {
        "id": "refactor",
        "title": "⚡ Optimisation Scalabilité & Modularité",
        "prompt": "Refactorise les modules clés pour assurer une architecture découplée, typée, asynchrone et scalable à grande échelle.",
        "category": "ARCHITECTURE"
    },
    {
        "id": "tests",
        "title": "🧪 Génération de Tests Unitaires & E2E",
        "prompt": "Écris des tests automatisés robustes (pytest) pour couvrir l'intégralité des fonctions critiques avec gestion des cas limites et mocks appropriés.",
        "category": "TESTS & QA"
    },
    {
        "id": "doc",
        "title": "📚 Documentation Exhaustive & Schémas",
        "prompt": "Génère une documentation d'architecture technique complète en Markdown, avec diagrammes Mermaid, descriptions des endpoints et guide d'installation pas-à-pas.",
        "category": "DOCUMENTATION"
    },
    {
        "id": "mcp_diag",
        "title": "📦 Diagnostic & Test des Outils MCP",
        "prompt": "Vérifie l'état de tous les serveurs MCP déclarés, teste les outils essentiels et corrige les configurations défaillantes.",
        "category": "MCP & OUTILS"
    }
]


def fallback_local_llm(prompt: str, reason: str = "Claude API 529 Overloaded") -> dict:
    """Exécute l'inférence via le moteur souverain local (LM Studio Tier 0 / Ollama) en cas de panne Claude."""
    try:
        try:
            from .inference import generate_completion
        except ImportError:
            from cockpit.core.inference import generate_completion
        sys_prompt = "Tu es l'assistant IA JARVIS-OMEGA en mode souverain autonome (repli local). Réponds de manière précise, concise et structurée."
        r = generate_completion(prompt, sys_prompt=sys_prompt, max_tokens=1000)
        if r.get("success") and r.get("content"):
            source = r.get("source", "Local GPU")
            lat = r.get("latency", 0.0)
            return {
                "success": True,
                "output": f"⚡ [REPLI SOUVERAIN ACTIF · {reason}]\n(Moteur: {source} · Latence: {lat}s)\n\n{r['content']}",
                "returncode": 0,
                "fallback_used": True,
                "model": r.get("model", "qwen3-8b"),
                "reason": reason
            }
    except Exception as e:
        pass

    return {
        "success": False,
        "output": f"⚠️ Échec Claude ({reason}) et échec des cascades locales.",
        "returncode": 1,
        "fallback_used": True
    }


def get_claude_info() -> dict:
    """Récupère la configuration, version et état de Claude Code."""
    installed = os.path.exists(CLAUDE_BIN) or bool(shutil.which("claude"))
    version = "Inconnue"
    if installed:
        try:
            # run_cmd : sans fenêtre console sous Windows (pythonw), utf-8, ne lève jamais
            r = run_cmd([CLAUDE_BIN, "--version"], timeout=3)
            version = r.stdout.strip() or r.stderr.strip() or "Installé"
        except Exception:
            version = "Installé"

    config_path = os.path.join(HOME, ".claude.json")
    mcp_count = 0
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_cfg = json.load(f)
                mcp_count = len(raw_cfg.get("mcpServers", {}))
        except Exception:
            pass

    return {
        "installed": installed,
        "bin_path": CLAUDE_BIN,
        "version": version,
        "mcp_count": mcp_count,
        "config_path": config_path,
        "has_config": os.path.exists(config_path),
        "status": "Alerte 529 Cloud (Bascule Souveraine M4/M6 Opérationnelle)"
    }


def run_claude_prompt(prompt: str, cwd: str = None, timeout: int = 12, force_local: bool = False) -> dict:
    """Exécute un prompt avec priorité absolue LM Studio Dual-GPU souverain."""
    if force_local or os.environ.get("JARVIS_FORCE_LOCAL_LLM", "1") == "1":
        return fallback_local_llm(prompt, reason="Mode Souverain LM Studio Dual-GPU (0-token)")

    work_dir = cwd or JARVIS_DIR
    try:
        r = run_cmd([CLAUDE_BIN, "-p", prompt], cwd=work_dir, timeout=timeout)
        if r.returncode == 124:
            # run_cmd ne lève jamais : 124 = délai dépassé (équivalent TimeoutExpired)
            return fallback_local_llm(prompt, reason="Timeout Claude Cloud (12s) -> Bascule Souveraine")
        if r.returncode == 127:
            return fallback_local_llm(prompt, reason=f"Exception Claude: {r.stderr}")
        out = (r.stdout or r.stderr or "").strip()
        
        is_529 = ("529" in out or "Overloaded" in out or "status.claude.com" in out or "rate limit" in out.lower() or r.returncode != 0)
        
        if is_529 or not out:
            reason = "529 Overloaded Cloud Intercepté" if ("529" in out or "Overloaded" in out) else "Erreur Cloud / Timeout"
            return fallback_local_llm(prompt, reason=reason)
            
        return {
            "success": True,
            "output": out,
            "returncode": 0,
            "fallback_used": False
        }
    except subprocess.TimeoutExpired:
        return fallback_local_llm(prompt, reason="Timeout Claude Cloud (12s) -> Bascule Souveraine")
    except Exception as e:
        return fallback_local_llm(prompt, reason=f"Exception Claude: {e}")


def launch_claude_interactive(mode: str = "default", cwd: str = None) -> bool:
    """Lance une session Claude Code dans un terminal dédié.

    Windows : Windows Terminal (wt.exe) ou cmd.exe via platform_compat.open_terminal ;
    le mode « tmux » (script du rig) n'existe pas → session simple à la place."""
    work_dir = cwd or JARVIS_DIR

    if IS_WINDOWS:
        if not CLAUDE_BIN or not os.path.exists(CLAUDE_BIN):
            return False
        if mode == "resume":
            argv = [CLAUDE_BIN, "-r"]
        elif mode == "doctor":
            argv = [CLAUDE_BIN, "doctor"]
        else:
            # « tmux » inclus : pas de tmux sous Windows, on ouvre une session Claude simple
            argv = [CLAUDE_BIN]
        proc = open_terminal(argv, title="Claude Code", cwd=work_dir, keep_open=True)
        return proc is not None

    term = shutil.which("gnome-terminal") or shutil.which("x-terminal-emulator") or "xterm"

    if mode == "tmux":
        cmd = "/home/turbo/jarvis/bin/ouvrir-claude-code-tmux.sh"
    elif mode == "resume":
        cmd = f"cd '{work_dir}' && {CLAUDE_BIN} -r"
    elif mode == "doctor":
        cmd = f"{CLAUDE_BIN} doctor; read -p 'Entrée pour fermer'"
    else:
        cmd = f"cd '{work_dir}' && {CLAUDE_BIN}"
        
    try:
        subprocess.Popen([term, "--", "bash", "-c", cmd], start_new_session=True)
        return True
    except Exception:
        return False
