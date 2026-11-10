# Project: Invoice Processor & Validator

## 1. Problem Statement
Processing invoices manually is tedious, slow, and error-prone. Accounting and operations teams often spend hours copying data from PDFs into systems of record. This microservice automates invoice processing by receiving invoices (PDF or images), extracting structured data via OCR (Optical Character Recognition) and heuristics, validating fiscal rules (like tax calculations and VAT formatting), and exporting the clean data to JSON/CSV or pushing it directly to Google Sheets.

## 2. Architecture
The architecture is designed to handle both synchronous (single page, fast) and asynchronous (multi-page, heavy OCR) workloads.

```mermaid
flowchart TD
    Client[Client Application] -->|Upload PDF/Image| FastAPI[FastAPI Service]
    
    FastAPI -->|Single-page / Quick| SyncProcess[Sync Pipeline]
    FastAPI -->|Multi-page PDF| AsyncProcess[Async Pipeline: Celery]
    
    AsyncProcess --> Redis[(Redis Queue)]
    Redis --> Worker[Celery Worker]
    Worker --> PDF2Img[pdf2image]
    
    SyncProcess --> PDF2Img
    PDF2Img --> Tesseract[Tesseract OCR]
    Tesseract --> Extraction[Regex & Heuristics]
    Extraction --> Validation[Business Logic Validation]
    
    Validation --> MinIO[(MinIO Storage)]
    Validation --> Postgres[(PostgreSQL DB)]
    
    MinIO -->|Stores original & raw text sidecar| Client
    Postgres -->|Stores structured invoice data| Client
    Worker -->|Status updates| Postgres
```

1. **Ingestion**: API receives PDF or Image payload.
2. **Preprocessing**: Converts PDFs to images via `pdf2image` (requires `poppler-utils`).
3. **OCR Engine**: Tesseract extracts raw text from the images.
4. **Extraction**: Regex and heuristics parse specific fields (Issuer, VAT, Dates, Totals, Line Items).
5. **Validation**: Business logic validates tax amounts, mathematical correctness, and required fields.
6. **Storage**: Extracted structured data goes to PostgreSQL, original files and raw text sidecars to MinIO.

## 3. Tech Stack
- **Framework**: FastAPI
- **OCR Engine**: Tesseract OCR, pytesseract
- **Image Processing**: pdf2image, Pillow, poppler-utils
- **Queue/Worker**: Celery + Redis (for async multi-page processing)
- **Database**: PostgreSQL
- **Storage**: MinIO

## 4. Environment Variables
Ensure the following variables are configured in `.env` (copied from `.env.example`):

```ini
# Database
DATABASE_URL=postgresql://user:change_me_db_password@postgres:5432/invoices
POSTGRES_USER=user
POSTGRES_PASSWORD=change_me_db_password
POSTGRES_DB=invoices

# Redis / Celery
REDIS_URL=redis://redis:6379/0

# MinIO Object Storage
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=change_me_minio_password
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=change_me_minio_password
MINIO_BUCKET=invoices-bucket
MINIO_SECURE=false

# API Security & Engine
API_BEARER_TOKEN=change_me_bearer_token
MAX_SYNC_PAGES=1
TESSERACT_CMD=tesseract
```

