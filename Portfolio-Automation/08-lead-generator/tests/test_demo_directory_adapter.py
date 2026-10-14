"""Adapter tests against the real saved HTML in ../demo-directory/ (DECISIONES-08 L6), served
through httpx.MockTransport so nothing ever touches the network.
"""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.fetching import PoliteFetcher
from app.sources.demo_directory import DemoDirectoryAdapter
from tests.fixtures.demo_data import BUSINESSES

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo-directory"
BASE_URL = "https://demo.test"


def _serve_from_disk(request: httpx.Request) -> httpx.Response:
    path = DEMO_DIR / request.url.path.lstrip("/")
    if not path.is_file():
        return httpx.Response(404)
    return httpx.Response(200, text=path.read_text(encoding="utf-8"))


@pytest.fixture
def adapter() -> DemoDirectoryAdapter:
    client = httpx.Client(transport=httpx.MockTransport(_serve_from_disk))
    fetcher = PoliteFetcher(client, min_interval=0, backoff_base=0.001)
    return DemoDirectoryAdapter(BASE_URL, fetcher)


def test_location_outside_bogota_returns_no_leads(adapter: DemoDirectoryAdapter):
    assert adapter.search("restaurantes", "Medellín") == []


def test_restaurantes_follows_pagination_and_parses_both_pages(adapter: DemoDirectoryAdapter):
    leads = adapter.search("restaurantes", "Bogotá")
    expected = [b for b in BUSINESSES if b.category == "restaurantes"]
    assert len(leads) == len(expected)
    assert {lead.company_name for lead in leads} == {b.name for b in expected}


def test_contadores_pagination(adapter: DemoDirectoryAdapter):
    leads = adapter.search("contadores", "Bogotá")
    expected = [b for b in BUSINESSES if b.category == "contadores"]
    assert len(leads) == len(expected)


@patch("app.sources.playwright_listing.fetch_js_rendered")
def test_js_rendered_listing_yields_leads_with_playwright(
    mock_fetch, adapter: DemoDirectoryAdapter
):
    mock_fetch.return_value = """
    <div data-category="clinicas-dentales">
        <div class="lead-card">
            <h3 class="name">Clinica Especial</h3>
            <p class="phone">1234</p>
        </div>
    </div>
    """
    leads = adapter.search("clinicas-dentales", "Bogotá")
    assert len(leads) == 1
    assert leads[0].company_name == "Clinica Especial"


def test_visits_the_business_site_to_find_its_email(adapter: DemoDirectoryAdapter):
    leads = adapter.search("restaurantes", "Bogotá")
    by_name = {lead.company_name: lead for lead in leads}

    with_site = by_name["Restaurante El Buen Sabor"]
    assert with_site.website is not None
    assert with_site.email == "contacto@elbuensabor.com.co"


def test_business_without_a_website_has_no_email(adapter: DemoDirectoryAdapter):
    leads = adapter.search("restaurantes", "Bogotá")
    by_name = {lead.company_name: lead for lead in leads}

    without_site = by_name["Asadero La Brasa Dorada"]
    assert without_site.website is None
    assert without_site.email is None


def test_business_with_a_website_but_no_email_on_the_contact_page(adapter: DemoDirectoryAdapter):
    leads = adapter.search("restaurantes", "Bogotá")
    by_name = {lead.company_name: lead for lead in leads}

    site_no_email = by_name["Restaurante La Fonda Antioqueña"]
    assert site_no_email.website is not None
    assert site_no_email.email is None


@patch("app.sources.playwright_listing.fetch_js_rendered")
def test_searching_all_categories_when_keyword_does_not_map_to_one(
    mock_fetch, adapter: DemoDirectoryAdapter
):
    mock_fetch.return_value = (
        '<div data-category="clinicas-dentales">'
        '<div class="lead-card"><h3 class="name">Fake</h3></div></div>'
    )
    leads = adapter.search("negocios", "Bogotá")

    # It should find the standard ones + 1 from our mock
    expected = len([b for b in BUSINESSES if b.category != "clinicas-dentales"]) + 1
    assert len(leads) == expected
