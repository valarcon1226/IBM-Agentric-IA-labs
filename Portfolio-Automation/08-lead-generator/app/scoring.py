"""Lead scoring 0-100 (README section 3.2, kept as-is by DECISIONES-08 L3)."""

from app.schemas import Lead

EMAIL_POINTS = 30
PHONE_POINTS = 20
WEBSITE_POINTS = 20
ADDRESS_GEO_POINTS = 15
CATEGORY_RATING_POINTS = 15


def score_lead(lead: Lead) -> int:
    total = 0
    if lead.email and lead.is_email_valid:
        total += EMAIL_POINTS
    if lead.phone_e164:
        total += PHONE_POINTS
    if lead.website:
        total += WEBSITE_POINTS
    if lead.address_raw and lead.lat is not None and lead.lng is not None:
        total += ADDRESS_GEO_POINTS
    if lead.category and lead.rating is not None:
        total += CATEGORY_RATING_POINTS
    return total
