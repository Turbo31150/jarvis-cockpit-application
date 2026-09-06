#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CORE CONFIGURATION
Centralized configuration, paths, ports, cluster topology, and organ registries.
"""

import os
import socket

HOSTNAME = socket.gethostname()
MACHINE_NAME = os.environ.get("JARVIS_MACHINE", HOSTNAME.upper())

# Base paths
#
# JARVIS_HOME rend l'application DEPLACABLE — ajoute le 2026-09-03 pour la
# version portable sur cle USB. Sans cette variable, la racine restait
# ~/jarvis en dur : l'application copiee sur une cle allait chercher ses
# donnees dans le home de la machine hote, et n'y trouvait rien.
# Ordre de decision : la variable si elle est posee, sinon ~/jarvis comme avant.
# Le comportement sur cette machine est donc INCHANGE tant que JARVIS_HOME
# n'est pas defini.
HOME = os.path.expanduser("~")

# ATTENTION : JARVIS_HOME est DEJA exportee par ~/.profile et vaut ~/jarvis.
# S'en servir comme signal de portabilite rendait PORTABLE toujours vrai.
# On introduit donc une variable DEDIEE, que seul le lanceur portable pose.
# Ordre : racine portable -> JARVIS_HOME de l'environnement -> ~/jarvis.
_RACINE_PORTABLE = os.environ.get("JARVIS_COCKPIT_ROOT")
JARVIS_DIR = (_RACINE_PORTABLE or os.environ.get("JARVIS_HOME")
              or os.path.join(HOME, "jarvis"))
PORTABLE = bool(_RACINE_PORTABLE)
COCKPIT_DIR = os.path.join(JARVIS_DIR, "cockpit")
BIN_DIR = os.path.join(JARVIS_DIR, "bin")
SCRIPTS_DIR = os.path.join(JARVIS_DIR, "scripts")
DATA_DIR = os.path.join(JARVIS_DIR, "data")
BOARD_DIR = os.path.join(JARVIS_DIR, "board")
LOGS_DIR = os.path.join(JARVIS_DIR, "logs")
CONTENT_DIR = "/storage/content" if os.path.exists("/storage") else os.path.join(HOME, "content")

# Databases
MASTER_DB = os.path.join(JARVIS_DIR, "jarvis_master.db")
BOARD_DB = os.path.join(BOARD_DIR, "board.db")
VECTOR_DB = os.path.join(DATA_DIR, "jarvis_vector_store.db")
LOGS_DB = os.path.join(LOGS_DIR, "jarvis_logs.db")
ETOILE_DB = os.path.join(DATA_DIR, "etoile.db")
SQL_CACHE = os.path.join(COCKPIT_DIR, ".sql-cache.tsv")

# Cluster Network Endpoints
M6_HOST = "10.42.0.230"
M6_PORT = 1234
M6_URL = f"http://{M6_HOST}:{M6_PORT}"

M4_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{M4_HOST}:{OLLAMA_PORT}"

# ── Rig GPU local "mining" (MàJ 2026-09-06) ────────────────────────────────
# 3 GPU NVIDIA épinglés à 3 instances Ollama dédiées (Vulkan off, PCI_BUS_ID,
# persistence mode ON, swap 32 Go). Chaque instance ne voit QUE sa carte.
OLLAMA_3080_URL  = f"http://{M4_HOST}:11434"   # RTX 3080 (idx1) → qwen3:8b     (chat principal, ~65 tok/s)
OLLAMA_2060_URL  = f"http://{M4_HOST}:11435"   # RTX 2060 (idx0) → qwen2.5:7b   (secondaire / délestage)
OLLAMA_EMBED_URL = f"http://{M4_HOST}:11436"   # GTX 1660S(idx2) → nomic-embed-text (vectorisation permanente, KEEP_ALIVE=-1)
CHAT_MODEL_3080  = "qwen3:8b"
CHAT_MODEL_2060  = "qwen2.5:7b"
EMBED_MODEL      = "nomic-embed-text"

CHAT_PROXY_PORT = 18800
CHAT_PROXY_URL = f"http://{M4_HOST}:{CHAT_PROXY_PORT}"

COCKPIT_PORT = int(os.environ.get("COCKPIT_PORT", "8600"))
WIDGET_PORT = int(os.environ.get("WIDGET_PORT", "8899"))
BOARD_PORT = 8795
S8_PORT = 8799

# Organes du Noyau (Sondés en direct)
ORGANES = [
    ("Passerelle LLM (chat_proxy)", "127.0.0.1", 18800, "Cascade 0-token · alias jarvis-auto/fast/code"),
    ("Antigravity (agy)",           "127.0.0.1", 18811, "Pont IDE Google Antigravity"),
    ("CDP BrowserOS",               "127.0.0.1", 9108,  "Chrome headless pilotable"),
    ("CDP authentifié",             "127.0.0.1", 9222,  "Session navigateur réelle (LinkedIn/Upwork)"),
    ("BrowserOS serve",             "127.0.0.1", 9201,  "Service BrowserOS"),
    ("OpenClaw daemon",             "127.0.0.1", 18789, "Moteur multi-agents ACP"),
    ("Ollama RTX 3080 (chat)",      "127.0.0.1", 11434, "qwen3:8b épinglé RTX 3080 · ~65 tok/s"),
    ("Ollama RTX 2060 (délestage)", "127.0.0.1", 11435, "qwen2.5:7b épinglé RTX 2060"),
    ("Ollama GTX 1660S (vecto)",    "127.0.0.1", 11436, "nomic-embed-text · vectorisation permanente"),
    ("Board OS Serveur",            "127.0.0.1", 8795,  "Serveur de corpus FTS5 & experts"),
    ("Cockpit Web PWA",             "127.0.0.1", 8600,  "Serveur applicatif desktop & web"),
    ("PostgreSQL 15 Swarm",         "127.0.0.1", 5432,  "Base jarvis_agents relationnelle/vecto"),
    ("Redis 7 Alpine",              "127.0.0.1", 6379,  "Bus d'événements & cache mémoire"),
    ("n8n Workflows",               "127.0.0.1", 5678,  "Moteur d'automatisation n8n"),
    ("Portainer CE",                "127.0.0.1", 9000,  "Console administration Docker"),
    ("Whisper Voice Bridge",        "127.0.0.1", 9742,  "Interface de transcription vocale"),
    ("S8 Hardware Voice Node",      "127.0.0.1", 8799,  "Bouton matériel micro distant S8"),
]

# Catégories d'applications pour le Hub Bureau
APP_CATEGORIES = [
    "TOUTES",
    "AGENTS & IA",
    "CLUSTER & MACHINES",
    "SAAS & WEB",
    "DÉVELOPPEMENT",
    "SYSTÈME & OUTILS",
    "MULTIMÉDIA & AUDIO",
    "WINDOWS REMOTE",
    "PROSPECTION & VENTE",
]
