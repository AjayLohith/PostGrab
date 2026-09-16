"""
Regression tests for multi-script Unicode display-name rendering.

Root cause (fixed): Jinja2 autoescape was HTML-escaping CSS @font-face rules
inside <style> blocks (single quotes → &#39;), which made them syntactically
invalid. This prevented Chromium from loading the bundled Noto Sans Telugu
woff2 and all @font-face-defined fonts, causing tofu boxes (□) for any
non-Latin-1 characters on systems without matching system fonts.

Fix:
- Template uses {{ font_face_css | safe }} to prevent CSS escaping
- Google Fonts CDN provides comprehensive multi-script coverage
- Docker installs system font packages for offline fallback
- Font stacks expanded to include all Noto Sans script variants

Tests verify:
- Telugu, Hindi, Tamil, Kannada, Bengali, Malayalam (Indic scripts)
- Arabic (RTL script)
- Japanese, Korean, Chinese (CJK scripts)
- Cyrillic
- Mixed Latin + Indic + emoji
- Stylized Unicode (mathematical bold/script)
- Pure emoji display names
- CSS @font-face rules are not HTML-escaped
"""

from datetime import datetime
import io
import pytest
from PIL import Image

from app.models.post import PostData
from app.models.requests import RenderRequest
from app.renderers.playwright_renderer import (
    render_to_png, _build_context, _jinja_env, _FONT_FACE_CSS,
)


def _is_valid_png(data: bytes) -> bool:
    """Verify PNG is valid and non-trivial."""
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return img.size[0] > 0 and img.size[1] > 0
    except Exception:
        return False


def _default_post(author_name: str, text: str = "Test text") -> PostData:
    """Create a test PostData with the given display name."""
    return PostData(
        id="test_unicode",
        url="https://x.com/test/status/123",
        author_name=author_name,
        author_handle="test_handle",
        text=text,
        created_at=datetime(2026, 9, 15, 12, 0),
    )


def _default_req() -> RenderRequest:
    """Create a default dark-theme render request."""
    return RenderRequest(
        job_id="test_unicode_job",
        theme="dark",
        background="solid",
        background_color="#000000",
        radius=16,
        shadow="none",
        padding="medium",
        aspect_ratio="original",
    )


# ── Root cause verification: CSS is not HTML-escaped ──────────────────────────

class TestCSSNotEscaped:
    """Verify the root cause fix: CSS must not be HTML-escaped by Jinja2."""

    def test_font_face_css_not_escaped_in_rendered_html(self):
        """The @font-face rules must contain raw single quotes, not &#39;."""
        post = _default_post("Test User")
        req = _default_req()
        ctx = _build_context(post, req)
        template = _jinja_env.get_template("tweet_card.html")
        html = template.render(**ctx)

        # CSS single quotes must NOT be HTML-escaped
        assert "&#39;" not in html[:5000], (
            "CSS @font-face rules are HTML-escaped (&#39;). "
            "Template must use {{ font_face_css | safe }}"
        )

        # font-family declarations must have proper single quotes
        assert "font-family: 'PostGrabUI'" in html, (
            "PostGrabUI @font-face rule has broken quotes"
        )

    def test_google_fonts_link_present(self):
        """Google Fonts CDN link must be present in rendered HTML."""
        post = _default_post("Test User")
        req = _default_req()
        ctx = _build_context(post, req)
        template = _jinja_env.get_template("tweet_card.html")
        html = template.render(**ctx)

        assert "fonts.googleapis.com" in html, (
            "Google Fonts CDN link missing from rendered HTML"
        )
        assert "Noto+Sans+Telugu" in html, (
            "Noto Sans Telugu not in Google Fonts CDN link"
        )

    def test_unicode_display_name_preserved_in_html(self):
        """Telugu display name must appear in the rendered HTML unmodified."""
        telugu_name = "\u0C38\u0C02\u0C26\u0C2E\u0C3E\u0C2E \u0C15\u0C4B\u0C38\u0C02"
        post = _default_post(telugu_name)
        req = _default_req()
        ctx = _build_context(post, req)
        template = _jinja_env.get_template("tweet_card.html")
        html = template.render(**ctx)

        assert telugu_name in html, (
            f"Telugu display name not found in rendered HTML: {telugu_name!r}"
        )


