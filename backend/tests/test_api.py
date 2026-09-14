"""Integration tests for FastAPI routes using mocked extractors."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

# Import app after patching
from app.models.post import PostData, MediaItem
from app.extractors.base import PostNotFoundError, ExtractionError


def make_post_data(**kwargs) -> PostData:
    defaults = dict(
        id="1234567890",
        url="https://x.com/testuser/status/1234567890",
        author_name="Test User",
        author_handle="testuser",
        avatar_url=None,
        text="Hello world! This is a test post.",
        created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        reply_count=5,
        repost_count=10,
        like_count=50,
        view_count=1000,
        media=[],
    )
    defaults.update(kwargs)
    return PostData(**defaults)


@pytest.fixture
def client():
    """Create test client with mocked extraction."""
    import main
    from app.core.rate_limiter import rate_limiter
    rate_limiter.reset()
    return TestClient(main.app, raise_server_exceptions=False)


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ── Extract ───────────────────────────────────────────────────────────────────

class TestExtract:
    def test_invalid_url_returns_422(self, client):
        resp = client.post("/api/extract", json={"url": "not-a-url"})
        assert resp.status_code == 422

    def test_non_x_url_returns_422(self, client):
        resp = client.post("/api/extract", json={"url": "https://youtube.com/watch?v=abc"})
        assert resp.status_code == 422

    def test_empty_url_returns_422(self, client):
        resp = client.post("/api/extract", json={"url": ""})
        assert resp.status_code == 422

    def test_missing_url_field_returns_422(self, client):
        resp = client.post("/api/extract", json={})
        assert resp.status_code == 422

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_successful_extraction(self, mock_extract, client):
        mock_extract.return_value = make_post_data()

        resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["post"]["author_handle"] == "testuser"
        assert data["post"]["text"] == "Hello world! This is a test post."
        assert "capabilities" in data

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_post_not_found_returns_404(self, mock_extract, client):
        mock_extract.side_effect = PostNotFoundError()

        resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/deleted/status/9999999999"},
        )
        assert resp.status_code == 404

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_extraction_error_returns_502(self, mock_extract, client):
        mock_extract.side_effect = ExtractionError("Service unavailable", recoverable=True)

        resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        assert resp.status_code == 502

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_capabilities_video_post(self, mock_extract, client):
        post = make_post_data(
            media=[
                MediaItem(
                    type="video",
                    url="https://video.twimg.com/ext_tw_video/123/vid/abc.mp4",
                    width=1280,
                    height=720,
                    duration=30.0,
                    mime_type="video/mp4",
                )
            ]
        )
        mock_extract.return_value = post

        resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        assert resp.status_code == 200
        caps = resp.json()["capabilities"]
        assert caps["video"] is True
        assert caps["download_all"] is True

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_capabilities_text_only_post(self, mock_extract, client):
        post = make_post_data(media=[])
        mock_extract.return_value = post

        resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        caps = resp.json()["capabilities"]
        assert caps["video"] is False
        assert caps["images"] is False
        assert caps["tweet_image"] is True
        assert caps["download_all"] is False


# ── Render ────────────────────────────────────────────────────────────────────

class TestRender:
    def test_render_invalid_job_returns_404(self, client):
        resp = client.post(
            "/api/render",
            json={"job_id": "job_doesnotexist"},
        )
        assert resp.status_code == 404

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_render_after_extract(self, mock_extract, client):
        mock_extract.return_value = make_post_data()

        # Extract first
        extract_resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        assert extract_resp.status_code == 200
        job_id = extract_resp.json()["job_id"]

        # Then render
        render_resp = client.post(
            "/api/render",
            json={"job_id": job_id, "theme": "dark", "background": "gradient"},
        )
        assert render_resp.status_code == 200
        data = render_resp.json()
        assert data["job_id"] == job_id
        assert data["asset_id"] == "tweet_card"
        assert data["filename"].endswith(".png")
        assert data["size"] > 0


# ── Download ──────────────────────────────────────────────────────────────────

class TestDownload:
    def test_download_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/download/job_nonexistent/tweet_card")
        assert resp.status_code == 404

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_download_tweet_card_after_render(self, mock_extract, client):
        mock_extract.return_value = make_post_data()

        # Extract
        extract_resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        job_id = extract_resp.json()["job_id"]

        # Render
        client.post("/api/render", json={"job_id": job_id})

        # Download
        dl_resp = client.get(f"/api/download/{job_id}/tweet_card")
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "image/png"
        # Should be valid PNG
        assert dl_resp.content[:4] == b"\x89PNG"

    def test_download_nonexistent_asset_returns_404(self, client):
        # First create a job via extraction
        with patch("app.extractors.manager.extraction_manager.extract") as mock_extract:
            mock_extract.return_value = make_post_data()
            resp = client.post(
                "/api/extract",
                json={"url": "https://x.com/testuser/status/1234567890"},
            )
            job_id = resp.json()["job_id"]

        # Try to download non-existent asset
        dl_resp = client.get(f"/api/download/{job_id}/nonexistent_asset")
        assert dl_resp.status_code == 404


# ── Job status ────────────────────────────────────────────────────────────────

class TestJobStatus:
    def test_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/job/job_nonexistent")
        assert resp.status_code == 404

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_job_status_after_extract(self, mock_extract, client):
        mock_extract.return_value = make_post_data()

        extract_resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        job_id = extract_resp.json()["job_id"]

        status_resp = client.get(f"/api/job/{job_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["job_id"] == job_id
        assert data["status"] == "extracted"

    @patch("app.extractors.manager.extraction_manager.extract")
    def test_quoted_video_sets_capabilities_and_allows_download(self, mock_extract, client):
        from app.models.post import MediaItem, MediaVariant, QuotedPostData
        q_video = MediaItem(
            type="video",
            url="https://video.twimg.com/ext_tw_video/123/pu/vid/1280x720/test.mp4",
            thumbnail_url="https://pbs.twimg.com/media/thumb.jpg",
            variants=[
                MediaVariant(url="https://video.twimg.com/test_720p.mp4", quality_label="720p", height=720)
            ],
        )
        post = make_post_data()
        post.media = []  # Root tweet has no video
        post.quoted_post = QuotedPostData(
            id="999888777",
            author_name="Quoted Author",
            author_handle="quoted_user",
            text="Quoted text with video",
            media=[q_video],
        )
        mock_extract.return_value = post

        extract_resp = client.post(
            "/api/extract",
            json={"url": "https://x.com/testuser/status/1234567890"},
        )
        assert extract_resp.status_code == 200
        data = extract_resp.json()
        assert len(data["post"]["media"]) == 0
        assert data["capabilities"]["video"] is True
        assert len(data["capabilities"]["video_qualities"]) == 1
        assert data["capabilities"]["video_qualities"][0]["label"] == "720p"
