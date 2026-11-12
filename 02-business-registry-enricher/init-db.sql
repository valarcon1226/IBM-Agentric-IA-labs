CREATE TABLE company_cache (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    company_identifier VARCHAR(50) NOT NULL,
    company_name VARCHAR(255),
    status VARCHAR(50),
    incorporation_date DATE,
    raw_data JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, company_identifier)
);

CREATE TABLE api_logs (
    log_id SERIAL PRIMARY KEY,
    registry_name VARCHAR(50),
    endpoint VARCHAR(255),
    response_code INT,
    response_time_ms INT,
    error_message TEXT,
    company_identifier VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
