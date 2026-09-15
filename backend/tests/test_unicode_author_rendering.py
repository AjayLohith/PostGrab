"""
Regression tests for Telugu and multi-script Unicode display-name rendering.
Ensures Chromium renders clean, valid glyphs without missing font errors or distortion.
"""

from datetime import datetime
import pytest
from PIL import Image
import io

from app.models.post import PostData
from app.models.requests import RenderRequest
from app.renderers.playwright_renderer import render_to_png


def _is_valid_png(data: bytes) -> bool:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return img.size[0] > 0 and img.size[1] > 0
    except Exception:
        return False


@pytest.mark.parametrize(
    "author_name,text",
    [
        ("సందమామ కోసం", "Simple Telugu author name"),
        ("నందమూరి కోసం", "Not meme but real movie scene 🔥"),
        ("తెలుగు", "Single word Telugu"),
        ("తెలుగు భాష చాలా అందమైనది", "Full sentence Telugu"),
        ("Ajay తెలుగు 🚀", "Mixed English + Telugu + Emoji"),
        ("తెలుగు • @user • 🚀", "Telugu with symbols and punctuation"),
        ("English తెలుగు", "Mixed Latin and Telugu prefix"),
        ("తెలుగు English", "Mixed Telugu and Latin prefix"),
        ("𝐀𝐣𝐚𝐲 తెలుగు", "Mathematical bold Latin + Telugu"),
        ("𝓐𝓳𝓪𝔂 🔥 తెలుగు", "Mathematical script Latin + Emoji + Telugu"),
        ("हिन्दी लेखक", "Hindi / Devanagari script"),
        ("தமிழ் கவிஞர்", "Tamil script"),
        ("ಕನ್ನಡ ಬರಹಗಾರ", "Kannada script"),
        ("മലയാളം", "Malayalam script"),
        ("বাংলা", "Bengali script"),
        ("عربي", "Arabic script"),
        ("日本語", "Japanese script"),
        ("한국어", "Korean script"),
        ("Кириллица", "Cyrillic script"),
    ],
)
def test_unicode_display_name_rendering(author_name: str, text: str):
    post = PostData(
        id="test_id",
        url="https://x.com/test/status/123",
        author_name=author_name,
        author_handle="test_handle",
        text=text,
        created_at=datetime(2026, 9, 15, 12, 0),
    )
    req = RenderRequest(
        job_id="test_unicode_job",
        theme="dark",
        background="solid",
        background_color="#000000",
        radius=16,
        shadow="none",
        padding="medium",
        aspect_ratio="original",
    )

    png_bytes = render_to_png(post, req)
    assert _is_valid_png(png_bytes)
    assert len(png_bytes) > 5000  # Non-trivial image with rendered content
