#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
settings_engine.py — MOTEUR DE GESTION DES PARAMÈTRES & PRÉFÉRENCES COCKPIT OS
Gère la persistance bi-directionnelle : Fichier JSON local & Table SQLite jarvis_master.db.
"""

import os
import json
import sqlite3
from datetime import datetime

SETTINGS_FILE = os.path.expanduser("~/jarvis/data/cockpit_settings.json")
MASTER_DB = os.path.expanduser("~/jarvis/jarvis_master.db")

DEFAULT_SETTINGS = {
    "language": "fr",
    "theme": "cyan",
    "ui_scale": "normal",
    "grid_overlay": True,
    "glass_blur": "16px",
    "sound_enabled": True,
    "voice_rate": 1.0,
    "voice_pitch": 1.0,
    "telemetry_interval": 2000,
    "cpu_temp_alert": 88,
    "ai_engine": "qwen3:8b",
    "auto_refresh": True,
    # Moteur Whisper (Reconnaissance Vocale Locale)
    "whisper_model": "distil-large-v3",
    "whisper_device": "cuda",
    "whisper_language": "fr",
    "whisper_port": 9743,
    "whisper_auto_inject": True,
    # Moteur Flo (WhisperFlow & Orchestration Workflows)
    "flo_mode": "overlay",
    "flo_trigger_key": "Alt+X",
    "flo_guardian_autostart": True,
    "flo_active_workflow": "jarvis_system_health.json",
    # Moteur Lumen (Assistant Visuel, STT & Synthèse Contextuelle)
    "lumen_mode": "auto",
    "lumen_profile": "speed",
    "lumen_stt_engine": "whisper",
    "lumen_auto_detect_app": True,
    "last_saved": "2026-09-04 00:00:00"
}


def _init_db():
    try:
        os.makedirs(os.path.dirname(MASTER_DB), exist_ok=True)
        conn = sqlite3.connect(MASTER_DB)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS cockpit_settings (
                cle TEXT PRIMARY KEY,
                valeur TEXT,
                mis_a_jour_le TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SETTINGS] Erreur init_db: {e}")


def get_cockpit_settings() -> dict:
    """Retourne la configuration actuelle fusionnée avec les valeurs par défaut."""
    settings = dict(DEFAULT_SETTINGS)

    # 1. Tentative lecture fichier JSON
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
                return {"success": True, "settings": settings}
        except Exception:
            pass

    # 2. Repli vers SQLite
    try:
        _init_db()
        conn = sqlite3.connect(MASTER_DB)
        c = conn.cursor()
        c.execute("SELECT cle, valeur FROM cockpit_settings")
        rows = c.fetchall()
        conn.close()
        for cle, val in rows:
            try:
                settings[cle] = json.loads(val)
            except Exception:
                settings[cle] = val
    except Exception:
        pass

    return {"success": True, "settings": settings}


def save_cockpit_settings(new_settings: dict) -> dict:
    """Sauvegarde les paramètres dans le fichier JSON et la base SQLite."""
    if not isinstance(new_settings, dict):
        return {"success": False, "error": "Données de configuration invalides"}

    current = get_cockpit_settings().get("settings", dict(DEFAULT_SETTINGS))
    current.update(new_settings)
    current["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Sauvegarde JSON
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"success": False, "error": f"Erreur écriture JSON: {e}"}

    # 2. Sauvegarde SQLite
    try:
        _init_db()
        conn = sqlite3.connect(MASTER_DB)
        c = conn.cursor()
        now = datetime.now().isoformat()
        for cle, val in current.items():
            val_str = json.dumps(val) if not isinstance(val, str) else val
            c.execute("""
                INSERT INTO cockpit_settings (cle, valeur, mis_a_jour_le)
                VALUES (?, ?, ?)
                ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur, mis_a_jour_le=excluded.mis_a_jour_le
            """, (cle, val_str, now))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SETTINGS] Warning SQLite save: {e}")

    return {"success": True, "settings": current, "message": "Paramètres sauvegardés avec succès"}
