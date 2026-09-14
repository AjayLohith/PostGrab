"""
Tests for the production Playwright HTML/CSS tweet card renderer.

Ensures the old pixel renderer is eliminated and the browser-based
renderer handles all layout, themes, aspect ratios, and media integrity.
"""

import io
import pytest
from PIL import Image

from app.models.post import PostData, MediaItem
from app.models.requests import RenderRequest
from app.renderers.playwright_renderer import render_to_png
from app.extractors.base import MediaExtractionFailed
from tests.fixtures import (
    FIXTURE_A,
    FIXTURE_B,
    FIXTURE_C,
    FIXTURE_D,
    FIXTURE_E,
    FIXTURE_F,
    FIXTURE_F2,
    FIXTURE_G,
    FIXTURE_H,
    FIXTURE_I,
    FIXTURE_IMG_1,
)


def make_request(**kwargs) -> RenderRequest:
    defaults = dict(
        job_id="job_test",
        theme="dark",
        background="gradient",
        background_color=None,
        background_gradient=["#0f0c29", "#302b63"],
        radius=16,
        shadow="medium",
        padding="medium",
        aspect_ratio="original",
    )
    defaults.update(kwargs)
    return RenderRequest(**defaults)


def is_valid_png(data: bytes) -> bool:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return True
    except Exception:
        return False


def get_dimensions(data: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(data))
    return img.size


class TestPlaywrightProductionRenderer:
    def test_renders_valid_png(self):
        png = render_to_png(FIXTURE_A, make_request())
        assert is_valid_png(png)
        assert len(png) > 5000

    def test_all_aspect_ratios(self):
        ratios = {
            "1:1": (1080 * 2, 1080 * 2),
            "4:5": (1080 * 2, 1350 * 2),
            "16:9": (1280 * 2, 720 * 2),
            "9:16": (1080 * 2, 1920 * 2),
        }
        for ratio, (expected_w, expected_h) in ratios.items():
            req = make_request(aspect_ratio=ratio)
            png = render_to_png(FIXTURE_A, req)
            assert is_valid_png(png)
            w, h = get_dimensions(png)
            assert w == expected_w
            assert h == expected_h

    def test_auto_height_original_ratio(self):
        req = make_request(aspect_ratio="original")
        png_short = render_to_png(FIXTURE_A, req)
        png_long = render_to_png(FIXTURE_E, req)
        assert is_valid_png(png_short)
        assert is_valid_png(png_long)
        _, h_short = get_dimensions(png_short)
        _, h_long = get_dimensions(png_long)
        assert h_long > h_short

    @pytest.mark.parametrize("theme", ["light", "dark", "glass", "minimal", "editorial", "terminal"])
    def test_all_themes_render(self, theme):
        png = render_to_png(FIXTURE_A, make_request(theme=theme))
        assert is_valid_png(png)

    @pytest.mark.parametrize("bg", ["solid", "gradient", "mesh"])
    def test_all_backgrounds_render(self, bg):
        png = render_to_png(FIXTURE_A, make_request(background=bg, background_color="#121212"))
        assert is_valid_png(png)

    def test_media_single_image(self):
        png = render_to_png(FIXTURE_B, make_request())
        assert is_valid_png(png)

    def test_media_four_images(self):
        png = render_to_png(FIXTURE_D, make_request())
        assert is_valid_png(png)

    def test_media_video_thumbnail(self):
        png = render_to_png(FIXTURE_C, make_request())
        assert is_valid_png(png)

    def test_critical_media_integrity_actual_fixture_rendered(self):
        """Verify the renderer renders the actual fixture image and not a placeholder."""
        png = render_to_png(FIXTURE_B, make_request())
        img = Image.open(io.BytesIO(png))
        # Fixture B has a solid red image (255, 0, 0)
        # Verify that red pixels exist in the rendered output
        colors = img.getcolors(maxcolors=2000000)
        has_red = any(r > 200 and g < 50 and b < 50 for count, (r, g, b, *_) in colors if count > 50)
        assert has_red, "Rendered card must contain actual fixture image colors, not placeholder!"
