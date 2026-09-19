"""PostGrab API routes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from app.core.job_manager import JobStatus, job_manager
from app.core.rate_limiter import rate_limiter
from app.core.security import normalize_x_url, validate_x_url
from app.extractors.base import (
    ExtractionError,
    FontLoadFailed,
    ImageRenderFailed,
    MediaExtractionError,
    MediaExtractionFailed,
    PostExtractionFailed,
    PostNotFoundError,
    PostPrivateError,
    VideoDownloadFailed,
    ZipCreationFailed,
)
from app.extractors.manager import extraction_manager
from app.models.post import PostData
from app.models.requests import (
    Capabilities,
    DownloadMediaRequest,
    ExtractRequest,
    ExtractResponse,
    RenderRequest,
    RenderResponse,
)
from app.services.download_service import (
    ZIP_ASSET_ID,
    build_zip,
    download_all_media,
    download_media_item,
    MEDIA_ASSET_PREFIX,
)
from app.services.render_service import TWEET_ASSET_ID, render_tweet_card

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_error() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests. Please wait a moment before trying again.",
            "code": "rate_limited",
        },
    )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check endpoint."""
    stats = await job_manager.get_stats()
    return {"status": "ok", "jobs": stats}


@router.get("/ping")
async def ping():
    """Lightweight keep-alive ping — used by external cron to prevent Render free-tier sleep."""
    return {"status": "pong"}


async def _prewarm_assets(job_id: str) -> None:
    """Pre-warm media asset caching in background without mutating job status."""
    try:
        job = await job_manager.get_job(job_id)
        if job and job.post_data:
            from app.services.render_service import _resolve_media_assets
            from app.models.post import PostData
            post = PostData(**job.post_data)
            await _resolve_media_assets(post, job)
    except Exception as e:
        logger.debug("Background pre-warm for job %s: %s", job_id, e)


# ── Extract ───────────────────────────────────────────────────────────────────

@router.post("/extract", response_model=ExtractResponse)
async def extract_post(body: ExtractRequest, request: Request):
    """
    Extract post data from a public X URL.

    Creates a job, runs extraction, returns normalized post data
    and available download capabilities.
    """
    client_ip = _get_client_ip(request)
    if not await rate_limiter.is_allowed(client_ip):
        return _rate_limit_error()

    # Validate URL
    is_valid, error_msg = validate_x_url(body.url)
    if not is_valid:
        raise HTTPException(status_code=422, detail=error_msg)

    normalized_url = normalize_x_url(body.url)

    # Create job
    job = await job_manager.create_job()

    try:
        await job_manager.update_job(job.id, status=JobStatus.EXTRACTING)
        post = await extraction_manager.extract(normalized_url)
        post_dict = post.model_dump(mode="json")
        await job_manager.update_job(
            job.id,
            status=JobStatus.EXTRACTED,
            post_data=post_dict,
        )

        # Build capabilities - including media from quoted post if present
        has_video = post.has_video or (post.quoted_post is not None and any(m.type == "video" for m in post.quoted_post.media))
        has_gif = post.has_gif or (post.quoted_post is not None and any(m.type == "gif" for m in post.quoted_post.media))
        has_images = post.has_images or (post.quoted_post is not None and any(m.type == "image" for m in post.quoted_post.media))
        all_videos = post.all_videos

        caps = Capabilities(
            tweet_image=True,
            video=has_video,
            gif=has_gif,
            images=has_images,
            download_all=has_video or has_gif or has_images,
            video_qualities=[
                {
                    "label": v.quality_label or f"{v.height}p",
                    "url": v.url,
                    "width": v.width,
                    "height": v.height,
                    "bitrate": v.bitrate,
                }
                for video in all_videos
                for v in video.variants
                if v.url
            ],
        )

        # Kick off background asset pre-warm for instant card rendering
        asyncio.create_task(_prewarm_assets(job.id))

        return ExtractResponse(job_id=job.id, post=post, capabilities=caps)

    except (PostNotFoundError, PostPrivateError) as e:
        await job_manager.update_job(job.id, status=JobStatus.FAILED, error=e.message)
        raise HTTPException(status_code=404, detail=e.message)

    except ExtractionError as e:
        await job_manager.update_job(job.id, status=JobStatus.FAILED, error=e.message)
        raise HTTPException(status_code=502, detail=e.message)

    except Exception as e:
        logger.error("Unexpected error during extraction for job %s: %s", job.id, e)
        await job_manager.update_job(job.id, status=JobStatus.FAILED, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing this post.",
        )


