# Atlas-Ingest: Production System Architecture & Design Specification

**Document Version:** 2.0.0  
**Target:** High-Throughput Distributed Web Ingestion, LLM Extraction & Entity Intelligence  
**System Type:** Multi-Modal Batch & Real-Time Data Pipeline  
**Author:** Atlas-Ingest Engineering Team  

---

## 1. Executive Summary & System Overview

**Atlas-Ingest** is an enterprise-grade, multi-modal data ingestion and entity intelligence pipeline designed to continuously harvest, extract, normalize, and resolve structured intelligence from heterogeneous web sources.

The platform handles both **historical batch extraction** (startups, e-commerce products, arXiv research papers) and **real-time live monitoring** (technology news feeds, global remote tech job boards). Extracted unstructured data is transformed into strictly typed Pydantic models through a resilient multi-tier Large Language Model (LLM) orchestration layer, deduplicated and canonicalized via an asynchronous entity resolution engine, and exported to analytical storage and live Google Sheets dashboards.

```
+-----------------------------------------------------------------------------+
|                      ATLAS-INGEST SYSTEM TOPOLOGY                           |
+-----------------------------------------------------------------------------+

  [ DATA SOURCES ]
    * arXiv API / OAI-PMH                * Y-Combinator Directory (Playwright)
    * PapersWithCode API                 * Multi-Brand Shopify Endpoints
    * GitHub REST API                    * Global RSS Feeds & Tech Job Boards
           |                                      |
           v                                      v
  +---------------------------------------------------------------------------+
  | CRAWLER & INGESTION LAYER                                                 |
  |  - Async ArxivScraper (Semaphore=10)       - Headless Playwright Dynamic  |
  |  - PapersWithCode Cross-Referencing        - Trafilatura Article Body     |
  |  - GitHub Repo Correlator                  - Shopify Catalog Ingestion    |
  +---------------------------------------------------------------------------+
                                       |
                                       v (Raw HTML / JSON Payloads)
  +---------------------------------------------------------------------------+
  | LLM ORCHESTRATION & EXTRACTION LAYER                                      |
  |  - Semantic HTML Stripper & ContentChunker (tiktoken context guardian)    |
  |  - Multi-Tier Fallback Chain (LiteLLM):                                   |
  |      [Gemini-1.5-Flash] --(429/5xx)--> [Groq LLaMA-3.1] --(Fail)--> [DeepSeek]
  |  - Tenacity Resilient Retry Policy: Exponential jitter backoff (2s-10s)   |
  |  - Pydantic Schema Validation & Automatic Type Coercion                   |
  +---------------------------------------------------------------------------+
                                       |
                                       v (Typed Entity Objects)
  +---------------------------------------------------------------------------+
  | ENTITY RESOLUTION & GRAPH LINKAGE LAYER                                   |
  |  - Token Set Ratio Fuzzy Matching (TheFuzz, Threshold = 85)               |
  |  - 50+ Pre-Seeded Canonical Tech Giants & Unicorn Registry                |
  |  - Cross-Domain Entity Linker (Startups <-> Products <-> Papers <-> Jobs) |
  +---------------------------------------------------------------------------+
                                       |
                                       v
  +---------------------------------------------------------------------------+
  | EXPORT & STORAGE DESTINATIONS                                             |
  |  - Normalized CSV Data Lake (6 Tabular Collections)                       |
  |  - Automated Google Sheets Multi-Tab Sync (gspread / Google Cloud Auth)   |
  |  - Production Multi-Model Target: PostgreSQL + Neo4j Graph + pgvector     |
  +---------------------------------------------------------------------------+
```

---

## 2. Detailed Subsystem Architecture

### 2.1. Ingestion & Crawler Subsystem

The crawler layer comprises specialized, decoupled scraping engines tailored to diverse web transport mechanisms:

```
                  +-----------------------------------+
                  |        INGESTION SUBSYSTEM        |
                  +-----------------------------------+
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
        v                           v                           v
+-------------------+       +-------------------+       +-------------------+
|   ArxivScraper    |       |  DirectoryScraper |       |  NewsJobsScraper  |
| (API + Async)     |       | (Playwright/DOM)  |       | (RSS+Trafilatura) |
+-------------------+       +-------------------+       +-------------------+
| - arXiv Query API |       | - Chromium Engine |       | - RSS/Atom Feeds  |
| - PapersWithCode  |       | - Virtual Scroll  |       | - Trafilatura     |
| - GitHub Metadata |       | - Dynamic JS Eval |       | - Remote Classify |
| - Semaphore(10)   |       | - Anti-Bot Evasion|       | - Date Normalizer |
+-------------------+       +-------------------+       +-------------------+
```

1. **ArxivScraper & Academic Correlator (`src/crawlers/arxiv_scraper.py`):**
   - Harvests papers across AI/ML taxonomies (`cs.AI`, `cs.LG`, `cs.CV`, `cs.CL`, `cs.NE`).
   - Concurrently enriches abstracts with GitHub repository URLs and code release metadata using PapersWithCode APIs.
   - Leverages `asyncio.Semaphore(10)` to bound outbound concurrency, preventing upstream API rate limiting.

