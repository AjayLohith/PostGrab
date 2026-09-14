"""
Deterministic test fixtures for PostGrab tests.

These fixtures never make external network calls — they represent known post shapes
with authentic fixture media (embedded local data URIs) that can be used to test
the renderer, downloader, and API deterministically.
"""

import base64
from datetime import datetime, timezone
from pathlib import Path

from app.models.post import PostData, MediaItem, MediaVariant

FIXTURES_DIR = Path(__file__).parent / "fixtures_data"


def _get_data_uri(filename: str, mime: str = "image/jpeg") -> str:
    path = FIXTURES_DIR / filename
    if path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    # Fallback minimal 1x1 data URI if file not yet generated
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


FIXTURE_IMG_1 = _get_data_uri("img1.jpg")
FIXTURE_IMG_2 = _get_data_uri("img2.jpg")
FIXTURE_IMG_3 = _get_data_uri("img3.jpg")
FIXTURE_IMG_4 = _get_data_uri("img4.jpg")
FIXTURE_THUMB = _get_data_uri("thumb.jpg")
FIXTURE_AVATAR = _get_data_uri("avatar.jpg")

# ── Fixture A: Text only ──────────────────────────────────────────────────────
FIXTURE_A = PostData(
    id="1000000000000000001",
    url="https://x.com/testuser/status/1000000000000000001",
    author_name="Test User",
    author_handle="testuser",
    avatar_url=None,
    text="This is a plain text tweet with no media attached.",
    created_at=datetime(2024, 3, 15, 14, 30, 0, tzinfo=timezone.utc),
    reply_count=5,
    repost_count=12,
    like_count=87,
    view_count=1200,
    media=[],
    source="fixture",
)

# ── Fixture B: Text + one actual fixture image ─────────────────────────────────
FIXTURE_B = PostData(
    id="1000000000000000002",
    url="https://x.com/imageuser/status/1000000000000000002",
    author_name="Image User",
    author_handle="imageuser",
    avatar_url=FIXTURE_AVATAR,
    text="Here is a tweet with a single attached image.",
    created_at=datetime(2024, 4, 20, 9, 0, 0, tzinfo=timezone.utc),
    reply_count=3,
    repost_count=8,
    like_count=44,
    view_count=None,
    media=[
        MediaItem(
            type="image",
            url=FIXTURE_IMG_1,
            width=1200,
            height=675,
            mime_type="image/jpeg",
        )
    ],
    source="fixture",
)

# ── Fixture C: Text + video with authentic thumbnail ──────────────────────────
FIXTURE_C = PostData(
    id="1000000000000000003",
    url="https://x.com/videouser/status/1000000000000000003",
    author_name="Video User",
    author_handle="videouser",
    avatar_url=None,
    text="Check out this video clip!",
    created_at=datetime(2024, 5, 10, 18, 45, 0, tzinfo=timezone.utc),
    reply_count=15,
    repost_count=30,
    like_count=200,
    view_count=5000,
    media=[
        MediaItem(
            type="video",
            url=str(FIXTURES_DIR / "sample.mp4"),
            width=1280,
            height=720,
            duration=30.5,
            mime_type="video/mp4",
            thumbnail_url=FIXTURE_THUMB,
            variants=[
                MediaVariant(url=str(FIXTURES_DIR / "sample.mp4"), width=1280, height=720, bitrate=2176000.0, quality_label="1280×720"),
            ],
        )
    ],
    source="fixture",
)

# ── Fixture D: Text + four actual fixture images ───────────────────────────────
FIXTURE_D = PostData(
    id="1000000000000000004",
    url="https://x.com/multiimg/status/1000000000000000004",
    author_name="Multi Image",
    author_handle="multiimg",
    avatar_url=None,
    text="Four images in this tweet.",
    created_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    reply_count=None,
    repost_count=None,
    like_count=None,
    view_count=None,
    media=[
        MediaItem(type="image", url=FIXTURE_IMG_1, width=800, height=600, mime_type="image/jpeg"),
        MediaItem(type="image", url=FIXTURE_IMG_2, width=800, height=600, mime_type="image/jpeg"),
        MediaItem(type="image", url=FIXTURE_IMG_3, width=800, height=600, mime_type="image/jpeg"),
        MediaItem(type="image", url=FIXTURE_IMG_4, width=800, height=600, mime_type="image/jpeg"),
    ],
    source="fixture",
)

