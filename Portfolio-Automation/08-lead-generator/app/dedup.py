"""Fuzzy deduplication (DECISIONES-08 L3).

Two leads merge when the normalized name is a >85 `rapidfuzz.fuzz.token_sort_ratio` match AND
they share the same E.164 phone or the same website domain. Name similarity alone never merges
two leads: two distinct businesses with a generic, similar-sounding name (e.g. two unrelated
"Restaurante El Buen Sabor") must stay separate.
"""

from rapidfuzz import fuzz

from app.normalization import website_domain
from app.schemas import DedupLogEntry, Lead


def _same_identity(a: Lead, b: Lead) -> bool:
    if a.phone_e164 and b.phone_e164 and a.phone_e164 == b.phone_e164:
        return True
    domain_a, domain_b = website_domain(a.website), website_domain(b.website)
    return bool(domain_a and domain_b and domain_a == domain_b)


def _merge(keeper: Lead, duplicate: Lead) -> Lead:
    """Fill the keeper's empty fields with the duplicate's values."""
    merged = keeper.model_copy()
    for field_name in type(keeper).model_fields:
        if getattr(merged, field_name) in (None, "") and getattr(duplicate, field_name) not in (
            None,
            "",
        ):
            setattr(merged, field_name, getattr(duplicate, field_name))
    return merged


def dedup_leads(leads: list[Lead], threshold: int = 85) -> tuple[list[Lead], list[DedupLogEntry]]:
    kept: list[Lead] = []
    log: list[DedupLogEntry] = []

    for lead in leads:
        match_index = None
        for index, existing in enumerate(kept):
            name_a = lead.normalized_name or lead.company_name
            name_b = existing.normalized_name or existing.company_name
            similarity = fuzz.token_sort_ratio(name_a, name_b)
            if similarity >= threshold and _same_identity(lead, existing):
                match_index = index
                break

        if match_index is None:
            kept.append(lead)
            continue

        existing = kept[match_index]
        merged = _merge(existing, lead)
        kept[match_index] = merged
        log.append(
            DedupLogEntry(
                surviving_lead=merged,
                merged_lead_data=lead.model_dump(),
                similarity_score=float(
                    fuzz.token_sort_ratio(
                        lead.normalized_name or lead.company_name,
                        existing.normalized_name or existing.company_name,
                    )
                ),
            )
        )

    return kept, log
