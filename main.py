import asyncio
import logging
import os
from src.crawlers.arxiv_scraper import ArxivScraper
from src.crawlers.news_jobs_scraper import NewsJobsScraper
from src.llm.orchestrator import LLMOrchestrator
from src.llm.chunking import ContentChunker
from src.resolution.resolver import EntityResolver
from src.utils.exporter import DataExporter
from src.models.schemas import JobEntity

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

async def run_pipeline():
    logger.info("Starting AI Data Ingestion Pipeline...")
    
    # Initialize components
    arxiv_crawler = ArxivScraper(concurrency_limit=10)
    news_jobs_crawler = NewsJobsScraper(concurrency_limit=5, use_playwright=True)
    orchestrator = LLMOrchestrator()
    chunker = ContentChunker()
    resolver = EntityResolver()
    
    # Output directory
    os.makedirs("output", exist_ok=True)
    
    # ---------------------------------------------------------
    # PHASE I: Research Papers Extraction
    # ---------------------------------------------------------
    logger.info("Executing Phase I: Research Papers")
    papers = await arxiv_crawler.fetch_papers(query="all:AI", max_results=10) # 10 for demo speed
    
    # Correlate with GitHub
    papers_with_github = []
    for paper in papers:
        correlated = await arxiv_crawler.correlate_github(paper)
        papers_with_github.append(correlated)
        
    df_papers = DataExporter.entities_to_df(papers_with_github)
    DataExporter.export_csv(df_papers, "output/research_papers.csv")
    
    # ---------------------------------------------------------
    # PHASE II & III: Signal Ingestion & LLM Extraction (Jobs Demo)
    # ---------------------------------------------------------
    logger.info("Executing Phase II & III: Signal Ingestion via LLM")
    
    # Mocking a job board HTML payload that would trigger the LLM
    mock_job_html = """
    <html>
        <body>
            <h1>Machine Learning Engineer at OpenAI Inc</h1>
            <p>Posted 2 hours ago. Remote available.</p>
            <p>We are looking for an ML engineer...</p>
        </body>
    </html>
    """
    
    chunks = chunker.chunk_content(mock_job_html)
    extracted_jobs = []
    
    for chunk in chunks:
        # Require API key to actually run litellm, wrapping in try/except for local execution
        try:
            job: JobEntity = await orchestrator.extract_entity(chunk, JobEntity)
            if job:
                # Phase IV: Entity Resolution
                canonical_company = resolver.canonicalize(job.content.company)
                job.content.company = canonical_company
                extracted_jobs.append(job)
        except Exception as e:
            logger.warning("Skipping LLM call in demo without API keys.")
            break
            
    if extracted_jobs:
        df_jobs = DataExporter.entities_to_df(extracted_jobs)
        DataExporter.export_csv(df_jobs, "output/jobs.csv")
    
    # ---------------------------------------------------------
    # Export Mappings
    # ---------------------------------------------------------
    DataExporter.export_mapping_log(resolver.get_mapping_log(), "output/entity_mappings.csv")
    
    logger.info("Pipeline execution complete. Check /output directory.")
    await arxiv_crawler.close()
    await news_jobs_crawler.close()

if __name__ == "__main__":
    asyncio.run(run_pipeline())
