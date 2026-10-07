import datetime
import html
import json
import re
import urllib.parse
import urllib.request
from typing import List, Dict

from bs4 import BeautifulSoup

# ==========================================
# FUENTES DE DATOS FREELANCE (compartido entre freelance_hunter_agent.py y trend_spotter_agent.py)
# ==========================================
# NOTA (2026-09-24): se reemplazaron los feeds RSS. Upwork retiró el suyo (HTTP 410) y el RSS de
# Freelancer ignoraba el keyword (traía marketing/cripto/telemarketing). Fuentes actuales, las dos
# públicas y sin login, verificadas desde el homelab:
#   - API de Freelancer.com: trae presupuesto, moneda (con tipo de cambio a USD), tipo
#     fixed/hourly y cantidad de propuestas -> se puede filtrar sin gastar LLM.
#   - Bounties de GitHub (label de Algora "💎 Bounty"): issues open source pagados. Un PR
#     mergeado es plata + portafolio público verificable.
#   - Workana (2026-09-29): página pública /jobs con user-agent de navegador (ver fetch_workana).
# Reddit r/forhire devuelve 403 a clientes que no son navegador — no implementado.

# IDs de skills de Freelancer.com (GET /api/projects/0.1/jobs/?job_names[]=...). Filtrar por skill
# etiquetada es mucho más preciso que ?query=, que con "python automation" devolvía fotografía.
FREELANCER_SKILL_IDS = {
    13: "Python", 95: "Web Scraping", 3028: "AI Agents", 913: "Artificial Intelligence",
    2068: "Chatbot", 2878: "LangChain", 2966: "LLMs", 2719: "OpenAI", 3112: "n8n",
    2050: "Zapier", 1977: "Automation", 1679: "Selenium", 167: "Software Testing",
    1087: "API", 2688: "FastAPI",  # sin "Data Processing": trae casi solo data entry
    # páginas web (2026-10-02): sitios, landings y tiendas pequeñas
    17: "Website Design", 2839: "Website Development", 1031: "Web Development", 69: "WordPress",
    759: "React.js", 2376: "Next.js", 1595: "Webflow", 482: "Landing Pages", 2037: "Elementor",
    1088: "Full Stack Development", 1093: "Frontend Development", 502: "Shopify",
    # QA (2026-10-02): su experiencia principal, también como freelance
    208: "Test Automation", 67: "Testing / QA", 2576: "API Testing", 1112: "Selenium Webdriver",
    2577: "JMeter", 716: "Mobile App Testing", 219: "Website Testing",
}
FREELANCER_PAGES = 10  # x50 = los 500 proyectos más recientes con esas skills

# Side hustles del video de Patrick Dang (ver YouTube-RAG-Analyzer/Results): solo para el Trend Spotter, que mide
# cuánta demanda real tienen. El agente de Freelance NO los usa (no son proyectos técnicos para postular).
HUSTLE_SKILL_IDS = {
    2360: "Facebook Ads", 74: "Facebook Marketing", 1065: "Instagram Marketing", 156: "Ghostwriting",
    21: "Copywriting", 152: "YouTube", 688: "Video Editing", 676: "Video Production", 38: "SEO",
    1595: "Webflow", 569: "Email Marketing", 2666: "Klaviyo", 1683: "Lead Generation",
    1694: "Appointment Setting", 1639: "ClickFunnels", 3183: "GoHighLevel", 482: "Landing Pages",
}
HUSTLE_PAGES = 3
HUSTLE_WORKANA_CATEGORIES = ["design-multimedia", "sales-marketing", "writing-translation"]

BOUNTY_LANGUAGES = ["python", "typescript", "javascript"]

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) jobhunter/1.0"}


