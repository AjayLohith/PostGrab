"""
Playwright-based tweet card renderer.

Renders the tweet_card.html Jinja2 template using a headless Chromium
browser, producing a deterministic high-quality PNG with full Unicode,
emoji, and multi-script support through the browser's text engine.

No manual pixel positioning, coordinate calculations, or Pillow rendering.
The browser is the sole layout engine.
"""

from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.models.post import PostData
from app.models.requests import RenderRequest
from app.extractors.base import ImageRenderFailed

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"

# ── Canvas sizes for aspect ratios ───────────────────────────────────────────
CANVAS_SIZES: dict[str, tuple[int, int] | None] = {
    "original": None,
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1280, 720),
    "9:16": (1080, 1920),
}

PADDING_MAP = {"small": 24, "medium": 44, "large": 64}
CARD_PADDING_MAP = {"small": 20, "medium": 28, "large": 38}

# Device pixel ratio — renders at 2× for retina quality
DEVICE_SCALE = 2

# t.co and pic.twitter.com cleanup
_TCO_RE = re.compile(r"(\S)(https?://t\.co/\S+)", re.IGNORECASE)
_TCO_STRIP = re.compile(r"\s*(?:https?://)?(?:pic\.(?:twitter|x)\.com|t\.co)/\S+", re.IGNORECASE)


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = _TCO_RE.sub(r"\1 \2", text)
    text = _TCO_STRIP.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_ENTITY_RE = re.compile(r"(^|[^a-zA-Z0-9_])([@#][a-zA-Z0-9_]{1,30})")


def _format_tweet_text(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    safe = html.escape(cleaned, quote=False)
    return _ENTITY_RE.sub(r'\1<span class="tweet-entity">\2</span>', safe)


def _fmt_count(n: int | None) -> str | None:
    if n is None:
        return None
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_date(dt: datetime | None) -> str:
    if not dt:
        return ""
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.strftime('%M')} {ampm} · {dt.strftime('%b')} {dt.day}, {dt.year}"


def _to_data_uri(path_or_bytes: Path | bytes, mime_type: str = "image/png") -> str:
    """Convert a file path or raw bytes to a base64 data URI."""
    if isinstance(path_or_bytes, Path):
        data = path_or_bytes.read_bytes()
    else:
        data = path_or_bytes
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


# ── Font strategy ────────────────────────────────────────────────────────────
def _build_font_face_css() -> str:
    """
    Generate @font-face rules using local() src references.
    Allows Chromium to resolve native OS fonts (Segoe UI, Roboto, DejaVu, Noto).
    """
    return """
@font-face {
    font-family: 'PostGrabUI';
    src: local('Segoe UI'), local('segoeui'), local('Roboto'), local('Helvetica Neue'), local('Arial');
    font-weight: 400;
    font-style: normal;
}
@font-face {
    font-family: 'PostGrabUI';
    src: local('Segoe UI Bold'), local('segoeuib'), local('Roboto Bold'), local('Helvetica Neue Bold'), local('Arial Bold');
    font-weight: 700;
    font-style: normal;
}
/* Linux/Docker fallback */
@font-face {
    font-family: 'PostGrabUI';
    src: local('DejaVu Sans'), local('Liberation Sans');
    font-weight: 400;
    font-style: normal;
}
"""


_FONT_FACE_CSS = _build_font_face_css()


# ── Jinja2 environment ────────────────────────────────────────────────────────
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


# ── Playwright browser singleton ──────────────────────────────────────────────
_browser_lock = threading.Lock()
_thread_state = threading.local()
_browser_instances: dict[int, tuple[Any, Any]] = {}


def _get_browser():
    """Get or create the Chromium browser for the current worker thread."""
    thread_id = threading.get_ident()
    browser = getattr(_thread_state, "browser", None)
    if browser is not None and browser.is_connected():
        return browser

    with _browser_lock:
        browser = getattr(_thread_state, "browser", None)
        if browser is not None and browser.is_connected():
            return browser

        try:
            from playwright.sync_api import sync_playwright

            playwright_instance = sync_playwright().start()
            browser = playwright_instance.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--font-render-hinting=none",
                ],
            )
            _thread_state.playwright = playwright_instance
            _thread_state.browser = browser
            _browser_instances[thread_id] = (playwright_instance, browser)
            logger.info("Playwright Chromium browser started for thread %s.", thread_id)
            return browser
        except Exception as e:
            logger.error("Failed to start Playwright browser: %s", e)
            raise


