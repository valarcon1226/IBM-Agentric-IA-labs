# Project: News Aggregator & Intelligence Reporter

## 1. Problem Statement
Professionals need to stay updated with industry news across dozens of blogs, news sites, and journals. Manually checking these sites is inefficient, and standard RSS readers don't filter out noise, summarize long articles, or detect identical stories covered by different outlets.

This project is an automated intelligence system that aggregates news via RSS and web scraping (respecting `robots.txt`), categorizes content using keyword matching, deduplicates cross-source coverage via exact SHA-256 hashes and pgvector Cosine Similarity, summarizes articles using LLMs (with resilient fallback), and delivers concise, formatted HTML digests via SMTP to Mailpit.

## 2. Architecture & Workflow

### 2.1 Workflow Diagram

```mermaid
sequenceDiagram
    participant Sched as Celery Beat (Scheduler)
    participant Ingest as Ingestion Pipeline
    participant NLP as Categorization & Dedup
    participant LLM as Summarizer (LLM / Fallback)
    participant DB as PostgreSQL (pgvector + pg_trgm)
    participant Deliv as Email Notifier (Jinja2)
    participant Output as Mailpit (SMTP 1025 / UI 8029)
    
    Sched->>Ingest: Trigger Ingestion Job (every 15 min)
    Ingest->>Ingest: Fetch RSS & Web content (respecting robots.txt)
    Ingest->>NLP: Raw Articles
    NLP->>NLP: Step 1: Fast SHA-256 Hash Check
    NLP->>NLP: Step 2: Semantic pgvector / TF-IDF Search
    NLP->>DB: Save Unique or Link Duplicate Articles
    DB-->>LLM: Fetch Unsummarized Articles
    LLM->>DB: Save Bulleted Summaries
    Sched->>Deliv: Trigger Daily Digest Generation
    Deliv->>DB: Query Non-duplicate Stories & Duplicates
    Deliv->>Output: Send HTML Digest via SMTP (Mailpit)
```

### 2.2 Tech Stack
*   **Ingestion:** `feedparser` (RSS) and `httpx` + `trafilatura` (article text extraction respecting `robots.txt`). Feed and article URLs must be `http(s)`; local file paths and internal addresses (loopback, private, link-local) are refused, redirects included (SSRF guard, `ALLOW_PRIVATE_TARGETS=true` only in the demo compose).
*   **NLP & Machine Learning:** `scikit-learn` (TF-IDF vectorizer fallback), `pgvector` (Dense embeddings & Cosine Distance search `<=>`)
*   **AI Summarization:** OpenAI-compatible endpoint (Ollama `llama3:8b`, `nomic-embed-text` or deterministic `fake_llm`) with resilient excerpt fallback
*   **Database:** PostgreSQL with `pg_trgm` and `pgvector` (fixed image `pgvector/pgvector:0.7.4-pg16`)
*   **Orchestration & Delivery:** Celery + Celery Beat (`redis:7.4.2-alpine`), Jinja2 (HTML Email Templates), `smtplib` -> Mailpit (`axllent/mailpit:v1.21`)
*   **API:** FastAPI with Bearer Token authentication (port 8009)

## 3. Core Algorithms

### 3.1 Categorization (Keyword Matching)
Articles are categorized (e.g., "Inteligencia Artificial", "Ciberseguridad", "Cloud y DevOps", "Fintech y Mercados", "General") by matching article title and content against weighted keyword clusters.

### 3.2 Scalable Two-Step Deduplication
When a major event happens, many outlets publish the same story with different titles.
1. **O(1) Exact Match Hash:** Compute a SHA-256 hash of the normalized title + first 200 characters of normalized content. Check against existing `content_hash` in the database.
2. **Semantic Similarity (pgvector):** Compute dense embeddings for the article. Use a pgvector Cosine Distance query (`<=>`) with `threshold = 0.15` to detect cross-source duplicate coverage.
3. **TF-IDF Fallback:** If the embedding model is unavailable or disabled, `scikit-learn` TF-IDF unigram cosine similarity acts as fallback against recent articles.
4. If flagged as duplicate, link the new article to the parent article (`is_duplicate = TRUE`, `parent_article_id = <parent_id>`) and skip LLM summarization.

## 4. Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source_type VARCHAR(20) DEFAULT 'RSS', -- 'RSS', 'SCRAPE'
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'HEALTHY',
    last_fetched_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    keywords TEXT[] NOT NULL
);

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    author VARCHAR(100),
    published_date TIMESTAMP WITH TIME ZONE,
    raw_content TEXT,
    content_hash VARCHAR(64), -- Fast exact match (Title + 200 chars)
    embedding vector(768),    -- nomic-embed-text / OpenAI compatible
    ai_summary TEXT,          -- Bullet points generated by LLM or fallback
    is_duplicate BOOLEAN DEFAULT FALSE,
    parent_article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_title_trgm ON articles USING GIN (title gin_trgm_ops);
CREATE INDEX idx_articles_content_hash ON articles (content_hash);
CREATE INDEX idx_articles_embedding ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_articles_published_date ON articles (published_date);

