#!/usr/bin/env python
"""Renders ../demo-directory/ from ../tests/fixtures/demo_data.py (DECISIONES-08 L2).

Re-run after editing demo_data.py to keep the static fixtures and the adapter tests in sync:

    .venv\\Scripts\\python.exe scripts\\generate_demo_directory.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.fixtures.demo_data import BUSINESSES, CATEGORY_LABELS, Business  # noqa: E402

OUT = ROOT / "demo-directory"

PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""


def _card(biz: Business) -> str:
    website_html = ""
    if biz.site:
        website_html = (
            f'\n  <p class="website"><a href="/sitios/{biz.site}/index.html">Sitio web</a></p>'
        )
    return (
        '<article class="lead-card">\n'
        f'  <h3 class="name">{biz.name}</h3>\n'
        f'  <p class="category">{CATEGORY_LABELS[biz.category]}</p>\n'
        f'  <p class="phone">{biz.phone}</p>\n'
        f'  <p class="address">{biz.address}</p>'
        f"{website_html}\n"
        "</article>"
    )


def _listing_page(category: str, businesses: list[Business], *, next_href: str | None) -> str:
    cards = "\n".join(_card(b) for b in businesses)
    nav = (
        f'\n<nav class="pagination"><a href="{next_href}">Siguiente -&gt;</a></nav>'
        if next_href
        else ""
    )
    body = f'<div class="directory" data-category="{category}">\n{cards}\n</div>{nav}'
    return PAGE_TEMPLATE.format(title=f"Directorio — {CATEGORY_LABELS[category]}", body=body)


def _js_rendered_page(category: str, businesses: list[Business]) -> str:
    # The listing is injected by this script at runtime, same as a real SPA directory would do —
    # a plain httpx+BeautifulSoup fetch sees an empty container. Batch B adds a Playwright path
    # for exactly this page (DECISIONES-08 L2/L6: "una vista se pinta con JavaScript").
    import json

    payload = json.dumps(
        [
            {"name": b.name, "phone": b.phone, "address": b.address, "site": b.site}
            for b in businesses
        ]
    )
    script = f"""<script>
// TODO(batch B): rendered client-side on purpose; the httpx adapter cannot see these cards,
// a Playwright adapter is required for this listing.
var LEADS = {payload};
var container = document.querySelector('[data-category="{category}"]');
LEADS.forEach(function (lead) {{
  var card = document.createElement('article');
  card.className = 'lead-card';
  card.innerHTML = '<h3 class="name">' + lead.name + '</h3>' +
    '<p class="phone">' + lead.phone + '</p>' +
    '<p class="address">' + lead.address + '</p>';
  container.appendChild(card);
}});
</script>"""
    body = (
        f'<div class="directory" data-category="{category}" data-js-rendered="true"></div>\n'
        f"{script}\n"
        "<noscript>Esta vista requiere JavaScript (ver docs/DEMO-SCRIPT.md).</noscript>"
    )
    return PAGE_TEMPLATE.format(title=f"Directorio — {CATEGORY_LABELS[category]}", body=body)


def _site_pages(biz: Business) -> None:
    assert biz.site
    site_dir = OUT / "sitios" / biz.site
    site_dir.mkdir(parents=True, exist_ok=True)

    home_body = (
        f"<h1>{biz.name}</h1>"
        f'<p class="address">{biz.address}</p>'
        '<nav><a href="contacto.html">Contacto</a></nav>'
    )
    (site_dir / "index.html").write_text(
        PAGE_TEMPLATE.format(title=biz.name, body=home_body), encoding="utf-8"
    )

    email_html = (
        f'<p class="email"><a href="mailto:{biz.site_email}">{biz.site_email}</a></p>'
        if biz.site_email
        else "<p>Escríbenos por este formulario de contacto.</p>"
    )
    contacto_body = f'<h1>Contacto — {biz.name}</h1><p class="phone">{biz.phone}</p>{email_html}'
    (site_dir / "contacto.html").write_text(
        PAGE_TEMPLATE.format(title=f"Contacto — {biz.name}", body=contacto_body), encoding="utf-8"
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)

    by_category: dict[str, list[Business]] = {}
    for biz in BUSINESSES:
        by_category.setdefault(biz.category, []).append(biz)

    home_links = "\n".join(
        f'<li><a href="/{cat}/index.html">{label}</a></li>'
        for cat, label in CATEGORY_LABELS.items()
    )
    (OUT / "index.html").write_text(
        PAGE_TEMPLATE.format(title="Directorio de Negocios Bogotá", body=f"<ul>{home_links}</ul>"),
        encoding="utf-8",
    )
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    for category, businesses in by_category.items():
        cat_dir = OUT / category
        cat_dir.mkdir(exist_ok=True)

        if category == "clinicas-dentales":
            (cat_dir / "index.html").write_text(
                _js_rendered_page(category, businesses), encoding="utf-8"
            )
        else:
            page1 = [b for b in businesses if b.page == 1]
            page2 = [b for b in businesses if b.page == 2]
            (cat_dir / "index.html").write_text(
                _listing_page(category, page1, next_href="page-2.html"), encoding="utf-8"
            )
            (cat_dir / "page-2.html").write_text(
                _listing_page(category, page2, next_href=None), encoding="utf-8"
            )

        for biz in businesses:
            if biz.site:
                _site_pages(biz)

    print(f"Generated demo-directory for {len(BUSINESSES)} businesses.")


if __name__ == "__main__":
    main()
