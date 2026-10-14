"""Unit tests for fake-llm's regex parsing (DECISIONES-14 B1). Pure unit test, no Docker: imports
``fake-llm/server.py`` directly (it has no dependency, so this is safe/fast).
"""

import sys
from pathlib import Path

FAKE_LLM_DIR = Path(__file__).resolve().parent.parent / "fake-llm"
sys.path.insert(0, str(FAKE_LLM_DIR))

from server import build_daily_summary, extract_invoice  # noqa: E402

INVOICE_TEXT = """FACTURA DE VENTA
Proveedor: Distribuidora La Sabana SAS
NIT: 900123456-7
Fecha: 2026-09-30
Items:
- Tomate chonto x 20 = 60000
- Cebolla cabezona x 15 = 45000
Subtotal: 195000
IVA: 37050
Total: 232050
"""

REPORT_TEXT = """TAREA: REPORTE_DIARIO
Fecha: 2026-10-04
Ventas:
- Bandeja Paisa: 14 unidades, $476000
- Ajiaco Santafereño: 9 unidades, $261000
Total del dia: $737000
"""


def test_extract_invoice_parses_all_fields() -> None:
    result = extract_invoice(INVOICE_TEXT)
    assert result["proveedor"] == "Distribuidora La Sabana SAS"
    assert result["nit"] == "900123456-7"
    assert result["fecha"] == "2026-09-30"
    assert result["subtotal"] == 195000
    assert result["iva"] == 37050
    assert result["total"] == 232050
    assert result["items"] == [
        {"nombre": "Tomate chonto", "cantidad": 20, "precio": 60000},
        {"nombre": "Cebolla cabezona", "cantidad": 15, "precio": 45000},
    ]


def test_extract_invoice_missing_fields_are_none() -> None:
    result = extract_invoice("FACTURA DE VENTA\nSin mas datos.")
    assert result["proveedor"] is None
    assert result["total"] is None
    assert result["items"] == []


def test_build_daily_summary_repeats_prompt_numbers() -> None:
    summary = build_daily_summary(REPORT_TEXT)
    assert "2026-10-04" in summary
    assert "14" in summary
    assert "Bandeja Paisa" in summary
    assert "476000" in summary
    assert "737000" in summary
