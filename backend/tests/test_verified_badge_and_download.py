"""Regression tests for:
1. Verified blue badge rendering (conditional, data-driven).
2. Immediate video download preparation and streaming endpoint.
3. 150 MB hard limit enforcement with MediaTooLargeError / HTTP 413.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

import main
from app.core.config import MAX_VIDEO_SIZE_BYTES, settings
from app.core.job_manager import JobManager
from app.extractors.base import MediaTooLargeError
from app.models.post import MediaItem, PostData, QuotedPostData
from app.models.requests import RenderRequest
from app.renderers.playwright_renderer import _build_context, _jinja_env
from app.services.download_service import download_media_item


# ── Bug 1: Verified Badge Regression Tests ────────────────────────────────────

def test_verified_badge_rendered_when_verified_is_true():
    """Verified account must have the blue badge rendered next to the display name."""
    post = PostData(
        id="12345",
        url="https://x.com/verified_user/status/12345",
        author_name="Verified Account",
        author_handle="verified_user",
        is_verified=True,
        text="Hello world",
    )
    req = RenderRequest(job_id="test_job")
    context = _build_context(post, req)
    assert context["author_verified"] is True

    template = _jinja_env.get_template("tweet_card.html")
    html = template.render(**context)
    assert '<svg class="verified-badge"' in html
    assert 'aria-label="Verified account"' in html
    assert "#1d9bf0" in html


def test_verified_badge_not_rendered_when_verified_is_false():
    """Non-verified account must NOT show the verified badge SVG."""
    post = PostData(
        id="12346",
        url="https://x.com/regular_user/status/12346",
        author_name="Regular Account",
        author_handle="regular_user",
        is_verified=False,
        text="Hello world",
    )
    req = RenderRequest(job_id="test_job")
    context = _build_context(post, req)
    assert context["author_verified"] is False

    template = _jinja_env.get_template("tweet_card.html")
    html = template.render(**context)
    assert '<svg class="verified-badge"' not in html
    assert 'aria-label="Verified account"' not in html


def test_quoted_post_verified_badge_rendered_conditionally():
    """Quoted post author shows verified badge only if author is verified."""
    quoted_verified = QuotedPostData(
        id="99901",
        author_name="Quoted Verified",
        author_handle="quoted_ver",
        author_verified=True,
        text="Quoted text",
    )
    post_with_verified_quote = PostData(
        id="12347",
        url="https://x.com/user/status/12347",
        author_name="User",
        author_handle="user",
        is_verified=False,
        quoted_post=quoted_verified,
    )
    req = RenderRequest(job_id="test_job")
    ctx_verified = _build_context(post_with_verified_quote, req)
    assert ctx_verified["quoted"]["author_verified"] is True
    html_verified = _jinja_env.get_template("tweet_card.html").render(**ctx_verified)
    assert '<svg class="verified-badge verified-badge-sm"' in html_verified

    # Non-verified quote
    quoted_unverified = QuotedPostData(
        id="99902",
        author_name="Quoted Regular",
        author_handle="quoted_reg",
        author_verified=False,
        text="Quoted text",
    )
    post_with_unverified_quote = PostData(
        id="12348",
        url="https://x.com/user/status/12348",
        author_name="User",
        author_handle="user",
        is_verified=False,
        quoted_post=quoted_unverified,
    )
    ctx_unverified = _build_context(post_with_unverified_quote, req)
    assert ctx_unverified["quoted"]["author_verified"] is False
    html_unverified = _jinja_env.get_template("tweet_card.html").render(**ctx_unverified)
    assert '<svg class="verified-badge verified-badge-sm"' not in html_unverified


# ── Bug 2 & 3: 150 MB Limit & Immediate Download Tests ────────────────────────

@pytest.mark.asyncio
async def test_download_media_item_rejects_content_length_over_150mb(tmp_path):
    """If Content-Length header > 150 MB, download is rejected immediately with MediaTooLargeError."""
    manager = JobManager()
    settings.temp_dir = str(tmp_path)
    job = await manager.create_job()
    item = MediaItem(type="video", url="https://video.twimg.com/oversized.mp4")

    oversized_bytes = MAX_VIDEO_SIZE_BYTES + 1024  # 150 MB + 1 KB

    class MockStreamResponse:
        status_code = 200
        headers = {"content-type": "video/mp4", "content-length": str(oversized_bytes)}

        async def aiter_bytes(self, chunk_size=65536):
            yield b"never reached"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_client = MagicMock()
    mock_client.stream.return_value = MockStreamResponse()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(MediaTooLargeError) as exc_info:
            await download_media_item(job, item, "media_video_0", "oversized")
        assert "150 MB" in str(exc_info.value)


@pytest.mark.asyncio
async def test_download_media_item_rejects_streaming_over_150mb(tmp_path):
    """If Content-Length is missing but bytes received exceed 150 MB, download halts cleanly."""
    manager = JobManager()
    settings.temp_dir = str(tmp_path)
    job = await manager.create_job()
    item = MediaItem(type="video", url="https://video.twimg.com/chunked_large.mp4")

    class MockChunkedResponse:
        status_code = 200
        headers = {"content-type": "video/mp4"}  # No Content-Length

        async def aiter_bytes(self, chunk_size=1048576):
            # Yield chunks that exceed 150 MB
            chunk = b"0" * (10 * 1024 * 1024)  # 10 MB per chunk
            for _ in range(16):  # 160 MB total
                yield chunk

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_client = MagicMock()
    mock_client.stream.return_value = MockChunkedResponse()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(MediaTooLargeError) as exc_info:
            await download_media_item(job, item, "media_video_0", "chunked_large")
        assert "150 MB" in str(exc_info.value)
        # Ensure temporary file was cleaned up and not left corrupted
        assert not (job.temp_dir / "chunked_large.mp4.tmp").exists()
        assert not (job.temp_dir / "chunked_large.mp4").exists()


@pytest.mark.asyncio
async def test_download_media_item_under_150mb_succeeds(tmp_path):
    """Videos <= 150 MB download and register as assets atomically."""
    manager = JobManager()
    settings.temp_dir = str(tmp_path)
    job = await manager.create_job()
    item = MediaItem(type="video", url="https://video.twimg.com/valid.mp4")

    valid_size = 5 * 1024 * 1024  # 5 MB
    payload = b"V" * valid_size

    class MockValidResponse:
        status_code = 200
        headers = {"content-type": "video/mp4", "content-length": str(valid_size)}

        async def aiter_bytes(self, chunk_size=1048576):
            yield payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    mock_client = MagicMock()
    mock_client.stream.return_value = MockValidResponse()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        asset_id = await download_media_item(job, item, "media_video_0", "valid_video")
        assert asset_id == "media_video_0"
        asset = job.assets["media_video_0"]
        assert asset.file_path.exists()
        assert asset.file_path.stat().st_size == valid_size


def test_api_download_prepare_and_streaming_endpoints():
    """Test POST /download/prepare and GET /download/{job_id}/media/{media_index}."""
    client = TestClient(main.app)

    post = PostData(
        id="123456789",
        url="https://x.com/testuser/status/123456789",
        author_name="Test User",
        author_handle="testuser",
        media=[
            MediaItem(type="video", url="https://video.twimg.com/vid.mp4", duration=15.0)
        ],
    )

    with patch("app.extractors.manager.extraction_manager.extract", return_value=post):
        ext_resp = client.post("/api/extract", json={"url": "https://x.com/testuser/status/123456789"})
        assert ext_resp.status_code == 200
        job_id = ext_resp.json()["job_id"]

    # Test /download/prepare with mock download
    with patch("app.api.routes.download_media_item") as mock_dl:
        async def fake_dl(job, item, asset_id, filename_base):
            file_path = job.temp_dir / f"{filename_base}.mp4"
            file_path.write_bytes(b"TEST_VIDEO_DATA")
            job.add_asset(asset_id, f"{filename_base}.mp4", "video/mp4", file_path)
            return asset_id

        mock_dl.side_effect = fake_dl

        # 1. POST /download/prepare returns download metadata
        prep_resp = client.post("/api/download/prepare", json={"job_id": job_id, "media_index": 0})
        assert prep_resp.status_code == 200
        data = prep_resp.json()
        assert data["status"] == "ready"
        assert "download_url" in data
        assert "filename" in data
        assert data["filename"].endswith(".mp4")

        # 2. GET /download/{job_id}/media/{media_index} returns actual file directly
        get_resp = client.get(f"/api/download/{job_id}/media/0")
        assert get_resp.status_code == 200
        assert get_resp.content == b"TEST_VIDEO_DATA"
        assert "video/mp4" in get_resp.headers["content-type"]


def test_api_download_over_150mb_returns_413():
    """Test that downloading media > 150 MB returns HTTP 413 with clear error."""
    client = TestClient(main.app)

    post = PostData(
        id="123456780",
        url="https://x.com/testuser/status/123456780",
        author_name="Test User",
        author_handle="testuser",
        media=[
            MediaItem(type="video", url="https://video.twimg.com/too_big.mp4")
        ],
    )

    with patch("app.extractors.manager.extraction_manager.extract", return_value=post):
        ext_resp = client.post("/api/extract", json={"url": "https://x.com/testuser/status/123456780"})
        assert ext_resp.status_code == 200
        job_id = ext_resp.json()["job_id"]

    with patch("app.api.routes.download_media_item", side_effect=MediaTooLargeError("Video exceeds the 150 MB download limit.")):
        # Test POST /download/prepare
        resp_prepare = client.post("/api/download/prepare", json={"job_id": job_id, "media_index": 0})
        assert resp_prepare.status_code == 413
        assert resp_prepare.json()["detail"] == "Video exceeds the 150 MB download limit."

        # Test POST /download
        resp_dl = client.post("/api/download", json={"job_id": job_id, "media_index": 0})
        assert resp_dl.status_code == 413
        assert resp_dl.json()["detail"] == "Video exceeds the 150 MB download limit."
