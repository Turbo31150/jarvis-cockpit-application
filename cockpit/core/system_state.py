#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — SYSTEM STATE & AUDITED STATE MACHINE
==============================================
Modèle d'état strict multi-entités et bus d'audit pour Turbo OS / Cockpit.

Directives absolues :
1. Distinguer impérativement :
   - TASK_STATUS : TODO, READY, RUNNING, PAUSED, WAITING, VERIFYING, DONE, FAILED, BLOCKED, CANCELLED, ARCHIVED.
     * Pause ≠ Stop ≠ Cancel.
     * PAUSE : RUNNING → CHECKPOINT → PAUSED.
     * RESUME : PAUSED → RESTORE CHECKPOINT → VERIFY STATE → RUNNING.
     * Transitions interdites : DONE → RUNNING, CANCELLED → RUNNING, RUNNING → DONE sans VERIFY.
   - APPLICATION_STATUS : REGISTERED, STARTING, READY, RUNNING, STOPPING, STOPPED, ERROR, CRASHED, UNAVAILABLE, UNKNOWN.
     (READY ≠ RUNNING). Application = Process + Healthcheck + Interface/API/Window.
   - SERVICE_STATUS : DEFINED, STARTING, ACTIVE, DEGRADED, STOPPING, INACTIVE, FAILED, CRASH_LOOP, UNKNOWN.
   - TOOL_STATUS : REGISTERED, AVAILABLE, BUSY, EXECUTING, SUCCESS, ERROR, TIMEOUT, UNAVAILABLE, BLOCKED.
   - MODEL_STATUS : DISCOVERED, AVAILABLE, LOADING, LOADED, READY, GENERATING, UNLOADING, UNLOADED, ERROR, UNAVAILABLE.
   - HEALTH_STATUS : HEALTHY, DEGRADED, BLOCKED, ERROR, UNKNOWN.
   - COCKPIT_STATUS : INITIALIZING, READY, RUNNING, DEGRADED, STOPPING, STOPPED, ERROR.
   - BOARD_STATUS : SYNCING, READY, STALE, ERROR, OFFLINE.
   - ACTION_STATUS : PENDING, EXECUTING, COMPLETED, FAILED, CANCELLED, REJECTED.
   - DOMINO_STATUS : IDLE, SCHEDULED, EXECUTING, SUCCESS, FAILED, PAUSED.
