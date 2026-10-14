-- Sabor de Casa — n8n automation pack (DECISIONES-14 A1/A2).
-- Tables for the four flows (F1 lead/CRM, F2 invoices, F3 daily sales report, F4 payments),
-- plus `processed_events` (F4 idempotency) and `workflow_errors` (A5 error handling, an
-- addition not in the literal A1 list — every flow's `settings.errorWorkflow` points at
-- `shared-error-handler.json`, which needs somewhere to log without exposing secrets).

CREATE TABLE crm_leads (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(30),
    event_type VARCHAR(100),
    event_date DATE,
    guests INTEGER,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    provider_name VARCHAR(200),
    provider_nit VARCHAR(50),
    invoice_date DATE,
    subtotal_cop INTEGER,
    iva_cop INTEGER,
    total_cop INTEGER,
    items JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'validated', 'needs_review')),
    raw_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    sale_date DATE NOT NULL,
    dish_name VARCHAR(150) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_cop INTEGER NOT NULL CHECK (total_cop > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(150) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    total_cop INTEGER NOT NULL CHECK (total_cop > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP
);

-- Stripe-style webhooks retry; an event id is only ever applied once (F4 idempotency, A5).
CREATE TABLE processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE workflow_errors (
    id SERIAL PRIMARY KEY,
    workflow_name VARCHAR(150) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample sales data (F3, batch B). Fixed demo date (T-14-lote-b follow-up review): these rows
-- used to be CURRENT_DATE-relative, evaluated once when Postgres first initialized its volume,
-- so F3's "yesterday" query stopped finding them a few days later. The 07:00 cron still queries
-- real "yesterday" (CURRENT_DATE - 1, see workflows/f3-daily-report.json), but the demo date is
-- now fixed at 2025-01-15 (and the two days before it) so F3's manual webhook can request it
-- explicitly (`{"date": "2025-01-15"}`) and reliably see data regardless of when the stack is
-- run. See docs/DEMO-SCRIPT.md and README.md §5.
INSERT INTO sales (sale_date, dish_name, quantity, total_cop) VALUES
(DATE '2025-01-15', 'Bandeja Paisa', 14, 476000),
(DATE '2025-01-15', 'Ajiaco Santafereño', 9, 261000),
(DATE '2025-01-15', 'Sancocho de Gallina', 6, 162000),
(DATE '2025-01-15', 'Limonada de Coco', 20, 180000),
(DATE '2025-01-14', 'Bandeja Paisa', 11, 374000),
(DATE '2025-01-14', 'Arroz con Pollo', 8, 176000),
(DATE '2025-01-14', 'Postre de Tres Leches', 10, 110000),
(DATE '2025-01-13', 'Mondongo', 5, 130000),
(DATE '2025-01-13', 'Bandeja Paisa', 13, 442000),
(DATE '2025-01-13', 'Jugo Natural de Lulo (en agua)', 15, 120000);

-- Sample orders data (F4, demo/dueño view): a mix of already-paid and still-pending orders.
-- Tests insert and clean up their own rows independently of this seed data.
INSERT INTO orders (customer_name, customer_email, total_cop, status, paid_at) VALUES
('Laura Gómez', 'laura.gomez@example.com', 85000, 'paid', CURRENT_TIMESTAMP - INTERVAL '2 days'),
('Carlos Ruiz', 'carlos.ruiz@example.com', 142000, 'paid', CURRENT_TIMESTAMP - INTERVAL '1 day');
INSERT INTO orders (customer_name, customer_email, total_cop, status) VALUES
('Marta Osorio', 'marta.osorio@example.com', 96000, 'pending'),
('Diego Peña', 'diego.pena@example.com', 58000, 'pending');
