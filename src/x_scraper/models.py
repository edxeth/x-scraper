"""Pydantic data models for X/Twitter scraper."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env in package directory (works regardless of cwd)
_PACKAGE_DIR = Path(__file__).parent.parent.parent
_ENV_FILE = _PACKAGE_DIR / ".env"


class MediaItem(BaseModel):
    """Represents an image or video attachment from a tweet."""

    type: str  # "photo", "video", "animated_gif"
    url: str  # Direct URL to media
    width: int | None = None
    height: int | None = None
    video_url: str | None = None  # For videos: highest bitrate MP4


class TweetData(BaseModel):
    """Complete tweet data extracted from X."""

    id: str
    url: str
    text: str
    created_at: datetime | str  # Allow string for raw date parsing

    # Author (minimal)
    author_handle: str
    author_name: str | None = None

    # Media
    images: list[str] = Field(default_factory=list)  # Direct image URLs
    videos: list[str] = Field(default_factory=list)  # Direct video URLs (MP4)

    # Metadata
    is_thread: bool = False
    thread_position: int | None = None
    conversation_id: str | None = None


class ScraperResult(BaseModel):
    """Wrapper for scraper output."""

    success: bool
    url: str
    data: TweetData | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Auth - these are optional as Bird can auto-extract from browser
    auth_token: str | None = None
    ct0: str | None = None

    # Proxy
    proxy_url: str | None = None

    # Scraper settings
    parallel_workers: int = 5
    max_retry: int = 5
    retry_wait: int = 10
    output_dir: Path = Path("output")

    # Logging
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Get application settings, loading from .env if available."""
    return Settings()
