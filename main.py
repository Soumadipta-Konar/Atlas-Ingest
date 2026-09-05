import argparse
import asyncio
import logging
import os

from src.crawlers.arxiv_scraper import ArxivScraper  # type: ignore
from src.crawlers.news_jobs_scraper import NewsJobsScraper  # type: ignore
from src.crawlers.directory_scraper import DirectoryScraper # type: ignore
from src.llm.orchestrator import LLMOrchestrator  # type: ignore
from src.llm.chunking import ContentChunker  # type: ignore
from src.resolution.resolver import EntityResolver  # type: ignore
from src.utils.exporter import DataExporter  # type: ignore
from src.models.schemas import JobEntity  # type: ignore
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

async def run_phase1(args):
    logger.info(f"Starting Phase 1: Massive Data Acquisition (Target: {args.max_records} records per type)")
    os.makedirs("output", exist_ok=True)
    
    arxiv_crawler = ArxivScraper(concurrency_limit=10)
    directory_crawler = DirectoryScraper(concurrency_limit=10, use_playwright=True)
    orchestrator = LLMOrchestrator()
    resolver = EntityResolver(seed_file=getattr(args, 'seed_file', None))
    
    # 1. Research Papers
    if args.run_papers:
        logger.info(f"Fetching Research Papers for topic: '{args.topic}'")
        papers = await arxiv_crawler.fetch_papers(query=f"all:{args.topic}", max_results=args.max_records)
        papers_with_github = []
        for paper in papers:
            papers_with_github.append(await arxiv_crawler.correlate_github(paper))
        df_papers = DataExporter.entities_to_df(papers_with_github)
        DataExporter.export_csv(df_papers, "output/research_papers.csv")
    
    # 2. Startups
    if args.run_startups:
        logger.info(f"Fetching Startups from: {args.startups_url}")
        startups = await directory_crawler.scrape_directory(args.startups_url, "startup", orchestrator, max_records=args.max_records)
        for s in startups:
            s.content.entityName = resolver.canonicalize(s.content.entityName)
        df_startups = DataExporter.entities_to_df(startups)
        DataExporter.export_csv(df_startups, "output/startups.csv")
    
    # 3. Products
    if args.run_products:
        logger.info(f"Fetching Products from: {args.products_url}")
        entity_type = "ecommerce" if args.ecommerce else "product"
        products = await directory_crawler.scrape_directory(args.products_url, entity_type, orchestrator, max_records=args.max_records)
        for p in products:
            if hasattr(p.content, 'startupName'):
                p.content.startupName = resolver.canonicalize(p.content.startupName)
            elif hasattr(p.content, 'productName'):
                p.content.productName = resolver.canonicalize(p.content.productName)
        df_products = DataExporter.entities_to_df(products)
        DataExporter.export_csv(df_products, "output/products.csv")

    mapping_log = resolver.get_mapping_log()
    if mapping_log:
        import pandas as pd
        df_mapping = pd.DataFrame(mapping_log)
        DataExporter.export_csv(df_mapping, "output/entity_mappings.csv")

    await arxiv_crawler.close()
    await directory_crawler.close()
    logger.info("Phase 1 complete.")

async def run_phase2(args):
    logger.info("Starting Phase 2: High-Fidelity Signal Ingestion (News & Jobs)")
    os.makedirs("output", exist_ok=True)
    
    scraper = NewsJobsScraper(concurrency_limit=5)
    
    news_sources = {
        "TechCrunch": "https://techcrunch.com/feed/",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "HackerNews": "https://hnrss.org/frontpage",
        "BBC Technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "Wired": "https://www.wired.com/feed/category/gear/latest/rss"
    }
    
    job_sources = {
        "YC HackerNews Jobs": "https://hnrss.org/jobs",
        "RemoteOK": "https://remoteok.com/rss",
        "WeWorkRemotely": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "Python.org Jobs": "https://www.python.org/jobs/feed/rss/",
        "Unstop": "https://unstop.com/feed" # Replaced Working Nomads with Unstop as requested
    }
    
    all_news = []
    for name, url in news_sources.items():
        news = await scraper.scrape_rss_news(url, name)
        all_news.extend(news)
        
    all_jobs = []
    for name, url in job_sources.items():
        jobs = await scraper.scrape_rss_jobs(url, name)
        all_jobs.extend(jobs)
        
    if all_news:
        df_news = DataExporter.entities_to_df(all_news)
        DataExporter.export_csv(df_news, "output/news.csv")
    else:
        logger.warning("No fresh news found to export.")
        
    if all_jobs:
        df_jobs = DataExporter.entities_to_df(all_jobs)
        DataExporter.export_csv(df_jobs, "output/jobs.csv")
    else:
        logger.warning("No fresh jobs found to export.")

    await scraper.close()
    logger.info("Phase 2 complete.")

def main():
    parser = argparse.ArgumentParser(
        description="Atlas-Ingest — AI Intelligence Ingestion Pipeline",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        dest="command", 
        required=True,
        help="Pipeline Execution Modes:\n  batch-extract : Massive One-Time Data Acquisition (Startups, Products, Papers)\n  live-monitor  : High-Fidelity Signal Ingestion (News & Jobs)"
    )
    
    # Batch Extract Subcommand
    parser_batch = subparsers.add_parser("batch-extract", help="Run Massive One-Time Data Acquisition")
    parser_batch.add_argument("--topic", type=str, default="AI", help="Research paper topic query (default: 'AI')")
    parser_batch.add_argument("--max-records", type=int, default=1000, help="Target number of records to scrape per category (default: 1000)")
    parser_batch.add_argument("--startups-url", type=str, default="https://www.ycombinator.com/companies", help="URL to scrape startups from")
    parser_batch.add_argument("--products-url", type=str, default="https://www.producthunt.com", help="URL to scrape products from")
    
    parser_batch.add_argument("--run-papers", action="store_true", help="Execute Research Papers extraction")
    parser_batch.add_argument("--run-startups", action="store_true", help="Execute Startups extraction")
    parser_batch.add_argument("--run-products", action="store_true", help="Execute Products extraction")
    parser_batch.add_argument("--ecommerce", action="store_true", help="Use Ecommerce Product schema instead of AI Software schema")
    parser_batch.add_argument("--seed-file", type=str, default=None, help="Path to a JSON file containing canonical entity names for resolution")
    
    # Live Monitor Subcommand
    parser_live = subparsers.add_parser("live-monitor", help="Run High-Fidelity Signal Ingestion (24h Freshness)")
    
    args = parser.parse_args()
    
    if args.command == "batch-extract":
        asyncio.run(run_phase1(args))
    elif args.command == "live-monitor":
        asyncio.run(run_phase2(args))

if __name__ == "__main__":
    main()
