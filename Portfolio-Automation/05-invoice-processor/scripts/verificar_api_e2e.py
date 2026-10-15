"""End-to-end verification script testing the running API with all 6 invoices."""

import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8005"
API_TOKEN = "change_me_bearer_token"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

INVOICE_FILES = [
    "factura_1_limpia.pdf",
    "factura_2_ruido.pdf",
    "factura_4_descuadre.pdf",
    "factura_5_sin_nit.pdf",
    "factura_6_ingles.pdf",
]


def test_health():
    print("--- 1. Healthcheck ---")
    r = httpx.get(f"{BASE_URL}/health", timeout=10)
    print(f"GET /health -> HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200


def process_all_invoices():
    print("\n--- 2. Procesamiento síncrono de las 6 facturas (POST /api/v1/invoices/process) ---")
    results = []
    for filename in INVOICE_FILES:
        filepath = FIXTURES_DIR / filename
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            r = httpx.post(
                f"{BASE_URL}/api/v1/invoices/process",
                headers=HEADERS,
                files=files,
                timeout=30,
            )
        if r.status_code == 200:
            data = r.json()
            results.append(data)
            print(f"[{filename}] HTTP {r.status_code}")
            print(f"  Emisor: {data.get('issuer_name')} | NIT/VAT: {data.get('issuer_vat')}")
            print(f"  Número: {data.get('invoice_number')} | Fecha: {data.get('invoice_date')}")
            sub = data.get("subtotal")
            tax = data.get("tax_amount")
            tot = data.get("total")
            cur = data.get("currency")
            print(f"  Subtotal: {sub} | Impuesto: {tax} | Total: {tot} {cur}")
            print(f"  is_valid: {data.get('is_valid')}")
            print(f"  validation_errors: {data.get('validation_errors')}")
        else:
            print(f"[{filename}] ERROR HTTP {r.status_code}: {r.text}")
    return results


def test_async_upload():
    print("\n--- 3. Procesamiento asíncrono con Celery (POST /api/v1/invoices/upload) ---")
    filepath = FIXTURES_DIR / "factura_3_multipage.pdf"
    with open(filepath, "rb") as f:
        files = {"file": ("factura_3_multipage_async.pdf", f, "application/pdf")}
        r = httpx.post(
            f"{BASE_URL}/api/v1/invoices/upload",
            headers=HEADERS,
            files=files,
            timeout=15,
        )
    print(f"POST /api/v1/invoices/upload -> HTTP {r.status_code}: {r.json()}")
    job_id = r.json().get("job_id")

    # Poll status
    print(f"Polling job {job_id}...")
    final_status = None
    for attempt in range(15):
        time.sleep(1)
        r_job = httpx.get(f"{BASE_URL}/api/v1/invoices/jobs/{job_id}", headers=HEADERS, timeout=10)
        status_data = r_job.json()
        status_str = status_data.get("status")
        prog = status_data.get("progress")
        msg = status_data.get("message")
        print(f"  Intento {attempt + 1}: status={status_str}, progress={prog}, message={msg}")
        if status_str in ("COMPLETED", "FAILED"):
            final_status = status_data
            break

    print("Resultado final del job asíncrono:", final_status)


def test_pagination_and_export():
    print("\n--- 4. Listado paginado y exportación CSV ---")
    r_list = httpx.get(f"{BASE_URL}/api/v1/invoices?page=1&limit=5", headers=HEADERS, timeout=10)
    print(f"GET /api/v1/invoices -> HTTP {r_list.status_code}")
    list_json = r_list.json()
    tot = list_json.get("total_records")
    pg = list_json.get("page")
    cnt = len(list_json.get("data", []))
    print(f"  total_records: {tot}, página: {pg}, registros devueltos: {cnt}")

    r_export = httpx.post(
        f"{BASE_URL}/api/v1/invoices/export",
        headers=HEADERS,
        json={"format": "csv"},
        timeout=10,
    )
    ctype = r_export.headers.get("content-type")
    print(f"POST /api/v1/invoices/export -> HTTP {r_export.status_code}, content-type: {ctype}")
    csv_lines = r_export.text.splitlines()
    print(f"  Líneas CSV exportadas: {len(csv_lines)}")
    if csv_lines:
        print(f"  Encabezado: {csv_lines[0]}")
        if len(csv_lines) > 1:
            print(f"  Fila muestra: {csv_lines[1]}")


def main():
    test_health()
    process_all_invoices()
    test_async_upload()
    test_pagination_and_export()
    print("\nDemostración de punta a punta finalizada con éxito.")


if __name__ == "__main__":
    main()
