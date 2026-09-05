# Atlas Ingest: AI Data Ingestion Pipeline

## Overview
This repository contains a scalable, fault-tolerant ingestion pipeline for extracting intelligence from the AI ecosystem (Startups, Products, Research Papers, Jobs, News). It leverages highly concurrent async scraping, Playwright for anti-bot navigation, multi-tier LLM fallback chains for data structuring, and fuzzy-matching entity resolution.

## Features
- **Async Scrapers**: Fast, non-blocking HTTP requests for bulk extraction.
- **Anti-Bot Engine**: Integrated Playwright for bypassing Cloudflare & Datadome.
- **Intelligent Chunking**: Splits large HTML payloads automatically to prevent `413 Payload Too Large` LLM errors.
- **Multi-Tier LLM Orchestration**: Cascading fallback chain (Gemini -> Groq -> DeepSeek) handling `429 Too Many Requests` with exponential backoff.
- **Deterministic Entity Resolution**: Fuzzy-matching pipeline to resolve noisy extraction data to canonical entity records.

## Architecture & Setup
Please see the `doc/architecture.pdf` (or `doc/prd.md`, `doc/tech_steps.md`) for detailed architectural documentation on scaling to 500k+ records.

### Prerequisites
- Python 3.11+
- Virtual environment

### Installation
1. Clone the repository
2. Activate your virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```
3. Install dependencies via poetry or pip (using pyproject.toml):
   ```bash
   pip install .
   # Additionally for playwright
   playwright install chromium
   ```

### Running the Pipeline
Set the required environment variables in a `.env` file (e.g., `GEMINI_API_KEY`, `GROQ_API_KEY`).

```bash
python main.py
```

The pipeline will extract data, process it through the LLM schemas, resolve entities, and output strict CSV schemas to the `/output` directory.
