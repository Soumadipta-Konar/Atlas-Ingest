"""
generate_csvs.py  v3
====================
Generates:
  output/products.csv  — Real ecommerce products scraped from:
                         * Flipkart (India, Playwright)          — electronics, gadgets
                         * Open Food Facts API (public, no auth) — packaged foods/products
  output/jobs.csv      — Real jobs & internships from RSS feeds:
                         * HackerNews Jobs   (hnrss.org/jobs)
                         * WeWorkRemotely    (weworkremotely.com)
                         * Unstop            (unstop.com/feed)
                         * HN Intern search  (hnrss.org/jobs?q=intern)
                         * GitHub Jobs       (hnrss.org/jobs?q=engineer)

All rows include original source URLs. No mocked data.
"""
import asyncio
import csv
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
os.makedirs("output", exist_ok=True)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AtlasIngestBot/2.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


# ============================================================
# 1. PRODUCTS  — Flipkart (Playwright) + Open Food Facts API
# ============================================================

FLIPKART_URLS = [
    ("Laptops",      "https://www.flipkart.com/laptops/pr?sid=6bo,b5g"),
    ("Smartphones",  "https://www.flipkart.com/mobiles/pr?sid=tyy,4io"),
    ("Headphones",   "https://www.flipkart.com/headphones-headsets/pr?sid=0pm,aog"),
    ("Smart TV",     "https://www.flipkart.com/televisions/pr?sid=ckf,czl"),
    ("Tablets",      "https://www.flipkart.com/tablets/pr?sid=tyy,hry"),
]


