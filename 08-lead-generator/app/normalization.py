"""Field normalization (DECISIONES-08 L3)."""

import re
import unicodedata

import phonenumbers

# Longest/most specific pattern first: alternation picks the first match, and "s.a.s." must win
# over "s.a." for a name ending in "... S.A.S.".
_SUFFIX_RE = re.compile(r"\s+(s\.?a\.?s\.?|ltda\.?)$")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and a trailing legal-entity suffix (sas/s.a.s./ltda/...)."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"\s+", " ", without_accents).strip().lower()
    cleaned = cleaned.rstrip(".")
    cleaned = _SUFFIX_RE.sub("", cleaned)
    return cleaned.strip()


def normalize_phone(raw: str | None, region: str = "CO") -> str | None:
    """Parse a Colombian (by default) phone number to E.164, or None if unparseable/invalid."""
    if not raw:
        return None

    cleaned = re.sub(r"[^\d+]", "", raw)
    if re.match(r"^(?:\+57)?1\d{7}$", cleaned):
        raw = "+57601" + cleaned[-7:]

    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def normalize_website(url: str | None) -> str | None:
    """Strip scheme, leading `www.` and a trailing slash so the same site always compares equal."""
    if not url:
        return None
    cleaned = url.strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = re.sub(r"^www\.", "", cleaned)
    cleaned = cleaned.rstrip("/")
    return cleaned or None


def website_domain(url: str | None) -> str | None:
    """The bare domain of a normalized website, used for dedup matching."""
    normalized = normalize_website(url)
    if not normalized:
        return None
    return normalized.split("/", 1)[0]
