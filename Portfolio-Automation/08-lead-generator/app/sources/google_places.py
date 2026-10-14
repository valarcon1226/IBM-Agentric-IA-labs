"""Google Places adapter (DECISIONES-08 L4): Text Search API."""

import os

import httpx

from app.schemas import RawLead
from app.sources.base import SourceAdapter


class GooglePlacesAdapter(SourceAdapter):
    name = "google-places"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        self.client = client or httpx.Client()

    def search(self, keyword: str, location: str) -> list[RawLead]:
        if not self.api_key:
            return []

        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,"
                "places.nationalPhoneNumber,places.websiteUri"
            ),
        }
        payload = {"textQuery": f"{keyword} in {location}"}

        response = self.client.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        leads: list[RawLead] = []

        for place in data.get("places", []):
            leads.append(
                RawLead(
                    company_name=place.get("displayName", {}).get("text", ""),
                    category=keyword,
                    phone_raw=place.get("nationalPhoneNumber"),
                    address_raw=place.get("formattedAddress"),
                    city=location,
                    website=place.get("websiteUri"),
                    source_url=None,
                    source_name=self.name,
                )
            )

        return leads