# ── Render ────────────────────────────────────────────────────────────────────

@router.post("/render", response_model=RenderResponse)
async def render_card(body: RenderRequest, request: Request):
    """
    Render a tweet card PNG for the given job with custom styles.

    Can be called multiple times to re-render with different settings.
    """
    client_ip = _get_client_ip(request)
    if not await rate_limiter.is_allowed(client_ip):
        return _rate_limit_error()

    job = await job_manager.get_job(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired. Please re-extract the post.")

    if job.post_data is None:
        raise HTTPException(status_code=400, detail="Job has not completed extraction yet.")

    try:
        asset_id = await render_tweet_card(job, body)
        asset = job.assets[asset_id]
        return RenderResponse(
            job_id=job.id,
            asset_id=asset_id,
            filename=asset.filename,
            size=asset.size,
        )
    except (MediaExtractionFailed, MediaExtractionError) as e:
        logger.error("Media error during render for job %s: %s", job.id, e)
        raise HTTPException(
            status_code=502,
            detail=f"MEDIA_EXTRACTION_FAILED: {e.message if hasattr(e, 'message') else str(e)}",
        )
    except ImageRenderFailed as e:
        logger.error("Render failed for job %s: %s", job.id, e)
        raise HTTPException(
            status_code=500,
            detail=f"IMAGE_RENDER_FAILED: {e.message if hasattr(e, 'message') else str(e)}",
        )
    except Exception as e:
        logger.error("Unexpected render error for job %s: %s", job.id, e)
        raise HTTPException(
            status_code=500,
            detail=f"IMAGE_RENDER_FAILED: {str(e)}",
        )


# ── Download single asset ─────────────────────────────────────────────────────

@router.get("/download/{job_id}/{asset_id}")
async def download_asset(job_id: str, asset_id: str, request: Request):
    """
    Download a specific job asset by ID.

    asset_id can be:
    - tweet_card → the rendered PNG
    - media_video_0 → first video
    - media_image_0 → first image
    - zip → the complete ZIP archive
    """
    client_ip = _get_client_ip(request)
    if not await rate_limiter.is_allowed(client_ip):
        return _rate_limit_error()

    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    asset = job.assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found in this job.")

    if not asset.file_path or not asset.file_path.exists():
        raise HTTPException(status_code=404, detail="Asset file is missing. Please re-render or re-extract.")

    file_size = asset.file_path.stat().st_size
    if file_size == 0:
        raise HTTPException(status_code=404, detail="Asset file is empty or corrupted.")

    # Complete image delivery: return full bytes to avoid chunked progressive rendering
    if asset.content_type and asset.content_type.startswith("image/"):
        content = asset.file_path.read_bytes()
        return Response(
            content=content,
            media_type=asset.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{asset.filename}"',
                "Content-Length": str(len(content)),
                "Cache-Control": "no-store",
            },
        )

    return FileResponse(
        path=str(asset.file_path),
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.filename,
        headers={
            "Content-Disposition": f'attachment; filename="{asset.filename}"',
            "Cache-Control": "no-store",
        },
    )


# ── Download media ────────────────────────────────────────────────────────────