def _get_json(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def _iso(ts) -> str:
    """Unix -> 'YYYY-MM-DD HH:MM:SS' en UTC (el mismo formato que created_at de SQLite)."""
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else None


def _relative_posted(text: str):
    """'Ayer', 'Hace 2 días', 'Hace casi una hora', '3 hours ago' -> fecha aproximada (Workana no da fecha exacta)."""
    t = (text or "").lower()
    now = datetime.datetime.now(datetime.timezone.utc)
    if not t:
        return None
    if "ayer" in t or "yesterday" in t:
        delta = datetime.timedelta(days=1)
    else:
        n = re.search(r"\d+", t)
        n = int(n.group()) if n else 1  # "una hora", "an hour", "casi una hora"
        unit = next((u for u, keys in (("minutes", ("minut",)), ("hours", ("hora", "hour")), ("days", ("día", "dia", "day")),
                                       ("weeks", ("semana", "week")), ("days30", ("mes", "month"))) if any(k in t for k in keys)), None)
        if unit is None:
            return None
        delta = datetime.timedelta(days=30 * n) if unit == "days30" else datetime.timedelta(**{unit: n})
    return (now - delta).strftime("%Y-%m-%d %H:%M:%S")


def freelancer_dates(urls) -> dict:
    """url -> (posted_at, closes_at, abierto?) consultando la API pública de Freelancer por seo_url (para gigs ya guardados)."""
    out = {}
    seos = {u.split("freelancer.com/projects/", 1)[1]: u for u in urls if "freelancer.com/projects/" in u}
    items = list(seos.items())
    for i in range(0, len(items), 50):
        query = urllib.parse.urlencode([("seo_urls[]", s) for s, _ in items[i:i + 50]])
        try:
            projects = _get_json("https://www.freelancer.com/api/projects/0.1/projects/?" + query)["result"]["projects"]
        except Exception as e:
            print(f"  [-] Error consultando fechas en Freelancer: {e}")
            continue
        for p in projects:
            url = seos.get(p.get("seo_url"))
            if url:
                sub = p.get("time_submitted") or p.get("submitdate")
                out[url] = (_iso(sub), _iso(sub + 86400 * (p.get("bidperiod") or 0)) if sub else None,
                            p.get("frontend_project_status") == "open")
    return out


def _clean(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(separator=" ", strip=True)


def fetch_freelancer_api(skill_ids=FREELANCER_SKILL_IDS, pages=FREELANCER_PAGES) -> List[Dict]:
    print("[+] Buscando en Freelancer.com (API pública, filtrado por skills)...")
    gigs = []
    base = [("limit", 50), ("full_description", "true"), ("job_details", "true"),
            ("sort_field", "time_updated")] + [("jobs[]", i) for i in skill_ids]
    for page in range(pages):
        url = ("https://www.freelancer.com/api/projects/0.1/projects/active/?"
               + urllib.parse.urlencode(base + [("offset", page * 50)]))
        try:
            projects = _get_json(url)["result"]["projects"]
        except Exception as e:
            print(f"  [-] Error en Freelancer (página {page + 1}): {e}")
            continue
        if not projects:
            break
        for p in projects:
            budget = p.get("budget") or {}
            rate = (p.get("currency") or {}).get("exchange_rate") or 1.0
            gigs.append({
                "platform": "Freelancer",
                "title": p.get("title", ""),
                "description": _clean(p.get("description") or p.get("preview_description", ""))[:1500],
                "url": f"https://www.freelancer.com/projects/{p.get('seo_url', p.get('id'))}",
                "project_type": p.get("type", ""),  # "fixed" | "hourly"
                # se pueden ofertar bidperiod días desde que se publicó: esa es la fecha de cierre
                "posted_at": _iso(p.get("time_submitted")),
                "closes_at": _iso((p.get("time_submitted") or 0) + 86400 * (p.get("bidperiod") or 0)) if p.get("time_submitted") else None,
                "budget_min_usd": round((budget.get("minimum") or 0) * rate),
                "budget_max_usd": round((budget.get("maximum") or budget.get("minimum") or 0) * rate),
                "competition": (p.get("bid_stats") or {}).get("bid_count") or 0,
                "skills": [j.get("name", "") for j in (p.get("jobs") or [])],
                "language": p.get("language", ""),
            })
    return gigs


def _bounty_amount_usd(issue: dict) -> int:
    """Algora pone el monto en un label ("$250") o en el título ("[$250]")."""
    texts = [l.get("name", "") for l in issue.get("labels", [])] + [issue.get("title", "")]
    for t in texts:
        m = re.search(r"\$\s?([\d,]+)", t)
        if m:
            return int(m.group(1).replace(",", ""))
    return 0


def fetch_github_bounties() -> List[Dict]:
    print("[+] Buscando bounties open source en GitHub (Algora)...")
    gigs = []
    for lang in BOUNTY_LANGUAGES:
        q = f'label:"💎 Bounty" state:open no:assignee language:{lang}'
        url = ("https://api.github.com/search/issues?"
               + urllib.parse.urlencode({"q": q, "per_page": 30, "sort": "created", "order": "desc"}))
        try:
            items = _get_json(url).get("items", [])
        except Exception as e:
            print(f"  [-] Error en GitHub bounties ({lang}): {e}")
            continue
        for it in items:
            amount = _bounty_amount_usd(it)
            repo = it.get("repository_url", "").split("/repos/")[-1]
            gigs.append({
                "platform": "GitHub Bounty",
                "title": f"[{repo}] {it.get('title', '')}",
                "description": (it.get("body") or "")[:1500],
                "url": it.get("html_url", ""),
                "project_type": "bounty",
                "posted_at": (it.get("created_at") or "").replace("T", " ").replace("Z", "") or None,
                "closes_at": None,  # abierto hasta que alguien lo resuelva
                "budget_min_usd": amount,
                "budget_max_usd": amount,
                "competition": it.get("comments", 0),  # proxy: cuánta gente ya está encima
                "skills": [lang],
                "language": "en",
            })
    return gigs


WORKANA_LANGS = ["es", "en"]
WORKANA_PAGES = 8  # la página trae ~9 en el HTML inicial -> ~70 por idioma, los más recientes de IT & Programación
# Workana da 403 a user-agents que no son navegador; con uno de navegador la página pública /jobs
# (permitida en su robots.txt) trae los proyectos como JSON en el atributo results-initials.
_BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
               "Accept-Language": "es"}


def _usd_range(text: str) -> tuple:
    """'USD 1.000 - 3.000' -> (1000, 3000) · 'Menos de USD 50' -> (0, 50) · 'Más de USD 3.000' -> (3000, 3000)."""
    nums = [int(n.replace(".", "").replace(",", "")) for n in re.findall(r"\d[\d.,]*", text or "")]
    if not nums:
        return 0, 0
    if re.search(r"menos|less", text, re.I):
        return 0, nums[0]
    return nums[0], nums[-1]


def fetch_workana(categories=("it-programming",), pages=WORKANA_PAGES) -> List[Dict]:
    print(f"[+] Buscando en Workana ({', '.join(categories)})...")
    gigs = []
    for category in categories:
        for lang in WORKANA_LANGS:
            for page in range(1, pages + 1):
                url = f"https://www.workana.com/jobs?category={category}&language={lang}&page={page}"
                try:
                    req = urllib.request.Request(url, headers=_BROWSER_UA)
                    with urllib.request.urlopen(req, timeout=20) as response:
                        html_text = response.read().decode("utf-8", "replace")
                    m = re.search(r"results-initials=(['\"])(.*?)\1", html_text, re.S)
                    results = json.loads(html.unescape(m.group(2)))["results"] if m else []
                except Exception as e:
                    print(f"  [-] Error en Workana ({lang}, página {page}): {e}")
                    continue
                for p in results:
                    lo, hi = _usd_range(_clean(p.get("budget", "")))
                    bids = re.search(r"\d+", _clean(p.get("totalBids", "")))
                    gigs.append({
                        "platform": "Workana",
                        "title": _clean(p.get("title", "")),
                        "description": _clean(p.get("description", ""))[:1500],
                        "url": f"https://www.workana.com/job/{p['slug']}" if p.get("slug") else "",
                        "project_type": "hourly" if p.get("isHourly") else "fixed",
                    "posted_at": _relative_posted(_clean(p.get("postedDate", ""))),
                    "closes_at": None,  # Workana no publica fecha de cierre
                        "budget_min_usd": lo,
                        "budget_max_usd": hi,
                        "competition": int(bids.group()) if bids else 0,
                        "skills": [s.get("anchorText", "") for s in (p.get("skills") or [])],
                        "language": lang,
                    })
    return gigs


def fetch_hustle_gigs() -> List[Dict]:
    """Gigs de marketing, video, SEO, redacción... (side hustles) para medir su demanda. Dedup por URL."""
    raw = fetch_freelancer_api(HUSTLE_SKILL_IDS, HUSTLE_PAGES) + fetch_workana(HUSTLE_WORKANA_CATEGORIES, HUSTLE_PAGES)
    return list({g["url"]: g for g in raw if g["url"]}.values())


def fetch_all_gigs() -> List[Dict]:
    """Fetch + dedup por URL en una sola llamada. Usado por ambos agentes."""
    raw = fetch_freelancer_api() + fetch_workana() + fetch_github_bounties()
    unique = list({g["url"]: g for g in raw if g["url"]}.values())
    print(f"[i] {len(raw)} resultados brutos -> {len(unique)} gigs únicos tras deduplicar.")
    return unique


if __name__ == "__main__":
    gigs = fetch_all_gigs()
    for g in gigs[:10]:
        print(f"- [{g['platform']}] {g['title']} | ${g['budget_min_usd']}-{g['budget_max_usd']} | {g['competition']} bids")