# ── Fixture E: Long tweet ─────────────────────────────────────────────────────
FIXTURE_E = PostData(
    id="1000000000000000005",
    url="https://x.com/longtweet/status/1000000000000000005",
    author_name="Long Tweeter",
    author_handle="longtweet",
    avatar_url=None,
    text=(
        "This is a significantly longer tweet that contains many words and should "
        "wrap naturally across multiple lines without any manual line breaks being "
        "inserted. The renderer should handle this gracefully and produce a card "
        "that is tall enough to contain all the text without clipping or overflow. "
        "Testing line wrapping behavior is important for real-world tweet content."
    ),
    created_at=datetime(2024, 7, 4, 20, 0, 0, tzinfo=timezone.utc),
    reply_count=100,
    repost_count=200,
    like_count=1500,
    view_count=25000,
    media=[],
    source="fixture",
)

# ── Fixture F: Unicode / stylized script display name ─────────────────────────
FIXTURE_F = PostData(
    id="1000000000000000006",
    url="https://x.com/unicodename/status/1000000000000000006",
    author_name="𝓢𝓬𝓻𝓲𝓹𝓽 𝓝𝓪𝓶𝓮",  # Unicode mathematical script chars — must NOT be normalized
    author_handle="unicodename",
    avatar_url=None,
    text="My display name uses Unicode mathematical script characters. They should be preserved exactly.",
    created_at=datetime(2024, 8, 15, 8, 0, 0, tzinfo=timezone.utc),
    reply_count=7,
    repost_count=3,
    like_count=55,
    view_count=800,
    media=[],
    source="fixture",
)

# ── Fixture F2: Unicode bold display name ─────────────────────────────────────
FIXTURE_F2 = PostData(
    id="1000000000000000007",
    url="https://x.com/boldname/status/1000000000000000007",
    author_name="𝐁𝐨𝐥𝐝 𝐍𝐚𝐦𝐞",  # Unicode mathematical bold chars
    author_handle="boldname",
    avatar_url=None,
    text="Bold Unicode display name. Tweet body should use consistent font regardless.",
    created_at=None,
    reply_count=None,
    repost_count=None,
    like_count=None,
    view_count=None,
    media=[],
    source="fixture",
)

# ── Fixture G: Emoji-heavy tweet ──────────────────────────────────────────────
FIXTURE_G = PostData(
    id="1000000000000000008",
    url="https://x.com/emojitweet/status/1000000000000000008",
    author_name="Emoji Person 🎉",
    author_handle="emojitweet",
    avatar_url=None,
    text="Launching something big today 🚀🔥 Couldn't be more excited ❤️ Thanks everyone 😂 Stay tuned 🤖🎉🇮🇳",
    created_at=datetime(2024, 9, 1, tzinfo=timezone.utc),
    reply_count=50,
    repost_count=100,
    like_count=999,
    view_count=10000,
    media=[],
    source="fixture",
)

# ── Fixture H: Non-English / Telugu ──────────────────────────────────────────
FIXTURE_H = PostData(
    id="1000000000000000009",
    url="https://x.com/teluguuser/status/1000000000000000009",
    author_name="తెలుగు వినియోగదారు",
    author_handle="teluguuser",
    avatar_url=None,
    text="నమస్కారం! ఈ ట్వీట్ తెలుగులో ఉంది. Unicode నిరంతరాయంగా పని చేయాలి.",
    created_at=datetime(2024, 9, 6, tzinfo=timezone.utc),
    reply_count=12,
    repost_count=5,
    like_count=67,
    view_count=None,
    media=[],
    source="fixture",
)

# ── Fixture I: Long username / display name ───────────────────────────────────
FIXTURE_I = PostData(
    id="1000000000000000010",
    url="https://x.com/verylongusername123/status/1000000000000000010",
    author_name="A Very Long Display Name That Should Truncate Properly",
    author_handle="verylongusername123",
    avatar_url=None,
    text="Testing long display name truncation in the tweet card header.",
    created_at=datetime(2024, 10, 1, tzinfo=timezone.utc),
    reply_count=0,
    repost_count=0,
    like_count=1,
    view_count=50,
    media=[],
    source="fixture",
)

ALL_FIXTURES = [
    FIXTURE_A, FIXTURE_B, FIXTURE_C, FIXTURE_D, FIXTURE_E,
    FIXTURE_F, FIXTURE_F2, FIXTURE_G, FIXTURE_H, FIXTURE_I,
]
