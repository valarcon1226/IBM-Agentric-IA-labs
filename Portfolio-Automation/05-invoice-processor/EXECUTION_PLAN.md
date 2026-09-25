# Execution Plan — Invoice Processor & Validator

Source of truth: `README.md`. No ML/feedback loop in this build — raw OCR text is stored as a MinIO sidecar file for manual debugging only.

## Prerequisites
- Docker + Docker Compose
- Tesseract OCR installed locally (`tesseract --version`) and in the Dockerfile
- Python 3.11+ (`fastapi`, `pytesseract`, `pdf2image`, `pillow`)
- 5-10 sample invoices (PDF/image) for fixtures

## Build Checklist

- [ ] Create the file/dir tree from README section 8; `docker-compose.yml` with `db` + `minio` only.
  - Verify: `docker compose up -d db minio` → healthy.
- [ ] Write init SQL for `invoices` and `line_items` (README section 4).
  - Verify: `\dt` lists both.
- [ ] Implement `core/ocr_engine.py` + `tests/test_ocr_engine.py` against sample invoices.
  - Verify: `pytest tests/test_ocr_engine.py -v` — non-empty text for every sample.
- [ ] Implement `services/extractor.py` (regex) + `tests/test_extractor.py` against raw-text fixtures.
  - Verify: `pytest tests/test_extractor.py -v` passes.
- [ ] Implement `services/validator.py` per README section 6 rules + unit tests (valid/invalid case per rule).
  - Verify: `pytest tests/test_validator.py -v` passes.
- [ ] Wire MinIO storage: original PDF + sidecar raw-text `.txt`, plus DB writes to `invoices`/`line_items`.
  - Verify: both MinIO objects exist post-processing; DB row's `is_valid`/`validation_errors` correct.
- [ ] Implement `POST /api/v1/invoices/process` and `GET /api/v1/invoices/{id}`.
  - Verify: curl example from README section 5.1 returns the documented shape.
- [ ] Full stack up + process all sample invoices end to end.
  - Verify: every sample produces a DB record with the expected `is_valid` outcome.

## Definition of Done
- [ ] `docker compose up -d` brings up `api`, `db`, `minio` healthy.
- [ ] `curl -X POST .../api/v1/invoices/process -F "file=@invoice.pdf"` (README 5.1) returns extracted fields and `is_valid`.
- [ ] All validation rules from README section 6 have a passing and failing test case.
- [ ] `pytest` full suite green.
- [ ] No ML model or training loop added.
