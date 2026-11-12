"""API endpoint unit and functional tests."""

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.models.database import Invoice, LineItem


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "invoice-processor"


def test_auth_rejection(client: TestClient):
    # No auth header
    res_no_auth = client.get("/api/v1/invoices")
    assert res_no_auth.status_code == 401

    # Invalid token
    res_bad_auth = client.get(
        "/api/v1/invoices",
        headers={"Authorization": "Bearer wrong_token"},
    )
    assert res_bad_auth.status_code == 401


def test_process_sync_endpoint(client: TestClient, auth_headers: dict, fixtures_dir: Path):
    clean_text = (fixtures_dir / "raw_text_1_limpia.txt").read_text(encoding="utf-8")

    with (
        patch("app.api.routes.ocr_engine.process_file", return_value=(clean_text, 1)),
        patch("app.api.routes.storage_service.upload_file", return_value="invoices/mock.pdf"),
        patch(
            "app.api.routes.storage_service.upload_text", return_value="invoices/mock.pdf.ocr.txt"
        ),
    ):
        files = {"file": ("factura_1_limpia.pdf", b"%PDF-mock-content", "application/pdf")}
        response = client.post(
            "/api/v1/invoices/process",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["issuer_name"] == "SOLUCIONES ANDINAS S.A.S."
        assert data["issuer_vat"] == "900.123.456-8"
        assert float(data["total"]) == 1785000.0
        assert data["is_valid"] is True
        assert len(data["validation_errors"]) == 0
        assert len(data["line_items"]) == 2


def test_upload_async_endpoint(client: TestClient, auth_headers: dict):
    mock_task = MagicMock()
    mock_task.id = "mock-celery-job-12345"

    with patch("app.api.routes.process_invoice_task.apply_async", return_value=mock_task):
        files = {"file": ("factura_multi.pdf", b"%PDF-mock-multi", "application/pdf")}
        response = client.post(
            "/api/v1/invoices/upload",
            files=files,
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "mock-celery-job-12345"
        assert data["status"] == "PENDING"


def test_job_status_endpoint(client: TestClient, auth_headers: dict):
    with patch("app.api.routes.AsyncResult") as mock_async_res:
        instance = MagicMock()
        instance.state = "PROCESSING"
        instance.info = {"progress": "60%", "message": "Running OCR"}
        mock_async_res.return_value = instance

        response = client.get(
            "/api/v1/invoices/jobs/mock-job-id",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "mock-job-id"
        assert data["status"] == "PROCESSING"
        assert data["progress"] == "60%"

        # Test aliases /api/v1/jobs/{id} and /jobs/{id}
        res_alias1 = client.get("/api/v1/jobs/mock-job-id", headers=auth_headers)
        assert res_alias1.status_code == 200
        assert res_alias1.json()["job_id"] == "mock-job-id"

        res_alias2 = client.get("/jobs/mock-job-id", headers=auth_headers)
        assert res_alias2.status_code == 200
        assert res_alias2.json()["job_id"] == "mock-job-id"


def test_list_and_get_invoice(client: TestClient, auth_headers: dict, db_session):
    # Seed an invoice
    inv_id = uuid.uuid4()
    invoice = Invoice(
        invoice_id=inv_id,
        original_filename="sample.pdf",
        minio_key="invoices/sample.pdf",
        issuer_name="Empresa Test",
        issuer_vat="900.123.456-8",
        invoice_number="INV-99",
        invoice_date=date(2026, 10, 1),
        total=Decimal("1500.00"),
        currency="COP",
        is_valid=True,
        validation_errors=[],
        status="COMPLETED",
    )
    item = LineItem(
        invoice_id=inv_id,
        description="Item de prueba",
        quantity=Decimal("1"),
        unit_price=Decimal("1500.00"),
        line_total=Decimal("1500.00"),
    )
    db_session.add(invoice)
    db_session.add(item)
    db_session.commit()

    # List
    list_res = client.get("/api/v1/invoices?page=1&limit=10", headers=auth_headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_records"] == 1
    assert list_data["data"][0]["issuer_name"] == "Empresa Test"

    # Get by ID
    get_res = client.get(f"/api/v1/invoices/{inv_id}", headers=auth_headers)
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["invoice_id"] == str(inv_id)
    assert len(get_data["line_items"]) == 1

    # 404 for unknown ID
    fake_id = uuid.uuid4()
    not_found_res = client.get(f"/api/v1/invoices/{fake_id}", headers=auth_headers)
    assert not_found_res.status_code == 404


def test_export_csv_endpoint(client: TestClient, auth_headers: dict, db_session):
    inv_id = uuid.uuid4()
    invoice = Invoice(
        invoice_id=inv_id,
        original_filename="export_sample.pdf",
        minio_key="invoices/export_sample.pdf",
        issuer_name="Exportadora Global",
        issuer_vat="900.123.456-8",
        invoice_number="EXP-01",
        invoice_date=date(2026, 10, 1),
        total=Decimal("5000.00"),
        is_valid=True,
        status="COMPLETED",
    )
    db_session.add(invoice)
    db_session.commit()

    export_res = client.post(
        "/api/v1/invoices/export",
        json={"format": "csv"},
        headers=auth_headers,
    )
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    csv_text = export_res.text
    assert "Exportadora Global" in csv_text
    assert "EXP-01" in csv_text


def test_upload_guards(client: TestClient, auth_headers: dict, fixtures_dir: Path):
    url = "/api/v1/invoices/process"
    bad_type = client.post(
        url, files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=auth_headers
    )
    assert bad_type.status_code == 415

    too_big = b"%PDF" + b"0" * (10 * 1024 * 1024)
    big = client.post(
        url, files={"file": ("big.pdf", too_big, "application/pdf")}, headers=auth_headers
    )
    assert big.status_code == 413

    multipage = (fixtures_dir / "factura_3_multipage.pdf").read_bytes()
    sync_multi = client.post(
        url,
        files={"file": ("factura_3_multipage.pdf", multipage, "application/pdf")},
        headers=auth_headers,
    )
    assert sync_multi.status_code == 422
    assert "/api/v1/invoices/upload" in sync_multi.json()["detail"]