## 5. Database Schema
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE invoices (
    invoice_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    status VARCHAR(50) DEFAULT 'COMPLETED', -- PENDING, PROCESSING, COMPLETED, FAILED
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE line_items (
    item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    description TEXT,
    quantity DECIMAL(10, 2),
    unit_price DECIMAL(12, 2),
    line_total DECIMAL(12, 2)
);

-- Indexes for fast retrieval
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_created_at ON invoices(created_at);
```

## 6. API Endpoints

All invoice API endpoints require Bearer authentication:
`-H "Authorization: Bearer change_me_bearer_token"`

### 6.0 GET /health
Health check endpoint (no auth required).
```bash
curl -X GET "http://127.0.0.1:8005/health"
```
**Response:**
```json
{
  "status": "healthy",
  "service": "05-invoice-processor",
  "database": "connected",
  "minio": "connected",
  "redis": "connected"
}
```

### 6.1 POST /api/v1/invoices/process (Synchronous)
Processes a single-page invoice immediately. Accepts PDF, PNG, JPG and TIFF up to 10 MB (415 / 413 otherwise); a PDF with more than `MAX_SYNC_PAGES` pages gets a 422 pointing to the async endpoint.
```bash
curl -X POST "http://127.0.0.1:8005/api/v1/invoices/process" \
  -H "Authorization: Bearer change_me_bearer_token" \
  -F "file=@tests/fixtures/factura_1_limpia.pdf"
```
**Response:**
```json
{
  "invoice_id": "abc12345-6789-def0-1234-56789abcdef0",
  "original_filename": "factura_1_limpia.pdf",
  "issuer_name": "ACME Soluciones SAS",
  "issuer_vat": "900123456-8",
  "invoice_number": "FE-1024",
  "invoice_date": "2026-03-15",
  "subtotal": 1000000.0,
  "tax_rate": 19.0,
  "tax_amount": 190000.0,
  "total": 1190000.0,
  "currency": "COP",
  "is_valid": true,
  "validation_errors": [],
  "status": "COMPLETED",
  "line_items": [
    {"description": "Servicio de desarrollo", "quantity": 1.0, "unit_price": 600000.0, "line_total": 600000.0},
    {"description": "Soporte mensual", "quantity": 1.0, "unit_price": 400000.0, "line_total": 400000.0}
  ]
}
```

### 6.2 POST /api/v1/invoices/upload (Asynchronous)
Uploads a multi-page invoice for background Celery processing.
```bash
curl -X POST "http://127.0.0.1:8005/api/v1/invoices/upload" \
  -H "Authorization: Bearer change_me_bearer_token" \
  -F "file=@tests/fixtures/factura_3_multipage.pdf"
```
**Response:**
```json
{
  "job_id": "5f64d08f-e9bb-43e7-8fd4-95ebfa22ec46",
  "status": "PENDING",
  "message": "Invoice queued for asynchronous processing."
}
```

### 6.3 GET /api/v1/invoices/jobs/{job_id}
Poll status of an async OCR job.
```bash
curl -X GET "http://127.0.0.1:8005/api/v1/invoices/jobs/5f64d08f-e9bb-43e7-8fd4-95ebfa22ec46" \
  -H "Authorization: Bearer change_me_bearer_token"
```
**Response:**
```json
{
  "job_id": "5f64d08f-e9bb-43e7-8fd4-95ebfa22ec46",
  "status": "COMPLETED",
  "invoice_id": "848e3e4a-b50e-4361-9a7c-6e693170a469",
  "error": null
}
```

### 6.4 GET /api/v1/invoices
List all processed invoices with pagination.
```bash
curl -X GET "http://127.0.0.1:8005/api/v1/invoices?page=1&limit=10" \
  -H "Authorization: Bearer change_me_bearer_token"
```
**Response:**
```json
{
  "data": [
    {
      "invoice_id": "abc12345-...",
      "issuer_name": "ACME Soluciones SAS",
      "total": 1190000.00,
      "is_valid": true,
      "status": "COMPLETED",
      "created_at": "2026-10-14T16:20:00Z"
    }
  ],
  "total_records": 6,
  "page": 1,
  "limit": 10
}
```

### 6.5 GET /api/v1/invoices/{id}
Retrieve full details of a specific invoice.
```bash
curl -X GET "http://127.0.0.1:8005/api/v1/invoices/abc12345-6789-def0-1234-56789abcdef0" \
  -H "Authorization: Bearer change_me_bearer_token"
```

### 6.6 POST /api/v1/invoices/export
Export processed invoices to a CSV file.
```bash
curl -X POST "http://127.0.0.1:8005/api/v1/invoices/export" \
  -H "Authorization: Bearer change_me_bearer_token" \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "delimiter": ","}' \
  --output facturas_exportadas.csv
```

## 7. Validation Rules
- **DIAN NIT Check**: Validates Colombian NIT verification digit using module 11 weighted algorithm.
- **Tax Verification**: `subtotal * tax_rate ≈ tax_amount` (with rounding tolerance).
- **Total Verification**: `subtotal + tax_amount ≈ total`.
- **Line Items Verification**: `sum(line_total) ≈ subtotal`.
- **Required Fields**: Issuer name, total, and invoice date must be present for `is_valid=true`.

## 8. Docker Services & Setup
Port assignment: API mapped to `127.0.0.1:8005:8005`. Postgres, Redis, and MinIO are kept internal on the Docker network.

```bash
# Build and run containers
docker compose up -d --build

# Inspect status
docker compose ps

# Run integration tests (real Tesseract OCR) in a throwaway container with the dev dependencies
docker compose run --rm --no-deps -v ./tests:/app/tests -v ./requirements-dev.txt:/app/requirements-dev.txt \
  -v ./pyproject.toml:/app/pyproject.toml api sh -c "pip install -q -r requirements-dev.txt && python -m pytest -m integration -q"

# Run E2E test script
python scripts/verificar_api_e2e.py

# Stop and clean up containers and volumes
docker compose down -v
```

## 9. File Structure
```
05-invoice-processor/
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes.py
│   ├── core/
│   │   ├── celery_app.py
│   │   ├── config.py
│   │   └── ocr_engine.py
│   ├── models/
│   │   ├── database.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── exporter.py
│   │   ├── extractor.py
│   │   ├── storage.py
│   │   └── validator.py
│   └── main.py
├── scripts/
│   ├── generar_facturas.py
│   └── verificar_api_e2e.py
├── tests/
│   ├── fixtures/
│   │   ├── factura_1_limpia.pdf
│   │   ├── factura_2_ruido.pdf
│   │   ├── factura_3_multipage.pdf
│   │   ├── factura_4_descuadre.pdf
│   │   ├── factura_5_sin_nit.pdf
│   │   ├── factura_6_ingles.pdf
│   │   └── raw_text_*.txt
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_extractor.py
│   ├── test_integration.py
│   └── test_validator.py
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── EXECUTION_PLAN.md
├── init-db.sql
├── pyproject.toml
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

## 10. Testing Strategy
1. **Sample Invoices**: Synthetic PDFs in `tests/fixtures/` generated with ReportLab covering clean, noise, multi-page, arithmetic errors, missing NIT, and English international invoices.
2. **Unit Tests (Fast)**: Pre-extracted `raw_text_*.txt` fixtures test regex extractors and business validators in milliseconds.
3. **Integration Tests**: Tested inside the container running Tesseract OCR, Poppler, PostgreSQL, MinIO, and Celery.
4. **E2E Script**: `scripts/verificar_api_e2e.py` runs against live stack testing all endpoints and fixtures.
