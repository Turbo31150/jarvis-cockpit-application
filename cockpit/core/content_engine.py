#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — CONTENT & CREATION ENGINE
High-impact AI generator for LinkedIn posts, Technical Deep-Dives, PRDs, and Code synthesizers.
"""

import os
import time
from .config import CONTENT_DIR
from .inference import generate_completion

os.makedirs(CONTENT_DIR, exist_ok=True)

CONTENT_TEMPLATES = {
    "linkedin": {
        "title": "Post LinkedIn Expert (IA & Cluster)",
        "prompt": "Rédige un post LinkedIn percutant, technique et sans blabla marketing sur le sujet suivant : {topic}. Mets en avant l'ingénierie concrète (cluster multi-noeuds, GPU locaux, RAG 0-token, architecture résiliente). Termine par un call-to-action d'ouverture.",
        "suffix": "linkedin"
    },
    "article": {
        "title": "Article Technique Approfondi",
        "prompt": "Rédige un article technique détaillé (1500 mots) sur le sujet suivant : {topic}. Inclus : Introduction, Architecture Système, Défis Techniques & Optimisations (VRAM, Latence, Cache), Exemple de Code / Implémentation, Conclusion.",
        "suffix": "article"
    },
    "prd": {
        "title": "PRD / Spécification d'Architecture",
        "prompt": "Rédige un document de spécification technique complet (PRD) pour : {topic}. Inclus : Objectifs, Exigences Fonctionnelles & Non-Fonctionnelles, Architecture de Données, Contrats d'API, Stratégie de Résilience & Fallback.",
        "suffix": "prd"
    },
    "code": {
        "title": "Module de Code Python / Rust Robuste",
        "prompt": "Écris un module de code complet, typé, documenté et prêt pour la production pour : {topic}. Zéro placeholder, gestion stricte des erreurs et des timeouts.",
        "suffix": "code"
    },
    "outreach": {
        "title": "Message de Prospection Grands Comptes",
        "prompt": "Rédige un message d'approche direct, hautement personnalisé et orienté valeur pour un CTO / Head of AI sur : {topic}. Fais valoir une expertise pointue en déploiement de modèles souverains et clusters locaux.",
        "suffix": "prospect"
    }
}

def generate_content(content_type: str, topic: str) -> dict:
    """Génère le contenu et l'enregistre automatiquement dans /storage/content/."""
    tmpl = CONTENT_TEMPLATES.get(content_type, CONTENT_TEMPLATES["linkedin"])
    sys_prompt = "Tu es le rédacteur en chef technique de JARVIS. Ton style est incisif, direct, hautement qualifié et crédible."
    user_prompt = tmpl["prompt"].format(topic=topic)
    
    res = generate_completion(user_prompt, sys_prompt=sys_prompt, max_tokens=2048)
    
    saved_file = None
    if res.get("success") and res.get("content"):
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{tmpl['suffix']}_{ts}.md"
        filepath = os.path.join(CONTENT_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as out_f:
                header = "# " + topic + "\n\nDate: " + time.strftime('%Y-%m-%d %H:%M:%S') + "\nType: " + content_type + "\nSource: " + str(res.get('source')) + "\n\n---\n\n"
                out_f.write(header)
                out_f.write(res["content"])
            saved_file = filepath
        except Exception:
            pass

    res["saved_file"] = saved_file
    res["content_type"] = content_type
    return res
