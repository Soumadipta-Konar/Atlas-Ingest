import logging
from datetime import datetime, timedelta
import re
from typing import List, Optional
from .base import BaseCrawler

logger = logging.getLogger(__name__)

class DateNormalizer:
    """Normalizes missing or relative dates to ISO-8601 strict timestamps."""
    
    @staticmethod
    def normalize(date_str: Optional[str]) -> datetime:
        now = datetime.utcnow()
        if not date_str:
            # Intelligent Heuristic: Assume now if totally missing but found in fresh scrape
            return now
            
        date_str = date_str.lower().strip()
        
        # Handle relative "X hours ago"
        hours_match = re.search(r'(\d+)\s+hour', date_str)
        if hours_match:
            hours = int(hours_match.group(1))
            return now - timedelta(hours=hours)
            
        # Handle relative "X days ago"
        days_match = re.search(r'(\d+)\s+day', date_str)
        if days_match:
            days = int(days_match.group(1))
            return now - timedelta(days=days)
            
        try:
            # Fallback to standard parsing (can be extended with dateutil)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}, defaulting to now")
            return now

class NewsJobsScraper(BaseCrawler):
    """Crawler for AI News and Job boards with 24-hour freshness tracking."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.normalizer = DateNormalizer()

    def is_fresh(self, dt: datetime) -> bool:
        """Enforces the 24-hour strict freshness challenge."""
        return datetime.utcnow() - dt <= timedelta(hours=24)

    async def scrape_news_source(self, url: str) -> List[str]:
        """Scrapes full text from a news source."""
        # Using playwright fallback to handle any JS protections
        html = await self._fetch_playwright(url)
        return [html] # Simplified for demo - would parse individual article links
        
    async def scrape_jobs(self, board_url: str) -> List[str]:
        """Scrapes job postings."""
        html = await self._fetch_playwright(board_url)
        return [html]
