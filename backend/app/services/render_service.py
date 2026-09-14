"""Render service — orchestrates tweet card rendering using Playwright + Chromium.

Old pixel-by-pixel Pillow renderer is completely removed from production.
Pre-fetches actual extracted media into deterministic local assets before rendering.
Zero placeholder / arbitrary fallback images.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

import httpx

from app.core.job_manager import Job, JobStatus, job_manager
from app.core.security import is_allowed_media_host, sanitize_filename
from app.extractors.base import ImageRenderFailed, MediaExtractionFailed
from app.models.post import PostData
from app.models.requests import RenderRequest
from app.services.download_service import extract_thumbnail_ffmpeg

logger = logging.getLogger(__name__)

TWEET_ASSET_ID = "tweet_card"


def _to_data_uri(content: bytes, mime_type: str = "image/jpeg") -> str:
    """Encode binary content as base64 data URI."""
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


async def _download_asset_bytes(
    url: str,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> tuple[bytes, str] | None:
    """
    Download media bytes with timeout.
    Returns (bytes, mime_type) or None on failure.
    """
    if not url:
        return None

    # Support data URIs directly
    if url.startswith("data:"):
        return None

    # Support local file paths (e.g. in test fixtures)
    if url.startswith("file://"):
        local_path = Path(url[7:])
        if local_path.exists():
            mime = "image/png" if local_path.suffix == ".png" else "image/jpeg"
            return (local_path.read_bytes(), mime)
        return None

    p = Path(url)
    if p.exists() and p.is_file():
        mime = "image/png" if p.suffix == ".png" else "image/jpeg"
        return (p.read_bytes(), mime)

    if not is_allowed_media_host(url):
        logger.warning("Blocked fetch from disallowed host: %s", url)
        return None

    try:
        if client is not None:
            resp = await client.get(url, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                resp = await c.get(url)
        if resp.status_code == 200 and len(resp.content) > 0:
            ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return (resp.content, ct)
        logger.warning("Media fetch returned HTTP %d for %s", resp.status_code, url)
        return None
    except Exception as e:
        logger.warning("Failed to fetch media from %s: %s", url, e)
        return None


async def _resolve_media_assets(post: PostData, job: Job) -> dict[str, Any]:
    """
    Pre-fetch all actual post media concurrently and convert to deterministic local assets.
    Results are cached on job._resolved_assets for instant re-use across renders.
    """
    if hasattr(job, "_resolved_assets") and job._resolved_assets is not None:
        return job._resolved_assets

    resolved: dict[str, Any] = {
        "avatar": None,
        "images": [],
        "video_thumbnail": None,
    }

    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, limits=limits) as http_client:

        # 1. Author Avatar task
        async def fetch_avatar() -> str | None:
            avatar_url = post.avatar_url
            if not avatar_url and post.author_handle:
                avatar_url = f"https://unavatar.io/x/{post.author_handle}"
            if not avatar_url:
                return None
            if avatar_url.startswith("data:"):
                return avatar_url
            res = await _download_asset_bytes(avatar_url, timeout=6.0, client=http_client)
            if res:
                return _to_data_uri(res[0], res[1])
            if post.author_handle and "unavatar.io" not in avatar_url:
                unav = f"https://unavatar.io/x/{post.author_handle}"
                fb = await _download_asset_bytes(unav, timeout=6.0, client=http_client)
                if fb:
                    return _to_data_uri(fb[0], fb[1])
            return None

        # 2. Attached Images tasks
        async def fetch_image(item: Any) -> str:
            if item.url.startswith("data:"):
                return item.url
            res = await _download_asset_bytes(item.url, timeout=10.0, client=http_client)
            if res is None:
                raise MediaExtractionFailed(
                    f"Could not load extracted media image from {item.url}. "
                    "Cannot generate tweet image without actual post media."
                )
            return _to_data_uri(res[0], res[1])

        # 3. Video Thumbnail task
        async def fetch_video_thumb() -> str | None:
            if not (post.has_video or post.has_gif):
                return None
            video_item = post.videos[0] if post.has_video else (post.gifs[0] if post.has_gif else None)
            if not video_item:
                return None
            if video_item.thumbnail_url:
                if video_item.thumbnail_url.startswith("data:"):
                    return video_item.thumbnail_url
                res = await _download_asset_bytes(video_item.thumbnail_url, timeout=8.0, client=http_client)
                if res:
                    return _to_data_uri(res[0], res[1])

            # Extract via FFmpeg if thumbnail download failed or missing
            if video_item.url and job.temp_dir:
                poster_path = job.temp_dir / f"poster_{sanitize_filename(post.id)}.jpg"
                source_video = None
                for asset in job.assets.values():
                    if "video" in asset.id and asset.file_path and asset.file_path.exists():
                        source_video = asset.file_path
                        break
                input_target = source_video or video_item.url
                ffmpeg_ok = await extract_thumbnail_ffmpeg(input_target, poster_path)
                if ffmpeg_ok and poster_path.exists():
                    return _to_data_uri(poster_path.read_bytes(), "image/jpeg")
            return None

        # 4. Quoted post assets
        async def fetch_quoted_assets() -> dict[str, Any] | None:
            if not post.quoted_post:
                return None
            qp = post.quoted_post
            q_res: dict[str, Any] = {
                "avatar": None,
                "video_thumbnail": None,
                "images": [],
            }

            q_avatar_url = qp.avatar_url or (f"https://unavatar.io/x/{qp.author_handle}" if qp.author_handle else None)
            if q_avatar_url:
                if q_avatar_url.startswith("data:"):
                    q_res["avatar"] = q_avatar_url
                else:
                    av = await _download_asset_bytes(q_avatar_url, timeout=5.0, client=http_client)
                    if av:
                        q_res["avatar"] = _to_data_uri(av[0], av[1])

            q_videos = [m for m in qp.media if m.type in ("video", "gif")]
            q_images = [m for m in qp.media if m.type == "image"]

            if q_videos and q_videos[0].thumbnail_url:
                if q_videos[0].thumbnail_url.startswith("data:"):
                    q_res["video_thumbnail"] = q_videos[0].thumbnail_url
                else:
                    th = await _download_asset_bytes(q_videos[0].thumbnail_url, timeout=6.0, client=http_client)
                    if th:
                        q_res["video_thumbnail"] = _to_data_uri(th[0], th[1])
            elif q_images:
                for qi in q_images[:4]:
                    if qi.url.startswith("data:"):
                        q_res["images"].append(qi.url)
                    else:
                        im = await _download_asset_bytes(qi.url, timeout=6.0, client=http_client)
                        if im:
                            q_res["images"].append(_to_data_uri(im[0], im[1]))

            return q_res

        # Execute all downloads concurrently in parallel
        avatar_task = fetch_avatar()
        images_tasks = [fetch_image(item) for item in post.images[:4]]
        video_thumb_task = fetch_video_thumb()
        quoted_task = fetch_quoted_assets()

        avatar_val, image_vals, video_thumb_val, quoted_val = await asyncio.gather(
            avatar_task,
            asyncio.gather(*images_tasks) if images_tasks else asyncio.sleep(0, result=[]),
            video_thumb_task,
            quoted_task,
        )

        resolved["avatar"] = avatar_val
        resolved["images"] = list(image_vals)
        resolved["video_thumbnail"] = video_thumb_val

        if quoted_val:
            resolved["quoted_avatar"] = quoted_val.get("avatar")
            resolved["quoted_video_thumbnail"] = quoted_val.get("video_thumbnail")
            resolved["quoted_images"] = quoted_val.get("images", [])

    job._resolved_assets = resolved
    return resolved


async def render_tweet_card(job: Job, request: RenderRequest) -> str:
    """
    Render the tweet card for a job using the Playwright + Chromium browser engine.

    Strictly uses real browser rendering (no Pillow/Canvas).
    Pre-fetches actual post media concurrently and memoizes renders for instant response.

    Returns:
        asset_id of the rendered image ("tweet_card")
    """
    # Check if exact same render is already available
    req_key = (
        request.theme,
        request.background,
        request.background_color,
        tuple(request.background_gradient or []),
        request.shadow,
        request.padding,
        request.aspect_ratio,
        request.radius,
    )

    if (
        hasattr(job, "_last_render_key")
        and job._last_render_key == req_key
        and TWEET_ASSET_ID in job.assets
        and job.assets[TWEET_ASSET_ID].file_path
        and job.assets[TWEET_ASSET_ID].file_path.exists()
    ):
        return TWEET_ASSET_ID

    await job_manager.update_job(job.id, status=JobStatus.RENDERING)

    try:
        post_data_dict = job.post_data
        if post_data_dict is None:
            raise ValueError("Job has no post data to render.")

        post = PostData(**post_data_dict)

        # Pre-fetch actual media assets concurrently
        resolved_assets = await _resolve_media_assets(post, job)

        # Render via Playwright Chromium
        from app.renderers.playwright_renderer import render_to_png

        loop = asyncio.get_event_loop()
        png_bytes = await loop.run_in_executor(
            None,
            lambda: render_to_png(post, request, resolved_assets),
        )

        if not png_bytes or len(png_bytes) == 0:
            raise ImageRenderFailed("Playwright produced an empty PNG.")

        # Build filename
        handle = sanitize_filename(post.author_handle or "unknown")
        post_id = sanitize_filename(post.id or "post")
        filename = f"{handle}_{post_id}_tweet.png"

        # Save to job temp dir
        assert job.temp_dir is not None
        file_path = job.temp_dir / filename
        file_path.write_bytes(png_bytes)

        if not file_path.exists() or file_path.stat().st_size == 0:
            raise ImageRenderFailed("Failed to write rendered tweet card PNG.")

        # Register asset and cache key
        job.add_asset(TWEET_ASSET_ID, filename, "image/png", file_path)
        job._last_render_key = req_key
        logger.info(
            "Rendered tweet card for job %s via Playwright: %s (%d bytes)",
            job.id, filename, len(png_bytes),
        )

        return TWEET_ASSET_ID

    except Exception as e:
        logger.error("Render failed for job %s: %s", job.id, e, exc_info=True)
        await job_manager.update_job(job.id, status=JobStatus.FAILED, error=str(e))
        raise
