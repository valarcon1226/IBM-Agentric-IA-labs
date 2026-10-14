-- B2B Lead Generator — schema from README section 4 (DECISIONES-08 L4).
-- Applied automatically by docker-entrypoint-initdb.d when the Postgres container is wired up
-- in batch B; written now so the skeleton matches the spec.

CREATE TABLE scraping_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'RUNNING',
    total_found INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- SET NULL: leads are the product; deleting a session's record must not delete its leads.
    session_id UUID REFERENCES scraping_sessions(id) ON DELETE SET NULL,
    company_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),
    category VARCHAR(100),
    website TEXT,
    email VARCHAR(255),
    is_email_valid BOOLEAN,
    phone_raw VARCHAR(50),
    phone_e164 VARCHAR(20),
    address_raw TEXT,
    city VARCHAR(100),
    lat DECIMAL(10, 7),
    lng DECIMAL(10, 7),
    rating DECIMAL(2, 1),
    source_url TEXT,
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Null-safe unique constraint
    CONSTRAINT unique_website_phone UNIQUE NULLS NOT DISTINCT (website, phone_e164)
);

CREATE INDEX idx_leads_search ON leads USING GIN (to_tsvector('english', company_name || ' ' || category));

CREATE TABLE dedup_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES scraping_sessions(id) ON DELETE CASCADE,
    surviving_lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
    merged_lead_id UUID, -- References the lead that was dropped/merged
    merged_lead_data JSONB,
    similarity_score DECIMAL(5,2),
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
