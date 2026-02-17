"""Background job queue system for long-running operations."""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

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
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0  # 0-100
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
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
    """Simple in-memory job queue with file-based persistence."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, function_name: str) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            function_name=function_name,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self.jobs[job_id] = job
        logger.info(f"Created job {job_id} for {function_name}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._lock:
            return self.jobs.get(job_id)

    def start_job(self, job_id: str) -> bool:
        """Mark job as running."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(timezone.utc).isoformat()
                logger.info(f"Started job {job_id}")
                return True
        return False

    def update_progress(self, job_id: str, progress: int) -> bool:
        """Update job progress (0-100)."""
        progress = max(0, min(100, progress))
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress
                return True
        return False

    def complete_job(self, job_id: str, result: Optional[str] = None) -> bool:
        """Mark job as completed successfully."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.result = result
                job.progress = 100
                logger.info(f"Completed job {job_id}")
                return True
        return False

    def fail_job(self, job_id: str, error: str) -> bool:
        """Mark job as failed."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.error = error
                logger.error(f"Failed job {job_id}: {error}")
                return True
        return False

    def submit_job(self, function_name: str, task: Callable, *args, **kwargs) -> str:
        """Create a job and run it in a background thread.

        Returns the job ID immediately.
        """
        job_id = self.create_job(function_name)

        def run_task() -> None:
            try:
                self.start_job(job_id)
                result = task(job_id, *args, **kwargs)
                self.complete_job(job_id, result)
            except Exception as e:
                logger.exception(f"Job {job_id} failed with exception")
                self.fail_job(job_id, str(e))

        # Start in background thread (daemon=True so it doesn't prevent app shutdown)
        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()

        return job_id


# Global job queue instance
_job_queue = JobQueue()


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    return _job_queue
