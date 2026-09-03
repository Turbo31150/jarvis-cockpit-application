#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — DATABASE ENGINE
Centralized database manager for SQLite living databases, FTS5 Board corpus, Master Tasks, and Vector Store.
"""

import os
import sqlite3
import subprocess
from .config import JARVIS_DIR, MASTER_DB, BOARD_DB, VECTOR_DB, SQL_CACHE

def get_board_stats() -> dict:
    """Lit les métriques exactes de board.db sans jamais recourir à des valeurs figées."""
    if not os.path.exists(BOARD_DB):
        return {"chunks": 0, "sources": 0, "domains": 0, "experts": 0, "status": "NON TROUVÉ"}
    try:
        con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True, timeout=3.0)
        c = con.cursor()
        n_ch = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        n_so = c.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        n_do = c.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
        n_ex = c.execute("SELECT COUNT(*) FROM experts").fetchone()[0]
        con.close()
        return {
            "chunks": n_ch,
            "sources": n_so,
            "domains": n_do,
            "experts": n_ex,
            "status": "OK",
            "summary": f"{n_ch:,} chunks · {n_do} domaines · {n_ex} experts".replace(",", " ")
        }
    except Exception as e:
        return {"chunks": 0, "sources": 0, "domains": 0, "experts": 0, "status": f"Erreur: {e}", "summary": "Indisponible"}

def search_board_fts(query: str, limit: int = 8) -> list[dict]:
    """Recherche plein texte dans le corpus de la Bibliothèque Vivante board.db."""
    if not os.path.exists(BOARD_DB) or not query.strip():
        return []
    try:
        con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True, timeout=4.0)
        c = con.cursor()
        c.execute("""
            SELECT c.id, c.domain_id, c.expert_id, s.title, c.text, s.url
            FROM chunks c
            JOIN sources s ON c.source_id = s.id
            WHERE c.text LIKE ? OR s.title LIKE ?
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
        rows = c.fetchall()
        con.close()
        return [
            {
                "id": r[0],
                "domain": r[1],
                "expert": r[2],
                "title": r[3] or "Sans titre",
                "snippet": (r[4][:300] + "...") if len(r[4]) > 300 else r[4],
                "source": r[5] or ""
            }
            for r in rows
        ]
    except Exception:
        return []

def get_vector_store_stats() -> dict:
    """Lit les métriques du store vectoriel (768D Nomic / document_vectors)."""
    if not os.path.exists(VECTOR_DB):
        return {"vectors": 0, "files": 0, "status": "NON TROUVÉ"}
    try:
        con = sqlite3.connect(f"file:{VECTOR_DB}?mode=ro", uri=True, timeout=3.0)
        c = con.cursor()
        n_vec = c.execute("SELECT COUNT(*) FROM document_vectors").fetchone()[0]
        n_fil = c.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
        con.close()
        return {"vectors": n_vec, "files": n_fil, "status": "OK"}
    except Exception as e:
        return {"vectors": 0, "files": 0, "status": f"Erreur: {e}"}

def get_master_tasks(limit: int = 100) -> list[dict]:
    """Récupère les tâches ordonnées depuis jarvis_master.db."""
    if not os.path.exists(MASTER_DB):
        return []
    try:
        con = sqlite3.connect(f"file:{MASTER_DB}?mode=ro", uri=True, timeout=3.0)
        con.row_factory = sqlite3.Row
        c = con.cursor()
        c.execute("""
            SELECT id, title, status, COALESCE(agent, 'GÉNÉRAL') AS category, progress, created_at
            FROM tasks
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def add_master_task(title: str, category: str = "GÉNÉRAL", priority: int = 1) -> bool:
    """Ajoute une tâche dans jarvis_master.db."""
    if not os.path.exists(MASTER_DB):
        return False
    try:
        con = sqlite3.connect(MASTER_DB, timeout=4.0)
        c = con.cursor()
        c.execute("INSERT INTO tasks (title, agent, status, progress) VALUES (?, ?, 'pending', 0)",
                  (title, category))
        con.commit()
        con.close()
        return True
    except Exception:
        return False

def update_master_task_status(task_id: int, status: str) -> bool:
    """Met à jour le statut d'une tâche (pending, in_progress, done)."""
    if not os.path.exists(MASTER_DB):
        return False
    try:
        con = sqlite3.connect(MASTER_DB, timeout=4.0)
        c = con.cursor()
        c.execute("UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, task_id))
        con.commit()
        con.close()
        return True
    except Exception:
        return False

def delete_master_task(task_id: int) -> bool:
    """Supprime une tâche de jarvis_master.db."""
    if not os.path.exists(MASTER_DB):
        return False
    try:
        con = sqlite3.connect(MASTER_DB, timeout=4.0)
        c = con.cursor()
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        con.commit()
        con.close()
        return True
    except Exception:
        return False

def scan_all_sqlite_databases() -> list[dict]:
    """Scanne et référence l'ensemble des bases SQLite vivantes."""
    bases_list = []
    try:
        cmd = "find " + JARVIS_DIR + " -maxdepth 3 -name '*.db' -size +1k 2>/dev/null | grep -vE '/(backups?|archive|old|corbeille)/' | sort -u"
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        paths = [l.strip() for l in p.stdout.splitlines() if l.strip()]

        for db_path in paths:
            try:
                con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
                c = con.cursor()
                tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                con.close()
                if not tables:
                    continue
                size_kb = round(os.path.getsize(db_path) / 1024, 1)
                size_str = f"{size_kb} Ko" if size_kb < 1024 else f"{round(size_kb/1024, 2)} Mo"
                rel = os.path.relpath(db_path, os.path.expanduser("~"))
                bases_list.append({
                    "name": os.path.basename(db_path),
                    "path": db_path,
                    "rel_path": rel,
                    "size_str": size_str,
                    "size_bytes": os.path.getsize(db_path),
                    "table_count": len(tables),
                    "tables": tables
                })
            except Exception:
                continue
    except Exception:
        pass

    bases_list.sort(key=lambda x: x["table_count"], reverse=True)
    return bases_list

def execute_safe_query(db_path: str, sql: str, limit: int = 50) -> dict:
    """Exécute une requête SQL en lecture sécurisée avec pagination."""
    if not os.path.exists(db_path):
        return {"error": "Base introuvable", "columns": [], "rows": [], "row_count": 0}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        c = con.cursor()
        c.execute(sql)
        cols = [d[0] for d in c.description] if c.description else []
        rows = c.fetchmany(limit)
        con.close()
        return {
            "error": None,
            "columns": cols,
            "rows": rows,
            "row_count": len(rows)
        }
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": [], "row_count": 0}
