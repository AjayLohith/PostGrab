"""
Tests for the Playwright tweet card renderer.

All tests use deterministic fixtures — no live network calls.
The only network activity is Chromium loading avatar URLs from pbs.twimg.com
in Fixture B; all others use no avatar (placeholder fallback).
"""

import io
import pytest
from PIL import Image

from app.models.requests import RenderRequest
from app.renderers.playwright_renderer import render_to_png, _clean_text
from tests.fixtures import (
    ALL_FIXTURES,
    FIXTURE_A, FIXTURE_B, FIXTURE_C, FIXTURE_D, FIXTURE_E,
    FIXTURE_F, FIXTURE_F2, FIXTURE_G, FIXTURE_H, FIXTURE_I,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def default_req(**kwargs) -> RenderRequest:
    defaults = dict(
        job_id="test",
        theme="dark",
        background="gradient",
        background_color=None,
        background_gradient=None,
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


def png_dimensions(data: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(data))
    return img.size  # (width, height)


# ── t.co cleanup unit tests (no Chromium) ─────────────────────────────────────

class TestCleanText:
    def test_strips_trailing_tco(self):
        result = _clean_text("Hello world https://t.co/abc123")
        assert "t.co" not in result
        assert "Hello world" in result

    def test_detaches_glued_tco(self):
        result = _clean_text("timehttps://t.co/xafYzbRGcD")
        assert "t.co" not in result
        assert "time" in result

    def test_preserves_text_without_tco(self):
        text = "This is a normal tweet without any short links."
        assert _clean_text(text) == text

    def test_empty_string(self):
        assert _clean_text("") == ""

    def test_only_tco(self):
        result = _clean_text("https://t.co/abc123")
        assert result == ""

    def test_multiple_tco_stripped(self):
        result = _clean_text("word1 https://t.co/abc word2 https://t.co/def")
        assert "t.co" not in result

    def test_collapses_extra_newlines(self):
        result = _clean_text("line1\n\n\n\nline2")
        assert "\n\n\n" not in result


# ── Playwright renderer — all fixtures ───────────────────────────────────────

class TestPlaywrightRenderer:
    """Each test renders a fixture and verifies the PNG is valid."""

    def test_fixture_a_text_only(self):
        png = render_to_png(FIXTURE_A, default_req())
        assert is_valid_png(png)
        assert len(png) > 10_000

    def test_fixture_b_single_image(self):
        # Image URL will 404 in test — renderer should handle gracefully
        png = render_to_png(FIXTURE_B, default_req())
        assert is_valid_png(png)

    def test_fixture_c_video_thumbnail(self):
        png = render_to_png(FIXTURE_C, default_req())
        assert is_valid_png(png)

    def test_fixture_d_four_images(self):
        png = render_to_png(FIXTURE_D, default_req())
        assert is_valid_png(png)

    def test_fixture_e_long_text(self):
        png = render_to_png(FIXTURE_E, default_req())
        assert is_valid_png(png)
        # Long text should produce a taller card than short text
        _, h_long = png_dimensions(png)
        png_short = render_to_png(FIXTURE_A, default_req())
        _, h_short = png_dimensions(png_short)
        # Long card must be at least as tall (2x device scale applied)
        assert h_long >= h_short

    def test_fixture_f_unicode_script_name(self):
        """Unicode mathematical script chars must not crash the renderer."""
        png = render_to_png(FIXTURE_F, default_req())
        assert is_valid_png(png)

    def test_fixture_f2_unicode_bold_name(self):
        png = render_to_png(FIXTURE_F2, default_req())
        assert is_valid_png(png)

    def test_fixture_g_emoji(self):
        """Emoji in tweet text must render without crashing."""
        png = render_to_png(FIXTURE_G, default_req())
        assert is_valid_png(png)

    def test_fixture_h_non_english_telugu(self):
        """Telugu script must render without crashing."""
        png = render_to_png(FIXTURE_H, default_req())
        assert is_valid_png(png)

    def test_fixture_i_long_username(self):
        png = render_to_png(FIXTURE_I, default_req())
        assert is_valid_png(png)


# ── All themes ────────────────────────────────────────────────────────────────

class TestAllThemes:
    @pytest.mark.parametrize("theme", ["light", "dark", "glass", "minimal", "editorial", "terminal"])
    def test_theme_renders(self, theme):
        png = render_to_png(FIXTURE_A, default_req(theme=theme))
        assert is_valid_png(png), f"Theme {theme} did not produce valid PNG"


# ── All backgrounds ───────────────────────────────────────────────────────────

class TestAllBackgrounds:
    @pytest.mark.parametrize("bg,color,grad", [
        ("solid",    "#ffffff", None),
        ("solid",    "#0f0c29", None),
        ("gradient", None,      ["#fc466b", "#3f5efb"]),
        ("mesh",     None,      ["#667eea", "#764ba2", "#f953c6"]),
    ])
    def test_background_renders(self, bg, color, grad):
        png = render_to_png(
            FIXTURE_A,
            default_req(background=bg, background_color=color, background_gradient=grad),
        )
        assert is_valid_png(png)


# ── Aspect ratios ─────────────────────────────────────────────────────────────

class TestAspectRatios:
    @pytest.mark.parametrize("ratio,expected_w,expected_h", [
        ("1:1",  1080, 1080),
        ("4:5",  1080, 1350),
        ("16:9", 1280, 720),
        ("9:16", 1080, 1920),
    ])
    def test_fixed_ratio_dimensions(self, ratio, expected_w, expected_h):
        png = render_to_png(FIXTURE_A, default_req(aspect_ratio=ratio))
        assert is_valid_png(png)
        w, h = png_dimensions(png)
        # device_scale=2 so actual pixel dims are 2×
        assert w == expected_w * 2, f"Expected width {expected_w*2}, got {w}"
        assert h == expected_h * 2, f"Expected height {expected_h*2}, got {h}"

    def test_original_ratio_is_auto_height(self):
        png = render_to_png(FIXTURE_A, default_req(aspect_ratio="original"))
        assert is_valid_png(png)
        w, h = png_dimensions(png)
        # Width should be 780px * 2 = 1560px; height is flexible
        assert w == 780 * 2


# ── Shadow and radius ─────────────────────────────────────────────────────────

class TestShadowAndRadius:
    @pytest.mark.parametrize("shadow", ["none", "soft", "medium", "strong"])
    def test_shadow_renders(self, shadow):
        png = render_to_png(FIXTURE_A, default_req(shadow=shadow))
        assert is_valid_png(png)

    @pytest.mark.parametrize("radius", [0, 8, 16, 24, 32])
    def test_radius_renders(self, radius):
        png = render_to_png(FIXTURE_A, default_req(radius=radius))
        assert is_valid_png(png)


# ── Padding ───────────────────────────────────────────────────────────────────

class TestPadding:
    @pytest.mark.parametrize("padding", ["small", "medium", "large"])
    def test_padding_renders(self, padding):
        png = render_to_png(FIXTURE_A, default_req(padding=padding))
        assert is_valid_png(png)
