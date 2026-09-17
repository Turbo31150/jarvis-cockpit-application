#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — UNIFIED DISPATCHER & ADAPTERS
========================================
Bus d'utilisation universel de Turbo OS / Cockpit :
  USER → COCKPIT → TURBO DISPATCHER → MODULE / AGENT / APP → RESULT → COCKPIT → BOARD / AUDIT / MEMORY

Directives :
  1. Interdiction de dispatchers concurrents. Un seul TurboDispatcher central.
  2. Adaptateurs unifiés :
     - VoiceAdapter (Vocal Whisper/Kokoro, commandes vocales)
     - ChatAdapter (Chat IA, délibération, Orbe)
     - BoardAdapter (Plan de contrôle interactif : OPEN, RUN, PAUSE, RESUME, CANCEL, RETRY, VERIFY, INSPECT)
     - TerminalAdapter (Terminaux, tmux, sessions distribuées)
     - BrowserAdapter (CDP, Web, scraping)
  3. Chaque action est auditée dans SystemState.
  4. Boucle d'exécution bornée (MAX_TOOL_LOOPS=10, timeout 45s) sans freeze interface.
"""

from __future__ import annotations

import os
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable

try:
    from .system_state import get_system_state, ActionStatus, TaskStatus
    from .application_manager import get_application_manager
except ImportError:
    from system_state import get_system_state, ActionStatus, TaskStatus
    from application_manager import get_application_manager

logger = logging.getLogger("TurboOS.Dispatcher")


# ─── ADAPTATEURS SPÉCIALISÉS DU BUS ──────────────────────────────────────────

class BaseAdapter:
    """Interface de base pour les adaptateurs du TurboDispatcher."""

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class VoiceAdapter(BaseAdapter):
    """Adaptateur Vocal : traite les commandes transcrites (STT) et prépare la synthèse (TTS)."""

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        raw_text = payload.get("text") or payload.get("transcript") or payload.get("message") or ""
        text = raw_text.strip()
        if not text:
            return {"success": False, "error": "Transcription vocale vide", "speech_response": "Je n'ai pas entendu."}

        # Détection d'intent vocal prioritaire
        t = text.lower()
        if any(w in t for w in ("pause", "arrête", "stop", "attends")):
            action = "PAUSE"
        elif any(w in t for w in ("reprends", "continue", "relance")):
            action = "RESUME"
        elif any(w in t for w in ("annule", "abandonne")):
            action = "CANCEL"
        else:
            action = "PROCESS_PROMPT"

        return {
            "success": True,
            "adapter": "VoiceAdapter",
            "action": action,
            "transcript": text,
            "speech_response": f"Instruction vocale reçue : {text}",
            "intent": "VOICE_COMMAND",
            "needs_tts": True,
        }


class ChatAdapter(BaseAdapter):
    """Adaptateur Chat : traite les messages textuels, prompts et délibérations."""

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        message = (payload.get("message") or payload.get("prompt") or payload.get("text") or "").strip()
        if not message:
            return {"success": False, "error": "Message de chat vide"}

        mode = payload.get("mode", "deliberate")
        return {
            "success": True,
            "adapter": "ChatAdapter",
            "message": message,
            "mode": mode,
            "routing": "ORBE_DELIBERATE" if mode == "deliberate" else "DIRECT_EXECUTE",
            "intent": "CHAT_CONVERSATION",
        }


class BoardAdapter(BaseAdapter):
    """Adaptateur Board : actions du plan de contrôle interactif.
    Actions supportées : OPEN, RUN, PAUSE, RESUME, CANCEL, RETRY, VERIFY, INSPECT.
    """

    ALLOWED_ACTIONS = {"OPEN", "RUN", "PAUSE", "RESUME", "CANCEL", "RETRY", "VERIFY", "INSPECT"}

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        action = (payload.get("action") or "").upper()
        entity_type = payload.get("entity_type") or "task"
        entity_id = payload.get("entity_id") or payload.get("id") or ""
        caller = payload.get("caller") or "cockpit_board"

        if action not in self.ALLOWED_ACTIONS:
            return {
                "success": False,
                "error": f"Action non autorisée : '{action}'. Actions valides : {sorted(list(self.ALLOWED_ACTIONS))}"
            }
        if not entity_id:
            return {"success": False, "error": "entity_id requis pour l'action Board"}

        state = get_system_state()
        app_mgr = get_application_manager()

        result: Dict[str, Any] = {"success": True, "action": action, "entity_type": entity_type, "entity_id": entity_id}

        if entity_type == "task":
            if action == "RUN":
                state.transition("task", entity_id, TaskStatus.RUNNING.value, reason="Lancement depuis Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} lancée"
            elif action == "PAUSE":
                state.pause_task(entity_id, reason="Mise en pause depuis Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} mise en pause avec checkpoint"
            elif action == "RESUME":
                state.resume_task(entity_id, reason="Reprise depuis Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} reprise depuis checkpoint"
            elif action == "CANCEL":
                state.transition("task", entity_id, TaskStatus.CANCELLED.value, reason="Annulation depuis Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} annulée"
            elif action == "VERIFY":
                state.verify_task(entity_id, reason="Demande de vérification Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} en cours de vérification"
            elif action == "INSPECT":
                ent = state.get_entity("task", entity_id)
                result["entity"] = ent.to_dict() if ent else None
            elif action == "RETRY":
                state.transition("task", entity_id, TaskStatus.READY.value, reason="Relance depuis Board", updated_by=caller)
                result["message"] = f"Tâche {entity_id} replacée en READY"
            else:
                result["message"] = f"Action {action} enregistrée sur {entity_id}"

        elif entity_type == "application":
            if action in ("RUN", "OPEN"):
                res = app_mgr.start(entity_id, caller=caller)
                result.update(res)
            elif action == "PAUSE":
                res = app_mgr.pause(entity_id, caller=caller)
                result.update(res)
            elif action == "RESUME":
                res = app_mgr.resume(entity_id, caller=caller)
                result.update(res)
            elif action == "CANCEL":
                res = app_mgr.stop(entity_id, caller=caller)
                result.update(res)
            elif action == "INSPECT":
                res = app_mgr.status(entity_id)
                result.update(res)
            else:
                result["message"] = f"Action {action} appliquée sur application {entity_id}"

        return result


class TerminalAdapter(BaseAdapter):
    """Adaptateur Terminal : exécution de commandes shell et sessions tmux."""

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        command = payload.get("command") or payload.get("cmd") or ""
        session = payload.get("session")
        if not command and not session:
            return {"success": False, "error": "Commande ou session requise"}

        return {
            "success": True,
            "adapter": "TerminalAdapter",
            "command": command,
            "session": session,
            "intent": "TERMINAL_EXEC",
        }


class BrowserAdapter(BaseAdapter):
    """Adaptateur Browser : contrôle CDP / Chrome et navigation web."""

    def handle(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "navigate")
        url = payload.get("url") or payload.get("target") or ""
        return {
            "success": True,
            "adapter": "BrowserAdapter",
            "action": action,
            "url": url,
            "intent": "BROWSER_ACTION",
        }


# ─── TURBO DISPATCHER CENTRAL ────────────────────────────────────────────────

class TurboDispatcher:
    """Orchestrateur central et unique de Turbo OS / Cockpit."""

    MAX_TOOL_LOOPS = 10
    LOOP_TIMEOUT_SECONDS = 45.0

    _adapters: Dict[str, BaseAdapter] = {
        "voice": VoiceAdapter(),
        "chat": ChatAdapter(),
        "board": BoardAdapter(),
        "terminal": TerminalAdapter(),
        "browser": BrowserAdapter(),
    }

    @classmethod
    def dispatch(cls, user_input_or_payload: Any,
                 context: Optional[Dict[str, Any]] = None,
                 source: str = "auto") -> Dict[str, Any]:
        """Achemine toute requête à travers le bus d'orchestration unifié.
        Garantit l'audit dans SystemState et la protection contre le freeze.
        """
        t0 = time.time()
        ctx = context or {}
        state = get_system_state()
        action_id = f"act-{uuid.uuid4().hex[:8]}"

        # Normalisation du payload
        if isinstance(user_input_or_payload, str):
            text = user_input_or_payload.strip()
            payload = {"text": text, "message": text}
        elif isinstance(user_input_or_payload, dict):
            payload = dict(user_input_or_payload)
            text = payload.get("text") or payload.get("message") or payload.get("command") or ""
        else:
            payload = {"data": user_input_or_payload}
            text = str(user_input_or_payload)

        # Enregistrement de l'action dans le système d'état
        state.register_entity("agent", action_id, ActionStatus.PENDING.value,
                              metadata={"source": source, "text": text[:100]}, updated_by="dispatcher")

        # 1. Sélection de l'adaptateur
        adapter_key = source.lower() if source != "auto" else cls._detect_source(text, payload)
        adapter = cls._adapters.get(adapter_key, cls._adapters["chat"])

        # Transition EXECUTING
        state.transition("agent", action_id, ActionStatus.EXECUTING.value,
                         reason=f"Pris en charge par {adapter.__class__.__name__}", updated_by="dispatcher")

        # 2. Exécution bornée avec coupe-circuit
        loop = ExecutionLoop(max_loops=cls.MAX_TOOL_LOOPS, timeout=cls.LOOP_TIMEOUT_SECONDS)
        try:
            adapter_res = adapter.handle(payload, ctx)
            if not adapter_res.get("success", True):
                state.transition("agent", action_id, ActionStatus.FAILED.value,
                                 reason=adapter_res.get("error", "Erreur adaptateur"), updated_by="dispatcher")
                adapter_res["duration_ms"] = round((time.time() - t0) * 1000, 1)
                adapter_res["action_id"] = action_id
                return adapter_res

            loop_res = loop.run(text, ctx)
            merged = {**adapter_res, **loop_res}
            merged["duration_ms"] = round((time.time() - t0) * 1000, 1)
            merged["action_id"] = action_id
            merged["adapter"] = adapter.__class__.__name__

            final_status = ActionStatus.COMPLETED.value if loop_res.get("success") else ActionStatus.FAILED.value
            state.transition("agent", action_id, final_status,
                             reason=loop_res.get("reason", "Exécution terminée"), updated_by="dispatcher")
            return merged

        except Exception as e:
            logger.exception("Erreur inattendue dans TurboDispatcher: %s", e)
            state.transition("agent", action_id, ActionStatus.FAILED.value,
                             reason=str(e), updated_by="dispatcher")
            return {
                "success": False,
                "error": f"DISPATCHER_ERROR: {e}",
                "action_id": action_id,
                "duration_ms": round((time.time() - t0) * 1000, 1),
            }

    @classmethod
    def dispatch_voice(cls, transcript: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.dispatch({"transcript": transcript}, context=context, source="voice")

    @classmethod
    def dispatch_chat(cls, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.dispatch({"message": message}, context=context, source="chat")

    @classmethod
    def dispatch_board(cls, action: str, entity_type: str, entity_id: str,
                       payload: Optional[Dict[str, Any]] = None,
                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        req = {"action": action, "entity_type": entity_type, "entity_id": entity_id}
        if payload:
            req.update(payload)
        return cls.dispatch(req, context=context, source="board")

    @classmethod
    def dispatch_terminal(cls, command: str, session: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.dispatch({"command": command, "session": session}, context=context, source="terminal")

    @classmethod
    def dispatch_browser(cls, action: str, target: str,
                         context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.dispatch({"action": action, "target": target}, context=context, source="browser")

    @staticmethod
    def _detect_source(text: str, payload: Dict[str, Any]) -> str:
        """Détecte intelligemment l'adaptateur cible en l'absence de source explicite."""
        if "action" in payload and ("entity_id" in payload or "entity_type" in payload):
            return "board"
        if "command" in payload:
            return "terminal"
        if "url" in payload or "target" in payload:
            return "browser"

        t = text.lower()
        if any(w in t for w in ("parle", "écoute", "voix", "micro", "casque")):
            return "voice"
        if any(w in t for w in ("sh ", "bash ", "ls ", "cd ", "grep ", "systemctl ", "tmux ")):
            return "terminal"
        if any(w in t for w in ("http://", "https://", "ouvre le site", "navigue")):
            return "browser"
        return "chat"


# ─── BOUCLE D'EXÉCUTION OUTILLÉE AVEC DISJONCTEUR ─────────────────────────────

class ExecutionLoop:
    """Boucle d'exécution outillée avec coupe-circuit et timeout strict."""

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
                    "reason": f"Délai maximal dépassé ({self.timeout}s). Interruption propre sans freeze.",
                    "steps_completed": self.current_step,
                    "history": self.history,
                }

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

        return {
            "success": False,
            "error": "MAX_TOOL_LOOPS_EXCEEDED",
            "reason": f"Limite de {self.max_loops} boucles atteinte sans convergence. Arrêt sécurisé.",
            "steps_completed": self.current_step,
            "history": self.history,
        }
