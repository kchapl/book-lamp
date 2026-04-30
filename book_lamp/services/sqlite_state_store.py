"""Process-local in-memory SQLite state for fast request-time access."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any


class SQLiteStateStore:
    """Tiny key/value state store backed by in-memory SQLite."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.RLock()
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM state WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return default
        return json.loads(row[0])

    def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value)
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                    (key, payload),
                )
