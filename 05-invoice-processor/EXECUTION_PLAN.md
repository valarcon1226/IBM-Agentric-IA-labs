# Execution Plan — Invoice Processor & Validator

Source of truth: `README.md`. No ML/feedback loop in this build — raw OCR text is stored as a MinIO sidecar file for manual debugging only.

## Prerequisites
- Docker + Docker Compose
- Tesseract OCR (instalado en Dockerfile con idiomas `spa` y `eng` + `poppler-utils`)
- Python 3.12 (`fastapi`, `pytesseract`, `pdf2image`, `pillow`, `pypdf`, `reportlab`)
- 6 facturas PDF ficticias en `tests/fixtures/` generadas con `scripts/generar_facturas.py`

## Build Checklist

- [x] Create the file/dir tree from README section 9; `docker-compose.yml` with `api`, `worker`, `postgres`, `redis`, `minio`.
  - Verify: `docker compose up -d --build` → todos los contenedores saludables (`healthy`).
- [x] Write init SQL for `invoices` and `line_items` (README section 5).
  - Verify: Tablas creadas con llaves primarias UUID, índices y restricciones en cascada.
- [x] Implement `core/ocr_engine.py` + `tests/test_integration.py` against sample invoices.
  - Verify: `pytest -m integration -q` — 4 passed ejecutando OCR real con Tesseract en contenedor.
- [x] Implement `services/extractor.py` (regex) + `tests/test_extractor.py` against raw-text fixtures.
  - Verify: `pytest tests/test_extractor.py -v` — 8 passed contra los 6 fixtures de texto.
- [x] Implement `services/validator.py` per README section 7 rules + unit tests (valid/invalid case per rule).
  - Verify: `pytest tests/test_validator.py -v` — 7 passed cubriendo reglas de IVA, total, NIT DIAN y campos obligatorios.
- [x] Wire MinIO storage: original PDF + sidecar raw-text `.ocr.txt`, plus DB writes to `invoices`/`line_items`.
  - Verify: Objetos persistidos en MinIO y registros en PostgreSQL con `is_valid` y `validation_errors`.
- [x] Implement `POST /api/v1/invoices/process`, `POST /api/v1/invoices/upload`, `GET /jobs/{id}`, `GET /invoices`, `GET /invoices/{id}`, `POST /export`.
  - Verify: Autenticación Bearer, procesamiento síncrono y asíncrono con Celery, paginación y exportación CSV.
- [x] Full stack up + process all sample invoices end to end.
  - Verify: `scripts/verificar_api_e2e.py` procesó las 6 facturas por la API en vivo arrojando los resultados esperados.

## Definition of Done
- [x] `docker compose up -d` brings up `api`, `worker`, `postgres`, `redis`, `minio` healthy.
- [x] `curl -X POST .../api/v1/invoices/process -F "file=@invoice.pdf"` returns extracted fields and `is_valid`.
- [x] All validation rules from README section 7 have a passing and failing test case.
- [x] `pytest` full suite green (23 passed en tests unitarios locales + 4 passed en tests de integración Docker = 27 tests).
- [x] No ML model or training loop added.
