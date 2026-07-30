"""SQLite-backed conversational and semantic memory."""
from __future__ import annotations

import json
import logging
import queue
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.config import default_database_path, env_float


class LongTermMemory:
    def __init__(self, llm, path=None):
        self.llm = llm
        self.path = Path(path or default_database_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._embedding_queue = queue.Queue()
        self._running = True
        self._initialize()
        self._worker = threading.Thread(
            target=self._embedding_worker,
            daemon=True,
            name="jarvis-memory-embedding",
        )
        self._worker.start()

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'conversation',
                    created_at TEXT NOT NULL,
                    embedding TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_created "
                "ON memories(created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def import_history_once(self, history):
        with self._write_lock, self._connect() as connection:
            imported = connection.execute(
                "SELECT value FROM memory_metadata WHERE key = 'json_history_imported'"
            ).fetchone()
            if imported:
                return
            ids = []
            for item in history:
                role = item.get("role", "assistant")
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                cursor = connection.execute(
                    "INSERT INTO memories(role, content, kind, created_at) "
                    "VALUES (?, ?, 'conversation', ?)",
                    (role, content, self._timestamp()),
                )
                ids.append((cursor.lastrowid, content))
            connection.execute(
                "INSERT OR REPLACE INTO memory_metadata(key, value) VALUES (?, ?)",
                ("json_history_imported", self._timestamp()),
            )
        for item in ids:
            self._embedding_queue.put(item)

    def add(self, role, content, kind="conversation"):
        content = str(content).strip()
        if not content:
            return None
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO memories(role, content, kind, created_at) "
                "VALUES (?, ?, ?, ?)",
                (role, content, kind, self._timestamp()),
            )
            memory_id = cursor.lastrowid
        self._embedding_queue.put((memory_id, content))
        return memory_id

    def add_exchange(self, user_text, assistant_text):
        self.add("user", user_text)
        self.add("assistant", assistant_text)

    def remember_fact(self, fact):
        self.add("system", fact, kind="fact")
        return f"Remembered: {fact}"

    def search(self, query, limit=4):
        query = str(query).strip()
        if not query:
            return []
        semantic = self._semantic_search(query, limit)
        return semantic or self._lexical_search(query, limit)

    def _semantic_search(self, query, limit):
        if not hasattr(self.llm, "embed"):
            return []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, role, content, kind, created_at, embedding "
                "FROM memories WHERE embedding IS NOT NULL "
                "ORDER BY id DESC LIMIT 500"
            ).fetchall()
        if not rows:
            return []
        try:
            query_vector = self.llm.embed(query)
        except Exception as exc:
            logging.debug("Semantic query embedding unavailable: %s", exc)
            return []

        threshold = env_float("JARVIS_MEMORY_SIMILARITY", 0.30)
        scored = []
        for row in rows:
            try:
                vector = json.loads(row["embedding"])
                if len(query_vector) != len(vector):
                    continue
                score = sum(a * b for a, b in zip(query_vector, vector))
            except (TypeError, ValueError):
                continue
            if score >= threshold and row["content"].strip().lower() != query.lower():
                scored.append((score, dict(row)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {**row, "score": round(score, 4), "embedding": None}
            for score, row in scored[:limit]
        ]

    def _lexical_search(self, query, limit):
        terms = {
            term
            for term in re.findall(r"[a-z0-9]{3,}", query.lower())
            if term not in {"what", "when", "where", "which", "about", "with"}
        }
        if not terms:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, role, content, kind, created_at "
                "FROM memories ORDER BY id DESC LIMIT 300"
            ).fetchall()
        scored = []
        for row in rows:
            content = row["content"].lower()
            score = sum(term in content for term in terms) / len(terms)
            if score > 0 and content != query.lower():
                scored.append((score, dict(row)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {**row, "score": round(score, 4)}
            for score, row in scored[:limit]
        ]

    def recent(self, limit=20):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, role, content, kind, created_at "
                "FROM memories ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def clear(self):
        with self._write_lock, self._connect() as connection:
            connection.execute("DELETE FROM memories")
        return "Long-term conversational memory was cleared."

    def wait_for_embeddings(self):
        """Wait until queued memories have been embedded (primarily for tests)."""
        self._embedding_queue.join()

    def close(self):
        if not self._running:
            return
        self._running = False
        self._embedding_queue.put(None)
        if threading.current_thread() is not self._worker:
            self._worker.join(timeout=2)

    def _embedding_worker(self):
        while self._running:
            item = self._embedding_queue.get()
            if item is None:
                self._embedding_queue.task_done()
                break
            batch = [item]
            while len(batch) < 16:
                try:
                    extra = self._embedding_queue.get_nowait()
                except queue.Empty:
                    break
                if extra is None:
                    self._running = False
                    self._embedding_queue.task_done()
                    break
                batch.append(extra)
            ids, texts = zip(*batch)
            try:
                if hasattr(self.llm, "embed"):
                    embeddings = self.llm.embed(list(texts))
                    with self._write_lock, self._connect() as connection:
                        for memory_id, vector in zip(ids, embeddings):
                            connection.execute(
                                "UPDATE memories SET embedding = ? WHERE id = ?",
                                (json.dumps(vector, separators=(",", ":")), memory_id),
                            )
            except Exception as exc:
                logging.debug("Background memory embedding failed: %s", exc)
            finally:
                for _ in batch:
                    self._embedding_queue.task_done()

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()
