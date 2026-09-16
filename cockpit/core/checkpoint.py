#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TURBO OS — CHECKPOINT ENGINE.

Sauvegarde/restaure l'état d'une tâche du moteur pour pouvoir l'INTERROMPRE et la
REPRENDRE au dernier pas sûr — jamais repartir de zéro. Écriture atomique.

États : RUNNING → PAUSED → RUNNING (resume) / CANCELLED / DONE / ROLLBACK.

CLI :
    checkpoint.py list                 # liste les checkpoints
    checkpoint.py show <task_id>       # état complet
    checkpoint.py pause <task_id>      # PAUSE (arrêt propre, reprise possible)
    checkpoint.py resume <task_id>     # RUNNING
    checkpoint.py cancel <task_id>     # CANCELLED
    checkpoint.py delete <task_id>
"""
from __future__ import annotations
import os, sys, json, time, glob

CKDIR = os.path.expanduser("~/jarvis/turbo-os/checkpoints")

def _path(tid: str) -> str:
    return os.path.join(CKDIR, f"{tid}.json")

def save(task_id: str, state: dict, status: str = "RUNNING") -> str:
    """Sauvegarde atomique de l'état (objective, step, trace, messages, files…)."""
    os.makedirs(CKDIR, exist_ok=True)
    data = {"task_id": task_id, "status": status, "state": state, "updated_at": time.time()}
    tmp = _path(task_id) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, _path(task_id))
    return _path(task_id)

def restore(task_id: str):
    p = _path(task_id)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def is_paused(task_id: str) -> bool:
    d = restore(task_id)
    return bool(d) and d.get("status") in ("PAUSED", "CANCELLED")

def is_cancelled(task_id: str) -> bool:
    d = restore(task_id)
    return bool(d) and d.get("status") == "CANCELLED"

def set_status(task_id: str, status: str):
    d = restore(task_id)
    if not d:
        return None
    return save(task_id, d["state"], status)

def list_ck() -> list:
    out = []
    for p in sorted(glob.glob(os.path.join(CKDIR, "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            st = d.get("state", {})
            out.append({"task_id": d["task_id"], "status": d.get("status"),
                        "step": st.get("step"), "objective": (st.get("objective") or "")[:60],
                        "updated_at": d.get("updated_at")})
        except Exception:
            pass
    return out

def delete(task_id: str) -> bool:
    p = _path(task_id)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "list":
        print(json.dumps(list_ck(), ensure_ascii=False, indent=2))
    elif cmd == "show" and arg:
        print(json.dumps(restore(arg), ensure_ascii=False, indent=2))
    elif cmd in ("pause", "resume", "cancel") and arg:
        st = {"pause": "PAUSED", "resume": "RUNNING", "cancel": "CANCELLED"}[cmd]
        print(f"{arg} -> {st} : {set_status(arg, st)}")
    elif cmd == "delete" and arg:
        print("supprimé" if delete(arg) else "introuvable")
    else:
        print(__doc__)
