"""Main scraper module using botasaurus and Bird CLI."""

from __future__ import annotations

from typing import Any

import structlog

from botasaurus.task import task

from x_scraper.bird_client import (
    BirdClient,
    BirdError,
    BirdRateLimitError,
    extract_image_urls,
    extract_video_urls,
)
from x_scraper.models import ScraperResult, TweetData, get_settings
from x_scraper.utils import normalize_x_url, parse_twitter_date, safe_get

logger = structlog.get_logger()


def parse_bird_response(raw_data: dict[str, Any], url: str) -> TweetData:
    """Parse Bird CLI JSON response into TweetData model.

    Args:
        raw_data: Raw JSON response from Bird CLI
        url: Original tweet URL

    Returns:
        Parsed TweetData model
    """
    # Extract author info
    author = raw_data.get("author", {})
    author_handle = (
        author.get("username", "") or author.get("handle", "") or author.get("screen_name", "")
    )
    author_name = author.get("name", "") or author.get("displayName", "")

    # Parse creation date
    created_at_raw = raw_data.get("createdAt", "") or raw_data.get("created_at", "")
    if created_at_raw:
        created_at = parse_twitter_date(created_at_raw)
    else:
        created_at = created_at_raw  # Keep as string if parsing fails

    # Extract media
    images = extract_image_urls(raw_data)
    videos = extract_video_urls(raw_data)

    # Check if part of thread
    conversation_id = raw_data.get("conversationId") or safe_get(
        raw_data, "legacy", "conversation_id_str"
    )
    tweet_id = raw_data.get("id", "")
    is_thread = conversation_id is not None and conversation_id != tweet_id

    return TweetData(
        id=tweet_id,
        url=url,
        text=raw_data.get("text", "") or raw_data.get("full_text", ""),
        created_at=created_at,
        author_handle=author_handle,
        author_name=author_name,
        images=images,
        videos=videos,
        is_thread=is_thread,
        conversation_id=conversation_id,
    )


@task(
    parallel=5,  # Process 5 URLs concurrently (configurable)
    max_retry=5,  # Retry on failure
    retry_wait=10,  # Wait 10s between retries
    close_on_crash=True,  # Cleanup on fatal error
    create_error_logs=True,  # Log errors to file
    output=None,  # We handle output ourselves
)
def scrape_tweets(data: dict[str, Any]) -> dict[str, Any]:
    """Scrape a single tweet URL using Bird CLI.

    This function is decorated with botasaurus @task which provides:
    - Parallel processing across multiple URLs
    - Automatic retry with exponential backoff
    - Error logging and recovery
    - Result persistence

    Args:
        data: Dict with 'url' key containing X tweet URL

    Returns:
        ScraperResult as dict containing success status and data/error
    """
    url = data.get("url", "")

    if not url:
        return ScraperResult(
            success=False,
            url="",
            error="No URL provided",
        ).to_dict()

    # Normalize URL
    url = normalize_x_url(url)

    # Get settings
    settings = get_settings()

    # Initialize Bird client
    client = BirdClient(
        auth_token=settings.auth_token,
        ct0=settings.ct0,
        proxy_url=settings.proxy_url,
    )

    try:
        logger.info("scraping_tweet", url=url)

        # Fetch tweet data via Bird CLI
        raw_data = client.read_tweet(url)

        # Parse response into TweetData
        tweet = parse_bird_response(raw_data, url)

        logger.info(
            "tweet_scraped",
            url=url,
            images=len(tweet.images),
            videos=len(tweet.videos),
        )

        return ScraperResult(
            success=True,
            url=url,
            data=tweet,
        ).to_dict()

    except BirdRateLimitError as e:
        logger.warning("rate_limited", url=url)
        # Let botasaurus retry handle this
        raise

    except BirdError as e:
        # If 404, try refreshing query IDs and retry
        if "404" in str(e) or "query" in str(e).lower():
            logger.info("refreshing_query_ids_for_retry", url=url)
            client.refresh_query_ids()
            raise  # Let botasaurus retry

        logger.error("scrape_failed", url=url, error=str(e))
        return ScraperResult(
            success=False,
            url=url,
            error=str(e),
        ).to_dict()

    except Exception as e:
        logger.exception("unexpected_error", url=url)
        return ScraperResult(
            success=False,
            url=url,
            error=f"Unexpected error: {e}",
        ).to_dict()


def scrape_urls(urls: list[str]) -> list[dict[str, Any]]:
    """Convenience function to scrape multiple URLs.

    Args:
        urls: List of X tweet URLs

    Returns:
        List of ScraperResult dicts
    """
    data = [{"url": url} for url in urls]
    return scrape_tweets(data)
