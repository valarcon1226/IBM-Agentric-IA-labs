"""NLP and deduplication processor for news articles.

Implements:
1. Exact SHA-256 hash deduplication (normalized title + first 200 chars).
2. Semantic similarity deduplication using pgvector cosine distance (<=>).
3. TF-IDF fallback deduplication using scikit-learn when embeddings are unavailable.
4. Keyword cluster categorization.
"""

import hashlib
import logging
import re
from typing import Any

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, removing special characters and extra spaces."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_content_hash(title: str, content: str) -> str:
    """Computes a SHA-256 hash of normalized title + first 200 chars of normalized content."""
    norm_title = normalize_text(title)
    norm_start = normalize_text(content[:250])[:200]
    payload = f"{norm_title}::{norm_start}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_embedding(
    text: str,
    base_url: str = "http://fake_llm:8080/v1",
    model: str = "nomic-embed-text",
    api_key: str = "none",
    timeout: float = 4.0,
) -> list[float] | None:
    """Fetches text embedding from an OpenAI-compatible endpoint (Ollama / Fake LLM)."""
    clean_input = text[:2000].strip()
    if not clean_input:
        return None

    endpoint = f"{base_url.rstrip('/')}/embeddings"
    headers = {"Content-Type": "application/json"}
    if api_key and api_key != "none":
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                endpoint,
                headers=headers,
                json={"input": clean_input, "model": model},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data and "embedding" in data[0]:
                    return data[0]["embedding"]
            logger.warning(f"Embedding request failed with status {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.debug(f"Error fetching embedding from {endpoint}: {exc}")

    return None


def detect_duplicate_vector(
    new_embedding: list[float],
    cursor,
    threshold: float = 0.15,
) -> str | None:
    """Finds matching parent article ID using pgvector cosine distance (<=>)."""
    if not new_embedding:
        return None

    query = """
        SELECT id, (embedding <=> %s::vector) AS distance
        FROM articles
        WHERE embedding IS NOT NULL AND is_duplicate = FALSE
        ORDER BY distance ASC
        LIMIT 1;
    """
    try:
        cursor.execute(query, (new_embedding,))
        row = cursor.fetchone()
        if row:
            article_id = str(row[0])
            distance = float(row[1])
            if distance < threshold:
                logger.info(
                    f"Duplicate detected via pgvector: distance {distance:.4f} < {threshold}"
                )
                return article_id
    except Exception as exc:
        logger.warning(f"pgvector query error: {exc}")

    return None


def detect_duplicate_tfidf(
    new_text: str,
    candidate_articles: list[dict[str, Any]],
    threshold: float = 0.35,
) -> str | None:
    """Fallback deduplication using TF-IDF and cosine similarity from scikit-learn."""
    if not candidate_articles or not new_text.strip():
        return None

    norm_new = normalize_text(new_text)
    corpus = [norm_new]
    valid_candidates = []

    for cand in candidate_articles:
        text = f"{cand.get('title', '')} {cand.get('raw_content', '')}"
        norm_cand = normalize_text(text)
        if norm_cand:
            corpus.append(norm_cand)
            valid_candidates.append(cand)

    if not valid_candidates:
        return None

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 1), min_df=1, max_df=1.0)
        tfidf_matrix = vectorizer.fit_transform(corpus)
        sim_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        max_idx = int(sim_scores.argmax())
        max_score = float(sim_scores[max_idx])

        if max_score >= threshold:
            matched_id = str(valid_candidates[max_idx]["id"])
            logger.info(
                f"Duplicate detected via TF-IDF fallback: score {max_score:.4f} >= {threshold}"
            )
            return matched_id
    except Exception as exc:
        logger.warning(f"TF-IDF duplicate detection error: {exc}")

    return None


def categorize_article(
    title: str,
    content: str,
    categories: list[dict[str, Any]],
) -> dict[str, Any]:
    """Matches article content against category keywords and returns best category.

    Categories is a list of dicts: [{'id': ..., 'name': ..., 'keywords': [...]}]
    """
    if not categories:
        return {"id": None, "name": "General"}

    norm_title = normalize_text(title)
    norm_content = normalize_text(content)
    full_text = f"{norm_title} {norm_content}"

    best_category = None
    best_score = 0

    general_cat = next(
        (c for c in categories if c.get("name", "").lower() == "general"), categories[0]
    )

    for cat in categories:
        name = cat.get("name", "")
        keywords = cat.get("keywords", [])
        if name.lower() == "general":
            continue

        score = 0
        for kw in keywords:
            kw_clean = normalize_text(kw)
            if not kw_clean:
                continue
            # Weight matches in title 3x, matches in body 1x
            title_matches = len(re.findall(r"\b" + re.escape(kw_clean) + r"\b", norm_title))
            content_matches = len(re.findall(r"\b" + re.escape(kw_clean) + r"\b", full_text))
            score += (title_matches * 3) + content_matches

        if score > best_score:
            best_score = score
            best_category = cat

    if best_category and best_score > 0:
        return best_category

    return general_cat
