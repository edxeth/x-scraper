"""Cookie extraction from browser for X/Twitter authentication.

This module provides utilities to extract auth cookies from browsers
where the user is already logged into X.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Config directory for storing cookies
CONFIG_DIR = Path.home() / ".config" / "x-scraper"
COOKIES_FILE = CONFIG_DIR / "cookies.json"


@dataclass
class XCookies:
    """X/Twitter authentication cookies."""

    auth_token: str
    ct0: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {"auth_token": self.auth_token, "ct0": self.ct0}

    def to_env(self) -> str:
        """Format as .env file content."""
        return f"AUTH_TOKEN={self.auth_token}\nCT0={self.ct0}\n"


def save_cookies(cookies: XCookies) -> Path:
    """Save cookies to config file.

    Args:
        cookies: XCookies instance

    Returns:
        Path to saved cookies file
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies.to_dict(), f, indent=2)
    logger.info("cookies_saved", path=str(COOKIES_FILE))
    return COOKIES_FILE


def load_cookies() -> XCookies | None:
    """Load cookies from config file.

    Returns:
        XCookies instance or None if not found
    """
    if not COOKIES_FILE.exists():
        return None

    try:
        with open(COOKIES_FILE) as f:
            data = json.load(f)
        return XCookies(
            auth_token=data.get("auth_token", ""),
            ct0=data.get("ct0", ""),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("cookies_load_failed", error=str(e))
        return None


def extract_cookies_via_bird() -> XCookies | None:
    """Extract cookies using Bird CLI's auto-detection.

    Bird can automatically extract cookies from Safari, Chrome, and Firefox.
    This function tests if Bird can authenticate without explicit credentials.

    Returns:
        XCookies if extraction successful, None otherwise
    """
    try:
        # Run Bird's 'whoami' command to test authentication
        # Bird will attempt to extract cookies from installed browsers
        result = subprocess.run(
            ["bird", "whoami"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Bird successfully authenticated - parse the username from output
            username = result.stdout.strip().split()[-1] if result.stdout else "unknown"
            logger.info(
                "bird_auto_auth_success",
                username=username,
            )
            # Note: We don't have the raw cookies, but Bird will use them
            # Return a placeholder to indicate auth works
            return XCookies(auth_token="[bird-managed]", ct0="[bird-managed]")

        logger.warning("bird_auto_auth_failed", stderr=result.stderr[:200] if result.stderr else "")
        return None

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("bird_auth_check_error", error=str(e))
        return None


def extract_cookies_from_env() -> XCookies | None:
    """Extract cookies from environment variables or .env file.

    Uses pydantic-settings to load from both os.environ AND .env file.

    Returns:
        XCookies if both AUTH_TOKEN and CT0 are set, None otherwise
    """
    from x_scraper.models import get_settings

    settings = get_settings()

    if settings.auth_token and settings.ct0:
        return XCookies(auth_token=settings.auth_token, ct0=settings.ct0)
    return None


def get_best_cookies() -> XCookies | None:
    """Get cookies from best available source.

    Priority:
    1. Environment variables
    2. Saved cookies file
    3. Bird auto-detection

    Returns:
        XCookies or None if no valid cookies found
    """
    # Try environment variables first
    cookies = extract_cookies_from_env()
    if cookies:
        logger.debug("using_env_cookies")
        return cookies

    # Try saved cookies
    cookies = load_cookies()
    if cookies and cookies.auth_token and cookies.auth_token != "[bird-managed]":
        logger.debug("using_saved_cookies")
        return cookies

    # Try Bird auto-detection
    cookies = extract_cookies_via_bird()
    if cookies:
        logger.debug("using_bird_auto_cookies")
        return cookies

    return None


def manual_cookie_instructions() -> str:
    """Return instructions for manually extracting cookies.

    Returns:
        Formatted instructions string
    """
    return """
To extract X/Twitter cookies manually:

1. Open X.com in your browser and ensure you're logged in
2. Open Developer Tools (F12 or Cmd+Option+I)
3. Go to the "Application" tab (Chrome) or "Storage" tab (Firefox)
4. Under "Cookies", find "x.com" or "twitter.com"
5. Find and copy these two cookies:
   - auth_token
   - ct0

6. Set them as environment variables:
   export AUTH_TOKEN=your_auth_token_value
   export CT0=your_ct0_value

Or save them to .env file:
   AUTH_TOKEN=your_auth_token_value
   CT0=your_ct0_value

Alternatively, Bird CLI can auto-extract from Safari/Chrome/Firefox:
   bird whoami

If Bird authenticates successfully, you don't need to set cookies manually.
"""
