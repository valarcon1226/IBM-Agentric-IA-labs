"""Unit tests for business logic and tax validation rules."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.services.extractor import extractor
from app.services.validator import validator


def test_dian_nit_dv_algorithm():
    # 900.123.456-8 is valid
    assert validator.validate_colombian_nit_dv("900123456", "8") is True
    # Wrong DV
    assert validator.validate_colombian_nit_dv("900123456", "3") is False
    # 901.234.567-7 is valid
    assert validator.validate_colombian_nit_dv("901234567", "7") is True


def test_vat_format_passing_and_failing():
    # Valid Colombian NIT with DV
    valid, err = validator.validate_vat_format("900.123.456-8")
    assert valid is True
    assert err is None

    # Invalid Colombian NIT with wrong DV
    valid, err = validator.validate_vat_format("900.123.456-3")
    assert valid is False
    assert "Dígito de verificación inválido" in err

    # Valid international VAT
    valid, err = validator.validate_vat_format("US-987654321")
    assert valid is True
    assert err is None

    # Missing / None VAT
    valid, err = validator.validate_vat_format(None)
    assert valid is False
    assert "Falta el NIT/VAT" in err


def test_required_fields_passing_and_failing():
    valid_data = {
        "issuer_name": "Empresa Valida SAS",
        "issuer_vat": "900.123.456-8",
        "invoice_number": "FEV-100",
        "invoice_date": date(2026, 10, 1),
        "subtotal": Decimal("100.00"),
        "tax_rate": Decimal("19.00"),
        "tax_amount": Decimal("19.00"),
        "total": Decimal("119.00"),
    }
    is_valid, errors = validator.validate(valid_data)
    assert is_valid is True
    assert len(errors) == 0

    # Missing issuer
    missing_issuer = dict(valid_data)
    missing_issuer["issuer_name"] = None
    is_valid, errors = validator.validate(missing_issuer)
    assert is_valid is False
    assert any("issuer_name" in e for e in errors)

    # Missing invoice date
    missing_date = dict(valid_data)
    missing_date["invoice_date"] = None
    is_valid, errors = validator.validate(missing_date)
    assert is_valid is False
    assert any("invoice_date" in e for e in errors)

    # Missing total
    missing_total = dict(valid_data)
    missing_total["total"] = None
    is_valid, errors = validator.validate(missing_total)
    assert is_valid is False
    assert any("total de la factura" in e for e in errors)


def test_tax_calculation_passing_and_failing():
    # Pass: 1000 * 19% = 190
    data_pass = {
        "issuer_name": "Empresa SAS",
        "issuer_vat": "900.123.456-8",
        "invoice_number": "FEV-1",
        "invoice_date": date(2026, 10, 1),
        "subtotal": Decimal("1000.00"),
        "tax_rate": Decimal("19.00"),
        "tax_amount": Decimal("190.00"),
        "total": Decimal("1190.00"),
    }
    is_valid, errors = validator.validate(data_pass)
    assert is_valid is True

    # Fail: 1000 * 19% != 50
    data_fail = dict(data_pass)
    data_fail["tax_amount"] = Decimal("50.00")
    data_fail["total"] = Decimal("1050.00")
    is_valid, errors = validator.validate(data_fail)
    assert is_valid is False
    assert any("Descuadre en impuesto" in e for e in errors)


def test_total_calculation_passing_and_failing():
    # Fail: 1000 subtotal + 190 tax != 2000 total
    data_fail = {
        "issuer_name": "Empresa SAS",
        "issuer_vat": "900.123.456-8",
        "invoice_number": "FEV-1",
        "invoice_date": date(2026, 10, 1),
        "subtotal": Decimal("1000.00"),
        "tax_rate": Decimal("19.00"),
        "tax_amount": Decimal("190.00"),
        "total": Decimal("2000.00"),
    }
    is_valid, errors = validator.validate(data_fail)
    assert is_valid is False
    assert any("Descuadre en total" in e for e in errors)


def test_line_item_math_passing_and_failing():
    data = {
        "issuer_name": "Empresa SAS",
        "issuer_vat": "900.123.456-8",
        "invoice_number": "FEV-1",
        "invoice_date": date(2026, 10, 1),
        "subtotal": Decimal("1000.00"),
        "total": Decimal("1000.00"),
        "line_items": [
            {
                "description": "Item 1",
                "quantity": Decimal("10"),
                "unit_price": Decimal("100"),
                "line_total": Decimal("1000"),
            },
        ],
    }
    is_valid, errors = validator.validate(data)
    assert is_valid is True

    # Mismatched line item
    data_bad_item = dict(data)
    data_bad_item["line_items"] = [
        {
            "description": "Item Bad",
            "quantity": Decimal("10"),
            "unit_price": Decimal("100"),
            "line_total": Decimal("500"),
        },
    ]
    is_valid, errors = validator.validate(data_bad_item)
    assert is_valid is False
    assert any("Descuadre en ítem" in e for e in errors)


def test_validate_all_six_fixtures(fixtures_dir: Path):
    # 1. Limpia -> VALID
    t1 = (fixtures_dir / "raw_text_1_limpia.txt").read_text(encoding="utf-8")
    v1, e1 = validator.validate(extractor.extract(t1))
    assert v1 is True
    assert len(e1) == 0

    # 2. Ruido -> VALID
    t2 = (fixtures_dir / "raw_text_2_ruido.txt").read_text(encoding="utf-8")
    v2, e2 = validator.validate(extractor.extract(t2))
    assert v2 is True
    assert len(e2) == 0

    # 3. Multipage -> VALID
    t3 = (fixtures_dir / "raw_text_3_multipage.txt").read_text(encoding="utf-8")
    v3, e3 = validator.validate(extractor.extract(t3))
    assert v3 is True
    assert len(e3) == 0

    # 4. Descuadre -> INVALID
    t4 = (fixtures_dir / "raw_text_4_descuadre.txt").read_text(encoding="utf-8")
    v4, e4 = validator.validate(extractor.extract(t4))
    assert v4 is False
    assert len(e4) >= 2

    # 5. Sin NIT -> INVALID
    t5 = (fixtures_dir / "raw_text_5_sin_nit.txt").read_text(encoding="utf-8")
    v5, e5 = validator.validate(extractor.extract(t5))
    assert v5 is False
    assert any("Falta el NIT/VAT" in err for err in e5)

    # 6. Ingles -> VALID
    t6 = (fixtures_dir / "raw_text_6_ingles.txt").read_text(encoding="utf-8")
    v6, e6 = validator.validate(extractor.extract(t6))
    assert v6 is True
    assert len(e6) == 0
