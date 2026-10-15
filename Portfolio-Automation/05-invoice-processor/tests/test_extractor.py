"""Unit tests for invoice text extractor."""

from decimal import Decimal
from pathlib import Path

from app.services.extractor import extractor, parse_date, parse_decimal


def test_parse_decimal_variations():
    assert parse_decimal("1,500,000.00") == Decimal("1500000.00")
    assert parse_decimal("1.500.000,50") == Decimal("1500000.50")
    assert parse_decimal("$ 700,000") == Decimal("700000")
    assert parse_decimal("12.000.000") == Decimal("12000000")
    assert parse_decimal("500.00") == Decimal("500.00")
    assert parse_decimal("invalid") is None
    assert parse_decimal(None) is None


def test_parse_date_variations():
    assert str(parse_date("2026-10-01")) == "2026-10-01"
    assert str(parse_date("01/10/2026")) == "2026-10-01"
    assert str(parse_date("01-10-2026")) == "2026-10-01"
    assert parse_date("invalid") is None
    assert parse_date(None) is None


def test_extract_factura_1_limpia(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_1_limpia.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "SOLUCIONES ANDINAS S.A.S."
    assert extracted.issuer_vat == "900.123.456-8"
    assert extracted.invoice_number == "FEV-1001"
    assert str(extracted.invoice_date) == "2026-10-01"
    assert str(extracted.due_date) == "2026-10-31"
    assert extracted.subtotal == Decimal("1500000")
    assert extracted.tax_rate == Decimal("19")
    assert extracted.tax_amount == Decimal("285000")
    assert extracted.total == Decimal("1785000")
    assert extracted.currency == "COP"
    assert len(extracted.line_items) == 2
    assert extracted.line_items[0].description == "Licencias de Software Cloud"
    assert extracted.line_items[0].quantity == Decimal("10")
    assert extracted.line_items[0].unit_price == Decimal("100000")
    assert extracted.line_items[0].line_total == Decimal("1000000")


def test_extract_factura_2_ruido(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_2_ruido.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "LOGISTICA Y ENVIOS DEL PACIFICO S.A.S."
    assert extracted.issuer_vat == "900.123.456-8"
    assert extracted.invoice_number == "FEV-2002"
    assert str(extracted.invoice_date) == "2026-10-02"
    assert extracted.subtotal == Decimal("700000")
    assert extracted.tax_amount == Decimal("133000")
    assert extracted.total == Decimal("833000")
    assert len(extracted.line_items) == 2


def test_extract_factura_3_multipage(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_3_multipage.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "DISTRIBUIDORA NACIONAL LOGISTICA S.A.S."
    assert extracted.issuer_vat == "901.234.567-7"
    assert extracted.invoice_number == "FEV-3003"
    assert str(extracted.invoice_date) == "2026-10-03"
    assert extracted.subtotal == Decimal("12000000")
    assert extracted.tax_amount == Decimal("2280000")
    assert extracted.total == Decimal("14280000")
    assert len(extracted.line_items) == 5


def test_extract_factura_4_descuadre(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_4_descuadre.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "SERVICIOS INDUSTRIALES DEL VALLE S.A.S."
    assert extracted.invoice_number == "FEV-4004"
    assert extracted.subtotal == Decimal("1000000")
    assert extracted.tax_amount == Decimal("50000")
    assert extracted.total == Decimal("2000000")


def test_extract_factura_5_sin_nit(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_5_sin_nit.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "CONSULTORES INDEPENDIENTES ASOCIADOS"
    assert extracted.issuer_vat is None
    assert extracted.invoice_number == "FEV-5005"
    assert extracted.subtotal == Decimal("800000")
    assert extracted.total == Decimal("952000")


def test_extract_factura_6_ingles(fixtures_dir: Path):
    text = (fixtures_dir / "raw_text_6_ingles.txt").read_text(encoding="utf-8")
    extracted = extractor.extract(text)

    assert extracted.issuer_name == "GLOBAL CLOUD SOLUTIONS INC"
    assert extracted.issuer_vat == "US-987654321"
    assert extracted.invoice_number == "INV-2026-6006"
    assert str(extracted.invoice_date) == "2026-10-06"
    assert extracted.currency == "USD"
    assert extracted.subtotal == Decimal("700.00")
    assert extracted.tax_rate == Decimal("10")
    assert extracted.tax_amount == Decimal("70.00")
    assert extracted.total == Decimal("770.00")
    assert len(extracted.line_items) == 2


def test_extract_empty_text():
    extracted = extractor.extract("")
    assert extracted.issuer_name is None
    assert extracted.total is None
    assert len(extracted.line_items) == 0