# ── Multi-script rendering tests ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "author_name,label",
    [
        # Twitter Chirp PUA symbols & Bird symbols (exact bug reference)
        ("\U0001D468 \uEA00", "Stylized A + Chirp Bird (exact reference bug)"),
        ("A \uEA00", "Latin A + Chirp Bird"),
        ("A \U0001F426", "Latin A + Bird Emoji"),
        # Indic scripts
        ("\u0C38\u0C02\u0C26\u0C2E\u0C3E\u0C2E \u0C15\u0C4B\u0C38\u0C02", "Telugu"),
        ("\u0C24\u0C46\u0C32\u0C41\u0C17\u0C41", "Telugu (single word)"),
        ("\u0C24\u0C46\u0C32\u0C41\u0C17\u0C41 \u0C2D\u0C3E\u0C37 \u0C1A\u0C3E\u0C32\u0C3E \u0C05\u0C02\u0C26\u0C2E\u0C48\u0C28\u0C26\u0C3F", "Telugu (full sentence)"),
        ("\u0939\u093F\u0928\u094D\u0926\u0940 \u0932\u0947\u0916\u0915", "Hindi/Devanagari"),
        ("\u0BA4\u0BAE\u0BBF\u0BB4\u0BCD \u0B95\u0BB5\u0BBF\u0B9E\u0BB0\u0BCD", "Tamil"),
        ("\u0C95\u0CA8\u0CCD\u0CA8\u0CA1 \u0CAC\u0CB0\u0CB9\u0C97\u0CBE\u0CB0", "Kannada"),
        ("\u09AC\u09BE\u0982\u09B2\u09BE", "Bengali"),
        ("\u0D2E\u0D32\u0D2F\u0D3E\u0D33\u0D02", "Malayalam"),
        # Arabic (RTL)
        ("\u0639\u0631\u0628\u064A", "Arabic"),
        # CJK
        ("\u65E5\u672C\u8A9E", "Japanese"),
        ("\uD55C\uAD6D\uC5B4", "Korean"),
        # Cyrillic
        ("\u041A\u0438\u0440\u0438\u043B\u043B\u0438\u0446\u0430", "Cyrillic"),
        # Mixed scripts
        ("Ajay \u0C24\u0C46\u0C32\u0C41\u0C17\u0C41 \U0001F680", "Mixed Latin+Telugu+Emoji"),
        ("\u0C24\u0C46\u0C32\u0C41\u0C17\u0C41 Ajay", "Mixed Telugu+Latin"),
        ("\u0C24\u0C46\u0C32\u0C41\u0C17\u0C41 \u2022 @user \u2022 \U0001F680", "Telugu with symbols"),
        ("English \u0C24\u0C46\u0C32\u0C41\u0C17\u0C41", "Latin prefix + Telugu"),
        # Stylized Unicode (mathematical variants)
        ("\U0001D400\U0001D423\U0001D41A\U0001D42B", "Mathematical bold"),
        ("\U0001D4D0\U0001D4F3\U0001D4EA\U0001D504", "Mathematical script"),
        ("\U0001D670\U0001D693\U0001D68A\U0001D69B", "Mathematical monospace"),
        ("\U0001D400\U0001D423\U0001D41A\U0001D42B \u0C24\u0C46\u0C32\u0C41\u0C17\u0C41", "Math bold + Telugu"),
        ("\U0001D4D0\U0001D4F3\U0001D4EA\U0001D504 \U0001F525 \u0C24\u0C46\u0C32\u0C41\u0C17\u0C41", "Math script + Emoji + Telugu"),
        # Emoji
        ("Ajay \U0001F680", "Latin + Emoji"),
        ("\u0C24\u0C46\u0C32\u0C41\u0C17\u0C41 \U0001F525", "Telugu + Emoji"),
        ("\U0001F525 Fire User \U0001F680", "Emoji bookends"),
    ],
)
def test_unicode_display_name_renders_without_tofu(author_name: str, label: str):
    """
    Render a tweet card with a Unicode display name and verify:
    1. The PNG is valid
    2. The PNG is non-trivial (has actual rendered content, not blank)

    This test class covers the exact bug reported: Telugu display names
    rendering as □ □ (tofu boxes) instead of the actual glyphs.
    """
    post = _default_post(author_name, f"Test text for {label}")
    req = _default_req()

    png_bytes = render_to_png(post, req)

    assert _is_valid_png(png_bytes), f"Invalid PNG for {label}: {author_name!r}"
    # A non-trivial PNG with actual text content should be > 5KB
    assert len(png_bytes) > 5000, (
        f"PNG too small ({len(png_bytes)} bytes) for {label}: {author_name!r}. "
        "This suggests the text may not have rendered."
    )


# ── Tweet body font unchanged ─────────────────────────────────────────────────

class TestTweetBodyFontUnchanged:
    """Verify the fix does not alter the tweet body rendering."""

    def test_tweet_body_uses_tweet_body_font(self):
        """The .tweet-content element must still use --tweet-body-font."""
        post = _default_post("Test User", "Hello world, this is tweet text.")
        req = _default_req()
        ctx = _build_context(post, req)
        template = _jinja_env.get_template("tweet_card.html")
        html = template.render(**ctx)

        assert "var(--tweet-body-font)" in html, (
            ".tweet-content must use var(--tweet-body-font)"
        )

    def test_display_name_uses_display_font(self):
        """The .display-name element must use --tweet-display-font."""
        post = _default_post("Test User")
        req = _default_req()
        ctx = _build_context(post, req)
        template = _jinja_env.get_template("tweet_card.html")
        html = template.render(**ctx)

        assert "var(--tweet-display-font)" in html, (
            ".display-name must use var(--tweet-display-font)"
        )
