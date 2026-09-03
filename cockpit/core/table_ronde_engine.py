#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — TABLE RONDE & 7 EXPERTS ENGINE
Orchestrates multi-agent consensus deliberation grounded in board.db FTS5 knowledge base.
"""

from .database import search_board_fts, get_board_stats
from .inference import generate_completion

EXPERTS = [
    {"id": "omega", "name": "🏛️ Omega Architecte", "role": "Architecture logicielle & Systèmes scalables", "color": "#38bdf8"},
    {"id": "shield", "name": "🛡️ Shield Sécurité", "role": "Audit de vulnérabilités & Bouclier mémoire", "color": "#f87171"},
    {"id": "turbo", "name": "⚡ Turbo Dev Senior", "role": "Ingénierie de performance & Optimisation M4/M6", "color": "#4ade80"},
    {"id": "data", "name": "🧠 Data & IA Scientist", "role": "RAG, Vectorisation Nomic 768D & FTS5", "color": "#c084fc"},
    {"id": "sre", "name": "🐳 SRE & Infra Swarm", "role": "Docker Swarm, Réseau direct ASIX & Haute Dispo", "color": "#fbbf24"},
    {"id": "biz", "name": "💼 Stratège Produit", "role": "Prospection, TJM & Offres Grands Comptes", "color": "#f472b6"},
    {"id": "arbitre", "name": "⚖️ Cognitive Arbitre", "role": "Consensus décisionnel & Synthèse actionnable", "color": "#00f0ff"},
]

def run_table_ronde_deliberation(question: str, domain: str = "TOUS") -> dict:
    """Lance la délibération du Conseil des Experts avec ancrage documentaire FTS5."""
    stats = get_board_stats()
    snippets = search_board_fts(question, limit=4)
    
    context_txt = ""
    if snippets:
        context_txt = "\n\n--- EXTRAITS PERTINENTS DU CORPUS FTS5 (board.db) ---\n"
        for s in snippets:
            context_txt += "• [" + str(s['domain']) + "] " + str(s['title']) + " : " + str(s['snippet']) + "\n"

    sys_prompt = (
        "Tu es le CONSEIL DES 7 EXPERTS DE JARVIS. Ta mission est d'analyser la demande, "
        "de confronter les points de vue techniques et d'aboutir à un consensus formel et actionnable.\n"
        "Structure ta réponse ainsi :\n"
        "1. 🔍 ANALYSE DE LA PROBLÉMATIQUE\n"
        "2. 💬 AVIS DES EXPERTS (Omega, Shield, Turbo, Data, SRE, Stratège)\n"
        "3. ⚖️ CONSENSUS ET PLAN D'ACTION IMMÉDIAT\n"
        "Langue : Français uniquement. Sois précis, technique et percutant."
    )

    full_prompt = "QUESTION / OBJECTIF :\n" + question + "\n" + context_txt
    
    res = generate_completion(full_prompt, sys_prompt=sys_prompt, max_tokens=1500)
    res["sources_count"] = len(snippets)
    res["sources"] = snippets
    res["corpus_summary"] = stats.get("summary", "")
    return res