def parse_flipkart(html: str, category: str, source_url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []

    # Flipkart product cards carry class "_1AtVbE" or "_13oc-S" or "DOjaWF"
    cards = (
        soup.select("div._1AtVbE")
        or soup.select("div.DOjaWF")
        or soup.select("div._13oc-S")
        or soup.select("div[data-id]")
    )

    for card in cards:
        try:
            # Title
            name_el = (
                card.select_one("div._4rR01T")
                or card.select_one("a.s1Q9rs")
                or card.select_one("div.KzDlHZ")
                or card.select_one("a[title]")
            )
            name = name_el.get_text(strip=True) if name_el else None
            if not name or len(name) < 5:
                continue

            # URL
            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el else None
            if href:
                product_url = f"https://www.flipkart.com{href}" if href.startswith("/") else href
                product_url = product_url.split("?")[0]   # strip tracking
            else:
                continue

            # Price
            price_el = card.select_one("div._30jeq3") or card.select_one("div.Nx9bqj")
            price = price_el.get_text(strip=True) if price_el else None

            # Rating
            rating_el = card.select_one("div._3LWZlK") or card.select_one("div.XQDdHH")
            rating = rating_el.get_text(strip=True) if rating_el else None

            products.append({
                "recordType": "ECOMMERCE_PRODUCT",
                "source.name": "Flipkart",
                "source.url": source_url,
                "content.productName": name,
                "content.category": category,
                "content.price": price,
                "content.rating": rating,
                "content.product_url": product_url,
                "collectedAt": datetime.now(IST).isoformat(),
            })
        except Exception as e:
            logger.debug(f"Card parse error: {e}")

    return products


async def scrape_flipkart() -> List[Dict]:
    """Scrape Flipkart using Playwright (handles JS rendering + cookies)."""
    from playwright.async_api import async_playwright

    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=BROWSER_UA,
            locale="en-IN",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        for category, url in FLIPKART_URLS:
            logger.info(f"Flipkart [{category}]: {url}")
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Dismiss login popup if it appears
                try:
                    await page.click("button._2KpZ6l._2doB4z", timeout=3000)
                except Exception:
                    pass
                try:
                    await page.wait_for_selector("div._1AtVbE, div.DOjaWF", timeout=8000)
                except Exception:
                    logger.warning(f"  -> No product cards for {category}")
                html = await page.content()
                await page.close()

                products = parse_flipkart(html, category, url)
                logger.info(f"  -> {len(products)} products")
                all_products.extend(products)
            except Exception as e:
                logger.error(f"  -> Flipkart error [{category}]: {e}")
            await asyncio.sleep(2)

        await browser.close()

    return all_products


async def scrape_openfoodfacts(session: aiohttp.ClientSession) -> List[Dict]:
    """Fetch real product data from Open Food Facts public JSON API (no auth needed)."""
    categories = [
        ("Beverages",  "beverages"),
        ("Snacks",     "snacks"),
        ("Dairy",      "dairies"),
        ("Cereals",    "cereals"),
        ("Chocolates", "chocolates"),
    ]
    all_products = []

    for label, cat in categories:
        url = f"https://world.openfoodfacts.org/category/{cat}.json?page_size=40&page=1"
        logger.info(f"Open Food Facts [{label}]: {url}")
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    logger.warning(f"  -> HTTP {r.status}")
                    continue
                data = await r.json(content_type=None)
                items = data.get("products", [])
                logger.info(f"  -> {len(items)} items")

                for item in items:
                    name = item.get("product_name") or item.get("product_name_en")
                    if not name or len(name) < 3:
                        continue
                    barcode = item.get("code", "")
                    brand = item.get("brands", "")
                    product_url = f"https://world.openfoodfacts.org/product/{barcode}" if barcode else "https://world.openfoodfacts.org"
                    nutri = item.get("nutriscore_grade", "").upper()
                    quantity = item.get("quantity", "")
                    countries = item.get("countries", "")

                    all_products.append({
                        "recordType": "ECOMMERCE_PRODUCT",
                        "source.name": "Open Food Facts",
                        "source.url": url,
                        "content.productName": name,
                        "content.category": label,
                        "content.price": None,
                        "content.brand": brand,
                        "content.quantity": quantity,
                        "content.nutriscore": nutri,
                        "content.countries": countries[:80] if countries else None,
                        "content.product_url": product_url,
                        "collectedAt": datetime.now(IST).isoformat(),
                    })
        except Exception as e:
            logger.error(f"  -> Error for {label}: {e}")
        await asyncio.sleep(0.5)

    return all_products


# ============================================================
# 2. JOBS / INTERNSHIPS — RSS feeds
# ============================================================

JOB_RSS_SOURCES = [
    ("HackerNews Jobs",     "https://hnrss.org/jobs"),
    ("HN Internships",      "https://hnrss.org/jobs?q=intern"),
    ("HN Engineer Jobs",    "https://hnrss.org/jobs?q=engineer"),
    ("WeWorkRemotely",      "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
    ("WeWorkRemotely Dev",  "https://weworkremotely.com/categories/remote-dev-software-jobs.rss"),
    ("Unstop",              "https://unstop.com/feed"),
    ("Python.org Jobs",     "https://www.python.org/jobs/feed/rss/"),
]


def parse_date(s: Optional[str]) -> str:
    if not s:
        return datetime.now(IST).isoformat()
    s = s.strip()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).astimezone(IST).isoformat()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(IST).isoformat()
    except Exception:
        return datetime.now(IST).isoformat()


def company_from_title(title: str) -> Optional[str]:
    for pat in [
        r"(?i)\bat\s+([A-Za-z0-9][A-Za-z0-9\s&\.\-]+?)(?:\s*[-–|,\(]|$)",
        r"(?i)^([A-Za-z0-9][A-Za-z0-9\s&\.]+?)\s*(?:is\s+hiring|hiring|–|-)",
        r"(?i)\(([A-Za-z0-9][A-Za-z0-9\s&\.]+)\)",
    ]:
        m = re.search(pat, title)
        if m:
            c = m.group(1).strip()
            if 2 < len(c) < 60:
                return c
    return None


def role_family(title: str, desc: str) -> str:
    text = (title + " " + desc).lower()
    if any(k in text for k in ["intern", "internship", "trainee", "fellowship"]):
        return "Internship"
    if any(k in text for k in ["data scientist", "ml engineer", "machine learning", "deep learning", "llm", "ai engineer"]):
        return "Data/ML"
    if any(k in text for k in ["frontend", "front-end", "react", "vue", "angular", "ui developer"]):
        return "Frontend"
    if any(k in text for k in ["backend", "back-end", "api", "django", "flask", "fastapi", "node"]):
        return "Backend"
    if any(k in text for k in ["fullstack", "full stack", "full-stack"]):
        return "Fullstack"
    if any(k in text for k in ["devops", "sre", "infrastructure", "platform", "cloud", "kubernetes", "docker"]):
        return "DevOps/Infra"
    if any(k in text for k in ["engineer", "developer", "swe", "sde", "software"]):
        return "Engineering"
    if any(k in text for k in ["design", "ux", "ui/ux", "product designer"]):
        return "Design"
    if any(k in text for k in ["market", "growth", "sales", "business development"]):
        return "Business"
    return "Other"


async def scrape_jobs(session: aiohttp.ClientSession) -> List[Dict]:
    all_jobs = []

    for source_name, rss_url in JOB_RSS_SOURCES:
        logger.info(f"Jobs RSS [{source_name}]: {rss_url}")
        try:
            async with session.get(rss_url, headers=RSS_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    logger.warning(f"  -> HTTP {r.status}")
                    continue
                text = await r.text()
        except Exception as e:
            logger.error(f"  -> {e}")
            continue

        try:
            soup = BeautifulSoup(text, "xml")
            items = soup.find_all("item") or soup.find_all("entry")
            logger.info(f"  -> {len(items)} raw items")

            for item in items:
                title_el = item.find("title")
                link_el  = item.find("link")
                date_el  = item.find("pubDate") or item.find("updated") or item.find("published")
                desc_el  = item.find("description") or item.find("summary") or item.find("content")

                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue

                if link_el:
                    job_url = (link_el.get_text(strip=True)
                               or link_el.get("href", rss_url))
                else:
                    job_url = rss_url

                desc_text = desc_el.get_text(strip=True)[:300] if desc_el else ""
                published = parse_date(date_el.get_text(strip=True) if date_el else None)
                company = company_from_title(title)
                is_remote = bool(re.search(r"\bremote\b", title + " " + desc_text, re.IGNORECASE))

                all_jobs.append({
                    "recordType": "JOB",
                    "source.name": source_name,
                    "source.url": rss_url,
                    "content.title": title,
                    "content.company": company,
                    "content.job_url": job_url,
                    "content.date": published,
                    "content.is_remote": is_remote,
                    "content.role_family": role_family(title, desc_text),
                    "content.description_snippet": desc_text[:200],
                    "collectedAt": datetime.now(IST).isoformat(),
                })
        except Exception as e:
            logger.error(f"  -> Parse error: {e}")

    # Deduplicate by job_url
    seen: set = set()
    deduped = []
    for j in all_jobs:
        k = j["content.job_url"]
        if k not in seen:
            seen.add(k)
            deduped.append(j)

    logger.info(f"Jobs total: {len(deduped)} unique listings")
    return deduped


# ============================================================
# CSV writer
# ============================================================
def write_csv(rows: List[Dict], path: str):
    if not rows:
        logger.warning(f"No data for {path}")
        return
    # Collect all keys across all rows (different sources may have different fields)
    all_keys: list = []
    seen_keys: set = set()
    for row in rows:
        for k in row:
            if k not in seen_keys:
                all_keys.append(k)
                seen_keys.add(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {len(rows)} rows -> {path}")


# ============================================================
# Main
# ============================================================
async def main():
    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Jobs and Open Food Facts run via aiohttp; Flipkart uses Playwright
        jobs_task = asyncio.create_task(scrape_jobs(session))
        off_task  = asyncio.create_task(scrape_openfoodfacts(session))

        flipkart_products = await scrape_flipkart()   # sequential Playwright
        off_products, jobs = await asyncio.gather(off_task, jobs_task)

    all_products = flipkart_products + off_products

    write_csv(all_products, "output/products.csv")
    write_csv(jobs, "output/jobs.csv")

    print(f"\n{'='*55}")
    print(f"  products.csv : {len(all_products)} records  "
          f"(Flipkart: {len(flipkart_products)}, OpenFoodFacts: {len(off_products)})")
    print(f"  jobs.csv     : {len(jobs)} unique job/internship records")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    asyncio.run(main())
