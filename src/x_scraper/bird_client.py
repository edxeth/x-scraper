"""Bird CLI Python wrapper for X/Twitter scraping.

Bird is a TypeScript CLI that handles X's GraphQL API, including:
- Cookie-based authentication
- Automatic query ID rotation
- Media extraction (images, videos)
- Rate limit handling

This module wraps Bird CLI for use in Python scrapers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


class BirdError(Exception):
    """Error from Bird CLI execution."""

    def __init__(self, message: str, stderr: str = "", returncode: int = 1):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


class BirdNotFoundError(BirdError):
    """Bird CLI is not installed or not in PATH."""

    def __init__(self) -> None:
        super().__init__(
            "Bird CLI not found. Install it with: bun install -g @nicepkg/bird\n"
            "Or see: https://github.com/steipete/bird"
        )


class BirdAuthError(BirdError):
    """Authentication failed - cookies may be expired."""

    pass


class BirdRateLimitError(BirdError):
    """Rate limit exceeded."""

    pass


@dataclass
class BirdConfig:
    """Configuration for Bird CLI client."""

    auth_token: str | None = None
    ct0: str | None = None
    proxy_url: str | None = None
    timeout: int = 60


class BirdClient:
    """Python wrapper around Bird CLI for X/Twitter scraping.

    Bird handles the complex parts of X scraping:
    - GraphQL API interception
    - Query ID rotation (X changes these frequently)
    - Cookie-based authentication
    - Media URL extraction

    Usage:
        client = BirdClient(auth_token="...", ct0="...")
        data = client.read_tweet("https://x.com/user/status/123")
    """

    def __init__(
        self,
        auth_token: str | None = None,
        ct0: str | None = None,
        proxy_url: str | None = None,
        timeout: int = 60,
    ):
        """Initialize Bird client.

        Args:
            auth_token: X auth token cookie (optional, Bird can auto-extract from browser)
            ct0: X CSRF token cookie (optional, Bird can auto-extract from browser)
            proxy_url: SOCKS5 proxy URL (optional)
            timeout: Command timeout in seconds
        """
        # Load from settings if not provided (includes .env file support)
        from x_scraper.models import get_settings

        settings = get_settings()

        self.auth_token = auth_token or settings.auth_token
        self.ct0 = ct0 or settings.ct0
        self.proxy_url = proxy_url or settings.proxy_url
        self.timeout = timeout

        # Verify Bird is installed
        self._verify_bird_installed()

    def _verify_bird_installed(self) -> None:
        """Check if Bird CLI is available."""
        if not shutil.which("bird"):
            raise BirdNotFoundError()

    def _build_env(self) -> dict[str, str]:
        """Build environment variables for Bird CLI."""
        env = os.environ.copy()

        if self.auth_token:
            env["AUTH_TOKEN"] = self.auth_token
        if self.ct0:
            env["CT0"] = self.ct0
        if self.proxy_url:
            # Bird uses HTTPS_PROXY for SOCKS proxies
            env["HTTPS_PROXY"] = self.proxy_url
            env["HTTP_PROXY"] = self.proxy_url

        return env

    def _run_bird(self, args: list[str]) -> dict[str, Any]:
        """Execute Bird CLI command and return parsed JSON.

        Args:
            args: Command arguments (e.g., ["read", "https://x.com/..."])

        Returns:
            Parsed JSON response from Bird

        Raises:
            BirdError: If command fails
            BirdAuthError: If authentication fails
            BirdRateLimitError: If rate limited
        """
        cmd = ["bird", *args, "--json"]

        logger.debug("executing_bird", command=cmd)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._build_env(),
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise BirdError(f"Bird command timed out after {self.timeout}s") from e
        except FileNotFoundError as e:
            raise BirdNotFoundError() from e

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error("bird_failed", returncode=result.returncode, stderr=stderr)

            # Classify error type
            if "401" in stderr or "Unauthorized" in stderr or "auth" in stderr.lower():
                raise BirdAuthError(
                    "Authentication failed. Re-extract cookies from your browser.",
                    stderr=stderr,
                    returncode=result.returncode,
                )
            if "429" in stderr or "rate" in stderr.lower():
                raise BirdRateLimitError(
                    "Rate limit exceeded. Wait before retrying.",
                    stderr=stderr,
                    returncode=result.returncode,
                )
            if "404" in stderr:
                raise BirdError(
                    "Tweet not found or query IDs outdated. Try: bird query-ids --fresh",
                    stderr=stderr,
                    returncode=result.returncode,
                )

            raise BirdError(
                f"Bird CLI failed: {stderr}",
                stderr=stderr,
                returncode=result.returncode,
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error("bird_json_parse_error", stdout=result.stdout[:500])
            raise BirdError(f"Failed to parse Bird output as JSON: {e}") from e

    def read_tweet(self, url: str) -> dict[str, Any]:
        """Fetch tweet data by URL.

        Args:
            url: Full X/Twitter URL (e.g., https://x.com/user/status/123)

        Returns:
            Dict containing tweet data with fields:
            - id: Tweet ID
            - text: Tweet content
            - author: Author info (handle, name, etc.)
            - media: List of media items (images, videos)
            - createdAt: Creation timestamp
            - etc.
        """
        logger.info("reading_tweet", url=url)
        return self._run_bird(["read", url])

    def refresh_query_ids(self) -> None:
        """Force refresh of X's rotating GraphQL query IDs.

        X rotates query IDs every few weeks. Call this if you get 404 errors.
        """
        logger.info("refreshing_query_ids")
        try:
            subprocess.run(
                ["bird", "query-ids", "--fresh"],
                env=self._build_env(),
                timeout=120,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            logger.warning("query_ids_refresh_timeout")
        except FileNotFoundError as e:
            raise BirdNotFoundError() from e

    def get_version(self) -> str:
        """Get Bird CLI version."""
        try:
            result = subprocess.run(
                ["bird", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "unknown"


def extract_image_urls(raw_data: dict[str, Any]) -> list[str]:
    """Extract full-resolution image URLs from Bird response.

    Args:
        raw_data: Raw response from Bird CLI

    Returns:
        List of image URLs with :orig suffix for full resolution
    """
    images: list[str] = []

    media_list = raw_data.get("media", [])
    for media in media_list:
        if media.get("type") == "photo":
            url = media.get("url", "")
            if url and "twimg.com" in url:
                # Ensure we get the original/full resolution
                # Remove any existing size suffix and add :orig
                base_url = url.split("?")[0]
                if not base_url.endswith(":orig"):
                    url = f"{base_url}?format=jpg&name=orig"
                images.append(url)

    return images


def extract_video_urls(raw_data: dict[str, Any]) -> list[str]:
    """Extract highest-quality video URLs from Bird response.

    Args:
        raw_data: Raw response from Bird CLI

    Returns:
        List of video URLs (highest bitrate MP4)
    """
    videos: list[str] = []

    media_list = raw_data.get("media", [])
    for media in media_list:
        if media.get("type") in ("video", "animated_gif"):
            video_url = media.get("videoUrl", "")
            if video_url:
                videos.append(video_url)

    return videos
