CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(255) NOT NULL,
    minio_key VARCHAR(500) NOT NULL,
    issuer_name VARCHAR(255),
    issuer_vat VARCHAR(50),
    recipient_name VARCHAR(255),
    recipient_vat VARCHAR(50),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    subtotal DECIMAL(12, 2),
    tax_rate DECIMAL(5, 2),
    tax_amount DECIMAL(12, 2),
    total DECIMAL(12, 2),
    currency VARCHAR(10),
    is_valid BOOLEAN DEFAULT FALSE,
    validation_errors JSONB,
    status VARCHAR(50) DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS line_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    description TEXT,
    quantity DECIMAL(10, 2),
    unit_price DECIMAL(12, 2),
    line_total DECIMAL(12, 2)
);

CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);
