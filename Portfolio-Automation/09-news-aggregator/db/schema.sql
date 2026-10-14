-- Schema para News Aggregator & Intelligence Reporter
-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla de fuentes de noticias (RSS y Web)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source_type VARCHAR(20) DEFAULT 'RSS', -- 'RSS', 'SCRAPE'
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'HEALTHY', -- 'HEALTHY', 'ERROR', 'PENDING'
    last_fetched_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de categorías para clasificación por palabras clave
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    keywords TEXT[] NOT NULL
);

-- Tabla de artículos recolectados
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    author VARCHAR(100),
    published_date TIMESTAMP WITH TIME ZONE,
    raw_content TEXT,
    content_hash VARCHAR(64), -- SHA-256 (título normalizado + inicio de contenido)
    embedding vector(768),    -- nomic-embed-text / OpenAI compatible
    ai_summary TEXT,          -- Viñetas generadas por LLM o fallback
    is_duplicate BOOLEAN DEFAULT FALSE,
    parent_article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices de búsqueda y deduplicación
CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles (content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_embedding ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles (published_date);

-- Tabla de boletines (digests) enviados
CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_audience VARCHAR(50) DEFAULT 'TEAM_DIGEST',
    recipient_email VARCHAR(255),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'SUCCESS', -- 'SUCCESS', 'FAILED'
    article_count INT DEFAULT 0,
    error_message TEXT
);

-- Tabla intermedia de artículos incluidos en cada boletín
CREATE TABLE IF NOT EXISTS digest_articles (
    digest_id UUID REFERENCES digests(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (digest_id, article_id)
);

-- Sembrado inicial de categorías si no existen
INSERT INTO categories (name, keywords)
VALUES
    ('Inteligencia Artificial', ARRAY['ia', 'ai', 'llm', 'gpt', 'machine learning', 'deep learning', 'redes neuronales', 'agentes', 'openai', 'anthropic']),
    ('Ciberseguridad', ARRAY['seguridad', 'ciberseguridad', 'vulnerabilidad', 'cve', 'malware', 'ransomware', 'phishing', 'hacker', 'ataque']),
    ('Cloud y DevOps', ARRAY['cloud', 'devops', 'kubernetes', 'docker', 'aws', 'azure', 'microservicios', 'terraform', 'ci/cd', 'linux']),
    ('Fintech y Mercados', ARRAY['fintech', 'mercado', 'inversión', 'economía', 'finanzas', 'startup', 'cripto', 'bitcoin', 'dólar']),
    ('General', ARRAY['tecnología', 'innovación', 'digital', 'software', 'internet'])
ON CONFLICT (name) DO NOTHING;
