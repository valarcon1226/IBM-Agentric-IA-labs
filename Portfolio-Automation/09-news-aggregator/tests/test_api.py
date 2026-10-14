"""Unit tests for FastAPI endpoints, security, CRUD and search."""

from unittest.mock import patch


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_auth_rejection(client):
    # Missing token
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 401

    # Invalid token
    resp = client.get("/api/v1/sources", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401


def test_sources_crud(client, auth_headers):
    # 1. Create source
    create_payload = {
        "name": "TechCrunch Feed",
        "url": "https://techcrunch.com/feed/",
        "source_type": "RSS",
        "is_active": True,
    }
    resp = client.post("/api/v1/sources", json=create_payload, headers=auth_headers)
    assert resp.status_code == 201
    source_data = resp.json()
    assert source_data["name"] == "TechCrunch Feed"
    assert source_data["health_status"] == "HEALTHY"
    source_id = source_data["id"]

    # 2. List sources
    resp = client.get("/api/v1/sources", headers=auth_headers)
    assert resp.status_code == 200
    sources = resp.json()
    assert any(s["id"] == source_id for s in sources)

    # 3. Update source
    update_payload = {"name": "TechCrunch News Global", "is_active": False}
    resp = client.put(f"/api/v1/sources/{source_id}", json=update_payload, headers=auth_headers)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "TechCrunch News Global"
    assert updated["is_active"] is False

    # 4. Delete source
    resp = client.delete(f"/api/v1/sources/{source_id}", headers=auth_headers)
    assert resp.status_code == 200

    # 5. Verify deletion
    resp = client.delete(f"/api/v1/sources/{source_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_articles_search(client, auth_headers, memory_db):
    # Seed articles directly into memory_db
    memory_db.create_article({
        "id": "art-1",
        "title": "Avances en modelos de lenguaje y redes neuronales",
        "url": "https://news.local/art-1",
        "category_id": "cat-1",
        "raw_content": "Detalles técnicos sobre transformers y LLMs.",
        "ai_summary": "- Viñeta de resumen 1.",
        "is_duplicate": False,
    })
    memory_db.create_article({
        "id": "art-2",
        "title": "Actualización de Kubernetes 1.32",
        "url": "https://news.local/art-2",
        "category_id": "cat-3",
        "raw_content": "Mejoras para clusters en la nube y DevOps.",
        "ai_summary": "- Viñeta de resumen 2.",
        "is_duplicate": False,
    })
    memory_db.create_article({
        "id": "art-3",
        "title": "Copia duplicada de modelo de lenguaje",
        "url": "https://news.local/art-3",
        "category_id": "cat-1",
        "raw_content": "Texto similar.",
        "ai_summary": None,
        "is_duplicate": True,
        "parent_article_id": "art-1",
    })

    # Search by keyword
    resp = client.get("/api/v1/articles?q=kubernetes", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert "Kubernetes" in items[0]["title"]

    # Filter by category
    resp = client.get("/api/v1/articles?category=Inteligencia Artificial", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    # Filter out duplicates
    resp = client.get("/api/v1/articles?is_duplicate=false", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["is_duplicate"] is False for item in items)


def test_digests_generate_and_list(client, auth_headers, memory_db):
    memory_db.create_article({
        "id": "art-digest-1",
        "title": "Noticia para el boletin de hoy",
        "url": "https://news.local/art-digest-1",
        "category_id": "cat-1",
        "raw_content": "Contenido para digest.",
        "ai_summary": "- Resumen ejecutivo.",
        "is_duplicate": False,
    })

    with patch("ingestion.pipeline.send_digest_email", return_value=True):
        payload = {
            "target_audience": "EJECUTIVOS",
            "recipient_email": "ceo@empresa.com",
        }
        resp = client.post("/api/v1/digests/generate", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        digest_data = resp.json()
        assert digest_data["target_audience"] == "EJECUTIVOS"
        assert digest_data["recipient_email"] == "ceo@empresa.com"
        assert digest_data["status"] == "SUCCESS"
        assert digest_data["article_count"] >= 1

    # List digests
    resp = client.get("/api/v1/digests", headers=auth_headers)
    assert resp.status_code == 200
    digests = resp.json()
    assert len(digests) >= 1
    assert digests[0]["target_audience"] == "EJECUTIVOS"
