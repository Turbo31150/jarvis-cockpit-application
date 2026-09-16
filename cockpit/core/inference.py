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
# Rig "mining" : gemma3:4b prioritaire en mode GPU 100% pour le Cockpit Bureau,
# puis gemma4 et gemma3.5. Les noms sont matchés SANS tenir compte du tag (:latest).
_OLLAMA_PREFERRED = ["gemma3:4b", "gemma3-4b", "gemma4", "gemma3.5", "qwen3:8b", "qwen2.5:7b", "qwen2.5:1.5b"]

# LM Studio LOCAL (0 token, illimité) — API OpenAI-compatible sur cette machine.
# Prioritaire sur le nœud M6 distant, souvent injoignable depuis le rig "mining".
# LM Studio écoute sur 0.0.0.0:1234 → joignable en loopback ET via l'IP tether USB
# du rig (192.168.42.241, interface enx*). On essaie plusieurs hôtes, 1er ouvert gagne.
_LMSTUDIO_CANDIDATES = [
    os.environ.get("JARVIS_LMSTUDIO_URL", ""),
    "http://127.0.0.1:1234",
    "http://192.168.42.241:1234",
]
# Ordre de préférence LM Studio (surchargé par JARVIS_LMSTUDIO_MODELS, CSV).
# La sélection reste RÉSIDENT-only : un nom absent/non chargé est simplement ignoré.
_LMSTUDIO_PREFERRED = [m.strip() for m in os.environ.get(
    "JARVIS_LMSTUDIO_MODELS",
    "gemma3:4b, gemma3-4b, gemma4, gemma3.5, qwen3-8b, qwen2.5-7b, mistral-7b-instruct, deepseek-r1-7b, qwen3-1.7b"
).split(",") if m.strip()]

# Modèles à raisonnement : on préfixe le prompt de « /nothink » (usage documenté
# sur GitHub, jarvis/docs/ARCHITECTURE.md) pour couper le <think> à la source.
_NOTHINK_MODELS = ("qwen3", "deepseek-r1", "deepseek-r1-7b", "-r1")


def _lmstudio_base(timeout: float = 0.5):
    """Retourne la 1ʳᵉ base LM Studio dont le port TCP répond (ou None)."""
    for base in _LMSTUDIO_CANDIDATES:
        if base and _port_open(base, timeout=timeout):
            return base
    return None


def _lmstudio_local_model(base_url: str, timeout: float = 2.0):
    """Modèle de chat RÉSIDENT (déjà chargé en VRAM) du LM Studio local.

    Doctrine rig "mining" (Notion ⛏️ « rig de minage reconverti ») : les 3 GPU
    sont sur des risers PCIe x1 → charger un modèle ~9 Go prend des MINUTES et
    fige l'API (« Engine protocol startup was aborted », HTTP 000). On ne doit
    JAMAIS déclencher de chargement JIT depuis le cockpit. On lit donc
    /api/v0/models (endpoint natif LM Studio, champ `state`) et on ne retient
    qu'un modèle déjà `loaded`. Si aucun n'est résident → None (tier-0 sauté,
    repli Ollama). Une fois chargé, l'inférence tourne en VRAM en ~2 s.
    """
    loaded = []
    # 1) LM Studio natif : /api/v0/models expose `state` → on ne retient que `loaded`.
    try:
        req = urllib.request.Request(f"{base_url}/api/v0/models")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode()).get("data", [])
        loaded = [m.get("id") for m in data
                  if m.get("state") == "loaded"
                  and m.get("type") != "embeddings"
                  and m.get("id") and "embed" not in m.get("id", "").lower()]
    except Exception:
        loaded = []
    # 2) Repli llama-server OpenAI (/v1/models) : les modèles listés sont servis en VRAM.
    #    Formats tolérés : {"data":[{"id"}]} (OpenAI) et {"models":[{"name"/"model"}]} (Ollama-bundled).
    if not loaded:
        try:
            req = urllib.request.Request(f"{base_url}/v1/models")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read().decode())
            items = d.get("data") or d.get("models") or []
            for m in items:
                mid = m.get("id") or m.get("name") or m.get("model")
                if mid and "embed" not in str(mid).lower():
                    loaded.append(mid)
        except Exception:
            loaded = []
    if not loaded:
        return None
    for pref in _LMSTUDIO_PREFERRED:
        if pref in loaded:
            return pref
    return loaded[0]


