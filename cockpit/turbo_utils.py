#!/usr/bin/env python3
"""turbo_utils — utilitaires Turbo OS (générés + testés par le run massif OMEGA, 10/10).

Fonctions pures et testées, câblées au cockpit : routage d'intention, TTL, détection de document,
masquage de token, formatage, intention vocale, clés de checkpoint, dédup, pourcentage, clamp.
"""
from __future__ import annotations
import re


def dispatch_route(text: str) -> str:
    """Routeur d'intention Turbo OS (minuscules)."""
    t = (text or "").lower()
    if "facture" in t or "pdf" in t or "scan" in t or "cerfa" in t:
        return "document"
    if "acces" in t or "token" in t or "jeton" in t:
        return "token"
    if "vram" in t or "gpu" in t:
        return "gpu"
    if "voix" in t or "parle" in t:
        return "voice"
    if "cherche" in t or "internet" in t:
        return "web"
    if "mail" in t or "email" in t:
        return "email"
    return "chat"


def parse_ttl(s: str) -> int:
    """'7d'->604800, '24h'->86400, '30m'->1800, '45s'->45, '0'/'' -> 0 (illimité)."""
    if not s or s == "0":
        return 0
    u = s[-1].lower()
    if u.isdigit():
        return int(s)
    return int(s[:-1]) * {"d": 86400, "h": 3600, "m": 60, "s": 1}.get(u, 86400)


def is_document(name: str) -> bool:
    return bool(re.search(r"\.(png|jpe?g|pdf|tiff?|bmp|webp)$", (name or ""), re.I))


def mask_token(tok: str) -> str:
    return f"{tok[:4]}...{tok[-4:]}" if tok and len(tok) > 8 else "****"


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} o"
    if n < 1024 * 1024:
        return f"{round(n / 1024, 1)} Ko"
    return f"{round(n / (1024 * 1024), 1)} Mo"


def parse_voice_intent(text: str) -> str:
    t = (text or "").lower()
    if "arrête" in t or "arrete" in t or "stop" in t:
        return "STOP"
    if "pause" in t or "attends" in t:
        return "PAUSE"
    if "reprends" in t or "continue" in t:
        return "RESUME"
    if "annule" in t:
        return "CANCEL"
    return "ASK"


def checkpoint_key(session: str, phase: str, n: int) -> str:
    return f"CP-{session}-{phase}-{n:03d}"


def dedup_keep_order(items: list) -> list:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def pct(a: int, b: int) -> float:
    return round(a / b * 100, 1) if b else 0.0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v
