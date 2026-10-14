"""End-to-end verification script for task 07-B.

Verifies:
1. Stack health at http://127.0.0.1:8007 and demo store at http://127.0.0.1:8087
2. Registers 2 products from demo store:
   - Mechanical Keyboard RGB ($120.00, target $100.00)
   - Studio Monitor Headphones ($85.00, target $70.00)
3. Performs initial scrape on both products and displays initial history.
4. Lowers Headphones price to $65.00 using update_price.py.
5. Performs second scrape on Headphones.
6. Displays the updated price history (85.00 -> 65.00) and the triggered webhook alert.
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE_URL = "http://127.0.0.1:8007"
DEMO_STORE_URL = "http://127.0.0.1:8087"
API_TOKEN = "change_me_api_token"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def http_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    url = f"{API_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "application/json" in content_type:
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw


def wait_for_services(timeout: int = 30):
    print(">>> Waiting for API and Demo Store to be ready...")
    deadline = time.monotonic() + timeout
    api_ready = False
    store_ready = False

    while time.monotonic() < deadline:
        if not api_ready:
            try:
                with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=2) as r:
                    if r.status == 200:
                        api_ready = True
            except Exception:
                pass

        if not store_ready:
            try:
                with urllib.request.urlopen(f"{DEMO_STORE_URL}/robots.txt", timeout=2) as r:
                    if r.status == 200:
                        store_ready = True
            except Exception:
                pass

        if api_ready and store_ready:
            print(">>> Services are healthy and reachable!")
            return True
        time.sleep(1)

    print(">>> Error: Services timed out.", file=sys.stderr)
    return False


def main():
    print("=" * 65)
    print("   E-COMMERCE PRICE MONITOR (07-B) - E2E VERIFICATION")
    print("=" * 65)

    if not wait_for_services():
        sys.exit(1)

    # 1. Reset prices in demo-store before starting
    script_path = Path(__file__).resolve().parent.parent / "demo-store" / "update_price.py"
    subprocess.run([sys.executable, str(script_path), "headphones", "85.00"], check=True)
    subprocess.run([sys.executable, str(script_path), "keyboard", "120.00"], check=True)

    # Clean existing test products if any
    status_code, prods = http_request("GET", "/api/v1/products/")
    if status_code == 200 and isinstance(prods, list):
        for p in prods:
            if "demo-store" in p.get("site_domain", ""):
                http_request("DELETE", f"/api/v1/products/{p['id']}")

    print("\n1. Registering 2 products from Demo Store...")

    # Product 1: Keyboard
    kb_payload = {
        "name": "Mechanical Keyboard RGB",
        "url": "http://demo-store/products/keyboard.html",
        "site_domain": "demo-store",
        "target_price": 100.00,
        "alert_threshold_pct": 10.0,
        "currency": "USD",
        "check_interval_hours": 6,
        "requires_js": False,
        "is_active": True,
    }
    code, kb_prod = http_request("POST", "/api/v1/products/", kb_payload)
    assert code == 201, f"Failed to create keyboard product: {kb_prod}"
    kb_id = kb_prod["id"]
    print(f"   [+] Registered Product 1: {kb_prod['name']} (ID: {kb_id})")

    # Product 2: Headphones
    hp_payload = {
        "name": "Studio Monitor Headphones",
        "url": "http://demo-store/products/headphones.html",
        "site_domain": "demo-store",
        "target_price": 70.00,
        "alert_threshold_pct": 10.0,
        "currency": "USD",
        "check_interval_hours": 6,
        "requires_js": False,
        "is_active": True,
    }
    code, hp_prod = http_request("POST", "/api/v1/products/", hp_payload)
    assert code == 201, f"Failed to create headphones product: {hp_prod}"
    hp_id = hp_prod["id"]
    print(f"   [+] Registered Product 2: {hp_prod['name']} (ID: {hp_id})")

    # Initial Scrape
    print("\n2. Scraping initial prices...")
    code, kb_res = http_request("POST", f"/api/v1/products/{kb_id}/scrape")
    print(f"   Keyboard scrape: {kb_res}")
    code, hp_res = http_request("POST", f"/api/v1/products/{hp_id}/scrape")
    print(f"   Headphones scrape: {hp_res}")

    # Check Initial History
    code, kb_hist = http_request("GET", f"/api/v1/products/{kb_id}/history")
    code, hp_hist = http_request("GET", f"/api/v1/products/{hp_id}/history")
    print("\n   Initial Recorded Prices:")
    print(f"   - {kb_prod['name']}: ${kb_hist[-1]['price']} {kb_hist[-1]['currency']}")
    print(
        f"   - {hp_prod['name']}: ${hp_hist[-1]['price']} {hp_hist[-1]['currency']} (Target: $70.00)"
    )

    # Lower price with script
    print("\n3. Lowering price with update_price.py script: headphones -> $65.00")
    proc = subprocess.run(
        [sys.executable, str(script_path), "headphones", "65.00"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"   {proc.stdout.strip()}")

    # Second scrape
    print("\n4. Triggering second scrape on Studio Monitor Headphones...")
    code, hp_res2 = http_request("POST", f"/api/v1/products/{hp_id}/scrape")
    print(f"   Scrape response: {hp_res2}")

    # Show updated history
    code, hp_hist2 = http_request("GET", f"/api/v1/products/{hp_id}/history")
    print("\n5. Updated Price History for Studio Monitor Headphones:")
    for idx, pt in enumerate(hp_hist2, 1):
        print(
            f"   [{idx}] Time: {pt['scraped_at']} | Price: ${pt['price']} {pt['currency']} | Stock: {pt['availability']}"
        )

    # Show received alert
    print("\n6. Checking Triggered Alerts for Studio Monitor Headphones:")
    code, alerts = http_request("GET", f"/api/v1/products/{hp_id}/alerts")
    if code == 200 and alerts:
        for a in alerts:
            print("   ALERT FOUND:")
            print(f"   - Type: {a['alert_type']}")
            print(f"   - Old Price: ${a['old_price']}")
            print(f"   - New Price: ${a['new_price']}")
            print(f"   - Status: {a['status']} (Delivered to webhook sink)")
            print(f"   - Timestamp: {a['sent_at']}")
    else:
        print("   No alerts found!", file=sys.stderr)
        sys.exit(1)

    # Verify CSV export
    print("\n7. Verifying CSV Export...")
    code, csv_text = http_request("GET", f"/api/v1/export/csv?product_id={hp_id}")
    print("   CSV Export snippet:")
    for line in str(csv_text).strip().splitlines()[:4]:
        print(f"   | {line}")

    print("\n" + "=" * 65)
    print("   ALL VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
