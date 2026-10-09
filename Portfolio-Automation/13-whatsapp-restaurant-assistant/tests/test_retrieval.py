"""Unit tests for app.retrieval (DECISIONES-13 W6/W10): chunking and BM25 retrieval over the
real `knowledge/*.md` files — no mocking, these files are part of the deliverable.
"""

from app.retrieval import chunk_markdown, retrieve
from app.text_utils import strip_accents, tokenize


def test_tokenize_lowercases_strips_accents_and_drops_short_tokens():
    tokens = tokenize("¿Hacen Domicilio a Usaquén? Sí, a 5 min.")
    assert "usaquen" in tokens
    assert "domicilio" in tokens
    # "a", "5" and "si" (2 letters after accent-stripping "sí") are too short to be useful tokens.
    assert "a" not in tokens
    assert "si" not in tokens


def test_strip_accents():
    assert strip_accents("Usaquén") == "Usaquen"
    assert strip_accents("alérgenos") == "alergenos"


def test_chunk_markdown_splits_on_each_heading():
    content = "# Título\nintro\n\n## Sección A\ncontenido A\n\n## Sección B\ncontenido B\n"
    chunks = chunk_markdown(content)
    assert len(chunks) == 3
    assert chunks[0].startswith("# Título")
    assert chunks[1].startswith("## Sección A")
    assert chunks[2].startswith("## Sección B")


def test_chunk_markdown_falls_back_to_paragraphs_without_headings():
    content = "primer párrafo\nsegunda línea\n\nsegundo párrafo"
    chunks = chunk_markdown(content)
    assert chunks == ["primer párrafo\nsegunda línea", "segundo párrafo"]


def test_retrieve_finds_opening_hours():
    results = retrieve("cual es el horario de atencion", k=3)
    assert any(chunk.source == "horarios.md" for chunk in results)


def test_retrieve_finds_suba_delivery_zone():
    results = retrieve("hacen domicilio a Suba cuanto cuesta", k=3)
    assert any(chunk.source == "zonas_domicilio.md" for chunk in results)


def test_retrieve_finds_allergen_info():
    results = retrieve("que alergenos tiene la bandeja paisa", k=3)
    assert any(chunk.source == "menu.md" for chunk in results)


def test_retrieve_respects_k():
    results = retrieve("reserva mesa domicilio menu horario evento", k=2)
    assert len(results) <= 2


def test_retrieve_returns_empty_for_pure_noise():
    assert retrieve("asdkjhasdkjhasd qwepoiqwepoi", k=3) == []
