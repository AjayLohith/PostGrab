"""API request and response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.post import PostData


class ExtractRequest(BaseModel):
    """Request to extract post data from an X URL."""
    url: str


class RenderRequest(BaseModel):
    """Request to render a tweet card image."""
    job_id: str
    theme: Literal["light", "dark", "glass", "minimal", "editorial", "terminal"] = "light"
    background: str = "solid"  # solid, blur
    background_color: str | None = "#ffffff"
    background_gradient: list[str] | None = None
    background_image_url: str | None = None
    radius: int = 16
    shadow: Literal["none", "soft", "medium", "strong"] = "none"
    padding: Literal["small", "medium", "large"] = "medium"
    aspect_ratio: Literal["original", "1:1", "4:5", "16:9", "9:16"] = "original"
    preset: str | None = None


class DownloadMediaRequest(BaseModel):
    """Request to download media files for a job."""
    job_id: str
    media_index: int = 0
    quality: str = "best"


class Capabilities(BaseModel):
    """What's available for download from this post."""
    tweet_image: bool = True
    video: bool = False
    gif: bool = False
    images: bool = False
    download_all: bool = False
    video_qualities: list[dict] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    """Response from post extraction."""
    job_id: str
    post: PostData
    capabilities: Capabilities


class RenderResponse(BaseModel):
    """Response from tweet image rendering."""
    job_id: str
    asset_id: str
    filename: str
    size: int


class ErrorResponse(BaseModel):
    """User-friendly error response."""
    error: str
    detail: str | None = None
    code: str | None = None
