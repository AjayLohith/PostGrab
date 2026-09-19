"""Download service — media downloading, file management, and ZIP creation."""

from __future__ import annotations

import asyncio
import io
import logging
import mimetypes
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.job_manager import Job, JobStatus, job_manager
from app.core.security import is_allowed_media_host, sanitize_filename
from app.models.post import MediaItem, PostData

logger = logging.getLogger(__name__)

# Asset ID prefixes
MEDIA_ASSET_PREFIX = "media_"
ZIP_ASSET_ID = "zip"


def _ext_from_content_type(ct: str | None, fallback: str = "bin") -> str:
    if not ct:
        return fallback
    ct = ct.split(";")[0].strip()
    ext = mimetypes.guess_extension(ct)
    if ext:
        return ext.lstrip(".")
    mapping = {
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/x-m4v": "mp4",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    return mapping.get(ct, fallback)


def _ext_from_url(url: str, fallback: str = "bin") -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lstrip(".")
    return suffix if suffix else fallback


async def extract_thumbnail_ffmpeg(video_input: str | Path, output_path: Path) -> bool:
    """
    Extract a poster frame from a video input using FFmpeg.

    Tries at 00:00:01 first, then 00:00:00 for ultra-short clips.
    """
    try:
        if output_path.exists() and output_path.stat().st_size > 0:
            return True

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            logger.warning("ffmpeg executable not found in PATH")
            return False

        # Attempt 1: 1.0 second offset
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin, "-y", "-ss", "00:00:01", "-i", str(video_input),
            "-vframes", "1", "-q:v", "2", str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if output_path.exists() and output_path.stat().st_size > 0:
            return True

        # Attempt 2: 0.0 second offset
        proc2 = await asyncio.create_subprocess_exec(
            ffmpeg_bin, "-y", "-ss", "00:00:00", "-i", str(video_input),
            "-vframes", "1", "-q:v", "2", str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        logger.warning("FFmpeg poster extraction error for %s: %s", video_input, e)
        return False


async def download_video_stream(url: str, output_path: Path) -> bool:
    """Download or merge video streams using yt-dlp with stream copy and fragment concurrency."""
    try:
        import yt_dlp
        loop = asyncio.get_event_loop()

        temp_output = output_path.with_name(f"{output_path.name}.tmp")

        def _do_ytdlp():
            opts = {
                "outtmpl": str(temp_output),
                "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                "merge_output_format": "mp4",
                "postprocessor_args": {
                    "merger": ["-c", "copy"],
                },
                "concurrent_fragment_downloads": 8,
                "retries": 3,
                "fragment_retries": 3,
                "socket_timeout": 15,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            candidate = temp_output
            if not candidate.exists() and temp_output.with_suffix(".mp4").exists():
                candidate = temp_output.with_suffix(".mp4")

            if candidate.exists() and candidate.stat().st_size > 0:
                if candidate != output_path:
                    candidate.replace(output_path)
                return True
            return False

        return await loop.run_in_executor(None, _do_ytdlp)
    except Exception as e:
        logger.warning("yt-dlp video stream download failed for %s: %s", url, e)
        return False


async def download_media_item(
    job: Job,
    item: MediaItem,
    asset_id: str,
    filename_base: str,
) -> str | None:
    """
    Download a single media item and register it as a job asset.

    Returns:
        asset_id if successful, None if skipped/failed
    """
    # Reuse cached asset if already downloaded and verified
    cached = job.assets.get(asset_id)
    if cached and cached.file_path and cached.file_path.exists() and cached.file_path.stat().st_size > 0:
        logger.info("Reusing existing downloaded media asset for job %s: %s", job.id, asset_id)
        return asset_id

    url = item.url

    # SSRF protection
    if not is_allowed_media_host(url):
        logger.warning("Blocked media download from disallowed host: %s", url)
        return None

    # Best-quality variant selection for video (prefer direct MP4s over HLS m3u8 manifests)
    if item.type in ("video", "gif") and item.variants:
        mp4_variants = [
            v for v in item.variants
            if (v.content_type == "mp4" or ".mp4" in v.url.lower()) and ".m3u8" not in v.url.lower()
        ]
        pool = mp4_variants if mp4_variants else item.variants
        best = max(
            pool,
            key=lambda v: (v.height or 0, v.bitrate or 0),
        )
        url = best.url

    assert job.temp_dir is not None
    max_bytes = settings.max_download_size_bytes

    # If stream is an HLS playlist, route directly to yt-dlp
    is_hls = ".m3u8" in url.lower() or (item.mime_type and "mpegurl" in item.mime_type.lower())
    if item.type in ("video", "gif") and is_hls:
        filename = f"{filename_base}.mp4"
        file_path = job.temp_dir / filename
        if await download_video_stream(url, file_path):
            job.add_asset(asset_id, filename, "video/mp4", file_path)
            return asset_id
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    logger.warning(
                        "Media download HTTP error for %s: HTTP %d", url, response.status_code
                    )
                    # If direct download failed and it's video, attempt yt-dlp
                    if item.type in ("video", "gif"):
                        filename = f"{filename_base}.mp4"
                        file_path = job.temp_dir / filename
                        if await download_video_stream(url, file_path):
                            job.add_asset(asset_id, filename, "video/mp4", file_path)
                            return asset_id
                    return None

                content_type = response.headers.get("content-type", "")
                ext = _ext_from_content_type(content_type) or _ext_from_url(url, "bin")

                if item.type == "video" and ext not in ("mp4", "webm", "mov", "mkv"):
                    ext = "mp4"
                elif item.type == "gif":
                    ext = "mp4"  # GIFs on X are delivered as mp4
                elif item.type == "image" and ext not in ("jpg", "jpeg", "png", "webp", "gif"):
                    ext = "jpg"

                filename = f"{filename_base}.{ext}"
                file_path = job.temp_dir / filename
                temp_file = job.temp_dir / f"{filename}.tmp"

                content_length_header = response.headers.get("content-length")
                expected_bytes = (
                    int(content_length_header)
                    if content_length_header and content_length_header.isdigit()
                    else None
                )

                downloaded = 0
                with open(temp_file, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1048576):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            logger.warning(
                                "Media file too large (>%dMB), aborting: %s",
                                settings.max_download_size_mb,
                                url,
                            )
                            f.close()
                            if temp_file.exists():
                                temp_file.unlink()
                            return None
                        f.write(chunk)

        if not temp_file.exists() or temp_file.stat().st_size == 0:
            logger.warning("Downloaded temp file is empty or missing: %s", temp_file)
            if temp_file.exists():
                temp_file.unlink()
            return None

        # Verify completeness against Content-Length if provided
        if expected_bytes is not None and downloaded != expected_bytes:
            logger.warning(
                "Download incomplete for %s: got %d bytes, expected %d",
                url, downloaded, expected_bytes,
            )
            if temp_file.exists():
                temp_file.unlink()
            return None

        # Atomic rename to final file path
        temp_file.replace(file_path)

        content_type_final = content_type.split(";")[0].strip() or "application/octet-stream"
        job.add_asset(asset_id, filename, content_type_final, file_path)
        logger.info(
            "Downloaded %s media for job %s: %s (%d bytes)",
            item.type, job.id, filename, downloaded,
        )
        return asset_id

    except Exception as e:
        logger.error("Failed to download media for job %s (%s): %s", job.id, url, e)
        # Attempt fallback for video
        if item.type in ("video", "gif"):
            filename = f"{filename_base}.mp4"
            file_path = job.temp_dir / filename
            if await download_video_stream(url, file_path):
                job.add_asset(asset_id, filename, "video/mp4", file_path)
                return asset_id
        return None


async def download_all_media(job: Job, post: PostData) -> list[str]:
    """
    Download all media items for a post.

    Returns:
        List of registered asset_ids
    """
    handle = sanitize_filename(post.author_handle or "unknown")
    post_id = sanitize_filename(post.id or "post")
    base = f"{handle}_{post_id}"

    tasks = []
    asset_ids = []

    # Video(s)
    for i, item in enumerate(post.videos):
        suffix = f"_video_{i + 1:02d}" if len(post.videos) > 1 else "_video"
        asset_id = f"{MEDIA_ASSET_PREFIX}video_{i}"
        filename_base = f"{base}{suffix}"
        tasks.append(download_media_item(job, item, asset_id, filename_base))
        asset_ids.append(asset_id)

    # GIFs
    for i, item in enumerate(post.gifs):
        suffix = f"_gif_{i + 1:02d}" if len(post.gifs) > 1 else "_gif"
        asset_id = f"{MEDIA_ASSET_PREFIX}gif_{i}"
        filename_base = f"{base}{suffix}"
        tasks.append(download_media_item(job, item, asset_id, filename_base))
        asset_ids.append(asset_id)

    # Images
    for i, item in enumerate(post.images):
        suffix = f"_image_{i + 1:02d}" if len(post.images) > 1 else "_image"
        asset_id = f"{MEDIA_ASSET_PREFIX}image_{i}"
        filename_base = f"{base}{suffix}"
        tasks.append(download_media_item(job, item, asset_id, filename_base))
        asset_ids.append(asset_id)

    # Quoted post media if present
    if post.quoted_post and post.quoted_post.media:
        q_handle = sanitize_filename(post.quoted_post.author_handle or "quoted")
        for i, item in enumerate(post.quoted_post.media):
            suffix = f"_quoted_{item.type}_{i + 1:02d}"
            asset_id = f"{MEDIA_ASSET_PREFIX}quoted_{item.type}_{i}"
            filename_base = f"{base}_{q_handle}{suffix}"
            tasks.append(download_media_item(job, item, asset_id, filename_base))
            asset_ids.append(asset_id)

    if tasks:
        await job_manager.update_job(job.id, status=JobStatus.DOWNLOADING)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = [
            aid for aid, result in zip(asset_ids, results)
            if result is not None and not isinstance(result, Exception)
        ]
        return successful

    return []


async def build_zip(job: Job, post: PostData) -> str | None:
    """
    Create a ZIP archive of all actual job assets.

    Returns:
        asset_id of the ZIP file, or None if no assets
    """
    # Only include existing, non-empty files
    valid_assets = [
        a for a in job.assets.values()
        if a.id != ZIP_ASSET_ID and a.file_path and a.file_path.exists() and a.file_path.stat().st_size > 0
    ]

    if not valid_assets:
        return None

    handle = sanitize_filename(post.author_handle or "unknown")
    post_id = sanitize_filename(post.id or "post")
    zip_name = f"{handle}_{post_id}.zip"
    folder_name = f"{handle}_{post_id}"

    assert job.temp_dir is not None
    zip_path = job.temp_dir / zip_name

    try:
        loop = asyncio.get_event_loop()

        def _create_zip():
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for asset in valid_assets:
                    zf.write(asset.file_path, arcname=f"{folder_name}/{asset.filename}")
            return zip_path.stat().st_size

        size = await loop.run_in_executor(None, _create_zip)
        if size == 0:
            return None

        job.add_asset(ZIP_ASSET_ID, zip_name, "application/zip", zip_path)
        logger.info("Built ZIP for job %s: %s (%d bytes)", job.id, zip_name, size)
        return ZIP_ASSET_ID

    except Exception as e:
        logger.error("Failed to build ZIP for job %s: %s", job.id, e)
        return None
