#!/usr/bin/env python3
"""turbo_engines — engines système Turbo OS (V4) : PC control (X11/xdotool), navigateur (CDP), vidéo (ffmpeg).

Réutilise les interfaces réelles déjà présentes : X11 :1, Chrome CDP :9222, ffmpeg x11grab.
Fonctions sûres par défaut (lecture) ; les actions (focus/keys/capture) sont explicites.
"""
from __future__ import annotations
import json
import os
import subprocess
import urllib.request

_ENV = {**os.environ, "DISPLAY": ":1", "XAUTHORITY": "/run/user/1000/gdm/Xauthority"}


# ── PC CONTROL (X11 / xdotool) ──
def window_list(limit: int = 50) -> list:
    """Liste des fenêtres visibles {id, name} sous X11 :1."""
    r = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", ""],
                       capture_output=True, text=True, env=_ENV, timeout=10)
    out = []
    for wid in [x for x in r.stdout.split() if x][:limit]:
        n = subprocess.run(["xdotool", "getwindowname", wid], capture_output=True,
                           text=True, env=_ENV, timeout=5).stdout.strip()
        if n:
            out.append({"id": wid, "name": n})
    return out


def window_focus(wid: str) -> bool:
    return subprocess.run(["xdotool", "windowactivate", "--sync", str(wid)],
                          env=_ENV, timeout=8).returncode == 0


def send_keys(wid: str, keys: str) -> bool:
    return subprocess.run(["xdotool", "key", "--window", str(wid), keys],
                          env=_ENV, timeout=8).returncode == 0


# ── NAVIGATEUR (Chrome CDP) ──
def browser_tabs(port: int = 9222) -> list:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=6) as r:
        tabs = json.loads(r.read())
    return [{"title": t.get("title"), "url": t.get("url")} for t in tabs if t.get("type") == "page"]


# ── VIDÉO (ffmpeg x11grab) ──
def capture_screen(seconds: int = 3, out: str = "/tmp/turbo-capture.mp4",
                   display: str = ":1", size: str = "1920x1080") -> str | None:
    subprocess.run(["ffmpeg", "-y", "-f", "x11grab", "-video_size", size, "-t", str(seconds),
                    "-i", f"{display}.0", "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
                   env=_ENV, capture_output=True, timeout=seconds + 40)
    return out if os.path.exists(out) and os.path.getsize(out) > 1000 else None
