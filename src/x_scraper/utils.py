"""Utility functions and logging setup for X/Twitter scraper."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

_PACKAGE_DIR = Path(__file__).parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PACKAGE_DIR / "output"


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def parse_x_url(url: str) -> dict[str, str | None]:
    """Parse X/Twitter URL to extract components.

    Args:
        url: Full X/Twitter URL

    Returns:
        Dict with 'username', 'tweet_id', 'type' (tweet, profile, etc.)
    """
    # Normalize URL
    url = url.strip()

    # Tweet URL pattern: https://x.com/username/status/1234567890
    # Also handles twitter.com URLs
    tweet_pattern = r"https?://(?:www\.)?(?:x|twitter)\.com/([^/]+)/status/(\d+)"
    match = re.match(tweet_pattern, url)

    if match:
        return {
            "username": match.group(1),
            "tweet_id": match.group(2),
            "type": "tweet",
        }

    # Profile URL pattern: https://x.com/username
    profile_pattern = r"https?://(?:www\.)?(?:x|twitter)\.com/([^/]+)/?$"
    match = re.match(profile_pattern, url)

    if match:
        return {
            "username": match.group(1),
            "tweet_id": None,
            "type": "profile",
        }

    return {
        "username": None,
        "tweet_id": None,
        "type": "unknown",
    }


def normalize_x_url(url: str) -> str:
    """Normalize X/Twitter URL to use x.com domain.

    Args:
        url: Input URL (may use twitter.com or x.com)

    Returns:
        Normalized URL using x.com
    """
    return url.replace("twitter.com", "x.com")


def generate_output_path(
    url: str,
    extension: str = "md",
    base_dir: Path | str | None = None,
    tweet_date: datetime | str | None = None,
) -> Path:
    """Generate a structured output path based on tweet metadata.

    Creates paths like: output/YYYY/MM/DD/author/tweet_id.ext

    Args:
        url: Tweet URL to parse for author and ID
        extension: File extension (md, json)
        base_dir: Base output directory (defaults to package output dir)
        tweet_date: Tweet creation date (uses current date if None)

    Returns:
        Path object for output file
    """
    if base_dir is None:
        base_dir = _DEFAULT_OUTPUT_DIR

    parsed = parse_x_url(url)

    author = parsed.get("username") or "unknown"
    tweet_id = parsed.get("tweet_id") or "tweet"

    if tweet_date is None:
        dt = datetime.now()
    elif isinstance(tweet_date, str):
        dt = parse_twitter_date(tweet_date)
    else:
        dt = tweet_date

    path = Path(base_dir) / dt.strftime("%Y/%m/%d") / author / f"{tweet_id}.{extension}"

    return path


def generate_batch_output_path(
    urls: list[str],
    extension: str = "md",
    base_dir: Path | str | None = None,
) -> Path:
    """Generate output path for batch scraping multiple tweets.

    For single tweet: output/YYYY/MM/DD/author/tweet_id.ext
    For multiple tweets: output/YYYY/MM/DD/batch_HHMMSS.ext

    Args:
        urls: List of tweet URLs
        extension: File extension (md, json)
        base_dir: Base output directory (defaults to package output dir)

    Returns:
        Path object for output file
    """
    if base_dir is None:
        base_dir = _DEFAULT_OUTPUT_DIR

    now = datetime.now()
    date_path = now.strftime("%Y/%m/%d")

    if len(urls) == 1:
        return generate_output_path(urls[0], extension, base_dir)
    else:
        timestamp = now.strftime("%H%M%S")
        return Path(base_dir) / date_path / f"batch_{timestamp}.{extension}"


def parse_twitter_date(date_str: str) -> datetime:
    """Parse X/Twitter date format to datetime.

    X uses format like: "Wed Jan 08 20:25:00 +0000 2026"

    Args:
        date_str: Date string from X

    Returns:
        Parsed datetime object
    """
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        # Try ISO format as fallback
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            # Return current time if parsing fails
            return datetime.now()


def format_image_url(url: str, size: str = "orig") -> str:
    """Format X image URL for desired size.

    Args:
        url: Base image URL
        size: Size variant ('orig', 'large', 'medium', 'small', 'thumb')

    Returns:
        Formatted URL with size parameter
    """
    if not url or "twimg.com" not in url:
        return url

    # Remove existing parameters
    base_url = url.split("?")[0]

    # Add format and size
    return f"{base_url}?format=jpg&name={size}"


def truncate_text(text: str, max_length: int = 280) -> str:
    """Truncate text to max length, adding ellipsis if needed.

    Args:
        text: Input text
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value.

    Args:
        data: Dictionary to traverse
        *keys: Keys to traverse
        default: Default value if not found

    Returns:
        Value at nested path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current


def format_tweet_as_markdown(data: dict[str, Any]) -> str:
    """Format a scraped tweet result as markdown.

    Args:
        data: ScraperResult dict with 'success', 'url', 'data', 'error' keys

    Returns:
        Formatted markdown string
    """
    if not data.get("success"):
        error = data.get("error", "Unknown error")
        url = data.get("url", "Unknown URL")
        return f"## ❌ Failed to scrape\n\n**URL:** {url}\n\n**Error:** {error}\n"

    tweet = data.get("data", {})
    if not tweet:
        return "## ❌ No tweet data\n"

    # Build markdown
    lines = []

    # Header with author
    author_handle = tweet.get("author_handle", "unknown")
    author_name = tweet.get("author_name", "")
    url = tweet.get("url", data.get("url", ""))

    if author_name:
        lines.append(f"## {author_name} (@{author_handle})")
    else:
        lines.append(f"## @{author_handle}")

    lines.append("")

    # Tweet text
    text = tweet.get("text", "")
    if text:
        lines.append(text)
        lines.append("")

    # Metadata
    created_at = tweet.get("created_at", "")
    if created_at:
        lines.append(f"**Posted:** {created_at}")

    lines.append(f"**URL:** [{url}]({url})")
    lines.append("")

    # Images
    images = tweet.get("images", [])
    if images:
        lines.append(f"### Images ({len(images)})")
        lines.append("")
        for i, img_url in enumerate(images, 1):
            lines.append(f"![Image {i}]({img_url})")
            lines.append("")

    # Videos
    videos = tweet.get("videos", [])
    if videos:
        lines.append(f"### Videos ({len(videos)})")
        lines.append("")
        for i, video_url in enumerate(videos, 1):
            lines.append(f"- [Video {i}]({video_url})")
        lines.append("")

    # Separator
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def format_results_as_markdown(results: list[dict[str, Any]]) -> str:
    """Format multiple scraped tweet results as markdown.

    Args:
        results: List of ScraperResult dicts

    Returns:
        Formatted markdown string
    """
    if not results:
        return "# No tweets scraped\n"

    lines = []
    lines.append("# Scraped Tweets")
    lines.append("")

    success_count = sum(1 for r in results if r.get("success"))
    lines.append(
        f"**Total:** {len(results)} tweets | **Success:** {success_count} | **Failed:** {len(results) - success_count}"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    for result in results:
        lines.append(format_tweet_as_markdown(result))

    return "\n".join(lines)
