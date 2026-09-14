"""oEmbed fallback extractor — uses Twitter's public oEmbed API."""

from __future__ import annotations

import re
import logging
from datetime import datetime

import httpx

from app.models.post import PostData
from app.extractors.base import (
    ExtractionError,
    PostNotFoundError,
)
from app.core.security import extract_post_info

logger = logging.getLogger(__name__)

OEMBED_URL = "https://publish.x.com/oembed"


class OEmbedExtractor:
    """
    Fallback extractor using Twitter's public oEmbed API.

    Provides basic metadata (author, text) when yt-dlp fails.
    Does NOT provide:
    - Engagement metrics (likes, reposts, etc.)
    - Direct media URLs
    - Avatar URLs
    - Timestamps
    """

    @property
    def name(self) -> str:
        return "oEmbed"

    async def extract(self, url: str) -> PostData:
        """Extract basic post data using oEmbed."""
        try:
            return await self._fetch_oembed(url)
        except PostNotFoundError:
            raise
        except ExtractionError:
            raise
        except Exception as e:
            logger.error("oEmbed extraction failed for %s: %s", url, e)
            raise ExtractionError(
                "Could not retrieve post information. "
                "The post may be deleted, private, or X may be temporarily unavailable.",
                recoverable=False,
            )

    async def _fetch_oembed(self, url: str) -> PostData:
        """Fetch oEmbed data from Twitter's public endpoint."""
        params = {
            "url": url,
            "omit_script": "true",
            "hide_media": "false",
            "hide_thread": "true",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(OEMBED_URL, params=params)

            if response.status_code == 404:
                raise PostNotFoundError()
            elif response.status_code == 403:
                raise PostNotFoundError(
                    "This post is not accessible. It may be from a private account."
                )
            elif response.status_code != 200:
                raise ExtractionError(
                    f"X returned an unexpected response (HTTP {response.status_code}). "
                    "Please try again in a moment.",
                    recoverable=True,
                )

            data = response.json()

        return self._map_to_post_data(url, data)

    def _map_to_post_data(self, url: str, data: dict) -> PostData:
        """Map oEmbed response to PostData."""

        # Extract post info from URL
        info = extract_post_info(url)
        post_id = info[1] if info else "unknown"
        url_username = info[0] if info else ""

        # Extract author from oEmbed
        author_name = data.get("author_name", "")
        author_handle = data.get("author_url", "").rstrip("/").split("/")[-1] or url_username

        # Extract text from HTML (oEmbed returns HTML, not plain text)
        html = data.get("html", "")
        text = self._extract_text_from_html(html)

        return PostData(
            id=post_id,
            url=url,
            author_name=author_name,
            author_handle=author_handle,
            avatar_url=f"https://unavatar.io/x/{author_handle}" if author_handle else None,
            text=text,
            created_at=None,  # oEmbed doesn't provide timestamp
            reply_count=None,
            repost_count=None,
            like_count=None,
            view_count=None,
            media=[],  # oEmbed doesn't provide direct media URLs
            source="oEmbed",
        )

    def _extract_text_from_html(self, html: str) -> str:
        """Extract plain text from oEmbed HTML response."""
        if not html:
            return ""

        # The oEmbed HTML contains a blockquote with the tweet text
        # Extract text between <p> tags within the blockquote
        p_pattern = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
        matches = p_pattern.findall(html)

        if not matches:
            return ""

        # Clean HTML tags from the extracted text
        text_parts = []
        for match in matches:
            # Remove HTML tags but keep link text
            clean = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", match)
            clean = re.sub(r"<br\s*/?>", "\n", clean)
            clean = re.sub(r"<[^>]+>", "", clean)
            clean = clean.strip()
            if clean:
                text_parts.append(clean)

        return "\n".join(text_parts)
