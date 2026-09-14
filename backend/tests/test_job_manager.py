"""Tests for job manager lifecycle and TTL expiration."""

import asyncio
import time
import pytest
from app.core.job_manager import JobManager, JobStatus


@pytest.fixture
def manager():
    return JobManager()


@pytest.mark.asyncio
async def test_create_job_returns_job(manager, tmp_path):
    """Creating a job should return a Job with CREATED status."""
    from app.core.config import settings
    original = settings.temp_dir
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    assert job.id.startswith("job_")
    assert job.status == JobStatus.CREATED
    assert job.temp_dir is not None
    assert job.temp_dir.exists()

    settings.temp_dir = original


@pytest.mark.asyncio
async def test_get_job_returns_existing(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    retrieved = await manager.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id


@pytest.mark.asyncio
async def test_get_job_nonexistent_returns_none(manager):
    result = await manager.get_job("job_doesnotexist")
    assert result is None


@pytest.mark.asyncio
async def test_update_job_status(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    updated = await manager.update_job(job.id, status=JobStatus.EXTRACTING)
    assert updated is not None
    assert updated.status == JobStatus.EXTRACTING


@pytest.mark.asyncio
async def test_update_job_post_data(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    data = {"id": "123", "text": "hello"}
    updated = await manager.update_job(job.id, post_data=data)
    assert updated.post_data == data


@pytest.mark.asyncio
async def test_expired_job_not_returned(manager, tmp_path):
    """Expired jobs should not be returned by get_job."""
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    # Manually expire the job by setting created_at in the past
    job.created_at = time.time() - (settings.job_ttl_seconds + 10)

    result = await manager.get_job(job.id)
    assert result is None


@pytest.mark.asyncio
async def test_cleanup_expired_removes_jobs(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    job.created_at = time.time() - (settings.job_ttl_seconds + 10)

    cleaned = await manager.cleanup_expired()
    assert cleaned == 1


@pytest.mark.asyncio
async def test_add_asset_to_job(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()

    # Create a fake file
    fake_file = job.temp_dir / "test.png"
    fake_file.write_bytes(b"PNG_CONTENT")

    asset = job.add_asset("tweet_card", "tweet.png", "image/png", fake_file)
    assert asset.id == "tweet_card"
    assert asset.size == 11  # len("PNG_CONTENT")
    assert "tweet_card" in job.assets


@pytest.mark.asyncio
async def test_get_stats(manager, tmp_path):
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    await manager.create_job()
    await manager.create_job()
    stats = await manager.get_stats()
    assert stats["total_jobs"] >= 2
    assert stats["active_jobs"] >= 2
