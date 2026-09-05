import logging
import asyncio
from typing import Optional, Dict, Any
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class BaseCrawler:
    """Base class for HTTP requests with rate limiting and exponential backoff."""
    
    def __init__(self, concurrency_limit: int = 50, use_playwright: bool = False):
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.use_playwright = use_playwright
        self._session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def fetch(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        async with self.semaphore:
            if self.use_playwright:
                return await self._fetch_playwright(url)
            
            session = await self.get_session()
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.text()

    async def _fetch_playwright(self, url: str) -> str:
        # Fallback for Cloudflare/JS rendered pages
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"]
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            content = await page.content()
            await browser.close()
            return content

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
