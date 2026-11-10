import re
from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

# The 27 EU member state codes used by VIES VAT validation. Greece uses "EL",
# not the ISO "GR". GB is handled separately below (routed to Companies House).
VIES_COUNTRY_CODES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "EL",
        "ES",
        "FI",
        "FR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
    }
)
SUPPORTED_COUNTRY_CODES = VIES_COUNTRY_CODES | {"GB"}

MAX_BATCH_SIZE = 100

_GB_IDENTIFIER_RE = re.compile(r"^[A-Z0-9]{8}$")
_FR_IDENTIFIER_RE = re.compile(r"^\d{9}$")
_VIES_IDENTIFIER_RE = re.compile(r"^[A-Z0-9]{2,12}$")


class CompanyRequest(BaseModel):
    country: str
    identifier: str

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        country = value.upper()
        if country not in SUPPORTED_COUNTRY_CODES:
            raise ValueError(f"Unsupported country code: {value}")
        return country

    @model_validator(mode="after")
    def validate_identifier(self) -> "CompanyRequest":
        identifier = self.identifier.upper()
        if self.country == "GB":
            if not _GB_IDENTIFIER_RE.match(identifier):
                raise ValueError("Invalid GB company number: expected 8 letters/digits")
        elif self.country == "FR":
            if not _FR_IDENTIFIER_RE.match(identifier):
                raise ValueError("Invalid FR SIREN number: expected 9 digits")
        else:
            if not _VIES_IDENTIFIER_RE.match(identifier):
                raise ValueError("Invalid VAT identifier: expected 2-12 letters/digits")
        self.identifier = identifier
        return self


class EnrichBatchRequest(BaseModel):
    companies: list[CompanyRequest]

    @field_validator("companies")
    @classmethod
    def validate_batch_size(cls, value: list[CompanyRequest]) -> list[CompanyRequest]:
        if not value:
            raise ValueError("At least one company is required")
        if len(value) > MAX_BATCH_SIZE:
            raise ValueError(f"Maximum {MAX_BATCH_SIZE} companies per request")
        return value

    @model_validator(mode="after")
    def dedupe_companies(self) -> "EnrichBatchRequest":
        seen: set[tuple[str, str]] = set()
        deduped: list[CompanyRequest] = []
        for company in self.companies:
            key = (company.country, company.identifier)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(company)
        self.companies = deduped
        return self


class CompanyResult(BaseModel):
    country: str
    identifier: str
    company_name: str | None = None
    status: str | None = None
    cached: bool = False
    error: str | None = None


class EnrichBatchResponse(BaseModel):
    results: list[CompanyResult]


class SingleEnrichResponse(BaseModel):
    country: str
    identifier: str
    company_name: str | None = None
    status: str | None = None
    incorporation_date: date | None = None
    raw_data: dict[str, Any] | None = None
    cached: bool = False
