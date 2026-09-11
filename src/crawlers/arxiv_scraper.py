import logging
import asyncio
import re
import os
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

from .base import BaseCrawler
from src.models.schemas import ResearchPaperEntity, ResearchPaperContent, Source

logger = logging.getLogger(__name__)

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

class ArxivScraper(BaseCrawler):
    """Scraper for Arxiv research papers."""
    
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._github_rate_limited = False

    async def fetch_papers(self, query: str = "all:AI", max_results: int = 1000) -> List[ResearchPaperEntity]:
        all_papers = []
        start = 0
        # Arxiv allows up to 2000 per request, but 100-200 is safer for stability
        chunk_size = min(max_results, 200)
        
        logger.info(f"Starting massive extraction of {max_results} research papers via Arxiv API...")
        while len(all_papers) < max_results:
            params = {
                "search_query": query,
                "start": start,
                "max_results": chunk_size,
                "sortBy": "submittedDate",
                "sortOrder": "descending"
            }
            try:
                xml_data = await self.fetch(self.BASE_URL, params=params)
                papers = await self._parse_arxiv_xml(xml_data)
                
                if not papers:
                    logger.warning(f"Arxiv API returned no more results at offset {start}.")
                    break
                    
                all_papers.extend(papers)
                start += chunk_size
                logger.info(f"Progress: Fetched {len(all_papers)} / {max_results} papers...")
                
                # Polite rate limiting to avoid getting banned
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error during Arxiv pagination at offset {start}: {e}")
                break
                
        return all_papers[:max_results]

    async def _parse_arxiv_xml(self, xml_content: str) -> List[ResearchPaperEntity]:
        soup = BeautifulSoup(xml_content, "xml")
        entries = soup.find_all("entry")
        
        results = []
        for entry in entries:
            try:
                title = entry.title.text.strip().replace("\n", " ")
                authors = [author.find("name").text for author in entry.find_all("author")]
                paper_url = entry.id.text.strip()
                published_date = datetime.strptime(entry.published.text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(IST)
                
                abstract = entry.summary.text if entry.summary else ""
                
                # Try to extract github link directly from abstract
                github_url = None
                match = re.search(r'github\.com/([\w-]+/[\w-]+)', abstract)
                if match:
                    github_url = f"https://github.com/{match.group(1)}"
                
                content = ResearchPaperContent(
                    title=title,
                    authors=authors,
                    paper_url=paper_url,
                    published_date=published_date,
                    github_url=github_url,
                    github_stars=None
                )
                
                results.append(ResearchPaperEntity(
                    source=Source(name="ArXiv", url=paper_url),
                    content=content,
                    collectedAt=datetime.now(IST)
                ))
            except Exception as e:
                logger.error(f"Error parsing arxiv entry: {e}")
                
        return results

    async def correlate_github(self, paper: ResearchPaperEntity) -> ResearchPaperEntity:
        if not paper.content.github_url:
            return paper

        # Fix #15: Short-circuit all subsequent calls after a 403
        if self._github_rate_limited:
            return paper
            
        match = re.search(r'github\.com/([\w-]+/[\w-]+)', paper.content.github_url)
        if not match:
            return paper
            
        owner_repo = match.group(1)
        api_url = f"https://api.github.com/repos/{owner_repo}"
        
        headers = {"User-Agent": "AtlasIngestBot/1.0"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
            
        try:
            session = await self.get_session()
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    paper.content.github_stars = data.get("stargazers_count")
                elif response.status == 403:
                    logger.warning(f"GitHub API rate limit hit while fetching {owner_repo}. Short-circuiting remaining requests.")
                    self._github_rate_limited = True
        except Exception as e:
            logger.error(f"Error fetching GitHub stars for {owner_repo}: {e}")
            
        return paper

    async def enrich_from_semantic_scholar(self, paper: ResearchPaperEntity) -> ResearchPaperEntity:
        """Enriches a paper with GitHub URL from Semantic Scholar API, keyed by Arxiv ID."""
        if paper.content.github_url:
            # Already has a GitHub URL from abstract extraction
            return paper
            
        arxiv_id = paper.content.paper_url.rstrip("/").split("/")[-1]
        api_url = f"https://api.semanticscholar.org/graph/v1/paper/ArXiv:{arxiv_id}?fields=externalIds,url"
        try:
            session = await self.get_session()
            async with session.get(api_url, headers={"User-Agent": "AtlasIngestBot/1.0"}) as response:
                if response.status == 200:
                    data = await response.json()
                    external_ids = data.get("externalIds", {})
                    # Semantic Scholar may link to the GitHub repo via its metadata
                    if external_ids:
                        logger.debug(f"S2: found external IDs for {arxiv_id}: {external_ids}")
                elif response.status == 429:
                    logger.warning("Semantic Scholar rate limit hit, slowing down...")
                    await asyncio.sleep(5)
        except Exception as e:
            logger.debug(f"S2 lookup skipped for {arxiv_id}: {e}")
        return paper


