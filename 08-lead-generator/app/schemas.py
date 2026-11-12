"""Shared data carriers for the scraping/enrichment pipeline (DECISIONES-08 L2/L3).

`RawLead` is what a source adapter returns, as scraped — no normalization applied yet.
`Lead` is the normalized, enriched record (one step away from a `leads` table row,
see ../init-db.sql). `DedupLogEntry` mirrors a `dedup_log` row.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel


class RawLead(BaseModel):
    company_name: str
    category: str | None = None
    phone_raw: str | None = None
    website: str | None = None
    email: str | None = None
    address_raw: str | None = None
    city: str | None = None
    rating: float | None = None
    lat: float | None = None
    lng: float | None = None
    source_url: str | None = None
    source_name: str = "demo-directory"


class Lead(BaseModel):
    company_name: str
    normalized_name: str | None = None
    category: str | None = None
    website: str | None = None
    email: str | None = None
    is_email_valid: bool | None = None
    phone_raw: str | None = None
    phone_e164: str | None = None
    address_raw: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    source_url: str | None = None
    source_name: str = "demo-directory"
    lead_score: int = 0

    @classmethod
    def from_raw(cls, raw: RawLead) -> "Lead":
        return cls(
            company_name=raw.company_name,
            category=raw.category,
            website=raw.website,
            email=raw.email,
            phone_raw=raw.phone_raw,
            address_raw=raw.address_raw,
            city=raw.city,
            lat=raw.lat,
            lng=raw.lng,
            rating=raw.rating,
            source_url=raw.source_url,
            source_name=raw.source_name,
        )


@dataclass
class DedupLogEntry:
    surviving_lead: Lead
    merged_lead_data: dict = field(default_factory=dict)
    similarity_score: float = 0.0


@dataclass
class SourceStat:
    """One row of the "Fuentes" Excel sheet (DECISIONES-08 L5)."""

    source_name: str
    leads_found: int
    duplicates_merged: int
