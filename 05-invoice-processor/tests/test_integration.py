"""Integration tests executing real OCR against sample PDF invoices."""

import shutil
from pathlib import Path

import pytest

from app.core.ocr_engine import ocr_engine
from app.services.extractor import extractor
from app.services.validator import validator

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def check_tesseract_available():
    if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
        pytest.skip("Tesseract o poppler no están disponibles en este entorno.")


def test_real_ocr_factura_1_limpia(fixtures_dir: Path):
    pdf_path = fixtures_dir / "factura_1_limpia.pdf"
    file_bytes = pdf_path.read_bytes()

    text, page_count = ocr_engine.process_file(file_bytes, pdf_path.name)
    assert page_count == 1
    assert "SOLUCIONES ANDINAS" in text
    assert "900.123.456-8" in text

    extracted = extractor.extract(text)
    assert extracted.invoice_number == "FEV-1001"
    is_valid, errors = validator.validate(extracted)
    assert is_valid is True
    assert len(errors) == 0


def test_real_ocr_factura_3_multipage(fixtures_dir: Path):
    pdf_path = fixtures_dir / "factura_3_multipage.pdf"
    file_bytes = pdf_path.read_bytes()

    text, page_count = ocr_engine.process_file(file_bytes, pdf_path.name)
    assert page_count == 2
    assert "DISTRIBUIDORA NACIONAL" in text

    extracted = extractor.extract(text)
    assert extracted.invoice_number == "FEV-3003"
    is_valid, errors = validator.validate(extracted)
    assert is_valid is True


def test_real_ocr_factura_4_descuadre(fixtures_dir: Path):
    pdf_path = fixtures_dir / "factura_4_descuadre.pdf"
    file_bytes = pdf_path.read_bytes()

    text, page_count = ocr_engine.process_file(file_bytes, pdf_path.name)
    extracted = extractor.extract(text)
    is_valid, errors = validator.validate(extracted)
    assert is_valid is False
    assert len(errors) > 0


def test_real_ocr_factura_6_ingles(fixtures_dir: Path):
    pdf_path = fixtures_dir / "factura_6_ingles.pdf"
    file_bytes = pdf_path.read_bytes()

    text, page_count = ocr_engine.process_file(file_bytes, pdf_path.name)
    assert "GLOBAL CLOUD SOLUTIONS" in text
    assert "US-987654321" in text

    extracted = extractor.extract(text)
    assert extracted.currency == "USD"
    is_valid, errors = validator.validate(extracted)
    assert is_valid is True
