import json
import logging
import os
import sqlite3
import time
from typing import Any, Optional, Union

logger = logging.getLogger("book_lamp.cache")


class SQLiteCache:
    """A simple persistent cache using SQLite.

    Designed to store API responses to reduce network calls and stay within quotas.
    """

    def __init__(self, db_path: Optional[str] = None, default_ttl: int = 86400 * 30):
        """Initialise the cache.

        Args:
            db_path: Path to the SQLite database. Defaults to .cache/api_cache.db in the project root.
            default_ttl: Default time-to-live in seconds (default 30 days).
        """
        if db_path is None:
            # Default to a .cache folder in the project root (where app.py is usually run from)
            base_dir = os.getcwd()
            db_path = os.path.join(base_dir, ".cache", "api_cache.db")

        self.db_path = db_path
        self.default_ttl = default_ttl
        self._init_db()

    def _init_db(self):
        """Create the cache table if it doesn't exist."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expiry INTEGER)"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expiry ON cache (expiry)")
        except Exception as e:
            logger.error(f"Failed to initialise SQLite cache at {self.db_path}: {e}")

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache.

        Returns None if the key is not found or has expired.
        """
        now = int(time.time())
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT value FROM cache WHERE key = ? AND expiry > ?", (key, now)
                ).fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Cache miss or error for key {key}: {e}")
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Store a value in the cache with a TTL."""
        ttl = ttl if ttl is not None else self.default_ttl
        expiry = int(time.time()) + ttl
        try:
            value_json = json.dumps(value)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expiry) VALUES (?, ?, ?)",
                    (key, value_json, expiry),
                )
        except Exception as e:
            logger.error(f"Failed to store value in cache for key {key}: {e}")

    def delete(self, key: str):
        """Delete a single key from the cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        except Exception as e:
            logger.error(f"Failed to delete key {key} from cache: {e}")

    def cleanup(self):
        """Remove expired entries from the cache."""
        now = int(time.time())
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM cache WHERE expiry <= ?", (now,))
                logger.info(f"Cleaned up {cursor.rowcount} expired cache entries")
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")


# Singleton instance for the application
_cache_instance: Optional[SQLiteCache] = None


class NoOpCache:
    """A cache implementation that does nothing. Used in test mode."""

    def get(self, key: str) -> Optional[Any]:
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        pass

    def delete(self, key: str):
        pass

    def cleanup(self):
        pass


def get_cache() -> Union[SQLiteCache, NoOpCache]:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        # Disable cache in test mode to avoid cross-test contamination
        if os.environ.get("TEST_MODE") == "1":
            return NoOpCache()
        _cache_instance = SQLiteCache()
    return _cache_instance
