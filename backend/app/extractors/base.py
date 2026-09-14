"""Base extractor protocol — all extractors implement this interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.post import PostData


@runtime_checkable
class PostExtractor(Protocol):
    """
    Protocol for post extraction.

    Extraction implementations can evolve independently as X changes
    its internal APIs and media delivery mechanisms.
    """

    async def extract(self, url: str) -> PostData:
        """
        Extract post data from a normalized X URL.

        Args:
            url: A normalized X post URL (https://x.com/user/status/123)

        Returns:
            PostData with normalized post information

        Raises:
            ExtractionError: If extraction fails
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable extractor name for logging."""
        ...


class ExtractionError(Exception):
    """Base exception for extraction failures."""

    def __init__(self, message: str, code: str = "extraction_failed", recoverable: bool = True):
        self.message = message
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)


class PostNotFoundError(ExtractionError):
    """The post was not found (deleted, private, or never existed)."""

    def __init__(self, message: str = "Post not found. It may be deleted, private, or the URL may be incorrect."):
        super().__init__(message, code="post_not_found", recoverable=False)


class PostPrivateError(ExtractionError):
    """The post is from a private/protected account."""

    def __init__(self, message: str = "This post is from a private account and cannot be accessed."):
        super().__init__(message, code="post_private", recoverable=False)


class RateLimitedError(ExtractionError):
    """The extraction service is rate limited."""

    def __init__(self, message: str = "We're temporarily rate limited. Please try again in a moment."):
        super().__init__(message, code="rate_limited", recoverable=True)


class MediaExtractionError(ExtractionError):
    """Failed to extract media from the post."""

    def __init__(self, message: str = "Could not extract media from this post.", code: str = "MEDIA_EXTRACTION_FAILED"):
        super().__init__(message, code=code, recoverable=True)


class PostExtractionFailed(ExtractionError):
    """Post extraction failed."""

    def __init__(self, message: str = "Could not retrieve post data from the provided URL."):
        super().__init__(message, code="POST_EXTRACTION_FAILED", recoverable=False)


class MediaExtractionFailed(ExtractionError):
    """Media extraction or download failed."""

    def __init__(self, message: str = "Could not retrieve or process post media."):
        super().__init__(message, code="MEDIA_EXTRACTION_FAILED", recoverable=False)


class ImageRenderFailed(ExtractionError):
    """Tweet card rendering failed."""

    def __init__(self, message: str = "Failed to render tweet card image."):
        super().__init__(message, code="IMAGE_RENDER_FAILED", recoverable=False)


class FontLoadFailed(ExtractionError):
    """Font loading failed during render."""

    def __init__(self, message: str = "Required fonts failed to load for rendering."):
        super().__init__(message, code="FONT_LOAD_FAILED", recoverable=False)


class VideoDownloadFailed(ExtractionError):
    """Video download failed."""

    def __init__(self, message: str = "Failed to download video stream."):
        super().__init__(message, code="VIDEO_DOWNLOAD_FAILED", recoverable=False)


class ZipCreationFailed(ExtractionError):
    """ZIP package creation failed."""

    def __init__(self, message: str = "Failed to create download ZIP archive."):
        super().__init__(message, code="ZIP_CREATION_FAILED", recoverable=False)

