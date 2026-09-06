"""
fill_gaps.py
============
Fills the two missing CSVs:
  output/startups.csv       — 1,000+ rows via YCombinator companies list (Playwright)
  output/entity_mappings.csv — populated as a side-effect of startup resolution
  output/products.csv       — 1,000+ rows via:
                               * Shopify public /products.json APIs (no auth needed)
                               * Open Food Facts JSON API (no auth needed)
"""
import asyncio
import csv
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
os.makedirs("output", exist_ok=True)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ============================================================
# 1. STARTUPS  —  YCombinator companies via Playwright
# ============================================================
async def scrape_yc_startups() -> List[Dict]:
    from playwright.async_api import async_playwright

    all_startups = []
    seen_names: set = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()
        url = "https://www.ycombinator.com/companies"
        logger.info(f"Loading YC companies: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)

        # Wait for initial cards
        try:
            await page.wait_for_selector("a[href*='/companies/']", timeout=15000)
        except Exception:
            logger.warning("Initial card wait timed out")

        # Scroll using JS count — avoids fragile hashed class selectors
        prev_count = 0
        stall_count = 0
        for scroll_num in range(60):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.2)
            count_now = await page.evaluate(
                "document.querySelectorAll(\"a[href^='/companies/']\").length"
            )
            logger.info(f"  Scroll {scroll_num+1}: {count_now} company links")
            if count_now >= 1020:
                logger.info("  Reached 1020 — stopping")
                break
            if count_now == prev_count:
                stall_count += 1
                if stall_count >= 5:
                    logger.info("  No new cards for 5 scrolls — end of list")
                    break
            else:
                stall_count = 0
            prev_count = count_now

        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    # Match all company links by href pattern (avoids hashed class names)
    all_links = soup.select("a[href]")
    cards = [c for c in all_links if re.match(r"^/companies/[a-z0-9\-]+$", c.get("href", ""))]
    logger.info(f"YC HTML parsed: {len(cards)} company cards")

    for card in cards:
        try:
            texts = [t.strip() for t in card.get_text(separator="|").split("|") if t.strip()]
            if not texts:
                continue
            name = texts[0]
            if not name or len(name) < 2:
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            href = card.get("href", "")
            company_url = f"https://www.ycombinator.com{href}"
            desc = " ".join(texts[1:3])[:200] if len(texts) > 1 else None

            all_startups.append({
                "schemaVersion": "1.0",
                "recordType": "STARTUP",
                "source.name": "YCombinator",
                "source.url": company_url,
                "content.entityName": name,
                "content.data.description": desc,
                "content.data.batch": None,
                "content.data.foundedYear": None,
                "content.data.fundingStage": "YC",
                "collectedAt": datetime.now(IST).isoformat(),
            })
        except Exception as e:
            logger.debug(f"Card parse error: {e}")

    logger.info(f"YC startups scraped: {len(all_startups)}")
    return all_startups


# ============================================================
# 2. ENTITY MAPPING LOG  — fuzzy match against seed list
# ============================================================
def build_entity_mappings(startups: List[Dict]) -> List[Dict]:
    from thefuzz import process
    SEED = [
        "OpenAI","Anthropic","DeepMind","Mistral AI","Cohere","Hugging Face",
        "Perplexity","Scale AI","Midjourney","Stability AI","Meta AI","Google AI",
        "xAI","Inflection AI","Databricks","Runway","Jasper AI","Adept AI",
        "Character AI","Together AI","Replicate","Anyscale","Weights & Biases",
        "LangChain","Pinecone","Weaviate","Galileo AI","Snorkel AI","Mosaic ML",
        "Lightning AI","Aleph Alpha","AI21 Labs","Imbue","Contextual AI","Descript",
        "ElevenLabs","Pika Labs","Luma AI","Synthesia","Twelve Labs","Tome","Glean",
        "Vectara","Qdrant","Chroma","LlamaIndex","Fixie AI","Dust","Comet ML","Superagent",
    ]
    mappings = []
    for s in startups:
        raw = s.get("content.entityName", "")
        result = process.extractOne(raw, SEED)
        if result and result[1] >= 85:
            canonical, score = result[0], result[1]
            s["content.entityName"] = canonical  # update in-place
        else:
            canonical, score = raw, 0
        mappings.append({"Raw Name": raw, "Canonical Name": canonical, "Match Score": score})
    return mappings