CREATE TABLE digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_audience VARCHAR(50) DEFAULT 'TEAM_DIGEST',
    recipient_email VARCHAR(255),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'SUCCESS',
    article_count INT DEFAULT 0,
    error_message TEXT
);

CREATE TABLE digest_articles (
    digest_id UUID REFERENCES digests(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (digest_id, article_id)
);
```

## 5. API Endpoints

All `/api/v1/*` endpoints require authentication via Bearer token: `Authorization: Bearer <API_BEARER_TOKEN>`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check (public, verifies DB connectivity) |
| `POST` | `/api/v1/sources` | Add a new RSS/Web source |
| `GET` | `/api/v1/sources` | List sources with health status and fetch times |
| `PUT` | `/api/v1/sources/{id}` | Update source attributes |
| `DELETE` | `/api/v1/sources/{id}` | Delete a source |
| `GET` | `/api/v1/articles` | Search articles (`pg_trgm` similarity, category, duplicate filter) |
| `GET` | `/api/v1/digests` | List past sent digests |
| `POST` | `/api/v1/digests/generate` | Manually generate and dispatch an HTML digest |
| `POST` | `/api/v1/ingest` | Trigger immediate ingestion of active sources |

### Example 1: Add a Source (POST `/api/v1/sources`)
```bash
curl -X POST "http://localhost:8009/api/v1/sources" \
     -H "Authorization: Bearer change_me_api_bearer_token" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "TechCrunch",
           "url": "https://techcrunch.com/feed/",
           "source_type": "RSS"
         }'
```

### Example 2: List Sources (GET `/api/v1/sources`)
```bash
curl -X GET "http://localhost:8009/api/v1/sources" \
     -H "Authorization: Bearer change_me_api_bearer_token"
```

### Example 3: Search Articles (GET `/api/v1/articles`)
```bash
curl -X GET "http://localhost:8009/api/v1/articles?q=kubernetes&category=Cloud&limit=20" \
     -H "Authorization: Bearer change_me_api_bearer_token"
```

### Example 4: Trigger Digest (POST `/api/v1/digests/generate`)
```bash
curl -X POST "http://localhost:8009/api/v1/digests/generate" \
     -H "Authorization: Bearer change_me_api_bearer_token" \
     -H "Content-Type: application/json" \
     -d '{ "target_audience": "TEAM_DIGEST", "recipient_email": "briefing@empresa-ficticia.com" }'
```

## 6. Implementation Code Examples

### 6.1 Duplicate Detection (pgvector Cosine Distance)

```python
def detect_duplicate_vector(new_embedding: list[float], cursor, threshold: float = 0.15) -> str | None:
    """Finds a matching article ID using pgvector cosine distance (<=>)."""
    query = """
        SELECT id, (embedding <=> %s::vector) AS distance 
        FROM articles 
        WHERE embedding IS NOT NULL AND is_duplicate = FALSE
        ORDER BY distance ASC 
        LIMIT 1;
    """
    cursor.execute(query, (new_embedding,))
    result = cursor.fetchone()
    if result and float(result["distance"]) < threshold:
        return str(result["id"])
    return None
```

### 6.2 HTML Email Template (Jinja2)
Articles are grouped by category and display bullet summaries generated by the LLM, with links to other outlets that reported the same story.

## 7. Docker Services & File Structure

### 7.1 Services
*   `postgres`: PostgreSQL 16 con `pgvector` y `pg_trgm` (`pgvector/pgvector:0.7.4-pg16`). Puerto interno 5432 (no publicado al host).
*   `redis`: Broker para tareas Celery (`redis:7.4.2-alpine`). Puerto interno 6379 (no publicado al host).
*   `mailpit`: Servidor SMTP y visor web de correos (`axllent/mailpit:v1.21`). UI web en `127.0.0.1:8029:8025`.
*   `fake_llm`: Servidor determinista compatible con OpenAI (chat completions y embeddings de 768 dimensiones).
*   `api`: Backend FastAPI (`127.0.0.1:8009:8009`).
*   `worker`: Worker Celery con programador Celery Beat para ingesta periódica y boletines.

### 7.2 File Structure
```text
09-news-aggregator/
├── api/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── routes.py
│   └── security.py
├── ingestion/
│   ├── pipeline.py
│   ├── rss_parser.py
│   └── text_extractor.py
├── intelligence/
│   ├── llm_summarizer.py
│   └── nlp_processor.py
├── delivery/
│   ├── templates/
│   │   └── email_digest.html
│   └── notifier.py
├── fake_llm/
│   └── server.py
├── db/
│   └── schema.sql
├── scripts/
│   └── run_demo.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── feed_tech_a.xml
│   │   ├── feed_tech_b.xml
│   │   ├── feed_tech_c.xml
│   │   └── sample_article.html
│   ├── test_api.py
│   ├── test_categorization.py
│   ├── test_dedup.py
│   ├── test_integration.py
│   ├── test_notifier.py
│   ├── test_rss_parser.py
│   ├── test_summarizer.py
│   └── test_text_extractor.py
├── celery_app.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## 8. Verification & Demo

### Quality Gates
```bash
ruff check .
pytest -q
pytest -m integration -q
```

### Docker Verification
```bash
docker compose up -d --build
docker compose ps
python scripts/run_demo.py
docker compose down -v
```
