"""Utility for logging skill usage by the agent.

This module provides a simple mechanism to track when skills from .agent/skills/
are being used during agent interactions.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# Try to import fcntl for file locking (Unix/Linux/Mac)
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Configure logging
LOG_DIR = Path(__file__).parent
SKILL_LOG_FILE = LOG_DIR / "skill_usage.log"
SKILL_LOG_JSON = LOG_DIR / "skill_usage.json"

logger = logging.getLogger(__name__)


def log_skill_usage(skill_name: str, context: str = "", action: str = "") -> None:
    """Log when a skill is being used by the agent.

    Uses file locking to prevent race conditions when multiple processes
    write concurrently.

    Args:
        skill_name: Name of the skill being used (e.g., 'librarian', 'book-lamp-development').
        context: Optional context about why the skill is being used.
        action: Optional description of what action is being taken with the skill.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    log_entry = {
        "timestamp": timestamp,
        "skill": skill_name,
        "context": context,
        "action": action,
    }

    # Write to JSON log (structured data) with file locking
    try:
        # Acquire exclusive lock for reading and writing JSON log
        if HAS_FCNTL:
            # Use fcntl for Unix/Linux/Mac - lock the JSON file directly
            # Open in append mode first to create if it doesn't exist, then lock
            with open(SKILL_LOG_JSON, "a+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    # Seek to beginning to read
                    f.seek(0)
                    content = f.read()

                    # Read existing entries
                    log_entries = []
                    if content.strip():
                        try:
                            log_entries = json.loads(content)
                        except (json.JSONDecodeError, ValueError):
                            log_entries = []

                    # Append new entry
                    log_entries.append(log_entry)

                    # Keep only last 1000 entries to prevent file from growing too large
                    if len(log_entries) > 1000:
                        log_entries = log_entries[-1000:]

                    # Write back (truncate and write)
                    f.seek(0)
                    f.truncate()
                    json.dump(log_entries, f, indent=2, ensure_ascii=False)
                    f.flush()  # Ensure it's written immediately
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            # Fallback for Windows: use atomic write (write to temp, then rename)
            # This is not perfect but better than no synchronization
            log_entries = []
            if SKILL_LOG_JSON.exists():
                try:
                    with open(SKILL_LOG_JSON, "r", encoding="utf-8") as f:
                        log_entries = json.load(f)
                except (json.JSONDecodeError, IOError):
                    log_entries = []

            log_entries.append(log_entry)

            if len(log_entries) > 1000:
                log_entries = log_entries[-1000:]

            # Atomic write: write to temp file, then rename
            temp_file = SKILL_LOG_JSON.with_suffix(".tmp")
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(log_entries, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure written to disk
                temp_file.replace(SKILL_LOG_JSON)
            except IOError as e:
                logger.warning(f"Failed to write skill usage log: {e}")
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except IOError:
                        pass
    except IOError as e:
        logger.warning(f"Failed to acquire lock for skill usage log: {e}")
        # Fallback: try to write without locking (may lose entries in race conditions)
        log_entries = []
        if SKILL_LOG_JSON.exists():
            try:
                with open(SKILL_LOG_JSON, "r", encoding="utf-8") as f:
                    log_entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                log_entries = []
        log_entries.append(log_entry)
        if len(log_entries) > 1000:
            log_entries = log_entries[-1000:]
        try:
            with open(SKILL_LOG_JSON, "w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=2, ensure_ascii=False)
        except IOError as write_error:
            logger.warning(f"Failed to write skill usage log: {write_error}")

    # Write to human-readable log file (append-only, less critical for synchronization)
    context_str = f" | Context: {context}" if context else ""
    action_str = f" | Action: {action}" if action else ""
    log_line = f"[{timestamp}] Skill: {skill_name}{context_str}{action_str}\n"

    try:
        # Use append mode with locking for text log
        if HAS_FCNTL:
            with open(SKILL_LOG_FILE, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(log_line)
                    f.flush()  # Ensure it's written immediately
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            # Windows: just append (append is generally atomic on most filesystems)
            with open(SKILL_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
                f.flush()
    except IOError as e:
        logger.warning(f"Failed to write skill usage log file: {e}")


def get_recent_skill_usage(limit: int = 20) -> list[dict]:
    """Get recent skill usage entries.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of recent log entries, most recent first.
    """
    if not SKILL_LOG_JSON.exists():
        return []

    try:
        with open(SKILL_LOG_JSON, "r", encoding="utf-8") as f:
            log_entries = json.load(f)
        return list(reversed(log_entries[-limit:]))
    except (json.JSONDecodeError, IOError):
        return []


def get_skill_statistics() -> dict:
    """Get statistics about skill usage.

    Returns:
        Dictionary with skill usage counts and other statistics.
    """
    default_stats = {
        "total_uses": 0,
        "by_skill": {},
        "unique_skills": 0,
    }

    if not SKILL_LOG_JSON.exists():
        return default_stats

    try:
        with open(SKILL_LOG_JSON, "r", encoding="utf-8") as f:
            log_entries = json.load(f)
    except (json.JSONDecodeError, IOError):
        return default_stats

    by_skill: dict[str, int] = {}
    for entry in log_entries:
        skill = entry.get("skill", "unknown")
        by_skill[skill] = by_skill.get(skill, 0) + 1

    return {
        "total_uses": len(log_entries),
        "by_skill": by_skill,
        "unique_skills": len(by_skill),
    }