2. Chaque entité a : status, previous_status, status_reason, updated_at, updated_by.
3. Chaque transition produit un événement d'audit irréversible.
"""

from __future__ import annotations

import os
import json
import time
import uuid
import threading
from enum import Enum
from typing import Dict, Any, List, Optional, Set

try:
    from . import checkpoint as ck_engine
except ImportError:
    try:
        import checkpoint as ck_engine
    except ImportError:
        ck_engine = None


# ─── ENUMS STRICTS MULTI-ENTITÉS ─────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO = "TODO"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class ApplicationStatus(str, Enum):
    REGISTERED = "REGISTERED"
    STARTING = "STARTING"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    CRASHED = "CRASHED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ServiceStatus(str, Enum):
    DEFINED = "DEFINED"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    INACTIVE = "INACTIVE"
    FAILED = "FAILED"
    CRASH_LOOP = "CRASH_LOOP"
    UNKNOWN = "UNKNOWN"


class ToolStatus(str, Enum):
    REGISTERED = "REGISTERED"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"


class ModelStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    AVAILABLE = "AVAILABLE"
    LOADING = "LOADING"
    LOADED = "LOADED"
    READY = "READY"
    GENERATING = "GENERATING"
    UNLOADING = "UNLOADING"
    UNLOADED = "UNLOADED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class CockpitStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class BoardStatus(str, Enum):
    SYNCING = "SYNCING"
    READY = "READY"
    STALE = "STALE"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class DominoStatus(str, Enum):
    IDLE = "IDLE"
    SCHEDULED = "SCHEDULED"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


# ─── TRANSITIONS AUTORISÉES PAR TYPE D'ENTITÉ ─────────────────────────────────

VALID_TRANSITIONS: Dict[str, Dict[str, Set[str]]] = {
    "task": {
        TaskStatus.TODO.value: {TaskStatus.READY.value, TaskStatus.CANCELLED.value, TaskStatus.ARCHIVED.value},
        TaskStatus.READY.value: {TaskStatus.RUNNING.value, TaskStatus.BLOCKED.value, TaskStatus.CANCELLED.value},
        # DIRECTIVE : RUNNING -> DONE sans VERIFY est INTERDIT !
        TaskStatus.RUNNING.value: {
            TaskStatus.PAUSED.value,
            TaskStatus.WAITING.value,
            TaskStatus.VERIFYING.value,
            TaskStatus.FAILED.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.CANCELLED.value,
        },
        TaskStatus.PAUSED.value: {TaskStatus.READY.value, TaskStatus.RUNNING.value, TaskStatus.CANCELLED.value, TaskStatus.ARCHIVED.value},
        TaskStatus.WAITING.value: {TaskStatus.RUNNING.value, TaskStatus.BLOCKED.value, TaskStatus.CANCELLED.value},
        TaskStatus.VERIFYING.value: {TaskStatus.DONE.value, TaskStatus.FAILED.value, TaskStatus.RUNNING.value},
        # DIRECTIVE : DONE -> RUNNING est INTERDIT !
        TaskStatus.DONE.value: {TaskStatus.ARCHIVED.value},
        TaskStatus.FAILED.value: {TaskStatus.READY.value, TaskStatus.ARCHIVED.value},
        TaskStatus.BLOCKED.value: {TaskStatus.READY.value, TaskStatus.CANCELLED.value, TaskStatus.ARCHIVED.value},
        # DIRECTIVE : CANCELLED -> RUNNING est INTERDIT !
        TaskStatus.CANCELLED.value: {TaskStatus.ARCHIVED.value},
        TaskStatus.ARCHIVED.value: set(),
    },
    "application": {
        ApplicationStatus.REGISTERED.value: {ApplicationStatus.STARTING.value, ApplicationStatus.READY.value, ApplicationStatus.UNAVAILABLE.value, ApplicationStatus.UNKNOWN.value},
        ApplicationStatus.STARTING.value: {ApplicationStatus.READY.value, ApplicationStatus.RUNNING.value, ApplicationStatus.ERROR.value, ApplicationStatus.CRASHED.value, ApplicationStatus.STOPPED.value},
        ApplicationStatus.READY.value: {ApplicationStatus.RUNNING.value, ApplicationStatus.STOPPING.value, ApplicationStatus.STOPPED.value, ApplicationStatus.UNAVAILABLE.value, ApplicationStatus.ERROR.value},
        ApplicationStatus.RUNNING.value: {ApplicationStatus.STOPPING.value, ApplicationStatus.STOPPED.value, ApplicationStatus.ERROR.value, ApplicationStatus.CRASHED.value, ApplicationStatus.READY.value},
        ApplicationStatus.STOPPING.value: {ApplicationStatus.STOPPED.value, ApplicationStatus.ERROR.value, ApplicationStatus.CRASHED.value},
        ApplicationStatus.STOPPED.value: {ApplicationStatus.STARTING.value, ApplicationStatus.REGISTERED.value, ApplicationStatus.READY.value},
        ApplicationStatus.ERROR.value: {ApplicationStatus.STARTING.value, ApplicationStatus.STOPPED.value, ApplicationStatus.UNKNOWN.value, ApplicationStatus.REGISTERED.value},
        ApplicationStatus.CRASHED.value: {ApplicationStatus.STARTING.value, ApplicationStatus.STOPPED.value, ApplicationStatus.UNKNOWN.value, ApplicationStatus.REGISTERED.value},
        ApplicationStatus.UNAVAILABLE.value: {ApplicationStatus.REGISTERED.value, ApplicationStatus.STARTING.value},
        ApplicationStatus.UNKNOWN.value: {ApplicationStatus.REGISTERED.value, ApplicationStatus.STARTING.value, ApplicationStatus.STOPPED.value, ApplicationStatus.READY.value, ApplicationStatus.RUNNING.value},
    },
    "service": {
        ServiceStatus.DEFINED.value: {ServiceStatus.STARTING.value, ServiceStatus.INACTIVE.value, ServiceStatus.ACTIVE.value},
        ServiceStatus.STARTING.value: {ServiceStatus.ACTIVE.value, ServiceStatus.DEGRADED.value, ServiceStatus.FAILED.value, ServiceStatus.STOPPING.value},
        ServiceStatus.ACTIVE.value: {ServiceStatus.DEGRADED.value, ServiceStatus.STOPPING.value, ServiceStatus.INACTIVE.value, ServiceStatus.FAILED.value, ServiceStatus.CRASH_LOOP.value},
        ServiceStatus.DEGRADED.value: {ServiceStatus.ACTIVE.value, ServiceStatus.STOPPING.value, ServiceStatus.INACTIVE.value, ServiceStatus.FAILED.value, ServiceStatus.CRASH_LOOP.value},
        ServiceStatus.STOPPING.value: {ServiceStatus.INACTIVE.value, ServiceStatus.FAILED.value},
        ServiceStatus.INACTIVE.value: {ServiceStatus.STARTING.value, ServiceStatus.DEFINED.value},
        ServiceStatus.FAILED.value: {ServiceStatus.STARTING.value, ServiceStatus.DEFINED.value, ServiceStatus.CRASH_LOOP.value, ServiceStatus.INACTIVE.value},
        ServiceStatus.CRASH_LOOP.value: {ServiceStatus.STARTING.value, ServiceStatus.INACTIVE.value, ServiceStatus.FAILED.value},
        ServiceStatus.UNKNOWN.value: {ServiceStatus.DEFINED.value, ServiceStatus.STARTING.value, ServiceStatus.ACTIVE.value, ServiceStatus.INACTIVE.value},
    },
    "tool": {
        ToolStatus.REGISTERED.value: {ToolStatus.AVAILABLE.value, ToolStatus.UNAVAILABLE.value, ToolStatus.BLOCKED.value},
        ToolStatus.AVAILABLE.value: {ToolStatus.BUSY.value, ToolStatus.EXECUTING.value, ToolStatus.UNAVAILABLE.value, ToolStatus.BLOCKED.value},
        ToolStatus.BUSY.value: {ToolStatus.AVAILABLE.value, ToolStatus.EXECUTING.value, ToolStatus.ERROR.value, ToolStatus.TIMEOUT.value},
        ToolStatus.EXECUTING.value: {ToolStatus.SUCCESS.value, ToolStatus.ERROR.value, ToolStatus.TIMEOUT.value, ToolStatus.AVAILABLE.value},
        ToolStatus.SUCCESS.value: {ToolStatus.AVAILABLE.value, ToolStatus.EXECUTING.value},
        ToolStatus.ERROR.value: {ToolStatus.AVAILABLE.value, ToolStatus.BLOCKED.value, ToolStatus.UNAVAILABLE.value},
        ToolStatus.TIMEOUT.value: {ToolStatus.AVAILABLE.value, ToolStatus.BLOCKED.value},
        ToolStatus.UNAVAILABLE.value: {ToolStatus.REGISTERED.value, ToolStatus.AVAILABLE.value},
        ToolStatus.BLOCKED.value: {ToolStatus.AVAILABLE.value, ToolStatus.UNAVAILABLE.value},
    },
    "model": {
        ModelStatus.DISCOVERED.value: {ModelStatus.AVAILABLE.value, ModelStatus.LOADING.value, ModelStatus.UNAVAILABLE.value},
        ModelStatus.AVAILABLE.value: {ModelStatus.LOADING.value, ModelStatus.READY.value, ModelStatus.UNAVAILABLE.value},
        ModelStatus.LOADING.value: {ModelStatus.LOADED.value, ModelStatus.READY.value, ModelStatus.ERROR.value},
        ModelStatus.LOADED.value: {ModelStatus.READY.value, ModelStatus.GENERATING.value, ModelStatus.UNLOADING.value, ModelStatus.UNLOADED.value},
        ModelStatus.READY.value: {ModelStatus.GENERATING.value, ModelStatus.UNLOADING.value, ModelStatus.UNLOADED.value, ModelStatus.ERROR.value},
        ModelStatus.GENERATING.value: {ModelStatus.READY.value, ModelStatus.ERROR.value, ModelStatus.UNLOADING.value},
        ModelStatus.UNLOADING.value: {ModelStatus.UNLOADED.value, ModelStatus.AVAILABLE.value, ModelStatus.ERROR.value},
        ModelStatus.UNLOADED.value: {ModelStatus.LOADING.value, ModelStatus.AVAILABLE.value},
        ModelStatus.ERROR.value: {ModelStatus.AVAILABLE.value, ModelStatus.LOADING.value, ModelStatus.UNAVAILABLE.value},
        ModelStatus.UNAVAILABLE.value: {ModelStatus.DISCOVERED.value, ModelStatus.AVAILABLE.value},
    },
}


class InvalidStateTransitionError(ValueError):
    """Exception levée lors d'une transition d'état illégale selon les règles du Coeur Turbo OS."""
    pass


# ─── ÉVÉNEMENT D'AUDIT ET ENTITÉ D'ÉTAT ───────────────────────────────────────

class AuditEvent:
    def __init__(self, entity_type: str, entity_id: str, from_status: Optional[str],
                 to_status: str, reason: str, actor: str, checkpoint_id: Optional[str] = None,
                 extra: Optional[dict] = None):
        self.id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.from_status = str(from_status) if from_status else None
        self.to_status = str(to_status)
        self.reason = reason
        self.actor = actor
        self.checkpoint_id = checkpoint_id
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "actor": self.actor,
            "checkpoint_id": self.checkpoint_id,
            "extra": self.extra,
        }


class EntityState:
    def __init__(self, entity_type: str, entity_id: str, status: str,
                 metadata: Optional[dict] = None, updated_by: str = "system"):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.status = str(status)
        self.previous_status: Optional[str] = None
        self.status_reason: str = "initialisation"
        self.updated_at: float = time.time()
        self.updated_by: str = updated_by
        self.checkpoint_id: Optional[str] = None
        self.metadata: Dict[str, Any] = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "status": self.status,
            "previous_status": self.previous_status,
            "status_reason": self.status_reason,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "checkpoint_id": self.checkpoint_id,
            "metadata": self.metadata,
        }


# ─── MACHINE D'ÉTAT GLOBALE DU SYSTÈME (SINGLETON) ───────────────────────────

class SystemState:
    """État central unifié et audité de Turbo OS."""

    STATE_DIR = os.path.expanduser("~/jarvis/turbo-os/state")
    AUDIT_FILE = os.path.join(STATE_DIR, "audit.jsonl")

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SystemState, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self._entities: Dict[str, Dict[str, EntityState]] = {
            "task": {},
            "application": {},
            "service": {},
            "tool": {},
            "model": {},
            "domino": {},
            "agent": {},
        }
        self._audit_log: List[AuditEvent] = []
        self._max_in_memory_audit = 5000
        self.cockpit_status = CockpitStatus.READY.value
        self.board_status = BoardStatus.READY.value
        self.health_status = HealthStatus.HEALTHY.value
        try:
            os.makedirs(self.STATE_DIR, exist_ok=True)
        except Exception:
            pass

    def reset(self):
        """Réinitialise l'état en mémoire (utilisé principalement pour les tests)."""
        with self._lock:
            self._init_state()

    def register_entity(self, entity_type: str, entity_id: str,
                        initial_status: str | Enum,
                        metadata: Optional[dict] = None,
                        updated_by: str = "system") -> EntityState:
        """Enregistre une nouvelle entité dans le système d'état."""
        status_val = initial_status.value if isinstance(initial_status, Enum) else str(initial_status)
        with self._lock:
            if entity_type not in self._entities:
                self._entities[entity_type] = {}
            ent = EntityState(entity_type, entity_id, status_val, metadata=metadata, updated_by=updated_by)
            self._entities[entity_type][entity_id] = ent
            self._record_audit(AuditEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                from_status=None,
                to_status=status_val,
                reason="Enregistrement de l'entité",
                actor=updated_by,
                extra=metadata or {}
            ))
            return ent

    def transition(self, entity_type: str, entity_id: str,
                   to_status: str | Enum,
                   reason: str,
                   updated_by: str = "user",
                   checkpoint_id: Optional[str] = None,
                   extra: Optional[dict] = None) -> EntityState:
        """Applique une transition d'état stricte avec validation et audit."""
        to_val = to_status.value if isinstance(to_status, Enum) else str(to_status)

        with self._lock:
            if entity_type not in self._entities or entity_id not in self._entities[entity_type]:
                # Enregistrement implicite si nécessaire
                self.register_entity(entity_type, entity_id, to_val, metadata=extra, updated_by=updated_by)
                return self._entities[entity_type][entity_id]

            ent = self._entities[entity_type][entity_id]
            from_val = ent.status

            # Validation des règles de transition
            type_rules = VALID_TRANSITIONS.get(entity_type)
            if type_rules:
                allowed_next = type_rules.get(from_val, set())
                # Exception : même état autorisé pour mise à jour de métadonnées
                if to_val != from_val and to_val not in allowed_next:
                    err_msg = (
                        f"Transition interdite pour {entity_type} '{entity_id}' : "
                        f"{from_val} -> {to_val}. Transitions autorisées : {sorted(list(allowed_next))}"
                    )
                    raise InvalidStateTransitionError(err_msg)

            # Application
            ent.previous_status = from_val
            ent.status = to_val
            ent.status_reason = reason
            ent.updated_at = time.time()
            ent.updated_by = updated_by
            if checkpoint_id:
                ent.checkpoint_id = checkpoint_id
            if extra:
                ent.metadata.update(extra)

            # Audit obligatoire
            self._record_audit(AuditEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                from_status=from_val,
                to_status=to_val,
                reason=reason,
                actor=updated_by,
                checkpoint_id=checkpoint_id,
                extra=extra or {}
            ))
            return ent

    # ─── PROTOCOLE PAUSE / RESUME STRICT AVEC CHECKPOINT ─────────────────────

    def pause_task(self, task_id: str, reason: str = "Pause demandée",
                   updated_by: str = "user", checkpoint_data: Optional[dict] = None) -> EntityState:
        """Protocole PAUSE strict : RUNNING -> CHECKPOINT -> PAUSED."""
        with self._lock:
            ent = self.get_entity("task", task_id)
            if not ent:
                raise ValueError(f"Tâche {task_id} introuvable")
            if ent.status != TaskStatus.RUNNING.value:
                raise InvalidStateTransitionError(
                    f"Impossible de mettre en pause la tâche {task_id} dans l'état {ent.status} (doit être RUNNING)"
                )

            # 1. Sauvegarde du checkpoint atomique
            ck_id = None
            if ck_engine:
                try:
                    payload = checkpoint_data or ent.metadata
                    ck_engine.save(task_id, payload, status=TaskStatus.PAUSED.value)
                    ck_id = task_id
                except Exception as ex:
                    reason += f" (Avertissement checkpoint: {ex})"

            # 2. Transition vers PAUSED
            return self.transition(
                "task", task_id, TaskStatus.PAUSED.value,
                reason=reason, updated_by=updated_by,
                checkpoint_id=ck_id, extra={"checkpoint_saved": True}
            )

    def resume_task(self, task_id: str, reason: str = "Reprise de la tâche",
                    updated_by: str = "user") -> EntityState:
        """Protocole RESUME strict : PAUSED -> RESTORE CHECKPOINT -> VERIFY STATE -> RUNNING."""
        with self._lock:
            ent = self.get_entity("task", task_id)
            if not ent:
                raise ValueError(f"Tâche {task_id} introuvable")
            if ent.status != TaskStatus.PAUSED.value:
                raise InvalidStateTransitionError(
                    f"Impossible de reprendre la tâche {task_id} dans l'état {ent.status} (doit être PAUSED)"
                )

            # 1. Restauration du checkpoint
            restored_state = None
            if ck_engine:
                try:
                    ck_data = ck_engine.restore(task_id)
                    if ck_data:
                        restored_state = ck_data.get("state")
                        ck_engine.set_status(task_id, TaskStatus.RUNNING.value)
                except Exception as ex:
                    reason += f" (Avertissement restauration: {ex})"

            # 2. Transition vers RUNNING
            extra = {"restored": bool(restored_state)}
            if restored_state:
                extra["restored_state"] = restored_state
            return self.transition(
                "task", task_id, TaskStatus.RUNNING.value,
                reason=reason, updated_by=updated_by,
                checkpoint_id=ent.checkpoint_id, extra=extra
            )

    def verify_task(self, task_id: str, reason: str = "Vérification des preuves en cours",
                    updated_by: str = "system") -> EntityState:
        """Passage obligatoire par l'état VERIFYING avant terminaison."""
        return self.transition("task", task_id, TaskStatus.VERIFYING.value, reason=reason, updated_by=updated_by)

    def complete_task(self, task_id: str, reason: str = "Tâche vérifiée et achevée",
                      updated_by: str = "system") -> EntityState:
        """Achève la tâche après vérification (VERIFYING -> DONE)."""
        with self._lock:
            ent = self.get_entity("task", task_id)
            if not ent:
                raise ValueError(f"Tâche {task_id} introuvable")
            if ent.status != TaskStatus.VERIFYING.value:
                # Si elle est RUNNING, on force le passage par VERIFYING pour respecter la directive
                if ent.status == TaskStatus.RUNNING.value:
                    self.verify_task(task_id, reason="Auto-vérification préalable obligatoire", updated_by=updated_by)
                else:
                    raise InvalidStateTransitionError(
                        f"Impossible d'achever la tâche {task_id} depuis l'état {ent.status} (doit être VERIFYING)"
                    )
            return self.transition("task", task_id, TaskStatus.DONE.value, reason=reason, updated_by=updated_by)

    # ─── ACCÈS ET AUDIT ─────────────────────────────────────────────────────────

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[EntityState]:
        with self._lock:
            return self._entities.get(entity_type, {}).get(entity_id)

    def list_entities(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if entity_type:
                return [e.to_dict() for e in self._entities.get(entity_type, {}).values()]
            out = []
            for t, items in self._entities.items():
                out.extend([e.to_dict() for e in items.values()])
            return out

    def _record_audit(self, event: AuditEvent):
        self._audit_log.append(event)
        if len(self._audit_log) > self._max_in_memory_audit:
            self._audit_log = self._audit_log[-self._max_in_memory_audit:]
        # Persistance asynchrone / append-only
        try:
            with open(self.AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def get_audit_log(self, entity_type: Optional[str] = None,
                      entity_id: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            events = self._audit_log
            if entity_type:
                events = [e for e in events if e.entity_type == entity_type]
            if entity_id:
                events = [e for e in events if e.entity_id == entity_id]
            return [e.to_dict() for e in events[-limit:]]

    def export_state(self) -> Dict[str, Any]:
        """Retourne l'état complet du système pour la télémétrie ou les dashboards."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "cockpit_status": self.cockpit_status,
                "board_status": self.board_status,
                "health_status": self.health_status,
                "entities_count": {k: len(v) for k, v in self._entities.items()},
                "entities": {k: [e.to_dict() for e in v.values()] for k, v in self._entities.items()},
                "audit_events_count": len(self._audit_log),
            }


def get_system_state() -> SystemState:
    """Accesseur canonique vers le singleton SystemState."""
    return SystemState()
