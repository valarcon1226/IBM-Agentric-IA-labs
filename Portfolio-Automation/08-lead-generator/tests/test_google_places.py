import httpx

from app.sources.google_places import GooglePlacesAdapter


def test_google_places_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    adapter = GooglePlacesAdapter()
    leads = adapter.search("dentist", "Bogota")
    assert leads == []


def test_google_places_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "fake_key")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://places.googleapis.com/v1/places:searchText"
        assert request.headers["x-goog-api-key"] == "fake_key"
        assert "application/json" in request.headers["content-type"]
        assert "places.displayName" in request.headers["x-goog-fieldmask"]

        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "displayName": {"text": "Clinica Dental"},
                        "formattedAddress": "Calle 1",
                        "nationalPhoneNumber": "3001234567",
                        "websiteUri": "https://clinica.com",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = GooglePlacesAdapter(client=client)
    leads = adapter.search("dentist", "Bogota")

    assert len(leads) == 1
    assert leads[0].company_name == "Clinica Dental"
    assert leads[0].address_raw == "Calle 1"
    assert leads[0].phone_raw == "3001234567"
    assert leads[0].website == "https://clinica.com"
    assert leads[0].category == "dentist"
    assert leads[0].city == "Bogota"
    assert leads[0].source_name == "google-places"
