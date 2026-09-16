#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS / JARVIS — MODEL REGISTRY, ROUTER & RUNTIME HEALTH
===========================================================
Source de vérité des modèles LLM et embeddings réellement chargés sur le rig.
Ports réels :
  - :1234 (GPU0, RTX 3080 10GB) : qwen2.5-7b (tools / execution / MCP)
  - :1235 (GPU1, RTX 2060 12GB) : qwen3-8b (reasoning / synthesis / table ronde)
  - :1300 (GPU0) : nomic-embed-text-v1.5 (embeddings 768d)
  - :1240 : Routeur local OMEGA HTTP
  - :11434 : DISABLED BY POLICY (Ollama local désactivé sur le rig mining)
"""

import os
import json
import socket
import urllib.request
from typing import Dict, Any, List, Optional


class ModelRegistry:
    """Catalogue unique des backends et modèles réels."""

    SLOTS = {
        "execution": {
            "name": "Qwen 2.5 7B Instruct",
            "model_id": "qwen2.5-7b",
            "port": 1234,
            "host": "127.0.0.1",
            "gpu": 0,
            "gpu_name": "NVIDIA GeForce RTX 3080",
            "role": "tools / execution / MCP / fast answers",
            "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "status": "active",
        },
        "reasoning": {
            "name": "Qwen 3 8B",
            "model_id": "qwen3-8b",
            "port": 1235,
            "host": "127.0.0.1",
            "gpu": 1,
            "gpu_name": "NVIDIA GeForce RTX 2060",
            "role": "reasoning / synthesis / board / arbitration",
            "endpoint": "http://127.0.0.1:1235/v1/chat/completions",
            "status": "active",
        },
        "embeddings": {
            "name": "Nomic Embed Text v1.5",
            "model_id": "nomic-embed-text-v1.5",
            "port": 1300,
            "host": "127.0.0.1",
            "gpu": 0,
            "gpu_name": "NVIDIA GeForce RTX 3080",
            "role": "embeddings (768 dimensions) / RAG vector search",
            "endpoint": "http://127.0.0.1:1300/v1/embeddings",
            "status": "active",
        },
        "ollama_legacy": {
            "name": "Ollama Daemon (:11434)",
            "model_id": "none",
            "port": 11434,
            "host": "127.0.0.1",
            "gpu": None,
            "gpu_name": None,
            "role": "legacy daemon",
            "endpoint": "http://127.0.0.1:11434",
            "status": "DISABLED BY POLICY",
        },
    }

    @classmethod
    def get_slot(cls, slot_name: str) -> Optional[Dict[str, Any]]:
        return cls.SLOTS.get(slot_name)

    @classmethod
    def list_models(cls) -> List[Dict[str, Any]]:
        return list(cls.SLOTS.values())


class RuntimeHealth:
    """Sondes de vivacité réelles (handshake TCP/HTTP, latence)."""

    @staticmethod
    def probe_port(host: str, port: int, timeout: float = 0.5) -> Dict[str, Any]:
        import time
        t0 = time.time()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency_ms = round((time.time() - t0) * 1000, 2)
                return {"online": True, "latency_ms": latency_ms, "error": None}
        except Exception as e:
            return {"online": False, "latency_ms": None, "error": type(e).__name__}

    @classmethod
    def check_all(cls) -> Dict[str, Any]:
        report = {}
        for key, info in ModelRegistry.SLOTS.items():
            if info["status"] == "DISABLED BY POLICY":
                report[key] = {
                    "model_id": info["model_id"],
                    "port": info["port"],
                    "online": False,
                    "status": "DISABLED BY POLICY",
                }
            else:
                probe = cls.probe_port(info["host"], info["port"])
                report[key] = {
                    "model_id": info["model_id"],
                    "port": info["port"],
                    "online": probe["online"],
                    "latency_ms": probe.get("latency_ms"),
                    "status": "OPERATIONAL" if probe["online"] else "DOWN",
                }
        return report


class ModelRouter:
    """Aiguillage déterministe selon l'intention ou le rôle."""

    @staticmethod
    def route_for_task(task_type: str) -> Dict[str, Any]:
        task_lower = (task_type or "").lower()
        if any(k in task_lower for k in ("tool", "exec", "mcp", "code", "fast")):
            return ModelRegistry.get_slot("execution")
        elif any(k in task_lower for k in ("embed", "vector", "rag_index")):
            return ModelRegistry.get_slot("embeddings")
        else:
            # Raisonnement, synthèse, arbitrage par défaut
            return ModelRegistry.get_slot("reasoning")


class BenchmarkRegistry:
    """Historique et enregistrement des benchmarks dual-GPU."""

    BENCHMARKS = {
        "qwen2.5-7b": {"port": 1234, "gpu": "RTX 3080", "tok_s": 48.4, "ttft_ms": 120},
        "qwen3-8b": {"port": 1235, "gpu": "RTX 2060", "tok_s": 24.1, "ttft_ms": 180},
    }

    @classmethod
    def get_benchmarks(cls) -> Dict[str, Any]:
        return cls.BENCHMARKS
