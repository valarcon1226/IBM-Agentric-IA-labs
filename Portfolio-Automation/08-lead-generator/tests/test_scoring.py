from app.schemas import Lead
from app.scoring import score_lead


def test_full_lead_scores_100():
    lead = Lead(
        company_name="Empresa",
        email="info@empresa.com",
        is_email_valid=True,
        phone_e164="+573001234567",
        website="empresa.com",
        address_raw="Calle 1 # 2-3",
        lat=4.65,
        lng=-74.05,
        category="restaurantes",
        rating=4.5,
    )
    assert score_lead(lead) == 100


def test_empty_lead_scores_0():
    assert score_lead(Lead(company_name="Empresa")) == 0


def test_email_present_but_invalid_does_not_score_email_points():
    lead = Lead(company_name="Empresa", email="info@empresa.com", is_email_valid=False)
    assert score_lead(lead) == 0


def test_email_present_but_unvalidated_does_not_score_email_points():
    lead = Lead(company_name="Empresa", email="info@empresa.com", is_email_valid=None)
    assert score_lead(lead) == 0


def test_phone_and_website_only():
    lead = Lead(company_name="Empresa", phone_e164="+573001234567", website="empresa.com")
    assert score_lead(lead) == 40


def test_address_without_geolocation_does_not_score():
    lead = Lead(company_name="Empresa", address_raw="Calle 1 # 2-3")
    assert score_lead(lead) == 0


def test_category_without_rating_does_not_score():
    lead = Lead(company_name="Empresa", category="restaurantes")
    assert score_lead(lead) == 0
