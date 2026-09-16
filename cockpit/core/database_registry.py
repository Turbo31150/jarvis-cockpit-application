#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS / JARVIS — DATABASE REGISTRY
=====================================
Catalogue unique et cartographie des bases de données réelles du cluster :
  - board.db (RAG, claims, sources, experts)
  - etoile.db (télémétrie, état des nœuds, graphe cognitif)
  - locomotive_moisson.db (pages web moissonnées)
  - domino_continu.db (tâches et workflows Domino)
  - jarvis_master.db (paramètres, sessions, checkpoints)
  - PostgreSQL (conteneur jarvis-postgres :5432, bases jarvis_main, jarvis, postgres)
"""

import os
import sqlite3
from typing import Dict, Any, List


class DatabaseRegistry:
    """Registre des bases SQLite et relationnelles du système."""

    DATABASES = [
        {
            "name": "board.db",
            "type": "SQLite (FTS5 + Vecteurs)",
            "path": "/home/turbo/jarvis/board/board.db",
            "owner": "RAG & Claims Engine",
            "purpose": "Corpus documentaire, claims auditables, RAG souverain",
            "source_of_truth": True,
            "read_write": "RW",
        },
        {
            "name": "etoile.db",
            "type": "SQLite",
            "path": "/home/turbo/jarvis/data/etoile.db",
            "owner": "Cognitive Topology",
            "purpose": "Graphe de routage cognitif et mémoire relationnelle",
            "source_of_truth": True,
            "read_write": "RW",
        },
        {
            "name": "locomotive_moisson.db",
            "type": "SQLite",
            "path": "/home/turbo/jarvis/databases/locomotive_moisson.db",
            "owner": "Web Scraper / Harvester",
            "purpose": "Pages web moissonnées et indexées pour prospection",
            "source_of_truth": True,
            "read_write": "RW",
        },
        {
            "name": "domino_continu.db",
            "type": "SQLite",
            "path": "/home/turbo/jarvis/domino-continu/domino_continu.db",
            "owner": "Domino Engine",
            "purpose": "Journal des étapes et exécutions Domino autonomes",
            "source_of_truth": True,
            "read_write": "RW",
        },
        {
            "name": "jarvis_master.db",
            "type": "SQLite",
            "path": "/home/turbo/jarvis/jarvis_master.db",
            "owner": "Master Controller",
            "purpose": "Tâches maîtres, paramètres système et logs d'orchestration",
            "source_of_truth": True,
            "read_write": "RW",
        },
        {
            "name": "jarvis-postgres",
            "type": "PostgreSQL 15 (Docker)",
            "path": "localhost:5432 (conteneur jarvis-postgres)",
            "owner": "Tour SSH / Swarm",
            "purpose": "Bases jarvis_main (7,7 Mo), jarvis (7,6 Mo), postgres",
            "source_of_truth": True,
            "read_write": "RW",
        },
    ]

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        result = []
        for db in cls.DATABASES:
            entry = dict(db)
            p = db["path"]
            if os.path.exists(p):
                entry["exists"] = True
                entry["size_bytes"] = os.path.getsize(p)
                entry["size_mb"] = round(os.path.getsize(p) / (1024 * 1024), 2)
            elif "localhost:5432" in p:
                entry["exists"] = True  # Conteneur géré séparément
            else:
                entry["exists"] = False
                entry["size_bytes"] = 0
                entry["size_mb"] = 0
            result.append(entry)
        return result
