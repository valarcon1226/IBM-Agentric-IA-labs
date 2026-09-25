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
# Reddit r/forhire y Workana devuelven 403 a clientes que no son navegador — no implementados.

# IDs de skills de Freelancer.com (GET /api/projects/0.1/jobs/?job_names[]=...). Filtrar por skill
# etiquetada es mucho más preciso que ?query=, que con "python automation" devolvía fotografía.
FREELANCER_SKILL_IDS = {
    13: "Python", 95: "Web Scraping", 3028: "AI Agents", 913: "Artificial Intelligence",
    2068: "Chatbot", 2878: "LangChain", 2966: "LLMs", 2719: "OpenAI", 3112: "n8n",
    2050: "Zapier", 1977: "Automation", 1679: "Selenium", 167: "Software Testing",
    1087: "API", 2688: "FastAPI",  # sin "Data Processing": trae casi solo data entry
}
FREELANCER_PAGES = 6  # x50 = los 300 proyectos más recientes con esas skills

BOUNTY_LANGUAGES = ["python", "typescript", "javascript"]

_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) jobhunter/1.0"}


def _get_json(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def _clean(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(separator=" ", strip=True)


def fetch_freelancer_api() -> List[Dict]:
    print("[+] Buscando en Freelancer.com (API pública, filtrado por skills)...")
    gigs = []
    base = [("limit", 50), ("full_description", "true"), ("job_details", "true"),
            ("sort_field", "time_updated")] + [("jobs[]", i) for i in FREELANCER_SKILL_IDS]
    for page in range(FREELANCER_PAGES):
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
                "budget_min_usd": amount,
                "budget_max_usd": amount,
                "competition": it.get("comments", 0),  # proxy: cuánta gente ya está encima
                "skills": [lang],
                "language": "en",
            })
    return gigs


def fetch_all_gigs() -> List[Dict]:
    """Fetch + dedup por URL en una sola llamada. Usado por ambos agentes."""
    raw = fetch_freelancer_api() + fetch_github_bounties()
    unique = list({g["url"]: g for g in raw if g["url"]}.values())
    print(f"[i] {len(raw)} resultados brutos -> {len(unique)} gigs únicos tras deduplicar.")
    return unique


if __name__ == "__main__":
    gigs = fetch_all_gigs()
    for g in gigs[:10]:
        print(f"- [{g['platform']}] {g['title']} | ${g['budget_min_usd']}-{g['budget_max_usd']} | {g['competition']} bids")
