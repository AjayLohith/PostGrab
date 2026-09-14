"""yt-dlp based post extractor with seamless syndication fallback."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

from app.models.post import MediaItem, MediaVariant, PostData, QuotedPostData
from app.extractors.base import (
    ExtractionError,
    MediaExtractionError,
    PostNotFoundError,
    RateLimitedError,
)
from app.core.security import extract_post_info

logger = logging.getLogger(__name__)


def _generate_syndication_token(post_id: str) -> str:
    """Generate the required base-36 syndication token for Twitter's tweet-result endpoint."""
    try:
        val = (float(post_id) / 1e15) * math.pi
        integral = int(val)
        fraction = val - integral
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        res = ""
        if integral == 0:
            res = "0"
        else:
            s = []
            n = integral
            while n > 0:
                s.append(digits[n % 36])
                n //= 36
            res = "".join(reversed(s))
        if fraction:
            res += "."
            f = fraction
            for _ in range(12):
                f *= 36
                d = int(f)
                res += digits[d]
                f -= d
        return re.sub(r"(0+|\.)", "", res)
    except Exception:
        return "5"


async def _fetch_syndication_data(post_id: str) -> dict[str, Any] | None:
    """Fetch complete tweet payload from Twitter's public syndication CDN."""
    if not post_id or not str(post_id).isdigit():
        return None
    try:
        import httpx
        token = _generate_syndication_token(post_id)
        url = f"https://cdn.syndication.twimg.com/tweet-result?id={post_id}&token={token}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and (data.get("text") or data.get("user") or data.get("mediaDetails")):
                    return data
            # Secondary fallback without token
            url_notoken = f"https://cdn.syndication.twimg.com/tweet-result?id={post_id}"
            resp_notoken = await client.get(url_notoken)
            if resp_notoken.status_code == 200:
                data = resp_notoken.json()
                if isinstance(data, dict) and (data.get("text") or data.get("user") or data.get("mediaDetails")):
                    return data
    except Exception as e:
        logger.debug("Syndication fetch failed for %s: %s", post_id, e)
    return None


def _extract_media_from_syndication(syn_data: dict[str, Any]) -> list[MediaItem]:
    """Extract MediaItem list from syndication CDN JSON (videos, photos, gifs)."""
    media_items: list[MediaItem] = []

    for m in syn_data.get("mediaDetails", []):
        m_type = m.get("type")
        poster = m.get("media_url_https")
        if m_type == "video":
            vinfo = m.get("video_info", {})
            duration_ms = vinfo.get("duration_millis")
            duration_sec = duration_ms / 1000.0 if duration_ms else None
            raw_variants = vinfo.get("variants", [])
            variants: list[MediaVariant] = []
            best_url = ""
            best_bitrate = -1.0
            best_w: int | None = None
            best_h: int | None = None

            for v in raw_variants:
                v_url = v.get("url") or v.get("src")
                if not v_url:
                    continue
                content_type = v.get("content_type") or v.get("type", "")
                bitrate = v.get("bitrate")

                w, h = None, None
                dim_match = re.search(r"/(\d+)x(\d+)/", v_url)
                if dim_match:
                    w, h = int(dim_match.group(1)), int(dim_match.group(2))

                quality_label = f"{h}p" if h else ("HLS Stream" if "mpegURL" in content_type else "MP4")
                bitrate_val = float(bitrate) if bitrate is not None else None

                variants.append(MediaVariant(
                    url=v_url,
                    content_type="mp4" if "mp4" in content_type else content_type,
                    bitrate=bitrate_val,
                    width=w,
                    height=h,
                    quality_label=quality_label,
                ))

                if "mp4" in content_type and bitrate_val and bitrate_val > best_bitrate:
                    best_bitrate = bitrate_val
                    best_url = v_url
                    best_w, best_h = w, h

            if not best_url and variants:
                best_url = variants[0].url

            media_items.append(MediaItem(
                type="video",
                url=best_url,
                width=best_w,
                height=best_h,
                duration=duration_sec,
                mime_type="video/mp4",
                thumbnail_url=poster,
                variants=variants,
            ))

        elif m_type == "photo":
            orig_info = m.get("original_info", {})
            media_items.append(MediaItem(
                type="image",
                url=poster,
                width=orig_info.get("width"),
                height=orig_info.get("height"),
                mime_type="image/jpeg",
                thumbnail_url=poster,
            ))

    # Check photos array if mediaDetails didn't yield images
    if not media_items and syn_data.get("photos"):
        for p in syn_data.get("photos", []):
            photo_url = p.get("url")
            if photo_url:
                media_items.append(MediaItem(
                    type="image",
                    url=photo_url,
                    width=p.get("width"),
                    height=p.get("height"),
                    mime_type="image/jpeg",
                    thumbnail_url=photo_url,
                ))

    return media_items


