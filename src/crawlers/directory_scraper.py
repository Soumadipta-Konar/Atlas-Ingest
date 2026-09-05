import logging
import asyncio
from typing import List, Dict, Any, TypeVar, Type, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseCrawler
from src.models.schemas import StartupEntity, StartupContent, Source, ProductEntity, ProductContent, PricingModel, EcommerceProductEntity, EcommerceProductContent
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DirectoryScraper(BaseCrawler):
    """Generic Scraper for massive directories (e.g. Amazon, ProductHunt)"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def scrape_directory(self, start_url: str, entity_type: str, orchestrator: Any, max_records: int = 1000) -> List[BaseModel]:
        """Scrapes a directory URL and extracts entities by parsing DOM and using LLM."""
        logger.info(f"Targeting {start_url} for {max_records} {entity_type} records...")
        results = []
        
        html = await self.fetch(start_url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Broad heuristic to find item cards across any e-commerce/directory site
        items = soup.find_all(["div", "li"], class_=lambda c: c and any(k in c.lower() for k in ["card", "item", "result", "product", "grid"]))
        
        if not items:
            logger.warning("Could not find standard item cards. Falling back to all list items.")
            items = soup.find_all("li")
            
        logger.info(f"Found {len(items)} potential items on page. Passing to LLM Extraction Engine...")
        
        target_count = min(max_records, len(items))
        
        schema_map = {
            "startup": StartupEntity,
            "product": ProductEntity,
            "ecommerce": EcommerceProductEntity
        }
        target_schema = schema_map.get(entity_type, ProductEntity)
        
        # Concurrency control for LLM API to prevent immediate 429 Rate Limits
        sem = asyncio.Semaphore(10)
        
        async def process_item(item):
            text_chunk = item.get_text(separator=' | ', strip=True)
            # Only process chunks that seem to have real content
            if len(text_chunk) > 20:
                async with sem:
                    try:
                        return await orchestrator.extract_entity(text_chunk, target_schema)
                    except Exception as e:
                        logger.debug(f"LLM failed to extract entity: {e}")
                        return None
            return None
            
        tasks = [process_item(item) for item in items[:target_count]]
        extracted_entities = await asyncio.gather(*tasks)
        
        for item, text_chunk in zip(items[:target_count], [item.get_text(separator=' | ', strip=True) for item in items[:target_count]]):
            if len(text_chunk) <= 20:
                continue
                
            idx = items.index(item)
            entity = extracted_entities[idx] if idx < len(extracted_entities) else None
            
            if entity:
                # Add source metadata dynamically
                entity.source = Source(name="Directory", url=start_url)
                entity.collectedAt = datetime.utcnow()
                results.append(entity)
            else:
                # Heuristic fallback if LLM completely fails (e.g., API key errors, rate limits)
                lines = [line.strip() for line in text_chunk.split('|') if line.strip()]
                
                # Filter out common UI junk words and very short lines
                junk = [
                    "sponsored", "trending", "results", "cart", "home", "orders", "shortcuts", "other color", 
                    "amazon's", "items related", "need help", "conditions of use", "debug info", "price:", "stars",
                    "keyboard", "buying options", "relevance to your search query", "for \"", "to move between items",
                    "check each product page", "you are seeing this ad", "customer review", "save extra with",
                    "free delivery"
                ]
                valid_lines = [l for l in lines if len(l) > 15 and not any(j in l.lower() for j in junk)]
                
                if not valid_lines:
                    continue
                name = valid_lines[0]
                
                if entity_type == "ecommerce":
                    price = next((l for l in lines if "$" in l or "₹" in l or "€" in l or "Rs" in l or "₹" in l), None)
                    results.append(EcommerceProductEntity(
                        source=Source(name="HeuristicFallback", url=start_url),
                        content=EcommerceProductContent(productName=name, price=price),
                        collectedAt=datetime.utcnow()
                    ))
                elif entity_type == "product":
                    results.append(ProductEntity(
                        source=Source(name="HeuristicFallback", url=start_url),
                        content=ProductContent(startupName=name, pricingModel=PricingModel.FREEMIUM),
                        collectedAt=datetime.utcnow()
                    ))
        
        # Deduplicate results based on product/startup name
        unique_results = []
        seen_names = set()
        for r in results:
            name = getattr(r.content, 'productName', None) or getattr(r.content, 'startupName', None)
            if name and name not in seen_names:
                seen_names.add(name)
                unique_results.append(r)
                
        logger.info(f"Successfully extracted {len(unique_results)} valid {entity_type} records (after deduplication).")
        return unique_results
