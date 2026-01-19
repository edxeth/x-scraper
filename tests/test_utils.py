"""Tests for utility functions."""

from datetime import datetime

import pytest

from x_scraper.utils import (
    parse_x_url,
    normalize_x_url,
    parse_twitter_date,
    format_image_url,
    truncate_text,
    safe_get,
)


class TestParseXUrl:
    """Tests for X URL parsing."""

    def test_parse_tweet_url(self) -> None:
        """Test parsing a tweet URL."""
        result = parse_x_url("https://x.com/bozhou_ai/status/2011738838767423983")

        assert result["username"] == "bozhou_ai"
        assert result["tweet_id"] == "2011738838767423983"
        assert result["type"] == "tweet"

    def test_parse_twitter_url(self) -> None:
        """Test parsing old twitter.com URL."""
        result = parse_x_url("https://twitter.com/elonmusk/status/123456789")

        assert result["username"] == "elonmusk"
        assert result["tweet_id"] == "123456789"
        assert result["type"] == "tweet"

    def test_parse_profile_url(self) -> None:
        """Test parsing a profile URL."""
        result = parse_x_url("https://x.com/bozhou_ai")

        assert result["username"] == "bozhou_ai"
        assert result["tweet_id"] is None
        assert result["type"] == "profile"

    def test_parse_unknown_url(self) -> None:
        """Test parsing an unrecognized URL."""
        result = parse_x_url("https://example.com/something")

        assert result["type"] == "unknown"


class TestNormalizeXUrl:
    """Tests for URL normalization."""

    def test_normalize_twitter_to_x(self) -> None:
        """Test converting twitter.com to x.com."""
        url = "https://twitter.com/user/status/123"
        normalized = normalize_x_url(url)

        assert "x.com" in normalized
        assert "twitter.com" not in normalized

    def test_normalize_already_x(self) -> None:
        """Test that x.com URLs are unchanged."""
        url = "https://x.com/user/status/123"
        normalized = normalize_x_url(url)

        assert normalized == url


class TestParseTwitterDate:
    """Tests for Twitter date parsing."""

    def test_parse_twitter_format(self) -> None:
        """Test parsing Twitter's date format."""
        date_str = "Wed Jan 08 20:25:00 +0000 2026"
        result = parse_twitter_date(date_str)

        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 8

    def test_parse_iso_format(self) -> None:
        """Test parsing ISO format as fallback."""
        date_str = "2026-01-15T10:30:00Z"
        result = parse_twitter_date(date_str)

        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1

    def test_parse_invalid_returns_current(self) -> None:
        """Test that invalid dates return current time."""
        result = parse_twitter_date("not a date")

        assert isinstance(result, datetime)


class TestFormatImageUrl:
    """Tests for image URL formatting."""

    def test_format_with_orig(self) -> None:
        """Test formatting with orig size."""
        url = "https://pbs.twimg.com/media/abc123.jpg"
        result = format_image_url(url, "orig")

        assert "name=orig" in result
        assert "format=jpg" in result

    def test_format_with_large(self) -> None:
        """Test formatting with large size."""
        url = "https://pbs.twimg.com/media/abc123.jpg"
        result = format_image_url(url, "large")

        assert "name=large" in result

    def test_format_non_twimg_unchanged(self) -> None:
        """Test that non-twimg URLs are unchanged."""
        url = "https://example.com/image.jpg"
        result = format_image_url(url)

        assert result == url


class TestTruncateText:
    """Tests for text truncation."""

    def test_truncate_long_text(self) -> None:
        """Test truncating long text."""
        text = "a" * 300
        result = truncate_text(text, 280)

        assert len(result) == 280
        assert result.endswith("...")

    def test_truncate_short_text_unchanged(self) -> None:
        """Test that short text is unchanged."""
        text = "Hello world"
        result = truncate_text(text, 280)

        assert result == text


class TestSafeGet:
    """Tests for safe dictionary traversal."""

    def test_safe_get_nested(self) -> None:
        """Test getting nested value."""
        data = {"a": {"b": {"c": 42}}}
        result = safe_get(data, "a", "b", "c")

        assert result == 42

    def test_safe_get_missing_returns_default(self) -> None:
        """Test that missing keys return default."""
        data = {"a": {"b": 1}}
        result = safe_get(data, "a", "x", "y", default="fallback")

        assert result == "fallback"

    def test_safe_get_none_value(self) -> None:
        """Test handling None values in path."""
        data = {"a": None}
        result = safe_get(data, "a", "b", default="default")

        assert result == "default"
