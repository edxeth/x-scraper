"""X/Twitter Scraper - Extract tweets with images and videos using Bird CLI."""

from x_scraper.scraper import scrape_tweets
from x_scraper.bird_client import BirdClient, BirdError
from x_scraper.models import TweetData, ScraperResult

__version__ = "0.1.0"
__all__ = ["scrape_tweets", "BirdClient", "BirdError", "TweetData", "ScraperResult"]