def _extract_quoted_post(
    syn_data: dict[str, Any] | None,
    info: dict[str, Any] | None = None,
) -> QuotedPostData | None:
    """Extract quoted post data from syndication CDN or yt-dlp info."""
    # 1. Prefer syndication quoted_tweet
    if syn_data and syn_data.get("quoted_tweet"):
        q = syn_data["quoted_tweet"]
        q_user = q.get("user") or {}
        q_name = q_user.get("name") or q_user.get("screen_name") or "User"
        q_handle = q_user.get("screen_name") or ""
        q_avatar = q_user.get("profile_image_url_https", "")
        if q_avatar:
            q_avatar = q_avatar.replace("_normal.", "_400x400.")
        if not q_avatar and q_handle:
            q_avatar = f"https://unavatar.io/x/{q_handle}"

        q_text = q.get("text", "")
        q_media = _extract_media_from_syndication(q)

        q_created_at: datetime | None = None
        if q.get("created_at"):
            try:
                q_created_at = datetime.fromisoformat(q["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

        return QuotedPostData(
            id=str(q.get("id_str") or "quoted"),
            url=f"https://x.com/{q_handle}/status/{q.get('id_str')}" if q_handle and q.get("id_str") else None,
            author_name=q_name,
            author_handle=q_handle,
            avatar_url=q_avatar,
            text=q_text,
            created_at=q_created_at,
            media=q_media,
        )

    # 2. Fallback to yt-dlp quoted_status
    if info and info.get("quoted_status"):
        qs = info["quoted_status"]
        q_name = qs.get("uploader") or qs.get("channel") or ""
        q_handle = qs.get("uploader_id") or qs.get("channel_id") or ""
        if q_handle.startswith("@"):
            q_handle = q_handle[1:]
        q_avatar = None
        for thumb in qs.get("thumbnails", []):
            t_url = thumb.get("url", "")
            if "profile_images" in t_url:
                q_avatar = t_url
                break
        if not q_avatar and q_handle:
            q_avatar = f"https://unavatar.io/x/{q_handle}"

        q_text = qs.get("description") or qs.get("title") or ""
        return QuotedPostData(
            id=str(qs.get("id", "quoted")),
            url=qs.get("webpage_url") or (f"https://x.com/{q_handle}/status/{qs.get('id')}" if q_handle and qs.get("id") else None),
            author_name=q_name or q_handle or "User",
            author_handle=q_handle,
            avatar_url=q_avatar,
            text=q_text,
            media=[],
        )

    return None


class YtDlpExtractor:
    """
    Primary extractor using yt-dlp with syndication CDN enhancement and fallback.

    Maps yt-dlp's info dictionary and Twitter syndication data to normalized PostData.
    """

    @property
    def name(self) -> str:
        return "yt-dlp"

    async def extract(self, url: str) -> PostData:
        """Extract post data using yt-dlp, enriched and backed by syndication CDN."""
        info_tuple = extract_post_info(url)
        post_id = info_tuple[1] if info_tuple else ""

        # Pre-fetch syndication data concurrently if post_id is available
        syn_data: dict[str, Any] | None = None
        if post_id and str(post_id).isdigit():
            syn_data = await _fetch_syndication_data(post_id)

        try:
            info = await self._extract_info(url)
            return self._map_to_post_data(url, info, syn_data, post_id)
        except PostNotFoundError:
            raise
        except RateLimitedError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            logger.warning("yt-dlp extraction failed for %s: %s", url, e)

            # If yt-dlp failed but syndication data is available, build post directly from it!
            if syn_data:
                logger.info("Constructing PostData directly from syndication CDN for %s", url)
                return self._build_post_data_from_syndication(url, post_id, syn_data)

            if "not found" in error_str or "404" in error_str:
                raise PostNotFoundError()
            elif "private" in error_str or "protected" in error_str:
                raise PostNotFoundError(
                    "This post is from a private account and cannot be accessed."
                )
            elif "rate" in error_str and "429" in error_str:
                raise RateLimitedError()
            elif "no video" in error_str or "unsupported url" in error_str:
                raise MediaExtractionError(
                    "yt-dlp could not extract media from this post. "
                    "It may be a text-only post or use an unsupported format."
                )
            else:
                raise ExtractionError(
                    "We couldn't retrieve this post via yt-dlp. "
                    f"Error: {type(e).__name__}: {str(e)[:200]}",
                    recoverable=True,
                )

    async def _extract_info(self, url: str) -> dict[str, Any]:
        """Run yt-dlp extract_info in a thread pool to avoid blocking."""
        import yt_dlp

        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "writeinfojson": False,
            "no_color": True,
        }

        def _do_extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _do_extract)

        if info is None:
            raise PostNotFoundError()

        return info

    def _build_post_data_from_syndication(
        self,
        url: str,
        post_id: str,
        syn_data: dict[str, Any],
    ) -> PostData:
        """Build a complete PostData model directly from Twitter syndication data."""
        user = syn_data.get("user") or {}
        author_name = user.get("name") or user.get("screen_name") or "User"
        author_handle = user.get("screen_name") or ""
        avatar_url = user.get("profile_image_url_https", "")
        if avatar_url:
            avatar_url = avatar_url.replace("_normal.", "_400x400.")
        if not avatar_url and author_handle:
            avatar_url = f"https://unavatar.io/x/{author_handle}"

        text = syn_data.get("text", "")
        media = _extract_media_from_syndication(syn_data)

        created_at: datetime | None = None
        raw_date = syn_data.get("created_at")
        if raw_date:
            try:
                created_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                pass

        reply_count = syn_data.get("conversation_count")
        like_count = syn_data.get("favorite_count")
        quoted_post = _extract_quoted_post(syn_data)

        return PostData(
            id=post_id or syn_data.get("id_str", "unknown"),
            url=url,
            author_name=author_name,
            author_handle=author_handle,
            avatar_url=avatar_url,
            text=text,
            created_at=created_at,
            reply_count=reply_count,
            repost_count=None,
            like_count=like_count,
            view_count=None,
            media=media,
            quoted_post=quoted_post,
            source="syndication",
        )

    def _map_to_post_data(
        self,
        url: str,
        info: dict[str, Any],
        syn_data: dict[str, Any] | None = None,
        extracted_post_id: str = "",
    ) -> PostData:
        """Map yt-dlp info dictionary to our normalized PostData model, enriched with syndication."""

        # Extract post ID
        post_id = info.get("id", "") or extracted_post_id
        if not post_id:
            parts = url.rstrip("/").split("/")
            post_id = parts[-1] if parts else "unknown"

        # Extract author info
        uploader = info.get("uploader", "") or info.get("channel", "") or ""
        uploader_id = info.get("uploader_id", "") or info.get("channel_id", "") or ""
        if uploader_id.startswith("@"):
            uploader_id = uploader_id[1:]

        # Extract text (yt-dlp uses 'description' for tweet text)
        text = info.get("description", "") or info.get("title", "") or ""

        # Extract avatar
        avatar_url = None
        thumbnails = info.get("thumbnails", [])
        for thumb in thumbnails:
            thumb_url = thumb.get("url", "")
            if "profile_images" in thumb_url or "profile_banners" in thumb_url:
                avatar_url = thumb_url
                break

        # Extract metrics
        reply_count = info.get("comment_count")
        repost_count = info.get("repost_count")
        like_count = info.get("like_count")
        view_count = info.get("view_count")

        # Extract timestamp
        timestamp = info.get("timestamp")
        created_at: datetime | None = None
        if timestamp:
            created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        # Enrich with syndication data if available
        if syn_data:
            syn_text = syn_data.get("text")
            if syn_text:
                text = syn_text

            user = syn_data.get("user") or {}
            syn_avatar = user.get("profile_image_url_https")
            if syn_avatar:
                avatar_url = syn_avatar.replace("_normal.", "_400x400.")

            if not uploader and user.get("name"):
                uploader = user["name"]
            if not uploader_id and user.get("screen_name"):
                uploader_id = user["screen_name"]

            if created_at is None and syn_data.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(syn_data["created_at"].replace("Z", "+00:00"))
                except Exception:
                    pass

            if like_count is None:
                like_count = syn_data.get("favorite_count")
            if reply_count is None:
                reply_count = syn_data.get("conversation_count")

        if not avatar_url and uploader_id:
            avatar_url = f"https://unavatar.io/x/{uploader_id}"

        # Check quoted post first
        quoted_post = _extract_quoted_post(syn_data, info)

        # 1. Authoritative media assignment from syndication CDN if available
        if syn_data:
            syn_media = _extract_media_from_syndication(syn_data)
            syn_has_video = any(m.type in ("video", "gif") for m in syn_media)
            syn_has_photo = any(m.type == "image" for m in syn_media)

            if syn_has_video:
                # Root tweet legitimately has its own video.
                # Enrich with yt-dlp variants if available for highest resolution MP4s
                yt_media = self._extract_media(info)
                yt_videos = [m for m in yt_media if m.type in ("video", "gif")]
                if yt_videos and yt_videos[0].variants:
                    for sm in syn_media:
                        if sm.type in ("video", "gif") and not sm.variants:
                            sm.variants = yt_videos[0].variants
                            if yt_videos[0].url:
                                sm.url = yt_videos[0].url
                media = syn_media
            elif syn_has_photo:
                # Root tweet legitimately has photos/images!
                # NEVER assign any video to root media
                media = syn_media
            else:
                # Root tweet has no media of its own (text-only or quote-only)
                media = []

            # Quoted tweet video enrichment:
            # If quoted post has a video, and yt-dlp extracted video formats (which actually belonged to the quote),
            # ensure quoted_post.media has the rich yt-dlp variants for download!
            if quoted_post and any(m.type in ("video", "gif") for m in quoted_post.media):
                yt_media = self._extract_media(info)
                yt_videos = [m for m in yt_media if m.type in ("video", "gif")]
                if yt_videos and yt_videos[0].variants:
                    for qm in quoted_post.media:
                        if qm.type in ("video", "gif") and not qm.variants:
                            qm.variants = yt_videos[0].variants
                            if yt_videos[0].url:
                                qm.url = yt_videos[0].url

        else:
            # 2. Fallback when syndication CDN was not available:
            # Check if yt-dlp formats originated from quoted_status
            qs = info.get("quoted_status")
            is_quoted_video = False
            if qs:
                qs_formats = qs.get("formats", [])
                root_formats = info.get("formats", [])
                qs_urls = {f.get("url") for f in qs_formats if f.get("url")}
                root_urls = {f.get("url") for f in root_formats if f.get("url")}
                if qs_urls and (root_urls == qs_urls or root_urls.issubset(qs_urls)):
                    is_quoted_video = True
                elif qs.get("thumbnail") and qs.get("thumbnail") == info.get("thumbnail") and str(qs.get("id")) != str(info.get("id")):
                    is_quoted_video = True

            if is_quoted_video:
                media = self._extract_images_from_thumbnails(info)
            else:
                media = self._extract_media(info)

        # 3. Strict Deduplication and Misattribution Guard:
        # If quoted_post exists and has media, the root tweet must NEVER duplicate the quoted media.
        if quoted_post and quoted_post.media:
            quoted_urls = {m.url for m in quoted_post.media if m.url}
            quoted_thumbs = {m.thumbnail_url for m in quoted_post.media if m.thumbnail_url}
            if info.get("quoted_status", {}).get("thumbnail"):
                quoted_thumbs.add(info["quoted_status"]["thumbnail"])

            # Filter out any media item from root media that matches quoted media
            filtered_media = []
            for m in media:
                if m.url and m.url in quoted_urls:
                    continue
                if m.thumbnail_url and m.thumbnail_url in quoted_thumbs:
                    continue
                filtered_media.append(m)
            media = filtered_media

            # Ensure quoted post has the video if yt-dlp extracted it
            if not any(m.type in ("video", "gif") for m in quoted_post.media):
                qs = info.get("quoted_status")
                if qs and qs.get("formats"):
                    quoted_vids = self._extract_media(qs)
                    if quoted_vids:
                        quoted_post.media = [m for m in quoted_vids if m.type in ("video", "gif")] + quoted_post.media

        return PostData(
            id=post_id,
            url=url,
            author_name=uploader,
            author_handle=uploader_id,
            avatar_url=avatar_url,
            text=text,
            created_at=created_at,
            reply_count=reply_count,
            repost_count=repost_count,
            like_count=like_count,
            view_count=view_count,
            media=media,
            quoted_post=quoted_post,
            source="yt-dlp",
        )

    def _extract_media(self, info: dict[str, Any]) -> list[MediaItem]:
        """Extract media items from yt-dlp info."""
        media: list[MediaItem] = []
        formats = info.get("formats", [])

        if not formats:
            return self._extract_images_from_thumbnails(info)

        duration = info.get("duration")
        is_gif = duration is not None and duration < 15 and info.get("format_note", "").lower() == "gif"

        video_variants: list[MediaVariant] = []
        best_format = None
        best_height = 0

        for fmt in formats:
            fmt_url = fmt.get("url", "")
            if not fmt_url:
                continue

            width = fmt.get("width")
            height = fmt.get("height")
            vcodec = fmt.get("vcodec", "none")
            acodec = fmt.get("acodec", "none")

            if vcodec == "none" and acodec != "none":
                continue

            quality_label = ""
            if width and height:
                quality_label = f"{width}×{height}"
            elif height:
                quality_label = f"{height}p"

            variant = MediaVariant(
                url=fmt_url,
                content_type=fmt.get("ext", "mp4"),
                bitrate=fmt.get("tbr"),
                width=width,
                height=height,
                quality_label=quality_label or fmt.get("format_note", ""),
            )
            video_variants.append(variant)

            fmt_height = height or 0
            if fmt_height > best_height:
                best_height = fmt_height
                best_format = fmt

        if video_variants:
            best_url = info.get("url", "")
            if best_format:
                best_url = best_format.get("url", best_url)

            media_type = "gif" if is_gif else "video"
            thumbnail_url = info.get("thumbnail")

            video_item = MediaItem(
                type=media_type,
                url=best_url,
                width=best_format.get("width") if best_format else None,
                height=best_format.get("height") if best_format else None,
                duration=duration,
                mime_type=f"video/{best_format.get('ext', 'mp4')}" if best_format else "video/mp4",
                thumbnail_url=thumbnail_url,
                file_size=best_format.get("filesize") if best_format else None,
                variants=video_variants,
            )
            media.append(video_item)

        images = self._extract_images_from_thumbnails(info)
        media.extend(images)

        return media

    def _extract_images_from_thumbnails(self, info: dict[str, Any]) -> list[MediaItem]:
        """Extract image media from yt-dlp thumbnails."""
        images: list[MediaItem] = []
        thumbnails = info.get("thumbnails", [])

        for thumb in thumbnails:
            thumb_url = thumb.get("url", "")
            if "profile_images" in thumb_url or "profile_banners" in thumb_url:
                continue
            if "tweet_video_thumb" in thumb_url:
                continue

            if "media" in thumb_url and "twimg.com" in thumb_url:
                images.append(MediaItem(
                    type="image",
                    url=thumb_url,
                    width=thumb.get("width"),
                    height=thumb.get("height"),
                    mime_type="image/jpeg",
                ))

        return images
