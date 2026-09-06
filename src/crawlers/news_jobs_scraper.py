import logging
from datetime import datetime, timedelta, timezone
import re
from typing import List, Optional, Any
import trafilatura

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))
from .base import BaseCrawler

logger = logging.getLogger(__name__)

class DateNormalizer:
    """Normalizes missing or relative dates to ISO-8601 strict timestamps."""
    
    @staticmethod
    def normalize(date_str: Optional[str]) -> datetime:
        now = datetime.now(IST)
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
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo:
                # Convert to IST
                dt = dt.astimezone(IST)
            return dt
        except Exception:
            pass
            
        try:
            # Fallback to standard parsing (can be extended with dateutil)
            # Handle both 'Z' and 'z' suffixes after the earlier .lower() call
            return datetime.fromisoformat(date_str.replace("z", "+00:00")).astimezone(IST)
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
        return datetime.now(IST) - dt <= timedelta(hours=24)

    async def fetch_full_text(self, url: str) -> Optional[str]:
        """Fetches and extracts full article text from a URL using trafilatura."""
        try:
            html = await self.fetch(url)
            return trafilatura.extract(html)
        except Exception as e:
            logger.warning(f"Full-text fetch failed for {url}: {e}")
            return None

    async def scrape_rss_news(self, url: str, source_name: str) -> List[Any]:
        """Scrapes news from an RSS feed, fetching full article text."""
        from src.models.schemas import NewsEntity, NewsContent, Source
        from bs4 import BeautifulSoup
        
        logger.info(f"Fetching News RSS: {url}")
        try:
            xml_data = await self.fetch(url)
            soup = BeautifulSoup(xml_data, "xml")
            items = soup.find_all("item") or soup.find_all("entry")
            
            results = []
            for item in items:
                title_node = item.find("title")
                link_node = item.find("link")
                pubDate_node = item.find("pubDate") or item.find("updated") or item.find("published")
                desc_node = item.find("description") or item.find("summary")
                
                if not title_node or not link_node:
                    continue
                    
                title = title_node.text.strip()
                if link_node.text.strip():
                    link = link_node.text.strip()
                elif link_node.has_attr('href'):
                    link = link_node['href']
                else:
                    link = ""
                    
                date_str = pubDate_node.text.strip() if pubDate_node else None
                published_date = self.normalizer.normalize(date_str)
                
                if not self.is_fresh(published_date):
                    continue
                    
                desc = desc_node.text.strip()[:500] if desc_node else None

                # Fetch full article text (capped at 5,000 chars to avoid sheet bloat)
                full_text = await self.fetch_full_text(link) if link else None
                if full_text:
                    full_text = full_text[:5000]
                
                entity = NewsEntity(
                    source=Source(name=source_name, url=url),
                    content=NewsContent(
                        title=title,
                        url=link,
                        published_date=published_date,
                        summary=desc,
                        full_text=full_text
                    ),
                    collectedAt=datetime.now(IST)
                )
                results.append(entity)
                
            return results
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []

    async def scrape_rss_jobs(self, url: str, source_name: str) -> List[Any]:
        """Scrapes jobs from an RSS feed."""
        from src.models.schemas import JobEntity, JobContent, Source
        from bs4 import BeautifulSoup
        import re
        
        logger.info(f"Fetching Jobs RSS: {url}")
        try:
            # Force headers to look like a browser so some RSS feeds don't block
            headers = {"User-Agent": "Mozilla/5.0"}
            xml_data = await self.fetch(url)
            soup = BeautifulSoup(xml_data, "xml")
            items = soup.find_all("item") or soup.find_all("entry")
            
            results = []
            for item in items:
                title_node = item.find("title")
                link_node = item.find("link")
                pubDate_node = item.find("pubDate") or item.find("updated") or item.find("published")
                desc_node = item.find("description") or item.find("summary")
                
                if not title_node or not link_node:
                    continue
                    
                title = title_node.text.strip()
                if link_node.text.strip():
                    link = link_node.text.strip()
                elif link_node.has_attr('href'):
                    link = link_node['href']
                else:
                    link = ""
                    
                date_str = pubDate_node.text.strip() if pubDate_node else None
                published_date = self.normalizer.normalize(date_str)
                
                if not self.is_fresh(published_date):
                    continue
                    
                company = None
                match = re.search(r'(?i)\bat\s+([A-Za-z0-9 ]+)', title)
                if match:
                    company = match.group(1).strip()

                # Derive is_remote from actual title/description text — do not assume
                desc_text = desc_node.text if desc_node else ""
                is_remote = bool(re.search(r'\bremote\b', title + " " + desc_text, re.IGNORECASE))
                
                entity = JobEntity(
                    source=Source(name=source_name, url=url),
                    collectedAt=datetime.now(IST),
                    content=JobContent(
                        company=company,
                        date=published_date,
                        is_remote=is_remote,
                        role_family="Engineering" if "engineer" in title.lower() or "developer" in title.lower() else "Other"
                    )
                )
                results.append(entity)
                
            return results
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
