#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — INFERENCE ENGINE
Multi-tier local LLM inference cascade (M6 GPU direct link -> Ollama local M4 -> Chat Proxy)
Ensures 0-token cost, strict reasoning token padding (>=512 tokens) and transparent fallback.
"""

import json
import time
import urllib.request
from .config import M6_URL, OLLAMA_URL, CHAT_PROXY_URL

def generate_completion(prompt: str, sys_prompt: str = "Tu es JARVIS, assistant IA d'élite.", max_tokens: int = 1024, temperature: float = 0.3) -> dict:
    """Cascade d'inférence robuste : M6 GPU direct -> M4 Ollama -> Chat Proxy."""
    # Règle M4/M6 : max_tokens >= 512 pour éviter les sorties vides sur modèles à raisonnement
    effective_max_tokens = max(max_tokens, 512)
    
    # 1. Tier 1 : Nœud M6 GPU (Lien direct 10.42.0.230)
    try:
        payload = json.dumps({
            "model": "qwen2.5-coder-14b-instruct",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": effective_max_tokens
        }).encode("utf-8")
        
        req = urllib.request.Request(f"{M6_URL}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            choice = data["choices"][0]["message"]
            content = choice.get("content", "").strip()
            if not content and "reasoning_content" in choice:
                content = choice["reasoning_content"].strip()
            if content:
                return {
                    "content": content,
                    "source": "M6 GPU (LM Studio qwen2.5-coder-14b)",
                    "latency": round(time.time() - t0, 2),
                    "success": True,
                    "model": "qwen2.5-coder-14b-instruct"
                }
    except Exception:
        pass

    # 2. Tier 2 : Ollama Local M4 (127.0.0.1:11434)
    full_prompt = sys_prompt + "\n\n" + prompt
    for model_name in ["gemma3:4b", "qwen2.5:7b"]:
        try:
            ol_payload = json.dumps({
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {"num_predict": effective_max_tokens, "temperature": temperature}
            }).encode("utf-8")
            
            req_ol = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=ol_payload, headers={"Content-Type": "application/json"})
            t0 = time.time()
            with urllib.request.urlopen(req_ol, timeout=25) as resp_ol:
                data_ol = json.loads(resp_ol.read().decode())
                content = data_ol.get("response", "").strip()
                if content:
                    return {
                        "content": content,
                        "source": f"M4 Local (Ollama {model_name})",
                        "latency": round(time.time() - t0, 2),
                        "success": True,
                        "model": model_name
                    }
        except Exception:
            continue

    # 3. Tier 3 : Chat Proxy (127.0.0.1:18800)
    try:
        proxy_payload = json.dumps({
            "model": "jarvis-fast",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": effective_max_tokens
        }).encode("utf-8")
        req_proxy = urllib.request.Request(f"{CHAT_PROXY_URL}/v1/chat/completions", data=proxy_payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req_proxy, timeout=20) as resp_proxy:
            data_proxy = json.loads(resp_proxy.read().decode())
            content = data_proxy["choices"][0]["message"]["content"].strip()
            if content:
                return {
                    "content": content,
                    "source": "Chat Proxy (127.0.0.1:18800)",
                    "latency": round(time.time() - t0, 2),
                    "success": True,
                    "model": "jarvis-fast"
                }
    except Exception:
        pass

    return {
        "content": "⚠️ Tous les moteurs d'inférence locaux sont actuellement indisponibles ou occupés.",
        "source": "AUCUN",
        "latency": 0.0,
        "success": False,
        "model": "none"
    }
