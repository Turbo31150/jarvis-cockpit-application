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


# ── Run massif #2 — engines V4 (vidéo / OCR / navigateur / PC control) ──
import unicodedata


def parse_duration(s: str) -> int:
    parts = [int(x) for x in str(s).split(":")]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def clean_ocr_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def extract_urls(text: str) -> list:
    return re.findall(r"https?://\S+", text or "")


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t


def key_combo(s: str) -> str:
    return "+".join(p.strip().lower() for p in (s or "").split("+"))


def format_duration(sec: int) -> str:
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def is_safe_path(p: str) -> bool:
    return ".." not in (p or "").split("/")


def build_ffmpeg_x11grab(display: str, size: str, out: str) -> str:
    return f"ffmpeg -y -f x11grab -video_size {size} -i {display}.0 {out}"


# ── Run massif #3 — utilitaires produit (facturation / identité / moat) ──
def parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"oui", "o", "true", "1", "yes", "vrai"}


def format_euro(cents: int) -> str:
    return f"{cents / 100:.2f} €".replace(".", ",")


def cerfa_num(text: str) -> str:
    m = re.search(r"cerfa\s*(\d{4,5}\*?\d{0,2})", text or "", re.I)
    return m.group(1) if m else ""


def siret_valid(s: str) -> bool:
    return bool(re.fullmatch(r"\d{14}", s or ""))


def word_count(text: str) -> int:
    return len((text or "").split())


def redact_email(e: str) -> str:
    if "@" not in (e or ""):
        return "***"
    local, dom = e.split("@", 1)
    return f"{local[:1]}***@{dom}"


def normalize_phone(s: str) -> str:
    s = s or ""
    digits = re.sub(r"\D", "", s)
    return ("+" + digits) if s.strip().startswith("+") else digits


def ratio_grounded(sup: int, weak: int, total: int) -> float:
    return round((sup + weak) / total * 100, 1) if total else 0.0