2. **DirectoryScraper (`src/crawlers/directory_scraper.py`):**
   - Utilizes headless Playwright Chromium instances to scrape complex client-side Single Page Applications (SPAs) like Y-Combinator company directories.
   - Emulates human interaction through smooth scrolling, viewport resizing, and dynamic network idle timeouts.

3. **News & Jobs Real-Time Scraper (`src/crawlers/news_jobs_scraper.py`):**
   - Polls high-velocity RSS/Atom feeds (TechCrunch, VentureBeat, Hacker News, RemoteOK, WeWorkRemotely, YC Work at a Startup).
   - Uses `trafilatura` for noise-free body text extraction, stripping ads, boilerplate, and tracking scripts.
   - Applies natural language heuristics to infer remote eligibility (`is_remote: bool`) and salary ranges.

---

### 2.2. Resilient LLM Extraction & Fallback Architecture

Unstructured web payloads are converted into structured, typed data through an orchestration layer built on `LiteLLM` and `Tenacity`.

```
                    RAW PAYLOAD (HTML / DOM / Text)
                                  |
                                  v
                 +----------------------------------+
                 |  Semantic HTML Stripping (CSS/JS)|
                 +----------------------------------+
                                  |
                                  v
                 +----------------------------------+
                 | ContentChunker (tiktoken BPE)    |
                 | Max Chunk: 4,000 Tokens          |
                 +----------------------------------+
                                  |
                                  v
            +---------------------------------------------+
            |          LLM ORCHESTRATOR DISPATCH          |
            +---------------------------------------------+
                                  |
            +---------------------+---------------------+
            | [Attempt 1]                               |
            v                                           |
+------------------------+                              |
| Primary Model:         |                              |
| Google Gemini 1.5 Flash|                              |
+------------------------+                              |
    | (Success)     | (HTTP 429 / 5xx / Rate Limit)     |
    v               v                                   |
[Success]   [Tenacity Exponential Jitter Retry]         |
                    | (Exhausted: 3 attempts)           |
                    v                                   |
            +-------------------------------------------+
            | [Attempt 2]
            v
+------------------------+
| Secondary Fallback:    |
| Groq / LLaMA-3.1-8B    |
+------------------------+
    | (Success)     | (HTTP 429 / Timeout / 5xx)
    v               v
[Success]   [Tenacity Exponential Jitter Retry]
                    | (Exhausted: 3 attempts)
                    v
            +-------------------------------------------+
            | [Attempt 3]                               |
            v                                           v
+------------------------+                  +------------------------+
| Tertiary Fallback:     |                  | Deterministic Regex    |
| DeepSeek Chat API      | ---(Total Fail)->| & Rule-Based Extractor |
+------------------------+                  +------------------------+
```

#### Fault Tolerance Strategies:
- **Context Window Overflow (HTTP 413) Protection:** Raw text is tokenized with `tiktoken`. Strings exceeding LLM context boundaries are split into semantic chunks with 200-token overlaps, extracted independently, and merged.
- **Rate Limit (HTTP 429) & Outage Recovery:** Handled via a multi-tier fallback hierarchy with jittered exponential backoff:
  `Backoff = random_uniform(0.5 * 2^attempt, 1.5 * 2^attempt)`
- **Strict Typing:** All extractions are parsed directly into Pydantic V2 schemas with automatic type coercion and validation guards.

---

### 2.3. Entity Resolution & Cross-Domain Linkage Engine

The **EntityResolver** (`src/resolution/resolver.py`) acts as the linkage bridge, uniting disparate records across all 5 operational verticals into a unified knowledge graph.

```
       Incoming Entities (Startups, Products, Papers, News, Jobs)
                                   |
                                   v
         +---------------------------------------------------+
         |            String Normalization Pipeline          |
         |  (Lowercase, Punctuation Stripping, Legal Suffix) |
         +---------------------------------------------------+
                                   |
                                   v
         +---------------------------------------------------+
         |      Fuzzy Matcher: thefuzz Token Set Ratio       |
         |  Against 50+ Seed Tech Entities (Threshold >= 85) |
         +---------------------------------------------------+
                                   |
                  +----------------+----------------+
                  |                                 |
                  v                                 v
         [ Match Found (Score >= 85) ]    [ No Match (< 85) ]
                  |                                 |
                  v                                 v
         Assign Canonical Seed ID          Generate Deterministic
         (e.g., seed_apple,                UUID5 Canonical ID
          seed_openai)                     (Namespace-seeded)
                  |                                 |
                  +----------------+----------------+
                                   |
                                   v
         +---------------------------------------------------+
         |          Cross-Domain Entity Link Record          |
         |  (Raw String, Canonical ID, Match Confidence, TS) |
         +---------------------------------------------------+
```

