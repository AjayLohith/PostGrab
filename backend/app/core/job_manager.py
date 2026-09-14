"""In-memory job manager with TTL-based expiration and temp file cleanup."""

import uuid
import time
import shutil
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job lifecycle status."""
    CREATED = "created"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    RENDERING = "rendering"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class JobAsset:
    """A downloadable asset within a job."""
    id: str
    filename: str
    content_type: str
    file_path: Path | None = None
    size: int = 0


@dataclass
class Job:
    """Represents a processing job with metadata and temp file tracking."""
    id: str
    status: JobStatus
    created_at: float
    post_data: dict | None = None
    assets: dict[str, JobAsset] = field(default_factory=dict)
    error: str | None = None
    temp_dir: Path | None = None

    @property
    def is_expired(self) -> bool:
        """Check if this job has exceeded its TTL."""
        return (time.time() - self.created_at) > settings.job_ttl_seconds

    def add_asset(self, asset_id: str, filename: str, content_type: str, file_path: Path) -> JobAsset:
        """Register a downloadable asset."""
        asset = JobAsset(
            id=asset_id,
            filename=filename,
            content_type=content_type,
            file_path=file_path,
            size=file_path.stat().st_size if file_path.exists() else 0,
        )
        self.assets[asset_id] = asset
        return asset


class JobManager:
    """
    Manages job lifecycle: creation, lookup, expiration, and cleanup.

    All state is in-memory. No database required.
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def _generate_id(self) -> str:
        """Generate a short, unique job ID."""
        return f"job_{uuid.uuid4().hex[:8]}"

    async def create_job(self) -> Job:
        """Create a new job with a temp directory."""
        job_id = self._generate_id()
        temp_dir = settings.temp_path / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        job = Job(
            id=job_id,
            status=JobStatus.CREATED,
            created_at=time.time(),
            temp_dir=temp_dir,
        )

        async with self._lock:
            self._jobs[job_id] = job

        logger.info("Created job %s with temp dir %s", job_id, temp_dir)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID. Returns None if not found or expired."""
        async with self._lock:
            job = self._jobs.get(job_id)

        if job is None:
            return None

        if job.is_expired:
            await self._cleanup_job(job_id)
            return None

        return job

    async def update_job(
        self,
        job_id: str,
        status: JobStatus | None = None,
        post_data: dict | None = None,
        error: str | None = None,
    ) -> Job | None:
        """Update a job's status and/or data."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            if status is not None:
                job.status = status
            if post_data is not None:
                job.post_data = post_data
            if error is not None:
                job.error = error

            return job

    async def _cleanup_job(self, job_id: str) -> None:
        """Remove a job and its temp directory."""
        async with self._lock:
            job = self._jobs.pop(job_id, None)

        if job and job.temp_dir and job.temp_dir.exists():
            try:
                shutil.rmtree(job.temp_dir)
                logger.info("Cleaned up job %s temp dir", job_id)
            except Exception as e:
                logger.error("Failed to clean up job %s: %s", job_id, e)

    async def cleanup_expired(self) -> int:
        """Clean up all expired jobs. Returns count of cleaned jobs."""
        async with self._lock:
            expired_ids = [
                job_id for job_id, job in self._jobs.items()
                if job.is_expired
            ]

        cleaned = 0
        for job_id in expired_ids:
            await self._cleanup_job(job_id)
            cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up %d expired jobs", cleaned)

        return cleaned

    async def start_cleanup_loop(self) -> None:
        """Start periodic cleanup of expired jobs."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background loop that periodically cleans expired jobs."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error: %s", e)

    async def stop_cleanup_loop(self) -> None:
        """Stop the periodic cleanup loop."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get_stats(self) -> dict:
        """Get job manager statistics for health checks."""
        async with self._lock:
            total = len(self._jobs)
            active = sum(1 for j in self._jobs.values() if not j.is_expired)
            expired = total - active

        return {
            "total_jobs": total,
            "active_jobs": active,
            "expired_jobs": expired,
        }


# Global job manager instance
job_manager = JobManager()
