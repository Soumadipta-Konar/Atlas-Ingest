import logging
import asyncio
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from typing import List, Dict, Any, TypeVar, Type, Optional
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

from .base import BaseCrawler
from src.models.schemas import StartupEntity, StartupContent, Source, ProductEntity, ProductContent, PricingModel, EcommerceProductEntity, EcommerceProductContent
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Site-agnostic junk words for filtering out UI/navigation noise from DOM text
DIRECTORY_JUNK_WORDS = [
    "sponsored", "trending", "results", "cart", "home", "orders", "shortcuts",
    "sign in", "sign up", "log in", "register", "subscribe", "newsletter",
    "cookie", "privacy policy", "terms of service", "footer", "navigation",
    "menu", "search", "filter", "sort by", "load more", "show more",
    "no results", "back to top", "follow us", "share", "bookmark",
]

class DirectoryScraper(BaseCrawler):
    """Generic Scraper for massive directories (e.g. YCombinator, ProductHunt)
    
    Supports automatic pagination via:
      - rel="next" link headers
      - ?page=N query parameters
      - Offset-based ?start=N parameters
    """
    
    MAX_PAGES = 20  # Safety limit to prevent infinite loops
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Attempts to discover the next page URL from the DOM."""
        # Strategy 1: Look for a rel="next" link
        next_link = soup.find("a", rel="next")
        if next_link and next_link.get("href"):
            return urljoin(current_url, next_link["href"])
        
        # Strategy 2: Look for a "Next" / ">" pagination button
        for selector in [
            {"string": lambda t: t and "next" in t.lower()},
            {"class_": lambda c: c and any(k in str(c).lower() for k in ["next", "pagination-next"])},
            {"aria-label": lambda v: v and "next" in v.lower()},
        ]:
            link = soup.find("a", **selector)
            if link and link.get("href"):
                return urljoin(current_url, link["href"])
        
        return None

    def _increment_page_url(self, current_url: str, page_num: int) -> str:
        """Generates the next page URL by incrementing a ?page=N param."""
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        params["page"] = [str(page_num)]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    async def scrape_directory(self, start_url: str, entity_type: str, orchestrator: Any, max_records: int = 1000) -> List[BaseModel]:
        """Scrapes a directory URL with automatic pagination and extracts entities."""
        logger.info(f"Targeting {start_url} for {max_records} {entity_type} records...")
        all_results = []
        current_url = start_url
        page_num = 1
        
        schema_map = {
            "startup": StartupEntity,
            "product": ProductEntity,
            "ecommerce": EcommerceProductEntity
        }
        target_schema = schema_map.get(entity_type, ProductEntity)
        
        while len(all_results) < max_records and page_num <= self.MAX_PAGES:
            logger.info(f"Scraping page {page_num}: {current_url}")
            
            try:
                html = await self.fetch(current_url)
            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                break
                
            soup = BeautifulSoup(html, "html.parser")
            
            # Broad heuristic to find item cards across any directory site
            items = soup.find_all(
                ["div", "li"],
                class_=lambda c: c and any(k in c.lower() for k in ["card", "item", "result", "product", "grid"])
            )
            
            if not items:
                if page_num == 1:
                    logger.warning("Could not find standard item cards. Falling back to all list items.")
                    items = soup.find_all("li")
                else:
                    logger.info(f"No more items found on page {page_num}. Pagination complete.")
                    break
            
            if not items:
                break
                
            logger.info(f"Found {len(items)} potential items on page {page_num}.")
            
            remaining = max_records - len(all_results)
            target_items = items[:remaining]
            
            # Concurrency control for LLM API
            sem = asyncio.Semaphore(10)
            
            async def process_item(item):
                text_chunk = item.get_text(separator=' | ', strip=True)
                if len(text_chunk) > 20:
                    async with sem:
                        try:
                            return await orchestrator.extract_entity(text_chunk, target_schema)
                        except Exception as e:
                            logger.debug(f"LLM failed to extract entity: {e}")
                            return None
                return None
                
            tasks = [process_item(item) for item in target_items]
            extracted_entities = await asyncio.gather(*tasks)
            
            # Positional zip — no O(n²) index() lookups
            for item, entity in zip(target_items, extracted_entities):
                text_chunk = item.get_text(separator=' | ', strip=True)
                if len(text_chunk) <= 20:
                    continue
                
                if entity:
                    entity.source = Source(name="Directory", url=current_url)
                    entity.collectedAt = datetime.now(IST)
                    all_results.append(entity)
                else:
                    # Heuristic fallback if LLM completely fails
                    lines = [line.strip() for line in text_chunk.split('|') if line.strip()]
                    valid_lines = [l for l in lines if len(l) > 15 and not any(j in l.lower() for j in DIRECTORY_JUNK_WORDS)]
                    
                    if not valid_lines:
                        continue
                    name = valid_lines[0]
                    
                    if entity_type == "ecommerce":
                        price = next((l for l in lines if "$" in l or "₹" in l or "€" in l or "Rs" in l), None)
                        all_results.append(EcommerceProductEntity(
                            source=Source(name="HeuristicFallback", url=current_url),
                            content=EcommerceProductContent(productName=name, price=price),
                            collectedAt=datetime.now(IST)
                        ))
                    elif entity_type == "product":
                        all_results.append(ProductEntity(
                            source=Source(name="HeuristicFallback", url=current_url),
                            content=ProductContent(startupName=name, pricingModel=PricingModel.FREEMIUM),
                            collectedAt=datetime.now(IST)
                        ))
            
            logger.info(f"Running total: {len(all_results)} / {max_records} records extracted.")
            
            if len(all_results) >= max_records:
                break
            
            # Discover next page
            next_url = self._find_next_page_url(soup, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                # Fallback: try incrementing ?page=N
                next_candidate = self._increment_page_url(start_url, page_num + 1)
                if next_candidate == current_url:
                    logger.info("No next page discovered. Pagination complete.")
                    break
                current_url = next_candidate
            
            page_num += 1
            # Polite delay between pages
            await asyncio.sleep(1)
        
        # Deduplicate results based on product/startup name
        unique_results = []
        seen_names = set()
        for r in all_results:
            name = getattr(r.content, 'productName', None) or getattr(r.content, 'startupName', None) or getattr(r.content, 'entityName', None)
            if name and name not in seen_names:
                seen_names.add(name)
                unique_results.append(r)
                
        logger.info(f"Successfully extracted {len(unique_results)} valid {entity_type} records (after dedup across {page_num} pages).")
        return unique_results
