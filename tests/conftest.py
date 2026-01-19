"""Pytest fixtures for x-scraper tests."""

import pytest


@pytest.fixture
def sample_tweet_url() -> str:
    """Sample X tweet URL for testing."""
    return "https://x.com/bozhou_ai/status/2011738838767423983"


@pytest.fixture
def sample_bird_response() -> dict:
    """Sample Bird CLI response for testing."""
    return {
        "id": "2011738838767423983",
        "text": "This is a sample tweet with some content.",
        "author": {
            "handle": "bozhou_ai",
            "name": "Bo Zhou",
            "id": "123456789",
        },
        "createdAt": "Wed Jan 15 10:30:00 +0000 2026",
        "media": [
            {
                "type": "photo",
                "url": "https://pbs.twimg.com/media/sample1.jpg",
                "width": 1200,
                "height": 800,
            },
            {
                "type": "photo",
                "url": "https://pbs.twimg.com/media/sample2.jpg",
                "width": 1200,
                "height": 800,
            },
            {
                "type": "video",
                "videoUrl": "https://video.twimg.com/ext_tw_video/sample.mp4",
                "width": 1920,
                "height": 1080,
            },
        ],
        "conversationId": "2011738838767423983",
    }


@pytest.fixture
def sample_bird_response_no_media() -> dict:
    """Sample Bird CLI response without media."""
    return {
        "id": "999888777666",
        "text": "A text-only tweet without any media.",
        "author": {
            "handle": "testuser",
            "name": "Test User",
        },
        "createdAt": "Mon Jan 20 15:00:00 +0000 2026",
        "media": [],
    }
