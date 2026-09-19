"""Tests for download service — ZIP building and filename sanitization."""

import asyncio
import zipfile
from pathlib import Path
import pytest

from app.core.job_manager import JobManager, JobStatus
from app.services.download_service import build_zip, ZIP_ASSET_ID
from app.models.post import PostData, MediaItem


def make_post(**kwargs) -> PostData:
    defaults = dict(
        id="123456",
        url="https://x.com/testuser/status/123456",
        author_name="Test User",
        author_handle="testuser",
        avatar_url=None,
        text="hello world",
        created_at=None,
        media=[],
    )
    defaults.update(kwargs)
    return PostData(**defaults)


@pytest.fixture
def manager():
    return JobManager()


@pytest.mark.asyncio
async def test_build_zip_with_assets(manager, tmp_path):
    """ZIP should contain all registered assets."""
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    post = make_post()

    # Add a fake tweet card asset
    card_path = job.temp_dir / "testuser_123456_tweet.png"
    card_path.write_bytes(b"FAKE_PNG_DATA")
    job.add_asset("tweet_card", "testuser_123456_tweet.png", "image/png", card_path)

    zip_asset_id = await build_zip(job, post)
    assert zip_asset_id == ZIP_ASSET_ID

    zip_asset = job.assets[ZIP_ASSET_ID]
    assert zip_asset.file_path is not None
    assert zip_asset.file_path.exists()

    # Verify ZIP contents
    with zipfile.ZipFile(zip_asset.file_path, "r") as zf:
        names = zf.namelist()
        assert any("tweet" in n for n in names)


@pytest.mark.asyncio
async def test_build_zip_empty_assets(manager, tmp_path):
    """ZIP should return None when no assets exist."""
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    post = make_post()

    result = await build_zip(job, post)
    assert result is None


@pytest.mark.asyncio
async def test_build_zip_excludes_zip_itself(manager, tmp_path):
    """The ZIP asset should not recursively contain itself."""
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    post = make_post()

    card_path = job.temp_dir / "tweet.png"
    card_path.write_bytes(b"FAKE")
    job.add_asset("tweet_card", "tweet.png", "image/png", card_path)

    await build_zip(job, post)
    # Build again — should not include the first ZIP in the second one
    await build_zip(job, post)

    zip_asset = job.assets[ZIP_ASSET_ID]
    with zipfile.ZipFile(zip_asset.file_path, "r") as zf:
        names = zf.namelist()
        zip_files = [n for n in names if n.endswith(".zip")]
        assert len(zip_files) == 0


@pytest.mark.asyncio
async def test_zip_filename_uses_handle_and_id(manager, tmp_path):
    """ZIP filename should follow pattern handle_postid.zip."""
    from app.core.config import settings
    settings.temp_dir = str(tmp_path)

    job = await manager.create_job()
    post = make_post(author_handle="myuser", id="9999")

    card_path = job.temp_dir / "myuser_9999_tweet.png"
    card_path.write_bytes(b"x")
    job.add_asset("tweet_card", "myuser_9999_tweet.png", "image/png", card_path)

    await build_zip(job, post)

    zip_asset = job.assets[ZIP_ASSET_ID]
    assert zip_asset.filename == "myuser_9999.zip"


@pytest.mark.asyncio
async def test_extract_thumbnail_ffmpeg(tmp_path):
    """FFmpeg should extract an authentic poster frame from a video."""
    from app.services.download_service import extract_thumbnail_ffmpeg
    from tests.fixtures import FIXTURES_DIR

    sample_mp4 = FIXTURES_DIR / "sample.mp4"
    assert sample_mp4.exists()
    poster_path = tmp_path / "poster.jpg"
    ok = await extract_thumbnail_ffmpeg(sample_mp4, poster_path)
    assert ok is True
    assert poster_path.exists()
    assert poster_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_download_media_item_cached_reuse(manager, tmp_path):
    """Already downloaded media asset should be reused without re-downloading."""
    from app.core.config import settings
    from app.services.download_service import download_media_item

    settings.temp_dir = str(tmp_path)
    job = await manager.create_job()
    file_path = job.temp_dir / "test_video.mp4"
    file_path.write_bytes(b"EXISTING_VIDEO_DATA")
    job.add_asset("media_video_0", "test_video.mp4", "video/mp4", file_path)

    item = MediaItem(type="video", url="https://video.twimg.com/test.mp4")
    result_id = await download_media_item(job, item, "media_video_0", "test_video")

    assert result_id == "media_video_0"
    assert file_path.read_bytes() == b"EXISTING_VIDEO_DATA"


@pytest.mark.asyncio
async def test_download_media_item_completeness_check(manager, tmp_path):
    """Download should be rejected if Content-Length mismatches actual downloaded bytes."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from app.core.config import settings
    from app.services.download_service import download_media_item

    settings.temp_dir = str(tmp_path)
    job = await manager.create_job()
    item = MediaItem(type="image", url="https://pbs.twimg.com/media/test.jpg")

    class MockStreamResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg", "content-length": "1000"}

        async def aiter_bytes(self, chunk_size=65536):
            # Only yield 500 bytes instead of expected 1000
            yield b"x" * 500

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_client = MagicMock()
    mock_client.stream.return_value = MockStreamResponse()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result_id = await download_media_item(job, item, "media_image_0", "test_image")
        assert result_id is None
        # Verify temporary file is not left around
        assert not (job.temp_dir / "test_image.jpg").exists()
        assert not (job.temp_dir / "test_image.jpg.tmp").exists()