# ============================================================
# 3. PRODUCTS  —  Shopify public JSON + Open Food Facts
# ============================================================

# These Shopify stores expose /products.json publicly (no auth)
SHOPIFY_STORES = [
    ("Gymshark",        "https://www.gymshark.com/products.json"),
    ("Allbirds",        "https://www.allbirds.com/products.json"),
    ("MVMT Watches",    "https://www.mvmt.com/products.json"),
    ("Kylie Cosmetics", "https://www.kyliecosmetics.com/products.json"),
    ("Brooklinen",      "https://www.brooklinen.com/products.json"),
    ("Chubbies",        "https://www.chubbies.com/products.json"),
    ("Taylor Stitch",   "https://www.taylorstitch.com/products.json"),
    ("Kettle & Fire",   "https://www.kettleandfire.com/products.json"),
    ("Death Wish Coffee","https://www.deathwishcoffee.com/products.json"),
    ("Beardbrand",      "https://www.beardbrand.com/products.json"),
    ("Ratio Coffee",    "https://ratiocoffee.com/products.json"),
    ("Partake Foods",   "https://partakefoods.com/products.json"),
    ("Solo Stove",      "https://www.solostove.com/products.json"),
    ("Ridge Wallet",    "https://www.ridge.com/products.json"),
    ("Bombas",          "https://bombas.com/products.json"),
    ("True Classic",    "https://trueclassictees.com/products.json"),
    ("Vuori",           "https://vuoriclothing.com/products.json"),
    ("Caraway Home",    "https://www.carawayhome.com/products.json"),
    ("Our Place",       "https://fromourplace.com/products.json"),
    ("Public Goods",    "https://www.publicgoods.com/products.json"),
]

OPENFOODFACTS_CATEGORIES = [
    ("Beverages", "beverages"),
    ("Snacks", "snacks"),
    ("Dairy", "dairies"),
    ("Cereals", "cereals"),
    ("Chocolates", "chocolates"),
    ("Biscuits", "biscuits"),
    ("Jams", "jams-and-marmalades"),
    ("Sauces", "sauces"),
    ("Pasta", "pastas"),
    ("Chips", "potato-chips"),
]


