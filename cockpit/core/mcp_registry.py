#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — MCP MATRIX REGISTRY
Discovers, catalogs, and inspects Model Context Protocol (MCP) servers across
Claude Code, ses plugins de marketplace et les connecteurs claude.ai.

Sur cette machine les serveurs MCP ne vivent PAS uniquement dans
~/.claude.json > mcpServers (souvent vide). Ils proviennent de trois sources :
  1. ~/.claude.json > mcpServers               (racine + par-projet, stdio/http)
  2. ~/.claude.json > claudeAiMcpEverConnected  (connecteurs claude.ai HTTP)
  3. Plugins de marketplace                     (clés « plugin:famille:nom »
     référencées dans ~/.claude/mcp-needs-auth-cache.json)
Le registre agrège les trois pour que la rubrique MCP ne soit plus vide.
"""

import os
import json
from .config import HOME

CLAUDE_JSON = os.path.join(HOME, ".claude.json")
AUTH_CACHE = os.path.join(HOME, ".claude", "mcp-needs-auth-cache.json")


def _load_json(path: str):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def get_claude_mcp_servers() -> dict:
    """Serveurs mcpServers déclarés dans ~/.claude.json (racine + tous les projets)."""
    data = _load_json(CLAUDE_JSON)
    if not isinstance(data, dict):
        return {}
    servers = dict(data.get("mcpServers", {}) or {})
    for proj in (data.get("projects", {}) or {}).values():
        if isinstance(proj, dict):
            for name, cfg in (proj.get("mcpServers", {}) or {}).items():
                servers.setdefault(name, cfg)
    return servers


def _entry(name, transport, endpoint, status, online, env=None, raw=None):
    return {
        "name": name,
        "transport": transport,
        "endpoint": str(endpoint or ""),
        "env": env or [],
        "status": status,
        "online": online,
        "raw_config": raw or {},
    }


def get_all_mcp_servers() -> list[dict]:
    """Catalogue unifié de tous les serveurs MCP connus de la machine."""
    result = []
    vus = set()

    # ── 1. Serveurs déclarés dans ~/.claude.json (stdio / http) ──
    for name, cfg in sorted(get_claude_mcp_servers().items()):
        cfg = cfg or {}
        is_http = (cfg.get("type") == "http" or "serverUrl" in cfg or "url" in cfg)
        transport = "HTTP / SSE" if is_http else "STDIO"
        endpoint = cfg.get("url") or cfg.get("serverUrl") or cfg.get("command", "")
        args = cfg.get("args", [])
        if args and isinstance(args, list):
            endpoint = f"{endpoint} {' '.join(str(a) for a in args[:3])}"
            if len(args) > 3:
                endpoint += " ..."
        result.append(_entry(name, transport, endpoint, "CONNECTÉ", True,
                             list((cfg.get("env") or {}).keys()), cfg))
        vus.add(name)

    # ── 2. Connecteurs claude.ai (HTTP hébergé côté Anthropic) ──
    data = _load_json(CLAUDE_JSON) or {}
    for name in (data.get("claudeAiMcpEverConnected", []) or []):
        if name in vus:
            continue
        result.append(_entry(name, "HTTP / claude.ai", "connecteur hébergé claude.ai",
                             "CONNECTÉ", True))
        vus.add(name)

    # ── 3. Plugins de marketplace (auth requise / disponibles) ──
    auth = _load_json(AUTH_CACHE) or {}
    for key in sorted(auth.keys()):
        if key.startswith("claude.ai "):
            name, transport, endpoint = key, "HTTP / claude.ai", "connecteur hébergé claude.ai"
        elif key.startswith("plugin:"):
            parts = key.split(":")
            fam = parts[1] if len(parts) > 1 else "?"
            nom = parts[-1]
            name, transport, endpoint = f"{nom} (plugin)", "Plugin MCP", f"famille : {fam}"
        else:
            name, transport, endpoint = key, "Plugin MCP", ""
        if name in vus:
            continue
        result.append(_entry(name, transport, endpoint, "AUTH REQUISE", False))
        vus.add(name)

    return result
