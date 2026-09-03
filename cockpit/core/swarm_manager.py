#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — SWARM & SERVICES MANAGER
Supervises Docker Swarm stacks, standalone containers, and local service ports.
"""

import subprocess
from .telemetry import is_port_open

SWARM_SERVICES = [
    {"name": "PostgreSQL 15 (Swarm)", "host": "127.0.0.1", "port": 5432, "role": "Base relationnelle & vectorielle master", "container": "jarvis-postgres"},
    {"name": "Redis 7 Alpine", "host": "127.0.0.1", "port": 6379, "role": "Event bus, caches & files de messages", "container": "jarvis-redis"},
    {"name": "n8n Automation", "host": "127.0.0.1", "port": 5678, "role": "Workflows d'orchestration & webhooks", "container": "jarvis-n8n"},
    {"name": "Portainer CE", "host": "127.0.0.1", "port": 9000, "role": "Interface d'administration Swarm", "container": "portainer"},
    {"name": "Ollama Local (OL1)", "host": "127.0.0.1", "port": 11434, "role": "Moteur d'inférence local (gemma3/qwen2.5)", "container": "systemd-ollama"},
    {"name": "Chat Proxy 18800", "host": "127.0.0.1", "port": 18800, "role": "Passerelle d'inférence unifiée", "container": "node-chat-proxy"},
    {"name": "Whisper Voice Bridge", "host": "127.0.0.1", "port": 9742, "role": "Bridge audio STT / TTS", "container": "whisper-bridge"},
    {"name": "BrowserOS Headless CDP", "host": "127.0.0.1", "port": 9108, "role": "Chrome headless d'automatisation", "container": "browseros"},
    {"name": "CDP Authentifié 9222", "host": "127.0.0.1", "port": 9222, "role": "Session Chrome authentifiée (LinkedIn)", "container": "chrome-cdp"},
]

def get_swarm_services_status() -> list[dict]:
    """Retourne l'état en direct de tous les services de l'infrastructure."""
    res = []
    for s in SWARM_SERVICES:
        online = is_port_open(s["host"], s["port"], timeout=0.2)
        res.append({
            "name": s["name"],
            "endpoint": f"{s['host']}:{s['port']}",
            "role": s["role"],
            "container": s["container"],
            "status": "UP" if online else "DOWN",
            "online": online
        })
    return res
