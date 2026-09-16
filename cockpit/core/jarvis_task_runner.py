#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS TASK RUNNER — exécuteur SÉQUENTIEL de file de tâches (processus secondaire).

S'appuie sur la boucle executor (jarvis_core_loop) : chaque tâche est une consigne
en langage naturel, exécutée RÉELLEMENT (full shell via run_bash + read_file + speak),
une par une, dans l'ordre. Réutilise la table `tasks` de jarvis_master.db :
statuts TODO → RUNNING → DONE|FAILED (états board §21). Catégorie dédiée
`CORE_LOOP` pour ne pas toucher aux autres tâches (mails, etc.).

Usage :
    python jarvis_task_runner.py --enqueue "Vérifie l'espace disque et résume."
    python jarvis_task_runner.py --run           # traite toute la file une fois
    python jarvis_task_runner.py --serve          # boucle (processus secondaire)
    python jarvis_task_runner.py --list
"""
from __future__ import annotations
import os
import sys
import json
import time
import sqlite3
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jarvis_core_loop  # boucle executor (tool-calling réel + TTS)

DB = os.path.expanduser("~/jarvis/jarvis_master.db")
CATEGORY = "CORE_LOOP"


def _conn():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


def enqueue(instruction: str, title: str = None, priority: str = "NORMAL") -> int:
    title = title or (instruction[:70] + ("…" if len(instruction) > 70 else ""))
    c = _conn()
    cur = c.execute(
        "INSERT INTO tasks (title,description,category,status,priority,machine,created_at,updated_at,progress)"
        " VALUES (?,?,?,?,?,?,?,?,0)",
        (title, instruction, CATEGORY, "TODO", priority, "mining", _now(), _now()))
    c.commit()
    tid = cur.lastrowid
    print(f"  + tâche #{tid} en file : {title}")
    return tid


def _pending(c):
    return c.execute(
        "SELECT id,title,description FROM tasks WHERE category=? AND status IN ('TODO','READY')"
        " ORDER BY CASE priority WHEN 'HAUTE' THEN 0 WHEN 'NORMAL' THEN 1 ELSE 2 END, id",
        (CATEGORY,)).fetchall()


def run_pending(speak: bool = False, verbose: bool = True) -> int:
    """Exécute séquentiellement toutes les tâches en attente. Retourne le nb traité."""
    c = _conn()
    done = 0
    while True:
        row = None
        pend = _pending(c)
        if not pend:
            break
        tid, title, desc = pend[0]
        # verrou : passe à RUNNING (séquentiel, une seule à la fois)
        c.execute("UPDATE tasks SET status='RUNNING',updated_at=?,progress=10 WHERE id=?",
                  (_now(), tid))
        c.commit()
        if verbose:
            print(f"\n▶️  #{tid} {title}")
        try:
            res = jarvis_core_loop.run(desc or title, speak_final=speak, verbose=verbose)
            status = "DONE" if res.get("status") == "answered" else "FAILED"
            summary = res.get("answer", "")[:1000]
            ctx = json.dumps({"status": res.get("status"),
                              "tool_loops": res.get("tool_loops"),
                              "trace": res.get("trace", [])}, ensure_ascii=False)[:4000]
        except Exception as e:
            status, summary, ctx = "FAILED", f"ERREUR runner: {e}", "{}"
        c.execute("UPDATE tasks SET status=?,consensus_summary=?,context=?,updated_at=?,progress=100 WHERE id=?",
                  (status, summary, ctx, _now(), tid))
        c.commit()
        done += 1
        if verbose:
            print(f"   {'✅' if status=='DONE' else '❌'} #{tid} -> {status} : {summary[:100]}")
    return done


def list_tasks():
    c = _conn()
    rows = c.execute(
        "SELECT id,status,title,substr(coalesce(consensus_summary,''),1,80) FROM tasks"
        " WHERE category=? ORDER BY id DESC LIMIT 20", (CATEGORY,)).fetchall()
    for r in rows:
        print(f"  #{r[0]:<5} [{r[1]:<8}] {r[2][:60]}  | {r[3]}")
    if not rows:
        print("  (file CORE_LOOP vide)")


def main():
    ap = argparse.ArgumentParser(description="JARVIS runner séquentiel de tâches")
    ap.add_argument("--enqueue", metavar="INSTRUCTION")
    ap.add_argument("--title")
    ap.add_argument("--priority", default="NORMAL")
    ap.add_argument("--run", action="store_true", help="traite la file une fois")
    ap.add_argument("--serve", action="store_true", help="boucle (processus secondaire)")
    ap.add_argument("--speak", action="store_true", help="vocalise la réponse finale")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--interval", type=int, default=15, help="secondes entre 2 scans (--serve)")
    args = ap.parse_args()

    if args.enqueue:
        enqueue(args.enqueue, args.title, args.priority)
    if args.list:
        list_tasks()
    if args.run:
        n = run_pending(speak=args.speak)
        print(f"\n{n} tâche(s) traitée(s).")
    if args.serve:
        print(f"[runner] processus secondaire — scan toutes les {args.interval}s (Ctrl-C pour stopper)")
        while True:
            n = run_pending(speak=args.speak, verbose=True)
            time.sleep(args.interval)
    if not any([args.enqueue, args.run, args.serve, args.list]):
        ap.print_help()


if __name__ == "__main__":
    main()
