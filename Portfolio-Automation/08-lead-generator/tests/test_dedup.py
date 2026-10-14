from app.dedup import dedup_leads
from app.normalization import normalize_name
from app.schemas import Lead


def _lead(name: str, **kwargs) -> Lead:
    return Lead(company_name=name, normalized_name=normalize_name(name), **kwargs)


def test_merges_same_phone_near_duplicate_names():
    a = _lead("Contadores Ruiz SAS", phone_e164="+576017890123", city="Bogotá")
    b = _lead("Contadores Ruiz S.A.S.", phone_e164="+576017890123", website="contadoresruiz.com.co")

    kept, log = dedup_leads([a, b])

    assert len(kept) == 1
    assert kept[0].website == "contadoresruiz.com.co"  # filled from the duplicate
    assert kept[0].city == "Bogotá"  # kept from the original
    assert len(log) == 1
    assert log[0].similarity_score >= 85


def test_merges_same_website_domain_near_duplicate_names():
    a = _lead(
        "Restaurante El Buen Sabor", website="elbuensabor.com.co", email="a@elbuensabor.com.co"
    )
    b = _lead(
        "Restaurante El Buen Sabor SAS", website="elbuensabor.com.co", phone_e164="+576012345678"
    )

    kept, _log = dedup_leads([a, b])

    assert len(kept) == 1
    assert kept[0].phone_e164 == "+576012345678"
    assert kept[0].email == "a@elbuensabor.com.co"


def test_does_not_merge_distinct_companies_with_similar_names():
    # High name similarity (same words, one extra token) but neither phone nor website match:
    # two different businesses, must stay separate.
    a = _lead("Restaurante El Buen Sabor", phone_e164="+576012345678")
    b = _lead("Restaurante El Buen Sabor Express", phone_e164="+573009998877")

    kept, log = dedup_leads([a, b])

    assert len(kept) == 2
    assert log == []


def test_does_not_merge_unrelated_companies_even_with_no_identity_fields():
    a = _lead("Panadería San José")
    b = _lead("Panadería San José")  # identical name, but no phone/website on either record

    kept, log = dedup_leads([a, b])

    assert len(kept) == 2
    assert log == []


def test_respects_custom_threshold():
    a = _lead("Café Central", phone_e164="+573001112222")
    b = _lead("Cafe Centrol", phone_e164="+573001112222")  # typo, still a high ratio

    kept_default, _ = dedup_leads([a, b])
    kept_strict, _ = dedup_leads([a, b], threshold=100)

    assert len(kept_default) == 1
    assert len(kept_strict) == 2
