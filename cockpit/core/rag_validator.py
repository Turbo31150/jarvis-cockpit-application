#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — FAIL-CLOSED RAG VALIDATOR (ENF6)
===========================================
Garde-fou souverain anti-hallucination avec seuil strict fail-closed (< 40%).

Règles de validation :
  1. Extraction des phrases et affirmations de la réponse.
  2. Vérification de l'ancrage lexical et sémantique dans les chunks sources (citations).
  3. Ancrage numérique strict : tout nombre/date/pourcentage dans la réponse doit
     apparaître dans les sources.
  4. Seuil minimal de fidélité : 40.0% (paramétrable via RAG_MIN_FAITH).
  5. FAIL-CLOSED : si fidélité < 40%, la réponse est REFUSÉE avec explication transparente.
"""

from __future__ import annotations

import os
import re
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_MIN_FAITHFULNESS = float(os.environ.get("RAG_MIN_FAITH", "40.0"))

STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "ou", "mais",
    "donc", "or", "ni", "car", "ce", "cet", "cette", "ces", "dans", "par", "pour",
    "en", "vers", "avec", "sans", "sous", "sur", "est", "sont", "a", "ont", "qui",
    "que", "quoi", "dont", "où", "il", "elle", "ils", "elles", "on", "nous", "vous",
    "je", "tu", "me", "te", "se", "y", "en", "ne", "pas", "plus", "au", "aux", "son",
    "sa", "ses", "leur", "leurs", "mon", "ma", "mes", "ton", "ta", "tes", "tout",
    "tous", "toute", "toutes", "the", "a", "an", "and", "or", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were", "be", "this", "that"
}


def _clean_text(text: str) -> str:
    """Nettoie les balises <think> et préfixes de persona."""
    t = re.sub(r"(?is)<think>.*?</think>", "", text or "")
    t = re.sub(r"(?is)^.*?</think>", "", t)
    t = re.sub(r"^\s*(JARVIS|Board|Conseil)\s*[:：\-]\s*", "", t.strip())
    return t.strip()


def _extract_sentences(text: str) -> List[str]:
    """Découpe en phrases significatives."""
    raw = re.split(r"(?<=[.!?\n])\s+", text)
    sentences = []
    for s in raw:
        cleaned = s.strip()
        # Filtre les phrases triviales trop courtes (< 15 caractères)
        if len(cleaned) >= 15:
            sentences.append(cleaned)
    return sentences


def _extract_tokens(text: str) -> set[str]:
    """Extrait les tokens de contenu (hors stopwords, min 3 caractères)."""
    words = re.findall(r"\b[a-zA-Z0-9À-ÿ_-]+\b", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _extract_numbers(text: str) -> set[str]:
    """Extrait les nombres entiers, décimaux et pourcentages."""
    nums = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", text)
    return {n.replace(",", ".") for n in nums}


def evaluate_faithfulness(candidate_text: str, source_chunks: List[str]) -> Dict[str, Any]:
    """Évalue la fidélité de l'énoncé par rapport aux fragments documentaires.
    Conforme au contrat attendu par /api/rag/ask et les routes RAG.
    """
    clean_cand = _clean_text(candidate_text)
    if not clean_cand:
        return {
            "faithfulness_score": 1.0 if source_chunks else 0.0,
            "faithfulness_pct": "100.0%" if source_chunks else "0.0%",
            "supported_sentences": 0,
            "total_sentences": 0,
            "supported_pct": 100.0 if source_chunks else 0.0,
            "numeric_grounding_pct": 100.0,
            "extrapolated_sample": [],
            "verdict": "Texte candidat vide.",
        }

    if not source_chunks:
        return {
            "faithfulness_score": 0.0,
            "faithfulness_pct": "0.0%",
            "supported_sentences": 0,
            "total_sentences": len(_extract_sentences(clean_cand)),
            "supported_pct": 0.0,
            "numeric_grounding_pct": 0.0,
            "extrapolated_sample": _extract_sentences(clean_cand)[:3],
            "verdict": "Aucune source fournie pour l'ancrage.",
        }

    # Agrégation des sources
    all_source_text = " \n ".join(source_chunks)
    source_tokens = _extract_tokens(all_source_text)
    source_numbers = _extract_numbers(all_source_text)

    sentences = _extract_sentences(clean_cand)
    if not sentences:
        sentences = [clean_cand]

    supported_count = 0
    extrapolated = []
    numeric_violations = 0
    numeric_total = 0

    for sent in sentences:
        sent_tokens = _extract_tokens(sent)
        sent_numbers = _extract_numbers(sent)

        # Vérification numérique stricte
        num_ok = True
        if sent_numbers:
            numeric_total += len(sent_numbers)
            unmatched_nums = [n for n in sent_numbers if n not in source_numbers]
            if unmatched_nums:
                num_ok = False
                numeric_violations += len(unmatched_nums)

        if not sent_tokens:
            supported_count += 1
            continue

        overlap = sent_tokens.intersection(source_tokens)
        overlap_ratio = len(overlap) / float(len(sent_tokens))

        # Vérification de sous-chaîne ou n-gram
        substring_found = any(sent.lower()[:30] in sc.lower() for sc in source_chunks)

        # Une phrase est soutenue si : overlap suffisant (>= 28%), sans invention numérique
        if (overlap_ratio >= 0.28 or substring_found) and num_ok:
            supported_count += 1
        else:
            extrapolated.append({
                "sentence": sent,
                "overlap_pct": round(overlap_ratio * 100, 1),
                "unmatched_numbers": list(sent_numbers - source_numbers) if not num_ok else []
            })

    total_sents = len(sentences)
    supported_pct = round((supported_count / float(total_sents)) * 100.0, 1) if total_sents else 0.0
    num_grounding_pct = round(((numeric_total - numeric_violations) / float(numeric_total)) * 100.0, 1) if numeric_total else 100.0

    score = round(supported_pct / 100.0, 2)
    verdict = (
        f"{supported_count}/{total_sents} phrases soutenues ({supported_pct}%). "
        f"Ancrage numérique : {num_grounding_pct}%."
    )

    return {
        "faithfulness_score": score,
        "faithfulness_pct": f"{supported_pct:.1f}%",
        "supported_sentences": supported_count,
        "total_sentences": total_sents,
        "supported_pct": supported_pct,
        "numeric_grounding_pct": num_grounding_pct,
        "extrapolated_sample": [e["sentence"] for e in extrapolated[:3]],
        "extrapolated_details": extrapolated[:5],
        "verdict": verdict,
    }


def validate_rag_response(answer: str, sources: List[Any],
                          threshold: float = DEFAULT_MIN_FAITHFULNESS) -> Dict[str, Any]:
    """Validation Fail-Closed selon la Directive Critique Turbo OS (ENF6)."""
    source_chunks = []
    for s in sources:
        if isinstance(s, str):
            source_chunks.append(s)
        elif isinstance(s, dict):
            txt = s.get("text") or s.get("extrait") or s.get("content") or s.get("title") or ""
            if txt:
                source_chunks.append(txt)

    faith = evaluate_faithfulness(answer, source_chunks)
    score_pct = faith.get("supported_pct", 0.0)

    is_valid = bool(source_chunks and score_pct >= threshold)
    if is_valid:
        status = "VALIDATED"
        reason = f"Fidélité certifiée : ancrage {score_pct:.1f}% >= {threshold:.1f}% sur {len(source_chunks)} sources."
        refusal_explanation = None
    else:
        status = "PREUVE_INSUFFISANTE"
        if not source_chunks:
            reason = "Fail-Closed ENF6 : Aucune citation valide trouvée dans la base documentaire."
            refusal_explanation = "Absence de sources formelles dans le corpus pour fonder une réponse certaine."
        else:
            reason = (
                f"Fail-Closed ENF6 : ancrage mesuré à {score_pct:.1f}% < seuil strict {threshold:.1f}%. "
                f"La réponse contient des extrapolations non prouvées."
            )
            refusal_explanation = (
                f"Preuve insuffisante ({score_pct:.1f}% de fidélité < {threshold:.1f}%). "
                f"Certaines affirmations ne sont pas vérifiables dans board.db."
            )

    return {
        "status": status,
        "is_valid": is_valid,
        "threshold_pct": threshold,
        "faithfulness": faith,
        "reason": reason,
        "refusal_explanation": refusal_explanation,
    }


def fail_closed_gate(answer: str, sources: List[Any],
                     threshold: float = DEFAULT_MIN_FAITHFULNESS) -> Tuple[bool, str, Dict[str, Any]]:
    """Garde-fou final : renvoie soit la réponse certifiée, soit le refus formel."""
    val = validate_rag_response(answer, sources, threshold=threshold)
    if val["is_valid"]:
        return True, answer, val
    else:
        refusal = (
            f"[RÉPONSE REFUSÉE — PREUVE INSUFFISANTE (Fail-Closed ENF6)]\n"
            f"Fidélité mesurée à {val['faithfulness']['supported_pct']:.1f}% (< {threshold:.1f}% requis).\n"
            f"Raison : {val['refusal_explanation']}\n"
            f"Veuillez enrichir la base de connaissances ou reformuler votre requête."
        )
        return False, refusal, val
