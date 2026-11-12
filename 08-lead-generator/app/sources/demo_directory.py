"""Demo-directory adapter (DECISIONES-08 L2): httpx + BeautifulSoup, politely rate-limited.

Visits each category listing (following pagination), then visits each lead's own site
(home + contacto, both served by demo-directory in the demo) to pick up its email.

One category ("clinicas-dentales") is rendered client-side on purpose, to justify a Playwright
adapter — see demo-directory/clinicas-dentales/index.html. TODO(batch B): add a Playwright-based
fetch for pages whose `.directory[data-js-rendered="true"]` container has no `.lead-card`
children; for now this adapter logs a warning and returns no leads for that listing.
"""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.fetching import PoliteFetcher
from app.schemas import RawLead
from app.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

_KEYWORD_TO_CATEGORY = {
    "restaurante": "restaurantes",
    "restaurantes": "restaurantes",
    "contador": "contadores",
    "contadores": "contadores",
    "contable": "contadores",
    "clinica dental": "clinicas-dentales",
    "clinicas dentales": "clinicas-dentales",
    "odontologia": "clinicas-dentales",
    "dental": "clinicas-dentales",
}
_ALL_CATEGORIES = ("restaurantes", "contadores", "clinicas-dentales")


def _categories_for(keyword: str) -> tuple[str, ...]:
    normalized = keyword.strip().lower()
    if normalized in _ALL_CATEGORIES:  # exact category slug, e.g. "clinicas-dentales"
        return (normalized,)
    category = _KEYWORD_TO_CATEGORY.get(normalized.replace("-", " "))
    return (category,) if category else _ALL_CATEGORIES


class DemoDirectoryAdapter(SourceAdapter):
    name = "demo-directory"

    def __init__(self, base_url: str, fetcher: PoliteFetcher) -> None:
        self.base_url = base_url.rstrip("/")
        self.fetcher = fetcher

    def search(self, keyword: str, location: str) -> list[RawLead]:
        if "bogot" not in location.strip().lower():
            return []  # every demo business is in Bogotá; nothing elsewhere.

        leads: list[RawLead] = []
        for category in _categories_for(keyword):
            leads.extend(self._search_category(category))
        return leads

    def _search_category(self, category: str) -> list[RawLead]:
        leads: list[RawLead] = []
        url: str | None = f"{self.base_url}/{category}/index.html"
        while url:
            response = self.fetcher.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            container = soup.select_one(f'[data-category="{category}"]')
            cards: list[Tag] = list(container.select(".lead-card")) if container else []

            if container is not None and container.get("data-js-rendered") == "true" and not cards:
                from app.sources.playwright_listing import fetch_js_rendered

                logger.info("Listing is JS-rendered; fetching with Playwright: %s", url)
                html = fetch_js_rendered(url, self.fetcher)
                soup = BeautifulSoup(html, "html.parser")
                container = soup.select_one(f'[data-category="{category}"]')
                cards = list(container.select(".lead-card")) if container else []

            for card in cards:
                leads.append(self._parse_card(card, category=category, source_url=url))

            next_link = soup.select_one(".pagination a")
            url = urljoin(url, str(next_link["href"])) if next_link else None

        for lead in leads:
            if lead.website:
                lead.email = self._find_email(lead.website)
        return leads

    def _parse_card(self, card: Tag, *, category: str, source_url: str) -> RawLead:
        def text_of(selector: str) -> str | None:
            node = card.select_one(selector)
            return node.get_text(strip=True) if node else None

        website_node = card.select_one(".website a")
        website = urljoin(source_url, str(website_node["href"])) if website_node else None

        return RawLead(
            company_name=text_of(".name") or "",
            category=category,
            phone_raw=text_of(".phone"),
            address_raw=text_of(".address"),
            city="Bogotá",
            website=website,
            source_url=source_url,
            source_name=self.name,
        )

    def _find_email(self, website_url: str) -> str | None:
        home = self.fetcher.get(website_url)
        soup = BeautifulSoup(home.text, "html.parser")
        contact_link = soup.select_one('nav a[href*="contacto"]')
        if contact_link is None:
            return None

        contacto_url = urljoin(website_url, str(contact_link["href"]))
        contacto = self.fetcher.get(contacto_url)
        contacto_soup = BeautifulSoup(contacto.text, "html.parser")
        email_node = contacto_soup.select_one(".email a")
        return email_node.get_text(strip=True) if email_node else None