def shutdown_browser():
    """Gracefully close the browser on application shutdown."""
    with _browser_lock:
        instances = list(_browser_instances.values())
        _browser_instances.clear()
        for playwright_instance, browser in instances:
            try:
                browser.close()
            except Exception:
                pass
            try:
                playwright_instance.stop()
            except Exception:
                pass
        _thread_state.browser = None
        _thread_state.playwright = None
    logger.info("Playwright browser shut down.")


def _shutdown_current_thread_browser() -> None:
    """Close the current thread's sync driver without touching other workers."""
    thread_id = threading.get_ident()
    with _browser_lock:
        instance = _browser_instances.pop(thread_id, None)
        _thread_state.browser = None
        _thread_state.playwright = None

    if instance is None:
        return

    playwright_instance, browser = instance
    try:
        browser.close()
    finally:
        playwright_instance.stop()


# ── Template context builder ──────────────────────────────────────────────────

def _build_context(
    post: PostData,
    request: RenderRequest,
    resolved_assets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Jinja2 template context from post data, render options, and local assets."""
    resolved_assets = resolved_assets or {}

    # Canvas dimensions
    preset = CANVAS_SIZES.get(request.aspect_ratio)
    outer_padding = PADDING_MAP.get(request.padding, 44)
    card_padding = CARD_PADDING_MAP.get(request.padding, 28)

    if preset:
        canvas_width, canvas_height = preset
    else:
        canvas_width = 780
        canvas_height = 0  # auto-height via element capture

    # Background
    default_bg = "#ffffff" if request.theme == "light" else "#000000"
    background_color = request.background_color or default_bg
    gradient_colors = ", ".join(request.background_gradient or ["#0f0c29", "#302b63"])

    # Mesh gradient colors
    mesh_colors = request.background_gradient or ["#667eea40", "#764ba240", "#f953c640", "#b91d7340", "#667eea40"]
    mesh_color_1 = mesh_colors[0] if len(mesh_colors) > 0 else "#667eea40"
    mesh_color_2 = mesh_colors[1] if len(mesh_colors) > 1 else "#764ba240"
    mesh_color_3 = mesh_colors[2] if len(mesh_colors) > 2 else "#f953c640"
    mesh_color_4 = mesh_colors[3] if len(mesh_colors) > 3 else "#b91d7340"
    mesh_color_5 = mesh_colors[4] if len(mesh_colors) > 4 else "#667eea40"
    mesh_base = "#0d1117"

    # Avatar resolution: prefer pre-resolved local asset / data URI
    avatar_url = resolved_assets.get("avatar") or post.avatar_url or ""

    # Media resolution: prefer pre-resolved local assets / data URIs
    images = resolved_assets.get("images", post.images[:4])
    has_video = post.has_video or post.has_gif
    video_item = post.videos[0] if post.has_video else (post.gifs[0] if post.has_gif else None)
    video_thumbnail = resolved_assets.get("video_thumbnail") or (video_item.thumbnail_url if video_item else "")

    # Metrics
    reply_fmt   = _fmt_count(post.reply_count)
    repost_fmt  = _fmt_count(post.repost_count)
    like_fmt    = _fmt_count(post.like_count)
    view_fmt    = _fmt_count(post.view_count)
    has_metrics = any(x is not None for x in [post.reply_count, post.repost_count, post.like_count, post.view_count])

    # Avatar initial for placeholder when no avatar exists
    avatar_initial = (post.author_name or post.author_handle or "?")[0].upper()

    # Radius for media (slightly less than card radius)
    media_radius = max(0, request.radius - 4)

    # Quoted post context
    quoted = None
    if post.quoted_post:
        qp = post.quoted_post
        q_has_video = any(m.type in ("video", "gif") for m in qp.media)
        q_video_item = [m for m in qp.media if m.type in ("video", "gif")]
        q_video_thumb = resolved_assets.get("quoted_video_thumbnail") or (q_video_item[0].thumbnail_url if q_video_item else "")
        q_images = resolved_assets.get("quoted_images") or [m.url for m in qp.media if m.type == "image"]
        quoted = {
            "author_name": qp.author_name or qp.author_handle,
            "author_handle": qp.author_handle,
            "avatar_url": resolved_assets.get("quoted_avatar") or qp.avatar_url or "",
            "avatar_initial": (qp.author_name or qp.author_handle or "?")[0].upper(),
            "text": _format_tweet_text(qp.text or ""),
            "date_str": _fmt_date(qp.created_at),
            "has_video": q_has_video,
            "video_thumbnail": q_video_thumb or "",
            "images": q_images,
        }

    return {
        # Layout
        "canvas_width":   canvas_width,
        "canvas_height":  canvas_height,
        "outer_padding":  outer_padding,
        "card_padding":   card_padding,
        "media_radius":   media_radius,
        # Style
        "theme":            request.theme,
        "background":       request.background,
        "background_color": background_color,
        "gradient_colors":  gradient_colors,
        "mesh_color_1":     mesh_color_1,
        "mesh_color_2":     mesh_color_2,
        "mesh_color_3":     mesh_color_3,
        "mesh_color_4":     mesh_color_4,
        "mesh_color_5":     mesh_color_5,
        "mesh_base":        mesh_base,
        "background_image_data": "",
        "radius":           request.radius,
        "shadow":           request.shadow,
        # Post
        "url":              post.url,
        "author_name":      post.author_name or post.author_handle,
        "author_handle":    post.author_handle,
        "avatar_url":       avatar_url,
        "avatar_initial":   avatar_initial,
        "date_str":         _fmt_date(post.created_at),
        "text":             _format_tweet_text(post.text or ""),
        # Quoted post
        "quoted":           quoted,
        # Media
        "media_images":     images,
        "has_video":        has_video,
        "video_thumbnail":  video_thumbnail or "",
        # Metrics
        "has_metrics":      has_metrics,
        "reply_count_fmt":  reply_fmt or "0",
        "repost_count_fmt": repost_fmt or "0",
        "like_count_fmt":   like_fmt or "0",
        "view_count_fmt":   view_fmt or "",
        "reply_count":      post.reply_count,
        "repost_count":     post.repost_count,
        "like_count":       post.like_count,
        "view_count":       post.view_count,
        # Fonts
        "font_face_css":    _FONT_FACE_CSS,
    }


# ── Main render function ──────────────────────────────────────────────────────

def render_to_png(
    post: PostData,
    request: RenderRequest,
    resolved_assets: dict[str, Any] | None = None,
) -> bytes:
    """
    Render a tweet card PNG using Playwright + Chromium.

    Runs synchronously — call via run_in_executor to avoid blocking async event loop.

    Returns:
        PNG bytes at DEVICE_SCALE× resolution
    """
    context = _build_context(post, request, resolved_assets)
    template = _jinja_env.get_template("tweet_card.html")
    html = template.render(**context)

    browser = _get_browser()
    page = browser.new_page(
        viewport={"width": context["canvas_width"] or 780, "height": 2400},
        device_scale_factor=DEVICE_SCALE,
    )

    try:
        page.set_content(html, wait_until="load")

        # Section 19 & 24: Wait for all fonts to be ready
        page.evaluate("() => document.fonts.ready")

        # Section 24 & 25: Wait for all images to load and verify natural dimensions
        page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            return Promise.all(imgs.map(img => {
                if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                return new Promise((resolve, reject) => {
                    img.addEventListener('load', () => {
                        if (img.naturalWidth > 0) resolve();
                        else reject(new Error('Image failed to decode (naturalWidth === 0)'));
                    });
                    img.addEventListener('error', () => {
                        reject(new Error('Image failed to load: ' + (img.src ? img.src.substring(0, 100) : 'unknown')));
                    });
                    setTimeout(() => {
                        if (img.complete && img.naturalWidth > 0) resolve();
                        else reject(new Error('Image load timed out: ' + (img.src ? img.src.substring(0, 100) : 'unknown')));
                    }, 3000);
                });
            }));
        }""")

        # Screenshot the wrapper element (auto-clips to content height)
        preset = CANVAS_SIZES.get(request.aspect_ratio)
        if preset:
            # Fixed canvas — screenshot clipped to exact preset dimensions
            png = page.screenshot(
                full_page=False,
                clip={"x": 0, "y": 0, "width": preset[0], "height": preset[1]},
            )
        else:
            # Auto-height — screenshot the wrapper element cleanly
            wrapper = page.locator("#capture")
            png = wrapper.screenshot()

        return png

    except Exception as e:
        logger.error("Playwright rendering error: %s", e)
        raise ImageRenderFailed(f"Chromium render error: {e}") from e

    finally:
        page.close()
        if threading.current_thread() is threading.main_thread():
            _shutdown_current_thread_browser()
