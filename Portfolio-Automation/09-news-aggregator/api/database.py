"""Database access layer with PostgreSQL/pgvector implementation and in-memory test fallback."""

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from api.config import settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class PostgresDatabase:
    """PostgreSQL database repository with pgvector and pg_trgm support."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextmanager
    def connection(self):
        conn = psycopg.connect(self.dsn, row_factory=dict_row)
        try:
            register_vector(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_health(self) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None

    def init_schema(self) -> None:
        if not SCHEMA_PATH.exists():
            logger.warning(f"Schema file not found at {SCHEMA_PATH}")
            return
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        logger.info("Database schema initialized successfully.")

    def get_sources(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM sources"
        params: list[Any] = []
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC;"

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    d["id"] = str(d["id"])
                    res.append(d)
                return res

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sources WHERE id = %s;", (source_id,))
                row = cur.fetchone()
                if row:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    return d
                return None

    def create_source(self, data: dict[str, Any]) -> dict[str, Any]:
        source_id = str(uuid.uuid4())
        query = """
            INSERT INTO sources (id, name, url, source_type, is_active, health_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
            SET name = EXCLUDED.name, is_active = EXCLUDED.is_active
            RETURNING *;
        """
        now = datetime.now(timezone.utc)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        source_id,
                        data["name"],
                        data["url"],
                        data.get("source_type", "RSS"),
                        data.get("is_active", True),
                        "HEALTHY",
                        now,
                    ),
                )
                row = cur.fetchone()
                if row:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    return d
                return {}

    def update_source(self, source_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        fields = []
        params = []
        for k in ("name", "url", "source_type", "is_active", "health_status"):
            if k in data and data[k] is not None:
                fields.append(f"{k} = %s")
                params.append(data[k])

        if not fields:
            return self.get_source(source_id)

        params.append(source_id)
        query = f"UPDATE sources SET {', '.join(fields)} WHERE id = %s RETURNING *;"

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                if row:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    return d
                return None

    def delete_source(self, source_id: str) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sources WHERE id = %s;", (source_id,))
                return cur.rowcount > 0

    def update_source_health(
        self,
        source_id: str,
        status: str,
        last_fetched: datetime,
        error: str | None = None,
    ) -> None:
        query = """
            UPDATE sources
            SET health_status = %s, last_fetched_at = %s, error_message = %s
            WHERE id = %s;
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (status, last_fetched, error, source_id))

    def get_categories(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM categories ORDER BY name ASC;")
                return [dict(r) for r in cur.fetchall()]

    def find_article_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        query = "SELECT * FROM articles WHERE content_hash = %s LIMIT 1;"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (content_hash,))
                row = cur.fetchone()
                return dict(row) if row else None

    def find_article_by_url(self, url: str) -> dict[str, Any] | None:
        query = "SELECT * FROM articles WHERE url = %s LIMIT 1;"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (url,))
                row = cur.fetchone()
                return dict(row) if row else None

    def find_duplicate_by_vector(
        self, embedding: list[float], threshold: float = 0.15
    ) -> str | None:
        if not embedding:
            return None
        query = """
            SELECT id, (embedding <=> %s::vector) AS distance
            FROM articles
            WHERE embedding IS NOT NULL AND is_duplicate = FALSE
            ORDER BY distance ASC
            LIMIT 1;
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (embedding,))
                row = cur.fetchone()
                if row and row["distance"] < threshold:
                    return str(row["id"])
        return None

    def create_article(self, article: dict[str, Any]) -> dict[str, Any]:
        article_id = article.get("id") or str(uuid.uuid4())
        query = """
            INSERT INTO articles (
                id, source_id, category_id, title, url, author, published_date,
                raw_content, content_hash, embedding, ai_summary, is_duplicate,
                parent_article_id, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING *;
        """
        now = datetime.now(timezone.utc)
        params = (
            article_id,
            article.get("source_id"),
            article.get("category_id"),
            article["title"],
            article["url"],
            article.get("author"),
            article.get("published_date") or now,
            article.get("raw_content"),
            article.get("content_hash"),
            article.get("embedding"),
            article.get("ai_summary"),
            article.get("is_duplicate", False),
            article.get("parent_article_id"),
            now,
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else {}

    def search_articles(
        self,
        q: str | None = None,
        category: str | None = None,
        is_duplicate: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []

        query = """
            SELECT a.*, c.name AS category_name, s.name AS source_name
            FROM articles a
            LEFT JOIN categories c ON a.category_id = c.id
            LEFT JOIN sources s ON a.source_id = s.id
        """

        if is_duplicate is not None:
            conditions.append("a.is_duplicate = %s")
            params.append(is_duplicate)

        if category:
            conditions.append("c.name ILIKE %s")
            params.append(f"%{category}%")

        order_by = "a.published_date DESC"

        if q:
            conditions.append("(a.title % %s OR a.title ILIKE %s)")
            params.extend([q, f"%{q}%"])
            order_by = "similarity(a.title, %s) DESC, a.published_date DESC"
            params.append(q)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY {order_by} LIMIT %s OFFSET %s;"
        params.extend([limit, offset])

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]

    def get_articles_for_digest(self, category: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT a.*, c.name AS category_name, s.name AS source_name
            FROM articles a
            LEFT JOIN categories c ON a.category_id = c.id
            LEFT JOIN sources s ON a.source_id = s.id
            WHERE a.is_duplicate = FALSE
        """
        params: list[Any] = []
        if category:
            query += " AND c.name ILIKE %s"
            params.append(f"%{category}%")
        query += " ORDER BY c.name ASC, a.published_date DESC LIMIT 50;"

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                articles = [dict(r) for r in cur.fetchall()]

                # Fetch duplicates for each parent article to enrich digest
                for art in articles:
                    cur.execute(
                        """
                        SELECT d.url, s.name AS source_name
                        FROM articles d
                        LEFT JOIN sources s ON d.source_id = s.id
                        WHERE d.parent_article_id = %s;
                        """,
                        (art["id"],),
                    )
                    art["duplicates"] = [dict(d) for d in cur.fetchall()]

                return articles

    def create_digest(
        self,
        target_audience: str,
        recipient_email: str | None,
        status: str,
        article_ids: list[str],
        error_message: str | None = None,
    ) -> dict[str, Any]:
        digest_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO digests (id, target_audience, recipient_email, sent_at, status, article_count, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                    """,
                    (
                        digest_id,
                        target_audience,
                        recipient_email,
                        now,
                        status,
                        len(article_ids),
                        error_message,
                    ),
                )
                digest = dict(cur.fetchone() or {})
                for aid in article_ids:
                    cur.execute(
                        "INSERT INTO digest_articles (digest_id, article_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                        (digest_id, aid),
                    )
                return digest

    def list_digests(self, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM digests ORDER BY sent_at DESC LIMIT %s;"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                return [dict(r) for r in cur.fetchall()]


class MemoryDatabase:
    """In-memory database for isolated, lightning-fast unit tests."""

    def __init__(self):
        self.sources: dict[str, dict[str, Any]] = {}
        self.categories: dict[str, dict[str, Any]] = {
            "cat-1": {
                "id": "cat-1",
                "name": "Inteligencia Artificial",
                "keywords": ["ia", "ai", "llm", "gpt"],
            },
            "cat-2": {
                "id": "cat-2",
                "name": "Ciberseguridad",
                "keywords": ["seguridad", "ciberseguridad", "malware"],
            },
            "cat-3": {
                "id": "cat-3",
                "name": "Cloud y DevOps",
                "keywords": ["cloud", "devops", "kubernetes", "docker"],
            },
            "cat-4": {
                "id": "cat-4",
                "name": "Fintech y Mercados",
                "keywords": ["fintech", "mercado", "inversión"],
            },
            "cat-5": {"id": "cat-5", "name": "General", "keywords": ["tecnología", "innovación"]},
        }
        self.articles: dict[str, dict[str, Any]] = {}
        self.digests: dict[str, dict[str, Any]] = {}
        self.digest_articles: list[tuple[str, str]] = []

    def check_health(self) -> bool:
        return True

    def init_schema(self) -> None:
        pass

    def get_sources(self, active_only: bool = False) -> list[dict[str, Any]]:
        items = list(self.sources.values())
        if active_only:
            items = [s for s in items if s.get("is_active", True)]
        return sorted(items, key=lambda s: str(s.get("created_at")), reverse=True)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        return self.sources.get(source_id)

    def create_source(self, data: dict[str, Any]) -> dict[str, Any]:
        for s in self.sources.values():
            if s.get("url") == data["url"]:
                s["name"] = data["name"]
                s["is_active"] = data.get("is_active", True)
                return s

        source_id = str(uuid.uuid4())
        item = {
            "id": source_id,
            "name": data["name"],
            "url": data["url"],
            "source_type": data.get("source_type", "RSS"),
            "is_active": data.get("is_active", True),
            "health_status": "HEALTHY",
            "last_fetched_at": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
        }
        self.sources[source_id] = item
        return item

    def update_source(self, source_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if source_id not in self.sources:
            return None
        item = self.sources[source_id]
        for k in ("name", "url", "source_type", "is_active", "health_status"):
            if k in data and data[k] is not None:
                item[k] = data[k]
        return item

    def delete_source(self, source_id: str) -> bool:
        return self.sources.pop(source_id, None) is not None

    def update_source_health(
        self,
        source_id: str,
        status: str,
        last_fetched: datetime,
        error: str | None = None,
    ) -> None:
        if source_id in self.sources:
            self.sources[source_id]["health_status"] = status
            self.sources[source_id]["last_fetched_at"] = last_fetched
            self.sources[source_id]["error_message"] = error

    def get_categories(self) -> list[dict[str, Any]]:
        return list(self.categories.values())

    def find_article_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        for a in self.articles.values():
            if a.get("content_hash") == content_hash:
                return a
        return None

    def find_article_by_url(self, url: str) -> dict[str, Any] | None:
        for a in self.articles.values():
            if a.get("url") == url:
                return a
        return None

    def find_duplicate_by_vector(
        self, embedding: list[float], threshold: float = 0.15
    ) -> str | None:
        # In memory simulation of vector distance using cosine distance
        if not embedding:
            return None
        import math

        for a in self.articles.values():
            if a.get("is_duplicate"):
                continue
            emb = a.get("embedding")
            if emb and len(emb) == len(embedding):
                dot = sum(x * y for x, y in zip(embedding, emb, strict=False))
                norm_a = math.sqrt(sum(x * x for x in embedding))
                norm_b = math.sqrt(sum(y * y for y in emb))
                if norm_a > 0 and norm_b > 0:
                    sim = dot / (norm_a * norm_b)
                    dist = 1.0 - sim
                    if dist < threshold:
                        return str(a["id"])
        return None

    def create_article(self, article: dict[str, Any]) -> dict[str, Any]:
        article_id = article.get("id") or str(uuid.uuid4())
        item = {
            "id": article_id,
            "source_id": article.get("source_id"),
            "category_id": article.get("category_id"),
            "title": article["title"],
            "url": article["url"],
            "author": article.get("author"),
            "published_date": article.get("published_date") or datetime.now(timezone.utc),
            "raw_content": article.get("raw_content"),
            "content_hash": article.get("content_hash"),
            "embedding": article.get("embedding"),
            "ai_summary": article.get("ai_summary"),
            "is_duplicate": article.get("is_duplicate", False),
            "parent_article_id": article.get("parent_article_id"),
            "created_at": datetime.now(timezone.utc),
        }
        self.articles[article_id] = item
        return item

    def search_articles(
        self,
        q: str | None = None,
        category: str | None = None,
        is_duplicate: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        results = []
        for a in self.articles.values():
            if is_duplicate is not None and a.get("is_duplicate") != is_duplicate:
                continue
            cat = self.categories.get(str(a.get("category_id")), {})
            cat_name = cat.get("name", "General")
            if category and category.lower() not in cat_name.lower():
                continue
            if q and (
                q.lower() not in a.get("title", "").lower()
                and q.lower() not in a.get("raw_content", "").lower()
            ):
                continue

            src = self.sources.get(str(a.get("source_id")), {})
            src_name = src.get("name", "Fuente")

            item = dict(a)
            item["category_name"] = cat_name
            item["source_name"] = src_name
            results.append(item)

        results.sort(key=lambda x: str(x.get("published_date")), reverse=True)
        return results[offset : offset + limit]

    def get_articles_for_digest(self, category: str | None = None) -> list[dict[str, Any]]:
        results = []
        for a in self.articles.values():
            if a.get("is_duplicate"):
                continue
            cat = self.categories.get(str(a.get("category_id")), {})
            cat_name = cat.get("name", "General")
            if category and category.lower() not in cat_name.lower():
                continue

            src = self.sources.get(str(a.get("source_id")), {})
            src_name = src.get("name", "Fuente")

            item = dict(a)
            item["category_name"] = cat_name
            item["source_name"] = src_name
            # Duplicates
            item["duplicates"] = [
                {
                    "url": d["url"],
                    "source_name": self.sources.get(str(d.get("source_id")), {}).get(
                        "name", "Fuente"
                    ),
                }
                for d in self.articles.values()
                if d.get("parent_article_id") == a["id"]
            ]
            results.append(item)

        results.sort(
            key=lambda x: (x.get("category_name", ""), str(x.get("published_date"))), reverse=True
        )
        return results[:50]

    def create_digest(
        self,
        target_audience: str,
        recipient_email: str | None,
        status: str,
        article_ids: list[str],
        error_message: str | None = None,
    ) -> dict[str, Any]:
        digest_id = str(uuid.uuid4())
        item = {
            "id": digest_id,
            "target_audience": target_audience,
            "recipient_email": recipient_email,
            "sent_at": datetime.now(timezone.utc),
            "status": status,
            "article_count": len(article_ids),
            "error_message": error_message,
        }
        self.digests[digest_id] = item
        for aid in article_ids:
            self.digest_articles.append((digest_id, aid))
        return item

    def list_digests(self, limit: int = 50) -> list[dict[str, Any]]:
        items = list(self.digests.values())
        items.sort(key=lambda d: str(d.get("sent_at")), reverse=True)
        return items[:limit]


_db_instance: PostgresDatabase | MemoryDatabase | None = None


def get_db() -> PostgresDatabase | MemoryDatabase:
    """Returns the singleton DB repository instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = PostgresDatabase(settings.DATABASE_URL)
    return _db_instance


def set_db(db: PostgresDatabase | MemoryDatabase) -> None:
    """Overrides the DB repository instance (e.g. for testing)."""
    global _db_instance
    _db_instance = db
