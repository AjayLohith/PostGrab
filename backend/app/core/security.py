"""Security utilities — URL validation, SSRF protection, filename sanitization."""

import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Allowed hosts for X/Twitter post URLs
ALLOWED_X_HOSTS = {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}

# Allowed hosts for media proxy (download from these domains only)
ALLOWED_MEDIA_HOSTS = {
    "pbs.twimg.com",
    "video.twimg.com",
    "abs.twimg.com",
    "ton.twimg.com",
    "twimg.com",
    "cdn.syndication.twimg.com",
    "unavatar.io",
}

# Pattern for valid X post URLs
X_POST_PATTERN = re.compile(
    r"^https?://(www\.)?(x\.com|twitter\.com)/([a-zA-Z0-9_]{1,15})/status/(\d+)"
)

# Safe filename characters
SAFE_FILENAME_CHARS = re.compile(r"[^a-zA-Z0-9_\-.]")


def validate_x_url(url: str) -> tuple[bool, str]:
    """
    Validate that a URL is a legitimate X/Twitter post URL.

    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL is required."

    url = url.strip()

    # Must start with http(s)
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format."

    # Check host
    if parsed.hostname not in ALLOWED_X_HOSTS:
        return False, (
            "Only x.com and twitter.com URLs are supported. "
            f"Got: {parsed.hostname}"
        )

    # Check path pattern
    match = X_POST_PATTERN.match(url)
    if not match:
        return False, (
            "URL must be a post URL in the format: "
            "https://x.com/username/status/1234567890"
        )

    return True, ""


def normalize_x_url(url: str) -> str:
    """
    Normalize a Twitter/X URL to the canonical x.com format.

    Example:
        twitter.com/user/status/123 → https://x.com/user/status/123
    """
    url = url.strip()

    # Ensure https
    if url.startswith("http://"):
        url = "https://" + url[7:]
    elif not url.startswith("https://"):
        url = "https://" + url

    # Replace twitter.com with x.com
    url = re.sub(
        r"https://(www\.)?(twitter\.com|x\.com)",
        "https://x.com",
        url,
    )

    # Remove query params and fragments (they're not needed for extraction)
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    url = f"https://x.com{clean_path}"

    return url


def extract_post_info(url: str) -> tuple[str, str] | None:
    """
    Extract username and post ID from a normalized X URL.

    Returns:
        (username, post_id) or None
    """
    match = X_POST_PATTERN.match(url)
    if match:
        return match.group(3), match.group(4)
    return None


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Sanitize a filename to be safe for filesystem use.

    Removes special characters, path traversal sequences, and limits length.
    """
    if not name:
        return "unknown"

    # Remove path traversal
    name = name.replace("..", "").replace("/", "").replace("\\", "")

    # Replace unsafe characters with underscore
    name = SAFE_FILENAME_CHARS.sub("_", name)

    # Remove leading/trailing dots and underscores
    name = name.strip("._")

    # Limit length
    if len(name) > max_length:
        name = name[:max_length]

    return name or "unknown"


def is_allowed_media_host(url: str) -> bool:
    """
    Check if a URL's host is in the allowed media hosts list.
    Prevents SSRF by restricting which hosts we'll download from.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        # Check exact match or subdomain match
        for allowed in ALLOWED_MEDIA_HOSTS:
            if hostname == allowed or hostname.endswith(f".{allowed}"):
                return True

        return False
    except Exception:
        return False


def validate_media_url(url: str) -> tuple[bool, str]:
    """
    Validate a media URL for safe downloading.

    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "Media URL is required."

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid media URL format."

    # Must be HTTPS
    if parsed.scheme not in ("http", "https"):
        return False, "Media URL must use HTTP or HTTPS."

    # Must be from allowed host
    if not is_allowed_media_host(url):
        return False, f"Media downloads from {parsed.hostname} are not allowed."

    return True, ""
