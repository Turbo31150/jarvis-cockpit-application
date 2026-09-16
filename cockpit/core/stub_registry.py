#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS / JARVIS — STUB REGISTRY
=================================
Catalogue d'honnêteté technique : enregistre et documente chaque stub,
route simulée ou endpoint non encore totalement câblé.
Élimine les faux "success:true" et garantit des retours authentiques.
"""

from typing import Dict, Any, List


class StubRegistry:
    """Registre unique des stubs et capacités partielles."""

    ENTRIES = [
        {
            "endpoint": "/api/scraping/recherche_gouv",
            "method": "GET",
            "status": "FIXED",
            "reason": "Query string détruite par urlparse",
            "expected_behavior": "Recherche Sirene live sur recherche-entreprises.api.gouv.fr",
            "replacement": "Corrigé le 2026-09-17 : parse 'params' direct. 100% réel.",
            "priority": "P0",
        },
        {
            "endpoint": "/api/chantiers/action",
            "method": "POST",
            "status": "FIXED",
            "reason": "Scripts ~/jarvis/prod/bin/prod-* inexistants",
            "expected_behavior": "Exécution d'étapes de production",
            "replacement": "Retourne désormais 501 not_implemented explicite au lieu d'un faux succès.",
            "priority": "P0",
        },
        {
            "endpoint": "/api/memory/stats",
            "method": "GET",
            "status": "FIXED",
            "reason": "Compteurs statiques en mémoire retournant 0",
            "expected_behavior": "Statistiques réelles de la DB SQLite",
            "replacement": "Branché sur la vraie base : total_actions=66, vectorized=16.",
            "priority": "P0",
        },
        {
            "endpoint": "/api/appliance/ha",
            "method": "GET",
            "status": "FIXED",
            "reason": "Affichait SYNCHRONIZED même en cas de divergence de checksum",
            "expected_behavior": "Surfaçage honnête de l'état de réplication",
            "replacement": "Surfacing authentique : CHECKSUM_MISMATCH documenté.",
            "priority": "P0",
        },
        {
            "endpoint": "/api/s9/status",
            "method": "GET",
            "status": "HONEST_STUB",
            "reason": "Pas de sonde physique continue du mobile S9/S8",
            "expected_behavior": "Statut de liaison USB / Wi-Fi avec le téléphone",
            "replacement": "Retourne bridge='non_sondé' avec vérification du dossier de backup.",
            "priority": "P1",
        },
        {
            "endpoint": "/api/veille/sources",
            "method": "GET",
            "status": "PARTIAL",
            "reason": "Fichier ~/jarvis/data/veille_sources.json optionnel",
            "expected_behavior": "Liste des flux RSS et cibles de veille",
            "replacement": "Repli statique déclaré si fichier absent.",
            "priority": "P2",
        },
        {
            "endpoint": "/api/drip/sequences",
            "method": "GET",
            "status": "PARTIAL",
            "reason": "Séquences email codées en dur sans CRM tiers",
            "expected_behavior": "Lecture séquences dynamiques",
            "replacement": "Déclaré statique.",
            "priority": "P2",
        },
        {
            "endpoint": "/api/swan",
            "method": "GET",
            "status": "REMOVED",
            "reason": "swan_stream_engine.py inexistant",
            "expected_behavior": "Flux événementiel Swan",
            "replacement": "Supprimé / 404 transparent.",
            "priority": "P1",
        },
    ]

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        return cls.ENTRIES

    @classmethod
    def get_info(cls, endpoint: str) -> Optional[Dict[str, Any]]:
        for entry in cls.ENTRIES:
            if entry["endpoint"] == endpoint:
                return entry
        return None

    @classmethod
    def is_stub(cls, endpoint: str) -> bool:
        info = cls.get_info(endpoint)
        return info is not None and info["status"] in ("STUB", "HONEST_STUB", "PARTIAL")