def list_ollama_models(timeout: float = 1.5) -> list:
    """Retourne les modèles Ollama réellement installés (vide si service absent)."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _ollama_resident_models(timeout: float = 1.5) -> list:
    """Modèles Ollama actuellement CHARGÉS en VRAM (via /api/ps)."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/ps")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _match_installed(pref: str, installed: list):
    """Résout un nom préféré vers le nom Ollama réellement installé, en tolérant
    le tag. Ex. : "gemma4" → "gemma4:latest", "gemma3.5" → "gemma3.5:latest".
    Priorité : correspondance exacte, puis "<pref>:latest", puis même base avant ':'."""
    if pref in installed:
        return pref
    if f"{pref}:latest" in installed:
        return f"{pref}:latest"
    # Un préféré sans tag (ex. "gemma4") matche tout "gemma4:<tag>" installé.
    if ":" not in pref:
        for m in installed:
            if m.split(":")[0] == pref:
                return m
    return None


def _ollama_candidates() -> list:
    """Modèles à essayer, doctrine « résident d'abord » (rig PCIe x1) : on privilégie
    le modèle DÉJÀ chargé pour ne pas déclencher un cold-load de ~9 Go qui traîne sur
    le bus x1 ; ensuite les préférés présents, puis le reste des installés."""
    installed = list_ollama_models()
    resident = _ollama_resident_models()
    if not installed:
        return resident or list(_OLLAMA_PREFERRED)  # tentative à l'aveugle si /api/tags échoue
    ordered = [m for m in resident if m in installed]                       # 1) déjà en VRAM
    for pref in _OLLAMA_PREFERRED:                                           # 2) préférés (tag-insensible)
        match = _match_installed(pref, installed)
        if match and match not in ordered:
            ordered.append(match)
    ordered += [m for m in installed if m not in ordered]                  # 3) reste
    return ordered

_CORE_PROMPT_CACHE = {}

def _load_core_prompt() -> str:
    """System prompt cœur de JARVIS (JARVIS CORE VOCAL V4). Chargé depuis
    ~/prompts/JARVIS_CORE_VOCAL_V4.md, avec fallback minimal. Synchronise LM Studio
    sur le noyau exécutif vocal (MODE=EXECUTION, anti-planification)."""
    import os
    if "core" in _CORE_PROMPT_CACHE:
        return _CORE_PROMPT_CACHE["core"]
    # canonique (EXECUTION MODE) d'abord, puis V4, puis fallback minimal
    for name in ("JARVIS_CORE_VOCAL.md", "JARVIS_CORE_VOCAL_V4.md"):
        path = os.path.expanduser("~/prompts/" + name)
        try:
            with open(path, encoding="utf-8") as f:
                txt = f.read().strip()
            if txt:
                _CORE_PROMPT_CACHE["core"] = txt
                return txt
        except Exception:
            continue
    return "Tu es JARVIS, assistant IA d'élite. MODE=EXECUTION : agis, n'annonce pas."

