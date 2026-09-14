"""Normalized post data models independent of X/yt-dlp response formats."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    """A single media attachment (image, video, or GIF)."""

    type: Literal["image", "video", "gif"]
    url: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    mime_type: str | None = None
    thumbnail_url: str | None = None
    file_size: int | None = None
    # Video-specific: available quality variants
    variants: list[MediaVariant] = Field(default_factory=list)


class MediaVariant(BaseModel):
    """A quality variant for a video/GIF."""

    url: str
    content_type: str | None = None
    bitrate: float | None = None  # yt-dlp returns tbr as float (e.g. 272.224)
    width: int | None = None
    height: int | None = None
    quality_label: str | None = None  # e.g., "1920×1080"


class QuotedPostData(BaseModel):
    """Normalized quoted post data for quote tweets."""

    id: str
    url: str | None = None
    author_name: str
    author_handle: str
    avatar_url: str | None = None
    text: str = ""
    created_at: datetime | None = None
    media: list[MediaItem] = Field(default_factory=list)


class PostData(BaseModel):
    """Normalized post data, independent of the raw X/yt-dlp response."""

    id: str
    url: str
    author_name: str
    author_handle: str
    avatar_url: str | None = None
    text: str = ""
    created_at: datetime | None = None
    reply_count: int | None = None
    repost_count: int | None = None
    like_count: int | None = None
    view_count: int | None = None
    media: list[MediaItem] = Field(default_factory=list)
    quoted_post: QuotedPostData | None = None
    source: str | None = None  # Which extractor produced this data

    @property
    def has_video(self) -> bool:
        return any(m.type == "video" for m in self.media)

    @property
    def has_images(self) -> bool:
        return any(m.type == "image" for m in self.media)

    @property
    def has_gif(self) -> bool:
        return any(m.type == "gif" for m in self.media)

    @property
    def videos(self) -> list[MediaItem]:
        return [m for m in self.media if m.type == "video"]

    @property
    def images(self) -> list[MediaItem]:
        return [m for m in self.media if m.type == "image"]

    @property
    def gifs(self) -> list[MediaItem]:
        return [m for m in self.media if m.type == "gif"]

    @property
    def all_videos(self) -> list[MediaItem]:
        vids = list(self.videos)
        if self.quoted_post and self.quoted_post.media:
            vids.extend([m for m in self.quoted_post.media if m.type == "video"])
        return vids

    @property
    def all_images(self) -> list[MediaItem]:
        imgs = list(self.images)
        if self.quoted_post and self.quoted_post.media:
            imgs.extend([m for m in self.quoted_post.media if m.type == "image"])
        return imgs

    @property
    def all_gifs(self) -> list[MediaItem]:
        g = list(self.gifs)
        if self.quoted_post and self.quoted_post.media:
            g.extend([m for m in self.quoted_post.media if m.type == "gif"])
        return g

    @property
    def all_media_items(self) -> list[MediaItem]:
        items = list(self.videos) + list(self.gifs) + list(self.images)
        if self.quoted_post and self.quoted_post.media:
            q_vids = [m for m in self.quoted_post.media if m.type == "video"]
            q_gifs = [m for m in self.quoted_post.media if m.type == "gif"]
            q_imgs = [m for m in self.quoted_post.media if m.type == "image"]
            items.extend(q_vids + q_gifs + q_imgs)
        return items

    @property
    def has_any_video(self) -> bool:
        return len(self.all_videos) > 0

    @property
    def has_any_media(self) -> bool:
        return len(self.all_media_items) > 0
