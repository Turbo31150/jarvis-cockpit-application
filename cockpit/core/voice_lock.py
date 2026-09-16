#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS / JARVIS — VOICE EXECUTION LOCK
========================================
Garantit qu'une seule exécution vocale ou synthèse TTS est active à la fois.
Élimine les collisions entre POST /ask, la boucle microphone et les notifications.
"""

import threading
import time
from typing import Optional


class VoiceExecutionLock:
    """Verrou réentrant pour l'exécution vocale et la synthèse TTS."""

    _lock = threading.Lock()
    _active_owner: Optional[str] = None
    _started_at: float = 0.0

    @classmethod
    def acquire(cls, owner: str, timeout: float = 10.0) -> bool:
        """Tente d'acquérir le verrou pour un émetteur donné."""
        acquired = cls._lock.acquire(timeout=timeout)
        if acquired:
            cls._active_owner = owner
            cls._started_at = time.time()
        return acquired

    @classmethod
    def release(cls, owner: str = None):
        """Libère le verrou si détenu."""
        try:
            cls._active_owner = None
            cls._started_at = 0.0
            cls._lock.release()
        except RuntimeError:
            pass  # Déjà relâché

    @classmethod
    def is_locked(cls) -> bool:
        return cls._lock.locked()

    @classmethod
    def get_status(cls) -> dict:
        return {
            "locked": cls._lock.locked(),
            "owner": cls._active_owner,
            "duration_s": round(time.time() - cls._started_at, 2) if cls._active_owner else 0.0,
        }
