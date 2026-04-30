"""Async Sheets sync wrapper with local in-memory SQLite-backed state."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Optional

from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.sheets_storage import GoogleSheetsStorage
from book_lamp.services.sqlite_state_store import SQLiteStateStore

logger = logging.getLogger(__name__)


class AsyncSQLiteStorage:
    """Serve reads/writes from local state and sync Sheets asynchronously."""

    def __init__(self, sheet_name: str) -> None:
        self.sheet_name = sheet_name
        self._state = SQLiteStateStore()
        self._local = MockStorage(sheet_name=sheet_name)
        self._local.set_authorised(True)
        self._credentials_dict: Optional[dict[str, Any]] = None
        self._spreadsheet_id: Optional[str] = None
        self._bootstrapped = False
        self._bootstrap_lock = threading.Lock()
        self._queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._outbox_lock = threading.RLock()
        self._max_attempts = 5
        self._outbox_seq = int(self._state.get("outbox_seq", 1))
        self._outbox: dict[int, dict[str, Any]] = {}
        self._metrics: dict[str, int] = {"processed": 0, "failed": 0, "retried": 0}
        self._worker = threading.Thread(target=self._sync_worker, daemon=True)
        self._worker.start()
        self._load_state()

    def configure_remote(
        self,
        credentials_dict: Optional[dict[str, Any]],
        spreadsheet_id: Optional[str] = None,
    ) -> None:
        self._credentials_dict = credentials_dict
        if spreadsheet_id:
            self._spreadsheet_id = spreadsheet_id

    @property
    def spreadsheet_id(self) -> Optional[str]:
        return self._spreadsheet_id

    def is_authorised(self) -> bool:
        if not self._credentials_dict:
            return False
        try:
            remote = self._new_remote()
            return remote.is_authorised()
        except Exception:
            return False

    def set_authorised(self, status: bool) -> None:
        self._local.set_authorised(status)

    def prefetch(self, force: bool = False) -> None:
        if force:
            self._bootstrapped = False
        self._ensure_bootstrap_started()

    def _ensure_bootstrap_started(self) -> None:
        if self._bootstrapped:
            return
        if self._bootstrap_lock.acquire(blocking=False):
            t = threading.Thread(target=self._bootstrap_from_remote, daemon=True)
            t.start()

    def _bootstrap_from_remote(self) -> None:
        try:
            if not self._credentials_dict:
                return
            remote = self._new_remote()
            remote.prefetch(force=True)
            self._local.books = list(remote.get_all_books())
            self._local.reading_records = list(remote.get_reading_records())
            self._local.reading_list = list(remote.get_reading_list())
            self._local.recommendations = list(remote.get_recommendations())
            self._local.settings = dict(remote.get_settings())
            self._local.next_book_id = (
                max((b.get("id", 0) for b in self._local.books), default=0) + 1
            )
            self._local.next_record_id = (
                max((r.get("id", 0) for r in self._local.reading_records), default=0)
                + 1
            )
            self._spreadsheet_id = remote.spreadsheet_id
            self._save_state()
            self._bootstrapped = True
            logger.info("AsyncSQLiteStorage bootstrap complete.")
        except Exception:
            logger.exception("AsyncSQLiteStorage bootstrap failed")
        finally:
            self._bootstrap_lock.release()

    def _new_remote(self) -> GoogleSheetsStorage:
        return GoogleSheetsStorage(
            sheet_name=self.sheet_name,
            credentials_dict=self._credentials_dict,
            spreadsheet_id=self._spreadsheet_id,
        )

    def _enqueue(self, op: str, payload: dict[str, Any]) -> None:
        now = time.time()
        with self._outbox_lock:
            outbox_id = self._outbox_seq
            self._outbox_seq += 1
            self._state.set("outbox_seq", self._outbox_seq)
            self._outbox[outbox_id] = {
                "id": outbox_id,
                "op": op,
                "payload": payload,
                "status": "pending",
                "attempts": 0,
                "last_error": None,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            }
            self._save_outbox()
        self._queue.put(("sync", {"outbox_id": outbox_id}))

    def _schedule_retry(self, outbox_id: int, delay_seconds: float) -> None:
        def _requeue() -> None:
            self._queue.put(("sync", {"outbox_id": outbox_id}))

        timer = threading.Timer(delay_seconds, _requeue)
        timer.daemon = True
        timer.start()

    def _sync_worker(self) -> None:
        while True:
            op, payload = self._queue.get()
            current_outbox_id: Optional[int] = None
            try:
                if op != "sync":
                    logger.warning("Unknown queue op type: %s", op)
                    continue
                outbox_id = payload["outbox_id"]
                current_outbox_id = outbox_id
                with self._outbox_lock:
                    entry = self._outbox.get(outbox_id)
                if not entry:
                    continue
                if entry["status"] in {"completed", "failed"}:
                    continue
                now = time.time()
                if entry["next_attempt_at"] > now:
                    self._schedule_retry(outbox_id, entry["next_attempt_at"] - now)
                    continue
                if not self._credentials_dict:
                    with self._outbox_lock:
                        entry["status"] = "pending"
                        entry["next_attempt_at"] = time.time() + 2.0
                        entry["updated_at"] = time.time()
                        self._save_outbox()
                    self._schedule_retry(outbox_id, 2.0)
                    continue

                remote = self._new_remote()
                op = entry["op"]
                payload = entry["payload"]
                if op == "add_book":
                    remote.add_book(**payload)
                elif op == "update_book":
                    remote.update_book(**payload)
                elif op == "delete_book":
                    remote.delete_book(payload["book_id"])
                elif op == "add_reading_record":
                    remote.add_reading_record(**payload)
                elif op == "update_reading_record":
                    remote.update_reading_record(**payload)
                elif op == "delete_reading_record":
                    remote.delete_reading_record(payload["record_id"])
                elif op == "add_to_reading_list":
                    remote.add_to_reading_list(payload["book_id"])
                elif op == "remove_from_reading_list":
                    remote.remove_from_reading_list(payload["book_id"])
                elif op == "update_reading_list_order":
                    remote.update_reading_list_order(payload["book_ids"])
                elif op == "start_reading":
                    remote.start_reading(payload["book_id"])
                elif op == "bulk_import":
                    remote.bulk_import(payload["items"])
                elif op == "save_recommendations":
                    remote.save_recommendations(payload["recommendations"])
                elif op == "update_setting":
                    remote.update_setting(payload["key"], payload["value"])
                else:
                    logger.warning("Unknown async sync op: %s", op)
                    continue
                with self._outbox_lock:
                    entry["status"] = "completed"
                    entry["updated_at"] = time.time()
                    self._metrics["processed"] += 1
                    self._save_outbox()
            except Exception:
                logger.exception("Async sync op failed: %s", op)
                with self._outbox_lock:
                    entry = (
                        self._outbox.get(current_outbox_id)
                        if current_outbox_id
                        else None
                    )
                    if entry:
                        entry["attempts"] += 1
                        entry["last_error"] = "sync_failure"
                        entry["updated_at"] = time.time()
                        if entry["attempts"] >= self._max_attempts:
                            entry["status"] = "failed"
                            self._metrics["failed"] += 1
                        else:
                            entry["status"] = "retrying"
                            backoff = min(60.0, float(2 ** (entry["attempts"] - 1)))
                            entry["next_attempt_at"] = time.time() + backoff
                            self._schedule_retry(entry["id"], backoff)
                            self._metrics["retried"] += 1
                        self._save_outbox()
            finally:
                self._queue.task_done()

    def _load_state(self) -> None:
        self._local.books = self._state.get("books", [])
        self._local.reading_records = self._state.get("reading_records", [])
        self._local.reading_list = self._state.get("reading_list", [])
        self._local.recommendations = self._state.get("recommendations", [])
        self._local.settings = self._state.get("settings", {})
        self._local.next_book_id = self._state.get("next_book_id", 1)
        self._local.next_record_id = self._state.get("next_record_id", 1)
        self._spreadsheet_id = self._state.get("spreadsheet_id", None)
        self._bootstrapped = bool(self._local.books or self._local.reading_records)
        self._outbox = {
            int(item["id"]): item
            for item in self._state.get("outbox", [])
            if "id" in item
        }
        self._metrics = self._state.get(
            "sync_metrics", {"processed": 0, "failed": 0, "retried": 0}
        )

    def _save_state(self) -> None:
        self._state.set("books", self._local.books)
        self._state.set("reading_records", self._local.reading_records)
        self._state.set("reading_list", self._local.reading_list)
        self._state.set("recommendations", self._local.recommendations)
        self._state.set("settings", self._local.settings)
        self._state.set("next_book_id", self._local.next_book_id)
        self._state.set("next_record_id", self._local.next_record_id)
        self._state.set("spreadsheet_id", self._spreadsheet_id)

    def _save_outbox(self) -> None:
        self._state.set("outbox", list(self._outbox.values()))
        self._state.set("sync_metrics", self._metrics)

    def wait_for_idle(self, timeout_seconds: float = 2.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return False

    def get_sync_diagnostics(self) -> dict[str, Any]:
        with self._outbox_lock:
            entries = list(self._outbox.values())
            pending = len(
                [e for e in entries if e["status"] in {"pending", "retrying"}]
            )
            failed = len([e for e in entries if e["status"] == "failed"])
            completed = len([e for e in entries if e["status"] == "completed"])
            return {
                "bootstrapped": self._bootstrapped,
                "spreadsheet_id": self._spreadsheet_id,
                "queue_unfinished_tasks": self._queue.unfinished_tasks,
                "outbox": {
                    "total": len(entries),
                    "pending": pending,
                    "failed": failed,
                    "completed": completed,
                },
                "metrics": dict(self._metrics),
                "recent_failures": [
                    {
                        "id": e["id"],
                        "op": e["op"],
                        "attempts": e["attempts"],
                        "last_error": e["last_error"],
                    }
                    for e in entries
                    if e["status"] == "failed"
                ][:10],
            }

    # --- read operations ---
    def get_all_books(self) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_all_books()

    def get_reading_records(
        self, book_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_reading_records(book_id=book_id)

    def get_book_by_id(self, book_id: int) -> Optional[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_book_by_id(book_id)

    def get_book_by_isbn(self, isbn13: str) -> Optional[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_book_by_isbn(isbn13)

    def get_reading_list(self) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_reading_list()

    def get_reading_history(self) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_reading_history()

    def get_settings(self) -> dict[str, str]:
        self._ensure_bootstrap_started()
        return self._local.get_settings()

    def get_recommendations(self) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.get_recommendations()

    def search(self, query: str) -> list[dict[str, Any]]:
        self._ensure_bootstrap_started()
        return self._local.search(query)

    # --- write operations ---
    def add_book(self, **kwargs: Any) -> dict[str, Any]:
        out = self._local.add_book(**kwargs)
        self._save_state()
        self._enqueue("add_book", kwargs)
        return out

    def update_book(self, **kwargs: Any) -> dict[str, Any]:
        out = self._local.update_book(**kwargs)
        self._save_state()
        self._enqueue("update_book", kwargs)
        return out

    def delete_book(self, book_id: int) -> bool:
        out = self._local.delete_book(book_id)
        self._save_state()
        self._enqueue("delete_book", {"book_id": book_id})
        return out

    def add_reading_record(self, **kwargs: Any) -> dict[str, Any]:
        out = self._local.add_reading_record(**kwargs)
        self._save_state()
        self._enqueue("add_reading_record", kwargs)
        return out

    def update_reading_record(self, **kwargs: Any) -> dict[str, Any]:
        out = self._local.update_reading_record(**kwargs)
        self._save_state()
        self._enqueue("update_reading_record", kwargs)
        return out

    def delete_reading_record(self, record_id: int) -> bool:
        out = self._local.delete_reading_record(record_id)
        self._save_state()
        self._enqueue("delete_reading_record", {"record_id": record_id})
        return out

    def add_to_reading_list(self, book_id: int) -> None:
        self._local.add_to_reading_list(book_id)
        self._save_state()
        self._enqueue("add_to_reading_list", {"book_id": book_id})

    def remove_from_reading_list(self, book_id: int) -> None:
        self._local.remove_from_reading_list(book_id)
        self._save_state()
        self._enqueue("remove_from_reading_list", {"book_id": book_id})

    def update_reading_list_order(self, book_ids: list[int]) -> None:
        self._local.update_reading_list_order(book_ids)
        self._save_state()
        self._enqueue("update_reading_list_order", {"book_ids": book_ids})

    def start_reading(self, book_id: int) -> None:
        self._local.start_reading(book_id)
        self._save_state()
        self._enqueue("start_reading", {"book_id": book_id})

    def bulk_import(self, items: list[dict[str, Any]]) -> int:
        out = self._local.bulk_import(items)
        self._save_state()
        self._enqueue("bulk_import", {"items": items})
        return out

    def save_recommendations(self, recommendations: list[dict[str, Any]]) -> None:
        self._local.save_recommendations(recommendations)
        self._save_state()
        self._enqueue("save_recommendations", {"recommendations": recommendations})

    def update_setting(self, key: str, value: str) -> None:
        self._local.update_setting(key, value)
        self._save_state()
        self._enqueue("update_setting", {"key": key, "value": value})
