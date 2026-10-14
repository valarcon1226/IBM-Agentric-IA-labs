"""API routes for sources, articles search, digests and ingestion."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_db
from api.models import (
    ArticleResponse,
    DigestGenerateRequest,
    DigestResponse,
    IngestResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from api.security import verify_bearer_token
from ingestion.pipeline import generate_and_dispatch_digest, run_ingestion_pipeline

router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_bearer_token)])


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def add_source(payload: SourceCreate) -> dict[str, Any]:
    db = get_db()
    source = db.create_source(payload.model_dump())
    return source


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(active_only: bool = False) -> list[dict[str, Any]]:
    db = get_db()
    return db.get_sources(active_only=active_only)


@router.put("/sources/{source_id}", response_model=SourceResponse)
def update_source(source_id: str, payload: SourceUpdate) -> dict[str, Any]:
    db = get_db()
    updated = db.update_source(source_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return updated


@router.delete("/sources/{source_id}", status_code=status.HTTP_200_OK)
def delete_source(source_id: str) -> dict[str, str]:
    db = get_db()
    deleted = db.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return {"message": "Source deleted successfully"}


@router.get("/articles", response_model=list[ArticleResponse])
def search_articles(
    q: str | None = Query(default=None, description="Término de búsqueda para título o contenido"),
    category: str | None = Query(default=None, description="Filtrar por nombre de categoría"),
    is_duplicate: bool | None = Query(default=None, description="Filtrar por duplicados"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    db = get_db()
    raw_articles = db.search_articles(
        q=q,
        category=category,
        is_duplicate=is_duplicate,
        limit=limit,
        offset=offset,
    )
    results = []
    for a in raw_articles:
        results.append({
            "id": str(a["id"]),
            "title": a["title"],
            "url": a["url"],
            "author": a.get("author"),
            "published_date": a.get("published_date"),
            "ai_summary": a.get("ai_summary"),
            "category": a.get("category_name"),
            "source_name": a.get("source_name"),
            "is_duplicate": a.get("is_duplicate", False),
            "parent_article_id": str(a["parent_article_id"]) if a.get("parent_article_id") else None,
            "created_at": a.get("created_at"),
        })
    return results


@router.get("/digests", response_model=list[DigestResponse])
def list_digests(limit: int = Query(default=50, ge=1, le=100)) -> list[dict[str, Any]]:
    db = get_db()
    raw = db.list_digests(limit=limit)
    return [
        {
            "id": str(d["id"]),
            "target_audience": d["target_audience"],
            "recipient_email": d.get("recipient_email"),
            "sent_at": d["sent_at"],
            "status": d["status"],
            "article_count": d.get("article_count", 0),
            "error_message": d.get("error_message"),
        }
        for d in raw
    ]


@router.post("/digests/generate", response_model=DigestResponse, status_code=status.HTTP_201_CREATED)
def trigger_digest(payload: DigestGenerateRequest) -> dict[str, Any]:
    digest = generate_and_dispatch_digest(
        target_audience=payload.target_audience,
        recipient_email=payload.recipient_email,
        category=payload.category,
    )
    return {
        "id": str(digest["id"]),
        "target_audience": digest["target_audience"],
        "recipient_email": digest.get("recipient_email"),
        "sent_at": digest["sent_at"],
        "status": digest["status"],
        "article_count": digest.get("article_count", 0),
        "error_message": digest.get("error_message"),
    }


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingest() -> dict[str, Any]:
    summary = run_ingestion_pipeline()
    return {
        "message": "Ingestion job completed successfully",
        **summary,
    }