def generate_completion(prompt: str, sys_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.3) -> dict:
    """Cascade d'inférence robuste : Ollama GPU / LM Studio GPU -> M6 GPU direct -> Chat Proxy."""
    # System prompt cœur JARVIS par défaut (V4) ; un sys_prompt explicite reste prioritaire.
    if sys_prompt is None:
        sys_prompt = _load_core_prompt()
    # Règle M4/M6 : max_tokens >= 512 pour éviter les sorties vides sur modèles à raisonnement
    effective_max_tokens = max(max_tokens, 512)

    # Récupération du réglage cockpit (par défaut gemma3:4b en mode GPU)
    cfg_engine = "gemma3:4b"
    try:
        from .settings_engine import get_cockpit_settings
        cfg_engine = get_cockpit_settings().get("settings", {}).get("ai_engine", "gemma3:4b")
    except Exception:
        pass

    prefer_gemma = any(k in str(cfg_engine).lower() for k in ("gemma", "4b"))

    def _call_ollama(cand_list):
        _gpu_prompt = sys_prompt + "\n\n" + prompt
        for model_name in cand_list:
            try:
                _gpu_payload = json.dumps({
                    "model": model_name,
                    "prompt": _gpu_prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {
                        "num_predict": max(64, effective_max_tokens),
                        "temperature": temperature,
                        "num_gpu": 999,
                    },
                }).encode("utf-8")
                _gpu_req = urllib.request.Request(f"{OLLAMA_URL}/api/generate",
                                                  data=_gpu_payload,
                                                  headers={"Content-Type": "application/json"})
                t0 = time.time()
                with urllib.request.urlopen(_gpu_req, timeout=120) as _gpu_resp:
                    _gpu_data = json.loads(_gpu_resp.read().decode())
                    content = (_gpu_data.get("response") or "").strip()
                    if "</think>" in content:
                        content = content.split("</think>")[-1].strip()
                    if content:
                        return {
                            "content": content,
                            "source": f"Ollama GPU ({model_name}, 100% GPU)",
                            "latency": round(time.time() - t0, 2),
                            "success": True,
                            "model": model_name,
                        }
            except Exception:
                continue
        return None

    def _call_lmstudio():
        try:
            base = _lmstudio_base()
            if base:
                modele = _lmstudio_local_model(base)
                if modele:
                    user_content = prompt
                    if any(tag in modele.lower() for tag in _NOTHINK_MODELS):
                        user_content = "/nothink\n" + prompt
                    payload = json.dumps({
                        "model": modele,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": temperature,
                        "max_tokens": effective_max_tokens
                    }).encode("utf-8")
                    req = urllib.request.Request(f"{base}/v1/chat/completions",
                                                 data=payload, headers={"Content-Type": "application/json"})
                    t0 = time.time()
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode())
                        choice = data["choices"][0]["message"]
                        content = (choice.get("content") or "").strip()
                        if not content and "reasoning_content" in choice:
                            content = choice["reasoning_content"].strip()
                        if "</think>" in content:
                            content = content.split("</think>")[-1].strip()
                        if content:
                            return {
                                "content": content,
                                "source": f"LM Studio GPU ({modele}, 0 token)",
                                "latency": round(time.time() - t0, 2),
                                "success": True,
                                "model": modele
                            }
        except Exception:
            pass
        return None

    # 1. Si gemma3:4b est préféré/configuré, Ollama GPU tourne en priorité absolue
    if prefer_gemma:
        cands = [m for m in _ollama_candidates() if "gemma" in m.lower()]
        res = _call_ollama(cands)
        if res:
            return res

    # 2. Sinon ou en repli : LM Studio GPU (qwen3-8b / qwen2.5-7b)
    res_lms = _call_lmstudio()
    if res_lms:
        return res_lms

    # 3. Repli Ollama général
    res_ol = _call_ollama(_ollama_candidates())
    if res_ol:
        return res_ol

    # Repli local :1234 /v1 (redondant avec le tier LM Studio ci-dessus ; filet si _call_lmstudio a échoué)
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

    # Repli legacy Ollama-natif /api/generate (daemon :11434 mort → 404 fast-fail ; conservé si un daemon Ollama est un jour relancé)
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

    # 2b. Repli délestage : RTX 2060 via :1235 (qwen3-8b, llama-server API OpenAI /v1/).
    #     Utile si le tier principal :1234 (3080) est occupé/indisponible.
    try:
        if _port_open(OLLAMA_2060_URL):
            ol_payload = json.dumps({
                "model": "qwen3-8b",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            }).encode("utf-8")
            req_ol = urllib.request.Request(f"{OLLAMA_2060_URL}/v1/chat/completions", data=ol_payload, headers={"Content-Type": "application/json"})
            t0 = time.time()
            with urllib.request.urlopen(req_ol, timeout=90) as resp_ol:
                data_ol = json.loads(resp_ol.read().decode())
                choice = data_ol["choices"][0]["message"]
                content = (choice.get("content") or choice.get("reasoning_content") or "").strip()
                if content:
                    return {
                        "content": content,
                        "source": "RTX 2060 (:1235 qwen3-8b, délestage)",
                        "latency": round(time.time() - t0, 2),
                        "success": True,
                        "model": "qwen3-8b"
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
    """Vectorisation via nomic-embed-text-v1.5 (:1300, llama-server OpenAI /v1/embeddings, 768d).

    inputs : str ou list[str]. Retourne {"embeddings": [...], "model", "source", "success"}.
    Le modèle reste chargé (KEEP_ALIVE=-1) → pas de coût de rechargement.
    """
    if isinstance(inputs, str):
        inputs = [inputs]
    try:
        if not _port_open(OLLAMA_EMBED_URL):
            raise ConnectionError("instance embeddings (:1300) hors-ligne")
        payload = json.dumps({"model": EMBED_MODEL, "input": inputs}).encode("utf-8")
        req = urllib.request.Request(f"{OLLAMA_EMBED_URL}/v1/embeddings", data=payload, headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            # OpenAI /v1/embeddings → {"data":[{"embedding":[...]}, ...]} ; fallback Ollama /api/embed
            if isinstance(data.get("data"), list):
                embs = [d["embedding"] for d in data["data"] if "embedding" in d]
            else:
                embs = data.get("embeddings") or ([data["embedding"]] if "embedding" in data else [])
            return {
                "embeddings": embs,
                "model": EMBED_MODEL,
                "source": "Embeddings (:1300, nomic-embed-text-v1.5)",
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
