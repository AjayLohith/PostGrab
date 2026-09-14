"""Extraction manager — orchestrates multiple extractors with fallback."""

from __future__ import annotations

import logging

from app.models.post import PostData
from app.extractors.base import ExtractionError, PostNotFoundError, PostPrivateError
from app.extractors.ytdlp_extractor import YtDlpExtractor
from app.extractors.oembed_extractor import OEmbedExtractor

logger = logging.getLogger(__name__)


class ExtractionManager:
    """
    Manages the extraction pipeline.

    Tries extractors in order:
    1. yt-dlp (primary — provides full metadata + media URLs)
    2. oEmbed (fallback — provides basic metadata only)

    If the primary extractor fails with a recoverable error,
    falls back to the next extractor. Non-recoverable errors
    (post not found, private) are raised immediately.
    """

    def __init__(self):
        self.extractors = [
            YtDlpExtractor(),
            OEmbedExtractor(),
        ]

    async def extract(self, url: str) -> PostData:
        """
        Extract post data using the best available extractor.

        Args:
            url: Normalized X post URL

        Returns:
            PostData from the first successful extractor

        Raises:
            ExtractionError: If all extractors fail
        """
        errors: list[tuple[str, ExtractionError]] = []

        for extractor in self.extractors:
            try:
                logger.info("Trying extractor: %s for %s", extractor.name, url)
                post = await extractor.extract(url)
                logger.info(
                    "Extraction successful via %s: post_id=%s, media_count=%d",
                    extractor.name,
                    post.id,
                    len(post.media),
                )
                return post

            except (PostNotFoundError, PostPrivateError) as e:
                # Non-recoverable: don't try other extractors
                logger.warning(
                    "Non-recoverable error from %s: %s",
                    extractor.name,
                    e.message,
                )
                raise

            except ExtractionError as e:
                logger.warning(
                    "Extractor %s failed (recoverable=%s): %s",
                    extractor.name,
                    e.recoverable,
                    e.message,
                )
                errors.append((extractor.name, e))

                if not e.recoverable:
                    raise

                # Continue to next extractor
                continue

            except Exception as e:
                logger.error(
                    "Unexpected error from %s: %s",
                    extractor.name,
                    str(e),
                )
                errors.append((
                    extractor.name,
                    ExtractionError(str(e)),
                ))
                continue

        # All extractors failed
        if errors:
            last_error = errors[-1][1]
            raise ExtractionError(
                "We couldn't retrieve this post after trying multiple methods. "
                "The post may be unavailable, or X may have temporarily changed "
                "how content is delivered. Please try again in a moment.",
                code="all_extractors_failed",
                recoverable=False,
            )

        raise ExtractionError(
            "No extractors available to process this URL.",
            code="no_extractors",
            recoverable=False,
        )


# Global extraction manager instance
extraction_manager = ExtractionManager()
