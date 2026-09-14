"""
End-to-end integration flow tests.

Exercises the single workflow required by Section 1 & Section 42:
Paste X post URL -> Extract ONCE -> PostData + MediaData -> Tweet HTML/CSS ->
Chromium Render -> Tweet PNG -> Media Download -> Download Everything (ZIP).
"""

import io
import zipfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from tests.fixtures import FIXTURE_A, FIXTURE_B, FIXTURE_C, FIXTURE_D


@pytest.fixture
def client():
    from app.core.rate_limiter import rate_limiter
    rate_limiter.reset()
    return TestClient(main.app, raise_server_exceptions=False)


def test_complete_e2e_flow_text_and_image(client):
    """
    Test full flow for post with image:
    Extract -> Render card -> Download PNG -> Download ZIP -> Verify archive.
    """
    with patch("app.extractors.manager.extraction_manager.extract") as mock_extract:
        mock_extract.return_value = FIXTURE_B

        # 1. Extract post ONCE
        extract_res = client.post("/api/extract", json={"url": FIXTURE_B.url})
        assert extract_res.status_code == 200
        extract_data = extract_res.json()
        job_id = extract_data["job_id"]
        assert extract_data["capabilities"]["tweet_image"] is True
        assert extract_data["capabilities"]["images"] is True

        # 2. Render Tweet card via Playwright Chromium
        render_res = client.post(
            "/api/render",
            json={
                "job_id": job_id,
                "theme": "dark",
                "background": "gradient",
                "aspect_ratio": "original",
            },
        )
        assert render_res.status_code == 200
        render_data = render_res.json()
        assert render_data["asset_id"] == "tweet_card"
        assert render_data["size"] > 0

        # 3. Download the generated PNG
        dl_png_res = client.get(f"/api/download/{job_id}/tweet_card")
        assert dl_png_res.status_code == 200
        assert dl_png_res.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(dl_png_res.content))
        img.verify()

        # 4. Download Everything (ZIP)
        dl_zip_res = client.post("/api/download-all", json={"job_id": job_id})
        assert dl_zip_res.status_code == 200
        assert dl_zip_res.headers["content-type"] == "application/zip"

        # Verify ZIP contains the tweet image and has valid structure
        with zipfile.ZipFile(io.BytesIO(dl_zip_res.content), "r") as zf:
            namelist = zf.namelist()
            assert any(name.endswith(".png") for name in namelist)


def test_complete_e2e_flow_video_thumbnail(client):
    """
    Test full flow for post with video:
    Extract -> Render card with authentic poster frame -> Download PNG.
    """
    with patch("app.extractors.manager.extraction_manager.extract") as mock_extract:
        mock_extract.return_value = FIXTURE_C

        extract_res = client.post("/api/extract", json={"url": FIXTURE_C.url})
        assert extract_res.status_code == 200
        job_id = extract_res.json()["job_id"]

        render_res = client.post(
            "/api/render",
            json={
                "job_id": job_id,
                "theme": "editorial",
                "background": "solid",
                "background_color": "#f8f5f0",
                "aspect_ratio": "16:9",
            },
        )
        assert render_res.status_code == 200
        data = render_res.json()
        assert data["asset_id"] == "tweet_card"

        dl_png_res = client.get(f"/api/download/{job_id}/tweet_card")
        assert dl_png_res.status_code == 200
        img = Image.open(io.BytesIO(dl_png_res.content))
        img.verify()


def test_truthful_error_when_media_cannot_be_loaded(client):
    """
    Test Section 8 & Section 37:
    Never substitute placeholders. If media cannot be loaded, raise MEDIA_EXTRACTION_FAILED.
    """
    from app.models.post import PostData, MediaItem

    unreachable_post = PostData(
        id="999999",
        url="https://x.com/fake/status/999999",
        author_name="Fake",
        author_handle="fake",
        text="Tweet with unreachable image",
        media=[
            MediaItem(
                type="image",
                url="https://pbs.twimg.com/media/completely_unreachable_99999999999.jpg",
                width=100,
                height=100,
            )
        ],
    )

    with patch("app.extractors.manager.extraction_manager.extract") as mock_extract:
        mock_extract.return_value = unreachable_post

        extract_res = client.post("/api/extract", json={"url": unreachable_post.url})
        job_id = extract_res.json()["job_id"]

        render_res = client.post("/api/render", json={"job_id": job_id})
        # Must fail with 502 MEDIA_EXTRACTION_FAILED, never return fake success
        assert render_res.status_code == 502
        detail = render_res.json()["detail"]
        assert "MEDIA_EXTRACTION_FAILED" in detail
