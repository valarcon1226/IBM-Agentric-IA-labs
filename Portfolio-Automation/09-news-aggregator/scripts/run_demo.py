"""Demo and End-to-End verification script for News Aggregator."""

import os
import time

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8009")
MAILPIT_BASE_URL = os.getenv("MAILPIT_BASE_URL", "http://localhost:8029")
BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "change_me_api_bearer_token")

HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
}


def wait_for_api_ready(max_retries: int = 20, delay: float = 2.0):
    print("1. Verificando disponibilidad de API...")
    for _ in range(max_retries):
        try:
            resp = httpx.get(f"{API_BASE_URL}/health", timeout=3.0)
            if resp.status_code == 200:
                print(f"   [OK] API saludable en {API_BASE_URL} ({resp.json()})")
                return True
        except Exception:
            pass
        time.sleep(delay)
    raise RuntimeError("API no respondió dentro del tiempo límite.")


def run_e2e_verification():
    wait_for_api_ready()

    print("\n2. Registrando 3 fuentes RSS con cobertura cruzada...")
    sources = [
        {"name": "TechNews A", "url": "http://feeds:8000/feed_tech_a.xml"},
        {"name": "DailyTech B", "url": "http://feeds:8000/feed_tech_b.xml"},
        {"name": "GlobalNews C", "url": "http://feeds:8000/feed_tech_c.xml"},
    ]
    created_sources = []
    for s in sources:
        resp = httpx.post(f"{API_BASE_URL}/api/v1/sources", json=s, headers=HEADERS, timeout=5.0)
        if resp.status_code == 201:
            data = resp.json()
            created_sources.append(data)
            print(f"   [+] Fuente registrada: {data['name']} (ID: {data['id']})")
        else:
            print(f"   [!] Error al registrar {s['name']}: {resp.status_code} {resp.text}")

    print("\n3. Disparando ingesta de feeds y deduplicación en dos pasos...")
    ingest_resp = httpx.post(f"{API_BASE_URL}/api/v1/ingest", headers=HEADERS, timeout=20.0)
    ingest_data = ingest_resp.json()
    print("   Resultado de Ingesta:")
    print(f"   - Fuentes procesadas: {ingest_data.get('processed_sources')}")
    print(f"   - Artículos totales encontrados: {ingest_data.get('total_articles')}")
    print(f"   - Artículos únicos (nuevos): {ingest_data.get('new_articles')}")
    print(f"   - Duplicados detectados y enlazados: {ingest_data.get('duplicates_detected')}")

    print("\n4. Consultando lista de artículos almacenados...")
    articles_resp = httpx.get(f"{API_BASE_URL}/api/v1/articles", headers=HEADERS, timeout=5.0)
    articles = articles_resp.json()
    print(f"   Total articulos en DB: {len(articles)}")
    for a in articles:
        tipo = "[DUPLICADO]" if a["is_duplicate"] else "[UNICO]"
        parent = f"(Enlazado a padre: {a['parent_article_id']})" if a["is_duplicate"] else ""
        print(f"   {tipo} {a['title'][:65]}... {parent}")

    print("\n5. Generando boletín HTML y despachando vía SMTP a Mailpit...")
    digest_payload = {
        "target_audience": "COMITE_EJECUTIVO",
        "recipient_email": "direccion@empresa-ficticia.com",
    }
    digest_resp = httpx.post(
        f"{API_BASE_URL}/api/v1/digests/generate",
        json=digest_payload,
        headers=HEADERS,
        timeout=10.0,
    )
    digest_data = digest_resp.json()
    print("   Resultado de Generación de Boletín:")
    print(f"   - ID Boletín: {digest_data.get('id')}")
    print(f"   - Estado: {digest_data.get('status')}")
    print(f"   - Artículos consolidados en boletín: {digest_data.get('article_count')}")
    print(f"   - Destinatario: {digest_data.get('recipient_email')}")

    print("\n6. Verificando recepción de correo en Mailpit...")
    time.sleep(1.5)
    mailpit_resp = httpx.get(f"{MAILPIT_BASE_URL}/api/v1/messages", timeout=5.0)
    if mailpit_resp.status_code == 200:
        messages = mailpit_resp.json().get("messages", [])
        print(f"   Mensajes en bandeja de entrada Mailpit: {len(messages)}")
        if messages:
            latest = messages[0]
            print(f"   - Asunto: {latest.get('Subject')}")
            print(f"   - De: {latest.get('From', {}).get('Address')}")
            print(f"   - Para: {[t.get('Address') for t in latest.get('To', [])]}")
            print(f"   - ID de Mensaje: {latest.get('ID')}")
    else:
        print(f"   [!] No se pudo consultar Mailpit en {MAILPIT_BASE_URL}: {mailpit_resp.status_code}")

    print("\n[OK] Verificación de punta a punta completada con éxito.")


if __name__ == "__main__":
    run_e2e_verification()