@router.post("/download")
async def download_media(body: DownloadMediaRequest, request: Request):
    """
    Download a specific media item from a job (video, GIF, or image).
    Fetches and stores the file in the job temp dir, then returns it.
    """
    client_ip = _get_client_ip(request)
    if not await rate_limiter.is_allowed(client_ip):
        return _rate_limit_error()

    job = await job_manager.get_job(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    if job.post_data is None:
        raise HTTPException(status_code=400, detail="Job has not completed extraction yet.")

    post = PostData(**job.post_data)
    all_media = post.all_media_items

    if body.media_index >= len(all_media):
        raise HTTPException(status_code=404, detail=f"Media index {body.media_index} out of range.")

    item = all_media[body.media_index]
    handle = _sanitize(post.author_handle or "unknown")
    post_id = _sanitize(post.id or "post")

    media_type_label = item.type
    asset_id = f"{MEDIA_ASSET_PREFIX}{media_type_label}_{body.media_index}"

    # Return cached asset if already downloaded
    cached = job.assets.get(asset_id)
    if cached and cached.file_path and cached.file_path.exists() and cached.file_path.stat().st_size > 0:
        if cached.content_type and cached.content_type.startswith("image/"):
            content = cached.file_path.read_bytes()
            return Response(
                content=content,
                media_type=cached.content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{cached.filename}"',
                    "Content-Length": str(len(content)),
                    "Cache-Control": "no-store",
                },
            )
        return FileResponse(
            path=str(cached.file_path),
            media_type=cached.content_type or "application/octet-stream",
            filename=cached.filename,
            headers={"Content-Disposition": f'attachment; filename="{cached.filename}"'},
        )

    # Download now
    from app.core.security import sanitize_filename
    filename_base = f"{sanitize_filename(handle)}_{sanitize_filename(post_id)}_{media_type_label}_{body.media_index + 1:02d}"
    downloaded_id = await download_media_item(job, item, asset_id, filename_base)

    if downloaded_id is None:
        raise HTTPException(
            status_code=502,
            detail="Could not download this media file. It may be unavailable or too large.",
        )

    asset = job.assets[downloaded_id]
    if asset.content_type and asset.content_type.startswith("image/"):
        content = asset.file_path.read_bytes()
        return Response(
            content=content,
            media_type=asset.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{asset.filename}"',
                "Content-Length": str(len(content)),
                "Cache-Control": "no-store",
            },
        )

    return FileResponse(
        path=str(asset.file_path),
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.filename,
        headers={"Content-Disposition": f'attachment; filename="{asset.filename}"'},
    )


def _sanitize(s: str) -> str:
    from app.core.security import sanitize_filename
    return sanitize_filename(s)


# ── Download all (ZIP) ────────────────────────────────────────────────────────

@router.post("/download-all")
async def download_all(request: Request, body: dict):
    """
    Download all assets for a job as a ZIP file.

    Requires: { "job_id": "...", "include_tweet_card": true }
    The tweet card must already be rendered before calling this endpoint.
    """
    client_ip = _get_client_ip(request)
    if not await rate_limiter.is_allowed(client_ip):
        return _rate_limit_error()

    job_id = body.get("job_id")
    if not job_id:
        raise HTTPException(status_code=422, detail="job_id is required.")

    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    if job.post_data is None:
        raise HTTPException(status_code=400, detail="Job has not completed extraction yet.")

    post = PostData(**job.post_data)

    # Download any missing media
    await download_all_media(job, post)

    # Build (or rebuild) ZIP
    zip_asset_id = await build_zip(job, post)
    if zip_asset_id is None:
        raise HTTPException(status_code=500, detail="Failed to build ZIP archive.")

    asset = job.assets[zip_asset_id]
    if not asset.file_path or not asset.file_path.exists():
        raise HTTPException(status_code=500, detail="ZIP file is missing after creation.")

    return FileResponse(
        path=str(asset.file_path),
        media_type="application/zip",
        filename=asset.filename,
        headers={"Content-Disposition": f'attachment; filename="{asset.filename}"'},
    )


# ── Job status ────────────────────────────────────────────────────────────────

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get current job status and available assets."""
    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    return {
        "job_id": job.id,
        "status": job.status,
        "error": job.error,
        "post_data": job.post_data,
        "assets": [
            {
                "id": a.id,
                "filename": a.filename,
                "content_type": a.content_type,
                "size": a.size,
            }
            for a in job.assets.values()
        ],
    }