- **Seed Knowledge Base:** Contains 50 curated industry giants (OpenAI, Google, Microsoft, Anthropic, Stripe, Shopify, Meta, NVIDIA, etc.).
- **Deduplication:** Prevents duplicate entity representation when company names vary across sources (e.g., `"Shopify Inc."`, `"Shopify Inc"`, `"shopify.com"` resolve to canonical `seed_shopify`).

---

## 3. Data Model & Schema Specification

All pipeline artifacts strictly implement validated Pydantic V2 models (`src/models/schemas.py`):

| Schema Name | Target Entity | Core Fields | Output Location |
| :--- | :--- | :--- | :--- |
| `StartupEntity` | Tech Companies / Startups | `name`, `batch`, `website`, `description`, `founders`, `tags`, `canonical_id` | `output/startups.csv` |
| `ProductEntity` | E-Commerce Items | `title`, `brand`, `price`, `currency`, `url`, `category`, `canonical_id` | `output/products.csv` |
| `ResearchPaperEntity`| Academic Papers | `title`, `authors`, `abstract`, `arxiv_id`, `published_date`, `github_repo_url`, `code_url` | `output/research_papers.csv` |
| `NewsEntity` | Tech News Articles | `title`, `source`, `url`, `published_at`, `summary`, `mentioned_entities`, `full_text` | `output/news.csv` |
| `JobEntity` | Job Postings | `title`, `company`, `location`, `is_remote`, `salary_range`, `url`, `source` | `output/jobs.csv` |
| `EntityMapping` | Graph Relationships | `raw_name`, `canonical_id`, `canonical_name`, `confidence_score`, `entity_type` | `output/entity_mappings.csv` |

---

## 4. Production Scale Roadmap (500,000+ Records)

For enterprise-scale production scaling to hundreds of thousands of daily records, Atlas-Ingest transitions to an event-driven, distributed microservices topology:

```
                                [ Seed URLs & Triggers ]
                                            |
                                            v
                    +-----------------------------------------------+
                    |        Apache Kafka Distributed Broker        |
                    |  Topics: raw_urls, crawled_dom, raw_entities  |
                    +-----------------------------------------------+
                                   |                |
            +----------------------+                +----------------------+
            |                                                              |
            v                                                              v
+-----------------------------------------+    +-----------------------------------------+
| Kubernetes Crawler Fleet (K8s HPA)      |    | Distributed LLM Worker Cluster          |
| - Stateless scraping pods (Playwright)  |    | - Dynamic batch inference workers       |
| - Residential Proxy Pool (Oxylabs)      |    | - Token-bucket rate limiter per model   |
| - Redis Bloom Filter URL Deduplication  |    | - Celery / Ray distributed tasks        |
+-----------------------------------------+    +-----------------------------------------+
                    |                                              |
                    +----------------------+-----------------------+
                                           |
                                           v
                    +-----------------------------------------------+
                    |          Unified Storage Lakehouse            |
                    +-----------------------------------------------+
                       |                   |                   |
                       v                   v                   v
            +--------------------+ +---------------+ +-------------------+
            | PostgreSQL (OLTP)  | | Neo4j (Graph) | | pgvector / Qdrant |
            | ACID entity tables | | Knowledge Map | | Vector Embeddings |
            +--------------------+ +---------------+ +-------------------+
```

### 4.1. Distributed URL Queue & Deduplication
- **Redis Bloom Filters:** Employs an O(1) memory-efficient Bloom Filter holding 10M+ URL signatures with an error probability < 0.01%.
- **Content Hashing:** Generates SHA-256 digests over normalized document text to prevent reprocessing mirrored content.

### 4.2. Storage Architecture
- **PostgreSQL (JSONB):** Primary relational storage for transactional integrity, polymorphic schema evolution, and fast indexing.
- **Neo4j Graph Database:** Powers multi-hop traversal queries (e.g., *"Find all papers authored by engineers at companies with active job postings for LLM Architects"*).
- **Vector Storage (pgvector):** Generates 1536-dimensional embeddings for semantic similarity search across extracted entities.

---

## 5. Technology Stack & Operational Matrix

| Component Layer | Technology Selection | Architectural Rationale |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.10+ / Asyncio | High-concurrency I/O throughput with native coroutine pipelines |
| **Browser Automation** | Playwright (Chromium) | Fast, reliable headless execution with anti-detection handling |
| **HTTP Extraction** | HTTPX / Trafilatura | Asynchronous HTTP/2 support + noise-free DOM readability |
| **LLM Gateway** | LiteLLM + Tenacity | Unified multi-provider SDK with automatic jittered failover |
| **Entity Resolution** | TheFuzz (Levenshtein) | High-accuracy fuzzy string normalization and matching |
| **Data Validation** | Pydantic V2 (Rust core) | Ultra-fast schema parsing, coercion, and validation |
| **Export & Sync** | gspread + Google Auth | Headless cloud synchronization to Google Sheets |
| **Documentation & CI** | xhtml2pdf / GitHub Actions | Automated regression testing and PDF build pipeline |

---

*Atlas-Ingest Architecture Specification Document — All Rights Reserved.*
