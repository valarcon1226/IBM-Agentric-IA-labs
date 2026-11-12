"""Lexical retrieval over `knowledge/*.md` with BM25 (DECISIONES-13 W6).

No embeddings service needed: `rank-bm25` scores chunks against the tokenized customer message.
The corpus is chunked once (by Markdown heading, falling back to blank-line paragraphs for text
with no heading) and the index is built once at startup — `_load_corpus` is cached.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.text_utils import tokenize

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


@dataclass(frozen=True)
class Chunk:
    source: str
    text: str


def _split_paragraphs(block: str) -> list[str]:
    return [p.strip() for p in block.split("\n\n") if p.strip()]


def chunk_markdown(content: str) -> list[str]:
    """Split one Markdown file into chunks: one per heading section (title line + its body).

    A file with no heading at all (not the case in `knowledge/` today, but handled for
    robustness) falls back to splitting by blank-line-separated paragraphs.
    """
    lines = content.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if current:
                sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    if len(sections) <= 1 and not any(line.startswith("#") for line in lines):
        return _split_paragraphs(content)

    return [block for section in sections if (block := "\n".join(section).strip())]


@cache
def _load_corpus() -> tuple[list[Chunk], BM25Okapi]:
    chunks: list[Chunk] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        for chunk_text in chunk_markdown(content):
            chunks.append(Chunk(source=path.name, text=chunk_text))
    tokenized = [tokenize(chunk.text) for chunk in chunks]
    return chunks, BM25Okapi(tokenized)


def retrieve(query: str, k: int = 3) -> list[Chunk]:
    """Return the top-`k` knowledge chunks most relevant to `query`, best first.

    Chunks that score 0 (no token overlap at all) are dropped rather than padding the result.
    """
    chunks, bm25 = _load_corpus()
    if not chunks:
        return []
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked[:k] if scores[i] > 0]
