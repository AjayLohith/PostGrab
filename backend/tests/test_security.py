"""Tests for URL validation, normalization, and security utilities."""

import pytest
from app.core.security import (
    validate_x_url,
    normalize_x_url,
    extract_post_info,
    sanitize_filename,
    is_allowed_media_host,
    validate_media_url,
)


# ── validate_x_url ────────────────────────────────────────────────────────────

class TestValidateXUrl:
    def test_valid_x_com_url(self):
        ok, err = validate_x_url("https://x.com/testuser/status/1234567890")
        assert ok is True
        assert err == ""

    def test_valid_twitter_com_url(self):
        ok, err = validate_x_url("https://twitter.com/testuser/status/9876543210")
        assert ok is True

    def test_valid_www_x_com(self):
        ok, err = validate_x_url("https://www.x.com/user/status/12345")
        assert ok is True

    def test_invalid_empty(self):
        ok, err = validate_x_url("")
        assert ok is False
        assert "required" in err.lower()

    def test_invalid_none(self):
        ok, err = validate_x_url(None)  # type: ignore
        assert ok is False

    def test_invalid_random_url(self):
        ok, err = validate_x_url("https://google.com")
        assert ok is False
        assert "x.com" in err.lower() or "twitter" in err.lower()

    def test_invalid_x_com_no_status(self):
        ok, err = validate_x_url("https://x.com/testuser")
        assert ok is False

    def test_invalid_no_scheme(self):
        ok, err = validate_x_url("x.com/user/status/123")
        assert ok is False

    def test_ssrf_private_ip(self):
        ok, err = validate_x_url("https://192.168.1.1/status/123")
        assert ok is False

    def test_ssrf_localhost(self):
        ok, err = validate_x_url("https://localhost/user/status/123")
        assert ok is False

    def test_valid_long_post_id(self):
        ok, err = validate_x_url("https://x.com/user/status/1234567890123456789")
        assert ok is True


# ── normalize_x_url ───────────────────────────────────────────────────────────

class TestNormalizeXUrl:
    def test_twitter_to_x(self):
        result = normalize_x_url("https://twitter.com/user/status/123")
        assert result == "https://x.com/user/status/123"

    def test_www_stripped(self):
        result = normalize_x_url("https://www.x.com/user/status/123")
        assert result == "https://x.com/user/status/123"

    def test_http_to_https(self):
        result = normalize_x_url("http://x.com/user/status/123")
        assert result.startswith("https://")

    def test_query_params_stripped(self):
        result = normalize_x_url("https://x.com/user/status/123?s=20&t=abc")
        assert "?" not in result

    def test_trailing_slash_stripped(self):
        result = normalize_x_url("https://x.com/user/status/123/")
        assert not result.endswith("/")


# ── extract_post_info ─────────────────────────────────────────────────────────

class TestExtractPostInfo:
    def test_extracts_username_and_id(self):
        result = extract_post_info("https://x.com/testuser/status/1234567890")
        assert result == ("testuser", "1234567890")

    def test_returns_none_for_invalid(self):
        result = extract_post_info("https://x.com/testuser")
        assert result is None


# ── sanitize_filename ─────────────────────────────────────────────────────────

class TestSanitizeFilename:
    def test_basic_safe_name(self):
        assert sanitize_filename("my_file.png") == "my_file.png"

    def test_removes_path_traversal(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_removes_special_chars(self):
        result = sanitize_filename("hello world!@#$%.txt")
        assert " " not in result
        assert "!" not in result

    def test_max_length(self):
        long_name = "a" * 200
        result = sanitize_filename(long_name)
        assert len(result) <= 100

    def test_empty_string(self):
        result = sanitize_filename("")
        assert result == "unknown"

    def test_backslash_removed(self):
        result = sanitize_filename("path\\file.txt")
        assert "\\" not in result

    def test_null_bytes_handled(self):
        result = sanitize_filename("file\x00name.txt")
        assert "\x00" not in result


# ── is_allowed_media_host ─────────────────────────────────────────────────────

class TestIsAllowedMediaHost:
    def test_pbs_twimg_allowed(self):
        assert is_allowed_media_host("https://pbs.twimg.com/media/xyz.jpg") is True

    def test_video_twimg_allowed(self):
        assert is_allowed_media_host("https://video.twimg.com/ext_tw_video/123/vid/1280x720/abc.mp4") is True

    def test_arbitrary_host_blocked(self):
        assert is_allowed_media_host("https://evil.com/malware.exe") is False

    def test_localhost_blocked(self):
        assert is_allowed_media_host("http://localhost/file") is False

    def test_private_ip_blocked(self):
        assert is_allowed_media_host("http://192.168.1.1/file") is False


# ── validate_media_url ────────────────────────────────────────────────────────

class TestValidateMediaUrl:
    def test_valid_twimg_url(self):
        ok, err = validate_media_url("https://pbs.twimg.com/media/xyz.jpg")
        assert ok is True

    def test_invalid_host(self):
        ok, err = validate_media_url("https://attacker.com/file.jpg")
        assert ok is False

    def test_empty_url(self):
        ok, err = validate_media_url("")
        assert ok is False
