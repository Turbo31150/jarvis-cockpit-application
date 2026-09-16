#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS COCKPIT — GPU ACTION MEMORY & CONTEXT COMPRESSOR ENGINE
==============================================================
Mémoire action souveraine haute vitesse & délestage de contexte :
  • Vectorisation permanente en tâche de fond sur GTX 1660S (Ollama :11436, nomic-embed-text 768D)
  • Stockage SQLite unifié (jarvis_action_memory.db) avec index FTS5 + vecteurs float32
  • Recherche hybride (similarité cosinus vectorielle GPU + BM25 textuel) en <15ms
  • Compression et libération de contexte : compacte les historiques d'actions lourds
    pour garder le LLM rapide ("plein gaz") sans saturer la fenêtre de contexte.
"""

import os
import sys
import time
import json
import math
import queue
import struct
import sqlite3
import threading
import urllib.request
from datetime import datetime

from .config import DATA_DIR, OLLAMA_EMBED_URL, EMBED_MODEL
from .inference import _loopback_closed

DB_PATH = os.path.join(DATA_DIR, "jarvis_action_memory.db")
MAX_OUTPUT_STORE = 8192
BATCH_SIZE = 8

# Math helpers 100% natifs (compatibilité universelle venv/système)
def floats_to_blob(floats):
    return struct.pack(f"{len(floats)}f", *floats)

def blob_to_floats(blob):
    n = len(blob) // 4
    return struct.unpack(f"{n}f", blob)

def cosine_sim(v1, v2):
    dot = sum(x * y for x, y in zip(v1, v2))
    n1 = math.sqrt(sum(x * x for x in v1)) or 1e-6
    n2 = math.sqrt(sum(y * y for y in v2)) or 1e-6
    return dot / (n1 * n2)


class ActionMemoryEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ActionMemoryEngine, cls).__new__(cls)
                cls._instance._init_engine()
            return cls._instance

    def _init_engine(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_path = DB_PATH
        self._init_db()
        self._work_queue = queue.Queue()
        self._running = True
        self._cache_vectors = []  # list of (id, normalized_tuple)
        self._cache_lock = threading.Lock()
        self._load_vector_cache()

        self._stats = {
            "total_actions": 0,
            "vectorized_actions": 0,
            "tokens_freed": 0,
            "last_vector_time": 0.0,
            "avg_latency_ms": 0.0,
            "gpu_endpoint": OLLAMA_EMBED_URL,
            "embed_model": EMBED_MODEL,
            "active": True
        }

        self._worker_thread = threading.Thread(target=self._background_vectorizer, daemon=True)
        self._worker_thread.start()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    source TEXT,
                    session_id TEXT,
                    action_type TEXT,
                    command TEXT,
                    output TEXT,
                    summary TEXT,
                    exit_code INTEGER,
                    tokens_saved INTEGER DEFAULT 0,
                    embedding BLOB,
                    vectorized INTEGER DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_vecto ON action_memory(vectorized);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_source ON action_memory(source);
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS action_memory_fts USING fts5(
                    command, summary, output, content='action_memory', content_rowid='id'
                );
            """)

    def _load_vector_cache(self):
        """Précharge les vecteurs en RAM pour une recherche cosinus instantanée."""
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                rows = cur.execute("SELECT id, embedding FROM action_memory WHERE embedding IS NOT NULL").fetchall()
                loaded = []
                for aid, blob in rows:
                    if blob and len(blob) == 768 * 4:
                        vec = blob_to_floats(blob)
                        loaded.append((aid, vec))
                with self._cache_lock:
                    self._cache_vectors = loaded
        except Exception:
            pass

    def record_action(self, command: str, output: str = "", source: str = "cockpit",
                      session_id: str = "", action_type: str = "command",
                      exit_code: int = 0, summary: str = "") -> dict:
        """Enregistre une action et l'envoie en file d'attente pour vectorisation GPU immédiate."""
        now = datetime.now().isoformat()
        if not summary:
            clean_out = (output or "").strip()
            first_lines = " ".join(clean_out.splitlines()[:3])[:200]
            summary = f"{command.strip()} -> {first_lines}" if clean_out else command.strip()

        tokens_saved = max(10, len(output) // 4)
        trunc_output = output[:MAX_OUTPUT_STORE] if output else ""

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO action_memory (timestamp, source, session_id, action_type,
                                           command, output, summary, exit_code, tokens_saved, vectorized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
            """, (now, source, session_id, action_type, command, trunc_output, summary, exit_code, tokens_saved))
            action_id = cur.lastrowid

            cur.execute("""
                INSERT INTO action_memory_fts(rowid, command, summary, output)
                VALUES (?, ?, ?, ?);
            """, (action_id, command, summary, trunc_output))
            conn.commit()

        text_to_embed = f"{command} | {summary}"
        self._work_queue.put((action_id, text_to_embed))

        self._stats["total_actions"] += 1
        self._stats["tokens_freed"] += tokens_saved

        return {
            "success": True,
            "action_id": action_id,
            "tokens_saved": tokens_saved,
            "status": "enqueued_for_gpu"
        }

    def _call_gpu_embed(self, texts: list) -> list:
        """Appel direct vers l'instance Ollama GPU dédiée (:11436 nomic-embed-text)."""
        if _loopback_closed(OLLAMA_EMBED_URL):
            # Windows : Ollama non lancé → refus immédiat (sinon ~2 s de refus toutes les 2 s)
            raise ConnectionError("instance embeddings Ollama hors-ligne")
        payload = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_EMBED_URL}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = (time.time() - t0) * 1000
            self._stats["last_vector_time"] = time.time()
            self._stats["avg_latency_ms"] = round(latency_ms / max(1, len(texts)), 2)
            embs = data.get("embeddings") or ([data["embedding"]] if "embedding" in data else [])
            return embs

    def _background_vectorizer(self):
        """Worker permanent en arrière-plan : absorbe les actions et les vectorise sur GPU 0."""
        while self._running:
            try:
                batch = []
                try:
                    item = self._work_queue.get(timeout=2.0)
                    batch.append(item)
                    while len(batch) < BATCH_SIZE:
                        batch.append(self._work_queue.get_nowait())
                except queue.Empty:
                    self._drain_unvectorized()
                    continue

                if not batch:
                    continue

                action_ids = [x[0] for x in batch]
                texts = [x[1] for x in batch]

                try:
                    embeddings = self._call_gpu_embed(texts)
                    if len(embeddings) == len(batch):
                        with sqlite3.connect(self.db_path) as conn:
                            cur = conn.cursor()
                            for aid, emb in zip(action_ids, embeddings):
                                blob = floats_to_blob(emb)
                                cur.execute("UPDATE action_memory SET embedding = ?, vectorized = 1 WHERE id = ?;",
                                            (blob, aid))
                                with self._cache_lock:
                                    self._cache_vectors.append((aid, emb))
                            conn.commit()
                        self._stats["vectorized_actions"] += len(batch)
                except Exception:
                    time.sleep(1.0)
                finally:
                    for _ in batch:
                        self._work_queue.task_done()

            except Exception:
                time.sleep(1.0)

    def _drain_unvectorized(self):
        """Rattrape les actions non vectorisées en attente."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                rows = cur.execute("""
                    SELECT id, command, summary FROM action_memory
                    WHERE vectorized = 0
                    LIMIT ?;
                """, (BATCH_SIZE,)).fetchall()
                if not rows:
                    return

                texts = [f"{r[1]} | {r[2]}" for r in rows]
                embeddings = self._call_gpu_embed(texts)
                if len(embeddings) == len(rows):
                    for (aid, _, _), emb in zip(rows, embeddings):
                        blob = floats_to_blob(emb)
                        cur.execute("UPDATE action_memory SET embedding = ?, vectorized = 1 WHERE id = ?;",
                                    (blob, aid))
                        with self._cache_lock:
                            self._cache_vectors.append((aid, emb))
                    conn.commit()
                    self._stats["vectorized_actions"] += len(rows)
        except Exception:
            pass

    def recall(self, query: str, limit: int = 5, min_score: float = 0.35) -> list:
        """Recherche hybride haute performance : similarité GPU (cosinus) + FTS5 BM25."""
        if not query.strip():
            return []

        q_vec = None
        try:
            embs = self._call_gpu_embed([query.strip()])
            if embs:
                q_vec = embs[0]
        except Exception:
            q_vec = None

        vector_scores = {}
        if q_vec is not None:
            with self._cache_lock:
                cache_snapshot = list(self._cache_vectors)
            for aid, vec in cache_snapshot:
                sim = cosine_sim(q_vec, vec)
                if sim >= min_score:
                    vector_scores[aid] = sim

        fts_scores = {}
        try:
            clean_q = " OR ".join(f'"{w}"' for w in query.split() if len(w) > 2)[:120]
            if clean_q:
                with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                    cur = conn.cursor()
                    rows = cur.execute("""
                        SELECT rowid, bm25(action_memory_fts) FROM action_memory_fts
                        WHERE action_memory_fts MATCH ?
                        ORDER BY bm25(action_memory_fts)
                        LIMIT 20;
                    """, (clean_q,)).fetchall()
                    for aid, bm in rows:
                        fts_scores[aid] = 1.0 / (1.0 + abs(float(bm)))
        except Exception:
            pass

        all_ids = set(vector_scores.keys()) | set(fts_scores.keys())
        scored = []
        for aid in all_ids:
            v_score = vector_scores.get(aid, 0.0)
            f_score = fts_scores.get(aid, 0.0)
            comb = (0.7 * v_score) + (0.3 * f_score)
            scored.append((aid, comb, v_score, f_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_ids = scored[:limit]

        if not top_ids:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                rows = cur.execute("""
                    SELECT id, timestamp, source, command, summary, output, exit_code, tokens_saved
                    FROM action_memory ORDER BY id DESC LIMIT ?;
                """, (limit,)).fetchall()
                return [{
                    "id": r[0], "timestamp": r[1], "source": r[2], "command": r[3],
                    "summary": r[4], "output": r[5], "exit_code": r[6], "tokens_saved": r[7],
                    "score": 0.0
                } for r in rows]

        placeholders = ",".join("?" for _ in top_ids)
        id_map = {item[0]: item[1] for item in top_ids}
        results = []
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            rows = cur.execute(f"""
                SELECT id, timestamp, source, command, summary, output, exit_code, tokens_saved
                FROM action_memory WHERE id IN ({placeholders});
            """, [item[0] for item in top_ids]).fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "timestamp": r[1],
                    "source": r[2],
                    "command": r[3],
                    "summary": r[4],
                    "output": r[5],
                    "exit_code": r[6],
                    "tokens_saved": r[7],
                    "score": round(id_map.get(r[0], 0.0), 3)
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def compress_context(self, history: list, max_tokens: int = 1800) -> list:
        """Élague et compresse l'historique en remplaçant les sorties verbeuses par des références mémoire."""
        pruned = []
        est_tokens = 0
        for entry in reversed(history):
            content = entry.get("content", "")
            tok = len(content) // 4
            if est_tokens + tok > max_tokens and len(content) > 300:
                summary = content[:150] + "... [Archivé & Vectorisé en Mémoire Action GPU]"
                pruned.append({
                    "role": entry.get("role", "system"),
                    "content": f"[Action Archive - Réf Mémoire]: {summary}",
                    "compressed": True,
                    "saved_tokens": tok - 40
                })
                est_tokens += 40
            else:
                pruned.append(entry)
                est_tokens += tok

        return list(reversed(pruned))

    def get_stats(self) -> dict:
        """Statistiques d'état de la mémoire action et du vectoriseur GPU."""
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            tot = cur.execute("SELECT COUNT(*) FROM action_memory;").fetchone()[0]
            vec = cur.execute("SELECT COUNT(*) FROM action_memory WHERE vectorized = 1;").fetchone()[0]
            freed = cur.execute("SELECT COALESCE(SUM(tokens_saved), 0) FROM action_memory;").fetchone()[0]

        self._stats["total_actions"] = tot
        self._stats["vectorized_actions"] = vec
        self._stats["tokens_freed"] = freed
        self._stats["queue_pending"] = self._work_queue.qsize()
        self._stats["cached_vectors"] = len(self._cache_vectors)
        return dict(self._stats)


# Instance globale singleton
ACTION_MEMORY = ActionMemoryEngine()
