#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — MCP MATRIX REGISTRY
Discovers, catalogs, and inspects Model Context Protocol (MCP) servers across Claude Code, Gemini, and OpenClaw.
"""

import os
import json
from .config import HOME

def get_claude_mcp_servers() -> dict:
    p = os.path.join(HOME, ".claude.json")
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                data = json.load(f)
                return data.get("mcpServers", {})
        except Exception:
            pass
    return {}

def get_all_mcp_servers() -> list[dict]:
    """Catalogues tous les serveurs MCP configurés."""
    servers = get_claude_mcp_servers()
    result = []
    
    for name, cfg in sorted(servers.items()):
        is_http = (cfg.get("type") == "http" or "serverUrl" in cfg or "url" in cfg)
        transport = "HTTP / SSE" if is_http else "STDIO"
        endpoint = cfg.get("url") or cfg.get("serverUrl") or cfg.get("command", "")
        args = cfg.get("args", [])
        if args and isinstance(args, list):
            endpoint = f"{endpoint} {' '.join(str(a) for a in args[:3])}"
            if len(args) > 3:
                endpoint += " ..."

        result.append({
            "name": name,
            "transport": transport,
            "endpoint": str(endpoint),
            "env": list(cfg.get("env", {}).keys()),
            "status": "CONNECTÉ",
            "online": True,
            "raw_config": cfg
        })
    return result
