import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseCrawler
from src.models.schemas import ResearchPaperEntity, ResearchPaperContent

logger = logging.getLogger(__name__)

class ArxivScraper(BaseCrawler):
    """Scraper for Arxiv research papers."""
    
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def fetch_papers(self, query: str = "all:AI", max_results: int = 100) -> List[ResearchPaperEntity]:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        xml_data = await self.fetch(self.BASE_URL, params=params)
        return await self._parse_arxiv_xml(xml_data)

    async def _parse_arxiv_xml(self, xml_content: str) -> List[ResearchPaperEntity]:
        soup = BeautifulSoup(xml_content, "xml")
        entries = soup.find_all("entry")
        
        results = []
        for entry in entries:
            try:
                title = entry.title.text.strip().replace("\n", " ")
                authors = [author.find("name").text for author in entry.find_all("author")]
                paper_url = entry.id.text.strip()
                published_date = datetime.strptime(entry.published.text, "%Y-%m-%dT%H:%M:%SZ")
                
                content = ResearchPaperContent(
                    title=title,
                    authors=authors,
                    paper_url=paper_url,
                    published_date=published_date,
                    github_url=None, # Will be correlated later
                    github_stars=None
                )
                
                results.append(ResearchPaperEntity(
                    content=content,
                    collectedAt=datetime.utcnow()
                ))
            except Exception as e:
                logger.error(f"Error parsing arxiv entry: {e}")
                
        return results

    async def correlate_github(self, paper: ResearchPaperEntity) -> ResearchPaperEntity:
        # Mock correlation logic for demo (Papers with Code API would be used here)
        # Assuming correlation finds a github URL
        paper.content.github_url = "https://github.com/example/repo"
        paper.content.github_stars = 420
        return paper
