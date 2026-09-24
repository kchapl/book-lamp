"""Background job queue system for long-running operations.

Supports both in-memory execution for testing and PostgreSQL persistence
for multi-worker production reliability.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from book_lamp.services.storage_factory import is_test_mode

logger = logging.getLogger("book_lamp")


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Represents a background job."""

    id: str
    status: JobStatus
    function_name: str
    created_at: str
    user_id: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0  # 0-100
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialisation."""
        return {
            "id": self.id,
            "status": self.status.value,
            "function_name": self.function_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
        }

    def wait_for_completion(self, timeout: float = 60.0) -> bool:
        """Wait for job to complete (for testing).

        Returns True if job completed, False if timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return True
            time.sleep(0.1)
        return False


class JobQueue:
    """Hybrid JobQueue supporting PostgreSQL persistence and in-memory test fallback."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def _get_pg_pool(self):
        if is_test_mode():
            return None
        try:
            from book_lamp.services.pg_storage import get_pool
            return get_pool()
        except Exception:
            return None

    def create_job(self, function_name: str, user_id: Optional[int] = None) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            function_name=function_name,
            created_at=now_str,
            user_id=user_id,
        )
        with self._lock:
            self.jobs[job_id] = job

        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO jobs (id, user_id, function_name, status, progress, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        [job_id, user_id, function_name, JobStatus.PENDING.value, 0, now_str],
                    )
            except Exception as e:
                logger.warning(f"Failed to persist job {job_id} to database: {e}")

        logger.info(f"Created job {job_id} for {function_name}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID from database or memory cache."""
        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    row = conn.execute(
                        "SELECT * FROM jobs WHERE id = %s", [job_id]
                    ).fetchone()
                    if row:
                        status_str = row.get("status", "pending")
                        status = JobStatus(status_str) if status_str in [s.value for s in JobStatus] else JobStatus.PENDING
                        return Job(
                            id=row["id"],
                            status=status,
                            function_name=row.get("function_name", ""),
                            created_at=str(row.get("created_at") or ""),
                            user_id=row.get("user_id"),
                            started_at=str(row.get("started_at") or "") if row.get("started_at") else None,
                            completed_at=str(row.get("completed_at") or "") if row.get("completed_at") else None,
                            progress=row.get("progress", 0),
                            result=row.get("result"),
                            error=row.get("error"),
                        )
            except Exception as e:
                logger.debug(f"Database lookup for job {job_id} fell back to memory: {e}")

        with self._lock:
            return self.jobs.get(job_id)

    def start_job(self, job_id: str) -> bool:
        """Mark job as running."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = now_str

        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    conn.execute(
                        "UPDATE jobs SET status = %s, started_at = %s WHERE id = %s",
                        [JobStatus.RUNNING.value, now_str, job_id],
                    )
            except Exception as e:
                logger.warning(f"Failed to update start status for job {job_id}: {e}")

        logger.info(f"Started job {job_id}")
        return True

    def update_progress(self, job_id: str, progress: int) -> bool:
        """Update job progress (0-100)."""
        progress = max(0, min(100, progress))
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress

        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    conn.execute(
                        "UPDATE jobs SET progress = %s WHERE id = %s",
                        [progress, job_id],
                    )
            except Exception as e:
                logger.warning(f"Failed to update progress for job {job_id}: {e}")

        return True

    def complete_job(self, job_id: str, result: Optional[str] = None) -> bool:
        """Mark job as completed successfully."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.completed_at = now_str
                job.result = result
                job.progress = 100

        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE jobs SET status = %s, progress = 100, result = %s, completed_at = %s
                        WHERE id = %s
                        """,
                        [JobStatus.COMPLETED.value, result, now_str, job_id],
                    )
            except Exception as e:
                logger.warning(f"Failed to persist completion for job {job_id}: {e}")

        logger.info(f"Completed job {job_id}")
        return True

    def fail_job(self, job_id: str, error: str) -> bool:
        """Mark job as failed."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.completed_at = now_str
                job.error = error

        pool = self._get_pg_pool()
        if pool:
            try:
                with pool.connection() as conn:
                    conn.execute(
                        """
                        UPDATE jobs SET status = %s, error = %s, completed_at = %s
                        WHERE id = %s
                        """,
                        [JobStatus.FAILED.value, error, now_str, job_id],
                    )
            except Exception as e:
                logger.warning(f"Failed to persist failure for job {job_id}: {e}")

        logger.error(f"Failed job {job_id}: {error}")
        return True

    def submit_job(self, function_name: str, task: Callable, *args, **kwargs) -> str:
        """Create a job and run it in a background thread."""
        user_id = kwargs.pop("user_id", None)
        if not user_id and args and isinstance(args[-1], int):
            user_id = args[-1]

        job_id = self.create_job(function_name, user_id=user_id)

        def run_task() -> None:
            try:
                self.start_job(job_id)
                result = task(job_id, *args, **kwargs)
                self.complete_job(job_id, result)
            except Exception as e:
                logger.exception(f"Job {job_id} failed with exception")
                self.fail_job(job_id, str(e))

        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()

        return job_id


# Global job queue instance
_job_queue = JobQueue()


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    return _job_queue
