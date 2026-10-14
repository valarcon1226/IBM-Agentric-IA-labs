"""Unit tests for exact hash, semantic vector, and TF-IDF deduplication."""

from fake_llm.server import generate_deterministic_embedding
from intelligence.nlp_processor import (
    compute_content_hash,
    detect_duplicate_tfidf,
    normalize_text,
)


def test_normalize_text():
    raw = "  ¡OpenAI Anuncia el Modelo GPT-5! Con 100% Razonamiento... "
    norm = normalize_text(raw)
    assert norm == "openai anuncia el modelo gpt 5 con 100 razonamiento"


def test_exact_hash_deduplication():
    title1 = "OpenAI lanza GPT-5"
    content1 = "Hoy OpenAI presentó oficialmente su nuevo modelo de inteligencia artificial con razonamiento avanzado."

    title2 = "openai lanza gpt 5"
    content2 = "hoy openai presentó oficialmente su nuevo modelo de inteligencia artificial con razonamiento avanzado."

    hash1 = compute_content_hash(title1, content1)
    hash2 = compute_content_hash(title2, content2)

    assert hash1 == hash2
    assert len(hash1) == 64

    # Different story produces different hash
    title3 = "Alerta por ransomware en servidores Linux"
    content3 = "Una vulnerabilidad crítica permite el secuestro remoto de servidores empresariales."
    hash3 = compute_content_hash(title3, content3)
    assert hash1 != hash3


def test_semantic_vector_similarity():
    story_a = "OpenAI presenta su nuevo modelo GPT-5 con razonamiento avanzado y arquitectura profunda en matematicas y codigo"
    story_b = "Llega GPT-5: OpenAI revoluciona la inteligencia artificial con nuevo motor de razonamiento profundo en codigo y matematicas"
    unrelated = "Alerta global por nueva ola de ataques de ransomware dirigidos a servidores Linux y vulnerabilidad critica"

    emb_a = generate_deterministic_embedding(story_a)
    emb_b = generate_deterministic_embedding(story_b)
    emb_unrelated = generate_deterministic_embedding(unrelated)

    # Cosine distance = 1 - dot product (vectors are unit length)
    sim_ab = sum(x * y for x, y in zip(emb_a, emb_b, strict=False))
    dist_ab = 1.0 - sim_ab

    sim_unrelated = sum(x * y for x, y in zip(emb_a, emb_unrelated, strict=False))
    dist_unrelated = 1.0 - sim_unrelated

    # Similar stories should have small distance (< 0.15), unrelated stories should have high distance (> 0.50)
    assert dist_ab < 0.15
    assert dist_unrelated > 0.50


def test_tfidf_fallback_deduplication():
    story_a = {
        "id": "article-parent-1",
        "title": "OpenAI presenta su nuevo modelo GPT-5 con razonamiento avanzado",
        "raw_content": "OpenAI ha anunciado hoy oficialmente el lanzamiento de GPT-5 con arquitectura de razonamiento profundo y matematicas.",
    }
    candidates = [story_a]

    # Near-duplicate with different phrasing
    story_b_text = "Llega GPT-5: OpenAI revoluciona la inteligencia artificial con nuevo motor de razonamiento profundo matematicas."
    matched_id = detect_duplicate_tfidf(story_b_text, candidates, threshold=0.35)
    assert matched_id == "article-parent-1"

    # Unrelated story
    unrelated_text = (
        "Alerta global por nueva ola de ataques de ransomware dirigidos a servidores Linux."
    )
    matched_unrelated = detect_duplicate_tfidf(unrelated_text, candidates, threshold=0.35)
    assert matched_unrelated is None
