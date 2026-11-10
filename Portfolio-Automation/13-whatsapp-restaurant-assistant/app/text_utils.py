"""Small Spanish-aware text helpers shared by `app.retrieval` (BM25 tokenization) and
`app.tools` (zone-name normalization) — DECISIONES-13 W6.
"""

import re
import unicodedata

_MIN_TOKEN_LENGTH = 3
_WORD_RE = re.compile(r"[a-z0-9]+")


def strip_accents(value: str) -> str:
    """Remove diacritics, e.g. "Usaquén" -> "Usaquen"."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_key(value: str) -> str:
    """Lowercase + accent-stripped key, used to match free-form zone names to known zones."""
    return strip_accents(value).strip().lower()


def tokenize(text: str) -> list[str]:
    """Lowercase, strip accents, keep only word characters, drop very short tokens."""
    normalized = strip_accents(text.lower())
    return [token for token in _WORD_RE.findall(normalized) if len(token) >= _MIN_TOKEN_LENGTH]
