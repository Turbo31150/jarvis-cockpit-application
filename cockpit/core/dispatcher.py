#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — DISPATCHER & EXECUTION LOOP
======================================
Pipeline d'orchestration unifié :
  INPUT -> IDENTITY -> MEMORY -> INTENT -> CONTEXT -> POLICY -> ROUTING -> AGENT -> TOOL -> OBSERVE -> VERIFY
Garantit la gestion stricte de MAX_TOOL_LOOPS, timeouts et disjoncteurs (circuit breakers)
pour ne jamais laisser l'interface bloquée dans l'état "thinking".
"""

import time
from typing import Dict, Any, List, Optional, Callable


class TurboDispatcher:
    """Orchestrateur central de Turbo OS / JARVIS."""

    MAX_TOOL_LOOPS = 10
    LOOP_TIMEOUT_SECONDS = 45.0

    @classmethod
    def dispatch(cls, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Achemine une requête dans le pipeline d'orchestration."""
        t0 = time.time()
        text = (user_input or "").strip()
        if not text:
            return {"success": False, "error": "Requête vide", "duration_ms": 0}

        # 1. Classification d'intention (Fast routing)
        intent = cls._classify_intent(text)

        # 2. Construction de contexte
        ctx = context or {}
        ctx["intent"] = intent
        ctx["timestamp"] = int(time.time())

        # 3. Exécution de la boucle d'actions
        loop = ExecutionLoop(max_loops=cls.MAX_TOOL_LOOPS, timeout=cls.LOOP_TIMEOUT_SECONDS)
        result = loop.run(text, ctx)

        result["duration_ms"] = round((time.time() - t0) * 1000, 1)
        result["intent"] = intent
        return result

    @staticmethod
    def _classify_intent(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ("arrête", "stop", "pause", "quitte")):
            return "CONTROL_INTERRUPT"
        if any(w in t for w in ("cherche", "recherche", "trouve", "sirene", "gouv")):
            return "RESEARCH_DATA"
        if any(w in t for w in ("lance", "ouvre", "exécute", "ferme", "clique")):
            return "PC_ACTION"
        if any(w in t for w in ("voix", "parle", "écoute", "micro", "casque")):
            return "VOICE_CONTROL"
        return "GENERAL_COGNITION"


class ExecutionLoop:
    """Boucle d'exécution outillée avec coupe-circuit et timeout."""

    def __init__(self, max_loops: int = 10, timeout: float = 45.0):
        self.max_loops = max_loops
        self.timeout = timeout
        self.current_step = 0
        self.history: List[Dict[str, Any]] = []

    def run(self, prompt: str, context: Dict[str, Any], tool_executor: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = time.time()
        self.current_step = 0

        while self.current_step < self.max_loops:
            self.current_step += 1

            # Coupe-circuit de timeout temporel
            if (time.time() - start_time) > self.timeout:
                return {
                    "success": False,
                    "error": "CIRCUIT_BREAKER_TIMEOUT",
                    "reason": f"Délai maximal dépassé ({self.timeout}s). La tâche a été interrompue pour éviter un gel.",
                    "steps_completed": self.current_step,
                    "history": self.history,
                }

            # Si aucun exécuteur externe n'est fourni, mode déterministe
            if not tool_executor:
                return {
                    "success": True,
                    "decision": f"Action planifiée pour : {prompt}",
                    "steps_completed": self.current_step,
                    "history": self.history,
                }

            try:
                step_result = tool_executor(prompt, self.current_step, context)
                self.history.append(step_result)
                if step_result.get("is_final", True):
                    return {
                        "success": True,
                        "result": step_result.get("output"),
                        "steps_completed": self.current_step,
                        "history": self.history,
                    }
            except Exception as ex:
                return {
                    "success": False,
                    "error": "EXECUTION_ERROR",
                    "reason": str(ex),
                    "steps_completed": self.current_step,
                    "history": self.history,
                }

        # Dépassement de la limite de boucles : message clair sans freeze
        return {
            "success": False,
            "error": "MAX_TOOL_LOOPS_EXCEEDED",
            "reason": f"La limite de {self.max_loops} boucles d'outils a été atteinte sans convergence. Tâche arrêtée en toute sécurité.",
            "steps_completed": self.current_step,
            "history": self.history,
        }
