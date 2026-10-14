"""Integration tests for end-to-end ingestion, deduplication and digest delivery."""

from unittest.mock import MagicMock, patch

import pytest

from api.database import MemoryDatabase, set_db
from fake_llm.server import handle_chat_completion, handle_embeddings
from ingestion.pipeline import generate_and_dispatch_digest, run_ingestion_pipeline


@pytest.mark.integration
def test_full_pipeline_cross_source_deduplication(feeds_url: str):
    """Verifies that 3 feeds covering the same story collapse to 1 parent + 2 duplicates."""
    db = MemoryDatabase()
    set_db(db)

    # Register 3 sources pointing to the fixture feeds served over HTTP
    db.create_source({"name": "TechNews A", "url": f"{feeds_url}/feed_tech_a.xml"})
    db.create_source({"name": "DailyTech B", "url": f"{feeds_url}/feed_tech_b.xml"})
    db.create_source({"name": "GlobalNews C", "url": f"{feeds_url}/feed_tech_c.xml"})

    # Mock the LLM endpoint using our fake_llm logic directly
    def fake_post(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        json_data = kwargs.get("json", {})
        if "embeddings" in url:
            mock_resp.json.return_value = handle_embeddings(json_data)
        elif "chat/completions" in url:
            mock_resp.json.return_value = handle_chat_completion(json_data)
        return mock_resp

    with patch("httpx.Client.post", side_effect=fake_post):
        # Run ingestion pipeline
        summary = run_ingestion_pipeline()

    assert summary["processed_sources"] == 3
    assert summary["total_articles"] == 6
    assert summary["new_articles"] == 4
    assert summary["duplicates_detected"] == 2

    # Query articles from DB
    articles = list(db.articles.values())
    assert len(articles) == 6

    # Verify duplicate linkage
    duplicates = [a for a in articles if a["is_duplicate"]]
    uniques = [a for a in articles if not a["is_duplicate"]]

    assert len(duplicates) == 2
    assert len(uniques) == 4

    # Parent article for GPT-5 should be from TechNews A
    gpt5_parent = next((a for a in uniques if "gpt-5" in a["title"].lower() or "gpt 5" in a["title"].lower()), None)
    assert gpt5_parent is not None
    assert gpt5_parent["ai_summary"] is not None

    for dup in duplicates:
        assert dup["parent_article_id"] == gpt5_parent["id"]
        assert dup["ai_summary"] is None  # duplicates are NOT re-summarized

    # Verify digest dispatch
    with patch("ingestion.pipeline.send_digest_email", return_value=True):
        digest = generate_and_dispatch_digest(
            target_audience="EQUIPO_LIDERAZGO",
            recipient_email="director@empresa.com",
        )

    assert digest["status"] == "SUCCESS"
    assert digest["article_count"] == 4  # exactly 4 unique stories in digest
