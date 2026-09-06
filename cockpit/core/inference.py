#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — INFERENCE ENGINE
Multi-tier local LLM inference cascade (M6 GPU direct link -> Ollama local M4 -> Chat Proxy)
Ensures 0-token cost, strict reasoning token padding (>=512 tokens) and transparent fallback.
"""

import os
import json
import time
import socket
import urllib.request
from urllib.parse import urlparse
from .config import (M6_URL, OLLAMA_URL, CHAT_PROXY_URL,
                     OLLAMA_2060_URL, OLLAMA_EMBED_URL, EMBED_MODEL,
                     CLOUD_PROVIDERS)


def _port_open(url: str, timeout: float = 0.5) -> bool:
    """Sonde TCP rapide : évite d'attendre le timeout HTTP complet sur un nœud absent."""
    try:
        p = urlparse(url)
        with socket.create_connection((p.hostname, p.port or 80), timeout=timeout):
            return True
    except Exception:
        return False

# Ordre de préférence si présents ; complété dynamiquement par /api/tags.
# Rig "mining" : qwen3:8b (RTX 3080) prioritaire, puis repli local.
_OLLAMA_PREFERRED = ["qwen3:8b", "qwen2.5:7b", "gemma3:4b", "qwen2.5:1.5b"]


def list_ollama_models(timeout: float = 1.5) -> list:
    """Retourne les modèles Ollama réellement installés (vide si service absent)."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _ollama_candidates() -> list:
    """Modèles à essayer : préférés présents d'abord, puis le reste des installés."""
    installed = list_ollama_models()
    if not installed:
        return list(_OLLAMA_PREFERRED)  # tentative à l'aveugle si /api/tags échoue
    ordered = [m for m in _OLLAMA_PREFERRED if m in installed]
    ordered += [m for m in installed if m not in ordered]
    return ordered

def generate_completion(prompt: str, sys_prompt: str = "Tu es JARVIS, assistant IA d'élite.", max_tokens: int = 1024, temperature: float = 0.3) -> dict:
    """Cascade d'inférence robuste : M6 GPU direct -> M4 Ollama -> Chat Proxy."""
    # Règle M4/M6 : max_tokens >= 512 pour éviter les sorties vides sur modèles à raisonnement
    effective_max_tokens = max(max_tokens, 512)
    
    # 1. Tier 1 : Nœud M6 GPU (Lien direct 10.42.0.230) — sondé avant appel
    try:
        if not _port_open(M6_URL):
            raise ConnectionError("M6 hors-ligne")
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

    # 2. Tier 2 : Ollama Local M4 (127.0.0.1:11434) — modèles auto-découverts
    full_prompt = sys_prompt + "\n\n" + prompt
    for model_name in _ollama_candidates():
        try:
            # Ollama (souvent CPU) : on respecte le budget demandé, sans le gonfler
            # à 512 comme pour M6 — sinon un petit modèle dépasse le timeout.
            ol_payload = json.dumps({
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "options": {"num_predict": max(64, min(max_tokens, 384)), "temperature": temperature}
            }).encode("utf-8")

            req_ol = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=ol_payload, headers={"Content-Type": "application/json"})
            t0 = time.time()
            with urllib.request.urlopen(req_ol, timeout=90) as resp_ol:
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

    # 2b. Tier 2b : délestage RTX 2060 (127.0.0.1:11435, qwen2.5:7b épinglé)
    #     Utile quand la 3080 (:11434) est occupée par un autre client (cockpit, IDE).
    try:
        if _port_open(OLLAMA_2060_URL):
            ol_payload = json.dumps({
                "model": "qwen2.5:7b",
                "prompt": full_prompt,
                "stream": False,
                "options": {"num_predict": max(64, min(max_tokens, 384)), "temperature": temperature}
            }).encode("utf-8")
            req_ol = urllib.request.Request(f"{OLLAMA_2060_URL}/api/generate", data=ol_payload, headers={"Content-Type": "application/json"})
            t0 = time.time()
            with urllib.request.urlopen(req_ol, timeout=90) as resp_ol:
                data_ol = json.loads(resp_ol.read().decode())
                content = data_ol.get("response", "").strip()
                if content:
                    return {
                        "content": content,
                        "source": "RTX 2060 (Ollama qwen2.5:7b, délestage)",
                        "latency": round(time.time() - t0, 2),
                        "success": True,
                        "model": "qwen2.5:7b"
                    }
    except Exception:
        pass

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


