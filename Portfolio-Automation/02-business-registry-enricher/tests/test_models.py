import pytest
from pydantic import ValidationError

from app.models import MAX_BATCH_SIZE, CompanyRequest, EnrichBatchRequest


def test_valid_gb_identifier_normalized_uppercase():
    company = CompanyRequest(country="gb", identifier="00000006")
    assert company.country == "GB"
    assert company.identifier == "00000006"


def test_valid_fr_identifier():
    company = CompanyRequest(country="FR", identifier="552081317")
    assert company.country == "FR"
    assert company.identifier == "552081317"


def test_valid_eu_vies_identifier():
    company = CompanyRequest(country="DE", identifier="123456789")
    assert company.country == "DE"
    assert company.identifier == "123456789"


def test_valid_el_for_greece():
    company = CompanyRequest(country="el", identifier="123456789")
    assert company.country == "EL"


def test_invalid_country_code_rejected():
    with pytest.raises(ValidationError):
        CompanyRequest(country="US", identifier="12345678")


def test_invalid_gb_identifier_rejected():
    with pytest.raises(ValidationError):
        CompanyRequest(country="GB", identifier="123")


def test_invalid_fr_identifier_rejected():
    with pytest.raises(ValidationError):
        CompanyRequest(country="FR", identifier="not-digits")


def test_invalid_vies_identifier_rejected():
    with pytest.raises(ValidationError):
        CompanyRequest(country="DE", identifier="a")


def test_batch_over_max_size_rejected():
    companies = [{"country": "FR", "identifier": f"{i:09d}"} for i in range(MAX_BATCH_SIZE + 1)]
    with pytest.raises(ValidationError):
        EnrichBatchRequest(companies=companies)


def test_batch_at_max_size_accepted():
    companies = [{"country": "FR", "identifier": f"{i:09d}"} for i in range(MAX_BATCH_SIZE)]
    batch = EnrichBatchRequest(companies=companies)
    assert len(batch.companies) == MAX_BATCH_SIZE


def test_batch_empty_rejected():
    with pytest.raises(ValidationError):
        EnrichBatchRequest(companies=[])


def test_batch_dedupes_by_country_and_identifier():
    batch = EnrichBatchRequest(
        companies=[
            {"country": "GB", "identifier": "00000006"},
            {"country": "gb", "identifier": "00000006"},
            {"country": "FR", "identifier": "552081317"},
        ]
    )
    assert len(batch.companies) == 2
