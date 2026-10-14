CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    url TEXT UNIQUE NOT NULL,
    site_domain VARCHAR(100) NOT NULL,
    css_selectors JSONB,
    target_price DECIMAL(10, 2),
    alert_threshold_pct DECIMAL(5, 2) DEFAULT 5.0,
    alert_threshold_abs DECIMAL(10, 2) DEFAULT 0.0,
    currency VARCHAR(10) DEFAULT 'USD',
    check_interval_hours INTEGER DEFAULT 6,
    requires_js BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    availability BOOLEAN DEFAULT TRUE,
    rating DECIMAL(3, 2),
    reviews_count INTEGER,
    seller_reputation VARCHAR(100),
    shipping_info TEXT,
    screenshot_path TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    old_price DECIMAL(10, 2),
    new_price DECIMAL(10, 2),
    alert_type VARCHAR(50),
    status VARCHAR(50),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraping_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    status VARCHAR(50),
    error_message TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_time ON price_history(product_id, scraped_at);
CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id);
CREATE INDEX IF NOT EXISTS idx_scraping_logs_product ON scraping_logs(product_id, executed_at);