async def scrape_shopify(session: aiohttp.ClientSession) -> List[Dict]:
    all_products = []
    seen_urls: set = set()

    for store_name, url in SHOPIFY_STORES:
        logger.info(f"Shopify [{store_name}]: {url}")
        # Paginate through all pages
        page_num = 1
        while True:
            paged_url = f"{url}?limit=250&page={page_num}"
            try:
                async with session.get(
                    paged_url,
                    headers={"User-Agent": BROWSER_UA},
                    timeout=aiohttp.ClientTimeout(total=20),
                    ssl=False
                ) as r:
                    if r.status != 200:
                        logger.warning(f"  -> HTTP {r.status} (page {page_num})")
                        break
                    data = await r.json(content_type=None)
            except Exception as e:
                logger.warning(f"  -> Error: {e}")
                break

            items = data.get("products", [])
            if not items:
                break

            for item in items:
                try:
                    title = item.get("title", "")
                    if not title:
                        continue
                    handle = item.get("handle", "")
                    # Build canonical product URL from store domain
                    store_domain = url.replace("/products.json", "")
                    product_url = f"{store_domain}/products/{handle}"
                    if product_url in seen_urls:
                        continue
                    seen_urls.add(product_url)

                    vendor = item.get("vendor", "")
                    product_type = item.get("product_type", "")
                    tags = ", ".join(item.get("tags", []))[:100]
                    # Price from first variant
                    variants = item.get("variants", [])
                    price = variants[0].get("price") if variants else None
                    if price:
                        price = f"${price}"
                    currency = "USD"
                    # Availability
                    available = any(v.get("available", False) for v in variants)

                    all_products.append({
                        "recordType": "ECOMMERCE_PRODUCT",
                        "source.name": store_name,
                        "source.url": product_url,
                        "content.productName": title,
                        "content.category": product_type or "General",
                        "content.brand": vendor,
                        "content.price": price,
                        "content.currency": currency,
                        "content.available": available,
                        "content.tags": tags,
                        "content.product_url": product_url,
                        "collectedAt": datetime.now(IST).isoformat(),
                    })
                except Exception as e:
                    logger.debug(f"  Item error: {e}")

            logger.info(f"  -> Page {page_num}: {len(items)} items  (total so far: {len(all_products)})")
            if len(items) < 250:
                break  # last page
            page_num += 1
            await asyncio.sleep(0.3)

        await asyncio.sleep(0.5)

    logger.info(f"Shopify total: {len(all_products)} products")
    return all_products


async def scrape_openfoodfacts(session: aiohttp.ClientSession, target: int = 400) -> List[Dict]:
    all_products = []
    per_page = 50

    for label, cat in OPENFOODFACTS_CATEGORIES:
        if len(all_products) >= target:
            break
        for page_num in range(1, 6):
            url = f"https://world.openfoodfacts.org/category/{cat}.json?page_size={per_page}&page={page_num}"
            logger.info(f"OpenFoodFacts [{label} p{page_num}]: {url}")
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20), ssl=False) as r:
                    if r.status != 200:
                        logger.warning(f"  -> HTTP {r.status}")
                        break
                    data = await r.json(content_type=None)
            except Exception as e:
                logger.warning(f"  -> {e}")
                break

            items = data.get("products", [])
            if not items:
                break

            for item in items:
                name = item.get("product_name") or item.get("product_name_en", "")
                if not name or len(name) < 3:
                    continue
                barcode = item.get("code", "")
                product_url = f"https://world.openfoodfacts.org/product/{barcode}" if barcode else "https://world.openfoodfacts.org"
                all_products.append({
                    "recordType": "ECOMMERCE_PRODUCT",
                    "source.name": "Open Food Facts",
                    "source.url": product_url,
                    "content.productName": name,
                    "content.category": label,
                    "content.brand": item.get("brands", ""),
                    "content.price": None,
                    "content.currency": None,
                    "content.available": True,
                    "content.tags": item.get("categories_tags", [""])[0].replace("en:", "") if item.get("categories_tags") else "",
                    "content.product_url": product_url,
                    "collectedAt": datetime.now(IST).isoformat(),
                })
            logger.info(f"  -> {len(items)} items  (total: {len(all_products)})")
            await asyncio.sleep(0.4)

    logger.info(f"OpenFoodFacts total: {len(all_products)} products")
    return all_products


# ============================================================
# CSV writer
# ============================================================
def write_csv(rows: List[Dict], path: str):
    if not rows:
        logger.warning(f"No data for {path}")
        return
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
    logger.info(f"Wrote {len(rows):,} rows -> {path}")


# ============================================================
# Main
# ============================================================
async def main():
    # Products already written (7,772 rows) — only redo startups + entity mappings
    startups = await scrape_yc_startups()
    mappings = build_entity_mappings(startups)

    write_csv(startups,  "output/startups.csv")
    write_csv(mappings,  "output/entity_mappings.csv")

    print(f"\n{'='*60}")
    print(f"  startups.csv       : {len(startups):>6,} rows")
    print(f"  entity_mappings.csv: {len(mappings):>6,} rows")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