def embed(inputs, timeout: float = 60.0) -> dict:
    """Vectorisation permanente via la GTX 1660S (Ollama :11436, nomic-embed-text résident).

    inputs : str ou list[str]. Retourne {"embeddings": [...], "model", "source", "success"}.
    Le modèle reste chargé (KEEP_ALIVE=-1) → pas de coût de rechargement.
    """
    if isinstance(inputs, str):
        inputs = [inputs]
    try:
        if not _port_open(OLLAMA_EMBED_URL):
            raise ConnectionError("instance embeddings (1660S) hors-ligne")
        payload = json.dumps({"model": EMBED_MODEL, "input": inputs}).encode("utf-8")
        req = urllib.request.Request(f"{OLLAMA_EMBED_URL}/api/embed", data=payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            embs = data.get("embeddings") or ([data["embedding"]] if "embedding" in data else [])
            return {
                "embeddings": embs,
                "model": EMBED_MODEL,
                "source": "GTX 1660S (Ollama nomic-embed-text)",
                "latency": round(time.time() - t0, 2),
                "success": bool(embs),
            }
    except Exception as e:
        return {"embeddings": [], "model": EMBED_MODEL, "source": "AUCUN",
                "latency": 0.0, "success": False, "error": str(e)}


# ── Fournisseurs cloud externes (Gemini / Mistral / Manus) ─────────────────────
# Déchargent le CPU local vers le cloud. Les clés sont lues DANS L'ENVIRONNEMENT
# au runtime (jamais stockées dans le code). Un fournisseur est "disponible" si
# son proxy local répond (Gemini) ou si sa clé + son URL sont présentes (OpenAI-compat).

def _cloud_key(prov):
    ke = prov.get("key_env")
    return os.environ.get(ke) if ke else None


def cloud_available(name):
    prov = CLOUD_PROVIDERS.get(name)
    if not prov or not prov.get("chat_url"):
        return False
    if prov["kind"] == "openai":
        return bool(_cloud_key(prov))
    if prov["kind"] == "proxy":
        return _port_open(prov["probe"])
    return False


def list_cloud_available():
    """Retourne la liste des fournisseurs cloud actuellement utilisables."""
    return [n for n in CLOUD_PROVIDERS if cloud_available(n)]


def generate_cloud(prompt, sys_prompt="Tu es JARVIS, assistant IA d'élite.",
                   provider=None, max_tokens=1024, temperature=0.3, timeout=120):
    """Inférence via un fournisseur cloud OpenAI-compat (Gemini proxy / Mistral / Manus).

    provider=None → essaie dans l'ordre gemini, mistral, manus (premier dispo qui répond).
    Retourne le dict standard {content, source, latency, success, model, provider}.
    """
    order = [provider] if provider else ["gemini", "mistral", "manus"]
    last_err = ""
    for name in order:
        prov = CLOUD_PROVIDERS.get(name)
        if not prov or not cloud_available(name):
            continue
        try:
            headers = {"Content-Type": "application/json"}
            key = _cloud_key(prov)
            if key:
                headers["Authorization"] = f"Bearer {key}"
            payload = json.dumps({
                "model": prov["model"],
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max(max_tokens, 256),
            }).encode("utf-8")
            req = urllib.request.Request(prov["chat_url"], data=payload, headers=headers)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    return {
                        "content": content,
                        "source": f"Cloud {name} ({prov['model']})",
                        "latency": round(time.time() - t0, 2),
                        "success": True,
                        "model": prov["model"],
                        "provider": name,
                    }
        except Exception as e:
            last_err = f"{name}: {e}"
            continue
    return {"content": "", "source": "AUCUN cloud dispo", "latency": 0.0,
            "success": False, "model": "none", "error": last_err}
