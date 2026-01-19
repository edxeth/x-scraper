"""Tests for Bird CLI client wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from x_scraper.bird_client import (
    BirdClient,
    BirdError,
    BirdNotFoundError,
    BirdAuthError,
    BirdRateLimitError,
    extract_image_urls,
    extract_video_urls,
)


class TestBirdClient:
    """Tests for BirdClient class."""

    def test_init_with_credentials(self) -> None:
        """Test client initialization with explicit credentials."""
        with patch("shutil.which", return_value="/usr/bin/bird"):
            client = BirdClient(
                auth_token="test_token",
                ct0="test_ct0",
            )
            assert client.auth_token == "test_token"
            assert client.ct0 == "test_ct0"

    def test_init_without_bird_raises_error(self) -> None:
        """Test that missing Bird CLI raises BirdNotFoundError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(BirdNotFoundError):
                BirdClient()

    def test_build_env_includes_credentials(self) -> None:
        """Test that credentials are included in environment."""
        with patch("shutil.which", return_value="/usr/bin/bird"):
            client = BirdClient(
                auth_token="my_token",
                ct0="my_ct0",
                proxy_url="socks5://proxy:1080",
            )
            env = client._build_env()
            assert env["AUTH_TOKEN"] == "my_token"
            assert env["CT0"] == "my_ct0"
            assert env["HTTPS_PROXY"] == "socks5://proxy:1080"

    def test_read_tweet_success(self, sample_bird_response: dict) -> None:
        """Test successful tweet reading."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"id": "123", "text": "Hello"}'

        with patch("shutil.which", return_value="/usr/bin/bird"):
            with patch("subprocess.run", return_value=mock_result):
                client = BirdClient(auth_token="test", ct0="test")
                result = client.read_tweet("https://x.com/user/status/123")

                assert result["id"] == "123"
                assert result["text"] == "Hello"

    def test_read_tweet_auth_error(self) -> None:
        """Test authentication error handling."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "401 Unauthorized"

        with patch("shutil.which", return_value="/usr/bin/bird"):
            with patch("subprocess.run", return_value=mock_result):
                client = BirdClient(auth_token="bad", ct0="bad")

                with pytest.raises(BirdAuthError):
                    client.read_tweet("https://x.com/user/status/123")

    def test_read_tweet_rate_limit_error(self) -> None:
        """Test rate limit error handling."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "429 Too Many Requests"

        with patch("shutil.which", return_value="/usr/bin/bird"):
            with patch("subprocess.run", return_value=mock_result):
                client = BirdClient(auth_token="test", ct0="test")

                with pytest.raises(BirdRateLimitError):
                    client.read_tweet("https://x.com/user/status/123")

    def test_read_tweet_generic_error(self) -> None:
        """Test generic error handling."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Something went wrong"

        with patch("shutil.which", return_value="/usr/bin/bird"):
            with patch("subprocess.run", return_value=mock_result):
                client = BirdClient(auth_token="test", ct0="test")

                with pytest.raises(BirdError):
                    client.read_tweet("https://x.com/user/status/123")


class TestMediaExtraction:
    """Tests for media URL extraction functions."""

    def test_extract_image_urls(self, sample_bird_response: dict) -> None:
        """Test image URL extraction."""
        images = extract_image_urls(sample_bird_response)

        assert len(images) == 2
        assert all("twimg.com" in url for url in images)
        assert all("name=orig" in url for url in images)

    def test_extract_image_urls_empty(self, sample_bird_response_no_media: dict) -> None:
        """Test image extraction with no media."""
        images = extract_image_urls(sample_bird_response_no_media)
        assert images == []

    def test_extract_video_urls(self, sample_bird_response: dict) -> None:
        """Test video URL extraction."""
        videos = extract_video_urls(sample_bird_response)

        assert len(videos) == 1
        assert "video.twimg.com" in videos[0]
        assert ".mp4" in videos[0]

    def test_extract_video_urls_empty(self, sample_bird_response_no_media: dict) -> None:
        """Test video extraction with no media."""
        videos = extract_video_urls(sample_bird_response_no_media)
        assert videos == []
