"""End-to-end ingestion and digest generation pipeline."""

import logging
from datetime import datetime, timezone
from typing import Any

from api.config import settings
from api.database import get_db
from delivery.notifier import render_digest_html, send_digest_email
from ingestion.rss_parser import parse_rss_feed
from ingestion.text_extractor import fetch_and_extract_url
from intelligence.llm_summarizer import summarize
from intelligence.nlp_processor import (
    categorize_article,
    compute_content_hash,
    detect_duplicate_tfidf,
    get_embedding,
)

logger = logging.getLogger(__name__)


def process_single_source(source: dict[str, Any]) -> dict[str, int]:
    """Ingests, deduplicates, categorizes, and persists articles from a source."""
    db = get_db()
    source_id = str(source["id"])
    url = source["url"]
    source_type = source.get("source_type", "RSS")

    stats = {"total": 0, "new": 0, "duplicates": 0}

    try:
        if source_type.upper() == "RSS":
            parsed_items = parse_rss_feed(url)
        else:
            body = fetch_and_extract_url(url)
            parsed_items = [
                {
                    "title": source["name"],
                    "url": url,
                    "author": "Web Crawler",
                    "published_date": datetime.now(timezone.utc),
                    "raw_content": body,
                }
            ]

        categories = db.get_categories()

        for item in parsed_items:
            stats["total"] += 1
            item_url = item["url"]

            # Skip if URL already stored
            if db.find_article_by_url(item_url):
                continue

            title = item["title"]
            raw_content = item.get("raw_content", "") or ""
            author = item.get("author", "Redacción")
            pub_date = item.get("published_date") or datetime.now(timezone.utc)

            # Step 1: Fast SHA-256 hash match
            content_hash = compute_content_hash(title, raw_content)
            existing_by_hash = db.find_article_by_hash(content_hash)

            if existing_by_hash:
                # Flag as duplicate of the matched article
                parent_id = str(existing_by_hash["id"])
                db.create_article(
                    {
                        "source_id": source_id,
                        "category_id": existing_by_hash.get("category_id"),
                        "title": title,
                        "url": item_url,
                        "author": author,
                        "published_date": pub_date,
                        "raw_content": raw_content,
                        "content_hash": content_hash,
                        "embedding": None,
                        "ai_summary": None,
                        "is_duplicate": True,
                        "parent_article_id": parent_id,
                    }
                )
                stats["duplicates"] += 1
                logger.info(
                    f"Duplicate flagged by SHA-256 hash: '{title}' -> Parent ID: {parent_id}"
                )
                continue

            # Step 2: Semantic similarity deduplication
            full_text = f"{title}. {raw_content}"
            embedding = get_embedding(
                full_text,
                base_url=settings.LLM_BASE_URL,
                model=settings.EMBEDDING_MODEL,
                api_key=settings.LLM_API_KEY,
            )

            parent_id = None
            if embedding:
                parent_id = db.find_duplicate_by_vector(
                    embedding, threshold=settings.SIMILARITY_THRESHOLD
                )
            else:
                # TF-IDF fallback against non-duplicate articles
                recent_articles = db.get_articles_for_digest()
                parent_id = detect_duplicate_tfidf(full_text, recent_articles, threshold=0.35)

            if parent_id:
                # Semantic duplicate detected
                db.create_article(
                    {
                        "source_id": source_id,
                        "category_id": None,
                        "title": title,
                        "url": item_url,
                        "author": author,
                        "published_date": pub_date,
                        "raw_content": raw_content,
                        "content_hash": content_hash,
                        "embedding": embedding,
                        "ai_summary": None,
                        "is_duplicate": True,
                        "parent_article_id": parent_id,
                    }
                )
                stats["duplicates"] += 1
                logger.info(f"Semantic duplicate detected: '{title}' -> Parent ID: {parent_id}")
            else:
                # Unique article: categorize and summarize
                matched_category = categorize_article(title, raw_content, categories)
                category_id = matched_category.get("id")

                ai_summary = summarize(
                    raw_content,
                    title=title,
                    provider=settings.LLM_PROVIDER,
                    base_url=settings.LLM_BASE_URL,
                    model=settings.LLM_MODEL,
                    api_key=settings.LLM_API_KEY,
                )

                db.create_article(
                    {
                        "source_id": source_id,
                        "category_id": category_id,
                        "title": title,
                        "url": item_url,
                        "author": author,
                        "published_date": pub_date,
                        "raw_content": raw_content,
                        "content_hash": content_hash,
                        "embedding": embedding,
                        "ai_summary": ai_summary,
                        "is_duplicate": False,
                        "parent_article_id": None,
                    }
                )
                stats["new"] += 1

        db.update_source_health(source_id, "HEALTHY", datetime.now(timezone.utc), None)

    except Exception as exc:
        logger.error(f"Error processing source {url}: {exc}")
        db.update_source_health(source_id, "ERROR", datetime.now(timezone.utc), str(exc))
        raise

    return stats


def run_ingestion_pipeline() -> dict[str, int]:
    """Ingests all active sources from the database."""
    db = get_db()
    sources = db.get_sources(active_only=True)
    summary = {
        "processed_sources": 0,
        "total_articles": 0,
        "new_articles": 0,
        "duplicates_detected": 0,
    }

    for source in sources:
        try:
            stats = process_single_source(source)
            summary["processed_sources"] += 1
            summary["total_articles"] += stats["total"]
            summary["new_articles"] += stats["new"]
            summary["duplicates_detected"] += stats["duplicates"]
        except Exception as exc:
            logger.warning(f"Failed ingesting source {source.get('name')}: {exc}")

    return summary


def generate_and_dispatch_digest(
    target_audience: str = "TEAM_DIGEST",
    recipient_email: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Generates an HTML digest from recent non-duplicate articles and sends it via SMTP."""
    db = get_db()
    articles = db.get_articles_for_digest(category=category)

    clustered: dict[str, list[dict[str, Any]]] = {}
    for art in articles:
        cat_name = art.get("category_name") or "General"
        clustered.setdefault(cat_name, []).append(art)

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    html_content = render_digest_html(target_audience, clustered, digest_date=now_str)

    to_email = recipient_email or settings.DEFAULT_DIGEST_EMAIL
    subject = f"Boletín Diario de Inteligencia - {now_str}"

    success = send_digest_email(
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        from_email=settings.SMTP_FROM,
        to_email=to_email,
        subject=subject,
        html_body=html_content,
    )

    article_ids = [str(a["id"]) for a in articles]
    status = "SUCCESS" if success else "FAILED"
    error_msg = None if success else "Error connecting to SMTP server"

    digest = db.create_digest(
        target_audience=target_audience,
        recipient_email=to_email,
        status=status,
        article_ids=article_ids,
        error_message=error_msg,
    )
    return digest
