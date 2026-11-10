"""Agente Aplicador: resolución de URL de postulación externa y ATS (Fase B de APPLICATOR_PLAN.md).

Determina dónde y cómo se postula a una vacante:
- Sigue enlaces de postulación externa fuera de LinkedIn/Indeed hacia el ATS de la empresa.
- Clasifica el ATS por dominio (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, BambooHR, Teamtailor, o genérico).
- Marca Easy Apply o vacantes sin enlace externo como apply_mode='manual'.
"""
import argparse
import json
import logging
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scrapling.parser import Selector
from edge_fetchers import DynamicFetcher, Fetcher
import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("apply_resolver")

# Mapeo oficial de dominios de ATS (Fase B de APPLICATOR_PLAN.md)
ATS_DOMAINS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "ashbyhq.com": "ashby",
    "workable.com": "workable",
    "smartrecruiters.com": "smartrecruiters",
    "myworkdayjobs.com": "workday",
    "bamboohr.com": "bamboohr",
    "teamtailor.com": "teamtailor",
}

# Control de ritmo: máx. 1 request cada 3 s a LinkedIn
_last_linkedin_request_time = 0.0
_last_search_time = 0.0


def _throttle_linkedin(url: str):
    """Respeta la regla: máx. 1 request cada 3 s a LinkedIn."""
    global _last_linkedin_request_time
    if "linkedin.com" in url.lower():
        now = time.time()
        elapsed = now - _last_linkedin_request_time
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)
        _last_linkedin_request_time = time.time()


def classify_ats(url: Optional[str]) -> Optional[str]:
    """Clasifica el ATS según el dominio del enlace de postulación.
    
    Retorna uno de: greenhouse, lever, ashby, workable, smartrecruiters, workday,
    bamboohr, teamtailor, o 'generico' si es otro dominio. Si no hay URL, retorna None.
    """
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return None
        for domain, name in ATS_DOMAINS.items():
            if hostname == domain or hostname.endswith("." + domain):
                return name
        return "generico"
    except Exception:
        return "generico"


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def lookup_ats_boards(company: str, title: str) -> Tuple[Optional[str], Optional[str]]:
    """Busca la vacante en el tablero público de la empresa (Greenhouse, Lever, Ashby) por empresa y título.
    LinkedIn sin sesión no muestra el link externo de "Apply", así que casi todas quedaban en manual.
    Devuelve (url_del_formulario, ats) o (None, None)."""
    import difflib
    import urllib.request
    base = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|gmbh|s\.?a\.?|technologies|labs?)\b\.?", "", (company or "").lower())
    words = re.findall(r"[a-z0-9]+", base)
    if not words or not title:
        return None, None
    slugs = list(dict.fromkeys(["".join(words), "-".join(words), words[0]]))
    boards = [
        ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{}/jobs",
         lambda d, s: [(j["title"], f"https://job-boards.greenhouse.io/{s}/jobs/{j['id']}") for j in d.get("jobs", [])]),
        ("lever", "https://api.lever.co/v0/postings/{}?mode=json",
         lambda d, s: [(j["text"], j["hostedUrl"]) for j in d] if isinstance(d, list) else []),
        ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{}",
         lambda d, s: [(j["title"], j["jobUrl"]) for j in d.get("jobs", [])]),
    ]
    want = _norm_title(title)
    for slug in slugs:
        for ats, api, parse in boards:
            try:
                with urllib.request.urlopen(api.format(urllib.parse.quote(slug)), timeout=8) as r:
                    postings = parse(json.load(r), slug)
            except Exception:  # 404 = la empresa no usa ese ATS con ese nombre
                continue
            best = max(postings, key=lambda p: difflib.SequenceMatcher(None, want, _norm_title(p[0])).ratio(), default=None)
            if best and difflib.SequenceMatcher(None, want, _norm_title(best[0])).ratio() >= 0.85:
                return best[1], ats
    return None, None


# Portales que muestran la vacante pero piden sesión o no dejan postular: la vacante se busca en la web de la empresa.
AGGREGATORS = ("jobright.ai", "welcometothejungle.com", "otta.com", "linkedin.com", "indeed.com", "glassdoor.com",
               "ziprecruiter.com", "simplyhired.com", "builtin.com", "wellfound.com", "jooble.org", "talent.com",
               "monster.com", "dice.com", "getonbrd.com", "computrabajo.com", "remoterocketship.com", "himalayas.app")


def _is_aggregator(url: str) -> bool:
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in AGGREGATORS)


def pick_search_result(html: str, company: str, title: str) -> Tuple[Optional[str], Optional[str]]:
    """De una página de resultados de DuckDuckGo Lite elige el link de la vacante en el ATS o la web de la empresa.
    Nunca otro portal. Devuelve (url, ats) o (None, None)."""
    company_words = [w for w in re.findall(r"[a-z0-9]+", (company or "").lower()) if len(w) > 2]
    title_words = set(_norm_title(title).split())
    fallback = None
    for a in Selector(html).css("a.result-link"):
        url = unwrap_redirect_url("https:" + a.attrib.get("href", "") if a.attrib.get("href", "").startswith("//") else a.attrib.get("href", ""))
        if not url.startswith("http") or _is_aggregator(url):
            continue
        ats = classify_ats(url)
        text = _norm_title(a.get_all_text(strip=True))
        title_hit = title_words and len(title_words & set(text.split())) / len(title_words) >= 0.6
        if ats != "generico" and title_hit:
            return url, ats
        host = urllib.parse.urlparse(url).hostname or ""
        if fallback is None and title_hit and company_words and company_words[0] in host:
            fallback = (url, ats)
    return fallback or (None, None)


def search_company_posting(company: str, title: str) -> Tuple[Optional[str], Optional[str]]:
    """Busca '<empresa> <cargo>' en DuckDuckGo Lite (gratis, sin clave) para postular desde la página de la empresa."""
    global _last_search_time
    title = re.split(r"\s+[-|–—(]", (title or "").strip(" -|–—"))[0]  # "QA Engineer - Remote | REF#1" → "QA Engineer"
    if not company or not title:
        return None, None
    time.sleep(max(0.0, 5.0 - (time.time() - _last_search_time)))  # DuckDuckGo responde 202 si van seguidas
    _last_search_time = time.time()
    q = urllib.parse.quote_plus(f"{company} {title} apply")
    try:
        resp = Fetcher.get(f"https://lite.duckduckgo.com/lite/?q={q}", stealthy_headers=True)
        if resp and resp.status == 200:
            return pick_search_result(resp.body.decode("utf-8", errors="ignore"), company, title)
        logger.warning(f"Búsqueda web HTTP {getattr(resp, 'status', None)} para {company} / {title}")
    except Exception as e:
        logger.warning(f"Búsqueda web falló para {company} / {title}: {e}")
    return None, None


def _board_fallback(job: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    url, ats = lookup_ats_boards(job.get("company", ""), job.get("title", ""))
    if not url:
        url, ats = search_company_posting(job.get("company", ""), job.get("title", ""))
    return (url, ats, "auto") if url else (None, None, "manual")


def unwrap_redirect_url(url: str) -> str:
    """Extrae la URL destino si está embebida en un parámetro de query (ej. ?url=... o ?dest=...)."""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        for param in ("url", "dest", "redirect", "target", "u", "jobUrl", "uddg"):
            if param in qs and qs[param]:
                candidate = urllib.parse.unquote(qs[param][0]).strip()
                if candidate.startswith(("http://", "https://")):
                    return candidate
    except Exception:
        pass
    return url


def follow_redirects(url: str, timeout: int = 8) -> str:
    """Sigue redirecciones HTTP hasta el dominio final."""
    if not url:
        return url
    # Si ya contiene el destino en query params, desenvuélvelo
    unwrapped = unwrap_redirect_url(url)
    if unwrapped != url:
        url = unwrapped

    # Si ya es un ATS conocido directo, no hace falta request extra
    ats = classify_ats(url)
    if ats and ats != "generico":
        return url

    try:
        _throttle_linkedin(url)
        resp = Fetcher.get(url, stealthy_headers=True, timeout=timeout)
        if resp and resp.status < 400 and hasattr(resp, "url") and resp.url:
            return unwrap_redirect_url(resp.url)
    except Exception as e:
        logger.debug(f"No se pudo seguir redirección para {url}: {e}")
    return url


def extract_apply_info(html: str, base_url: str = "", follow_redirects_online: bool = True) -> Tuple[Optional[str], Optional[str], str]:
    """Parsea el HTML de una oferta y extrae (apply_url, ats, apply_mode).
    
    Retorna:
    - apply_url: URL externa donde postular, o None si no hay.
    - ats: Nombre del ATS clasificado, o None si no hay URL.
    - apply_mode: 'auto' si hay URL externa, o 'manual' si es Easy Apply / sin enlace.
    """
    if not html:
        return None, None, "manual"

    selector = Selector(html)

    # 1. Detectar si la página tiene Easy Apply (LinkedIn Onsite, Indeed Apply, etc.)
    has_easy_apply = False

    # Check texto de botones o spans
    for text_candidate in ("Easy Apply", "Solicitud sencilla", "Postularme", "Easy apply"):
        matches = selector.find_by_text(text_candidate, first_match=False, partial=True)
        if matches:
            for m in matches:
                tag = getattr(m, "tag", "").lower()
                parent_tag = getattr(m.parent, "tag", "").lower() if hasattr(m, "parent") and m.parent else ""
                if tag in ("button", "span", "div", "a") or parent_tag in ("button", "a"):
                    has_easy_apply = True
                    break
        if has_easy_apply:
            break

    # Check atributos de LinkedIn / Indeed
    if not has_easy_apply:
        if selector.css("[data-tracking-control-name*='apply-link-onsite'], [data-control-name='jobdetails_topcard_inapply']"):
            has_easy_apply = True
        elif "SimpleOnsiteApply" in html or "easyApplyUrl" in html:
            has_easy_apply = True

    # 2. Buscar enlaces de postulación externa
    candidate_urls = []

    # Estrategia A: Enlaces con atributos explícitos de postulación externa
    offsite_selectors = [
        "a[data-tracking-control-name*='apply-link-offsite']",
        "a[data-indeed-apply-joburl]",
        "#applyButtonLinkContainer a",
        "a.ia-IndeedApplyButton",
        "a.topcard__link--apply",
        "a[href*='externalApply']",
    ]
    for sel in offsite_selectors:
        for a in selector.css(sel):
            href = a.attrib.get("href") or a.attrib.get("data-indeed-apply-joburl")
            if href:
                candidate_urls.append(href)

    # Estrategia B: Enlaces a dominios conocidos de ATS presentes en el HTML
    for a in selector.css("a[href]"):
        href = a.attrib.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        for domain in ATS_DOMAINS.keys():
            if domain in href.lower():
                candidate_urls.append(href)
                break

    # Estrategia C: Botones o enlaces por texto ("Apply on company website", "Apply for this position", "Apply")
    apply_texts = [
        "Apply on company website",
        "Apply for this position",
        "Apply on company site",
        "Apply externally",
        "Apply for this job",
        "Apply now",
        "Apply",
        "Postular a la vacante",
        "Postular en la web de la empresa",
        "Postular",
        "Solicitar puesto",
    ]
    for txt in apply_texts:
        matches = selector.find_by_text(txt, first_match=False, partial=True)
        if matches:
            for node in matches:
                # Filtrar tags ocultos o scripts
                if getattr(node, "tag", "").lower() in ("script", "style", "noscript"):
                    continue
                a_tag = node if getattr(node, "tag", "").lower() == "a" else node.find_ancestor(lambda n: getattr(n, "tag", "").lower() == "a")
                if a_tag and a_tag.attrib.get("href"):
                    candidate_urls.append(a_tag.attrib.get("href"))

    # Estrategia D: Scripts y metadatos JSON (LinkedIn decoratedJobPostingId, JSON-LD)
    if "companyApplyUrl" in html or "OffsiteApply" in html:
        m = re.search(r'"companyApplyUrl"\s*:\s*"([^"]+)"', html)
        if m:
            candidate_urls.append(m.group(1))

    # Filtrar y limpiar candidatos
    valid_url = None
    for raw in candidate_urls:
        if not raw:
            continue
        cleaned = raw.strip()
        if cleaned.startswith(("#", "javascript:", "mailto:")):
            continue
        # Descartar links internos de login, share, report, o navegación genérica
        low = cleaned.lower()
        if any(ign in low for ign in ("/login", "/signup", "/auth", "linkedin.com/signup", "indeed.com/account", "trk=public_jobs_nav_header")):
            continue
        
        # Resolver link relativo
        if base_url and not cleaned.startswith(("http://", "https://")):
            cleaned = urllib.parse.urljoin(base_url, cleaned)
            
        # Desenvolver parámetros embebidos (ej. ?url=...)
        cleaned = unwrap_redirect_url(cleaned)
        
        if cleaned.startswith(("http://", "https://")):
            valid_url = cleaned
            break

    # 3. Si se encontró URL válida, seguir redirección y clasificar
    if valid_url:
        final_url = follow_redirects(valid_url) if follow_redirects_online else valid_url
        ats = classify_ats(final_url)
        return final_url, ats, "auto"

    # 4. Si no hay link externo pero es Easy Apply -> manual
    if has_easy_apply:
        return None, None, "manual"

    # 5. Sin link encontrado -> manual
    return None, None, "manual"


def resolve(job: Union[Dict[str, Any], str], use_js_fallback: bool = True, follow_redirects_online: bool = True) -> Tuple[Optional[str], Optional[str], str]:
    """Resuelve (apply_url, ats, apply_mode) para una vacante.
    
    Argumentos:
    - job: dict con datos de la vacante (al menos 'url', opcionalmente 'apply_url' o 'html'),
      o un string con la URL de la vacante.
    - use_js_fallback: si es True y Fetcher HTTP no encuentra enlace, intenta con DynamicFetcher (Edge).
    - follow_redirects_online: si es True, sigue redirecciones HTTP hasta el dominio final.
    """
    if isinstance(job, str):
        job = {"url": job}

    url = (job.get("url") or "").strip()
    apply_url = job.get("apply_url")

    # Si ya tenemos un apply_url previo (ej. de JobSpy job_url_direct)
    if apply_url and str(apply_url).strip() and str(apply_url).lower() not in ("nan", "none", ""):
        apply_url = str(apply_url).strip()
        final_url = follow_redirects(apply_url) if follow_redirects_online else apply_url
        ats = classify_ats(final_url)
        apply_mode = "manual" if ats == "manual" else "auto"
        return final_url, ats, apply_mode

    # Si el job trae el HTML directamente (ideal para pruebas y fixtures)
    if "html" in job and job["html"]:
        return extract_apply_info(job["html"], base_url=url, follow_redirects_online=follow_redirects_online)

    if not url:
        return None, None, "manual"

    # Jobright, Welcome to the Jungle y similares piden sesión: buscar la vacante en la web de la empresa
    if _is_aggregator(url) and "linkedin.com" not in url.lower() and "indeed.com" not in url.lower():
        return _board_fallback(job)

    # Paso 1: Fetcher.get (sin navegador, HTTP puro con headers stealthy)
    html_content = ""
    effective_url = url
    try:
        _throttle_linkedin(url)
        resp = Fetcher.get(url, stealthy_headers=True)
        if resp and resp.status == 200:
            html_content = resp.body.decode("utf-8", errors="ignore")
            effective_url = getattr(resp, "url", url) or url
        elif resp and resp.status in (401, 403, 429):
            logger.warning(f"HTTP {resp.status} al obtener {url}.")
            if "linkedin.com" in url.lower():
                return _board_fallback(job)
    except Exception as e:
        logger.warning(f"Error al obtener {url} con Fetcher: {e}")

    if html_content:
        if "expired_jd_redirect" in effective_url.lower():
            logger.info(f"Vacante expirada o redirigida: {effective_url}")
            return None, None, "manual"

        cand_url, cand_ats, cand_mode = extract_apply_info(html_content, base_url=effective_url, follow_redirects_online=follow_redirects_online)
        if cand_url:
            return cand_url, cand_ats, cand_mode
        # Si explícitamente se detectó Easy Apply en el HTML, no hace falta JS
        if cand_mode == "manual" and ("Easy Apply" in html_content or "SimpleOnsiteApply" in html_content or "easy-apply" in html_content):
            return _board_fallback(job)  # puede estar también en el ATS de la empresa

    # Paso 2: DynamicFetcher con Edge headless (solo si la página necesita JS o dio error no bloqueante)
    if use_js_fallback and "linkedin.com" not in url.lower():
        try:
            logger.info(f"Intentando DynamicFetcher (Edge headless) para {url}...")
            _throttle_linkedin(url)
            resp_dyn = DynamicFetcher.fetch(url, headless=True)
            if resp_dyn and resp_dyn.status == 200:
                html_dyn = resp_dyn.body.decode("utf-8", errors="ignore")
                eff_dyn = getattr(resp_dyn, "url", url) or url
                return extract_apply_info(html_dyn, base_url=eff_dyn, follow_redirects_online=follow_redirects_online)
        except Exception as e:
            logger.error(f"DynamicFetcher falló para {url}: {e}")

    return _board_fallback(job)


def main():
    """Resuelve las vacantes 'CV Generado' sin apply_url de la DB activa."""
    parser = argparse.ArgumentParser(description="Resuelve apply_url y ATS para vacantes CV Generado.")
    parser.add_argument("--limit", type=int, default=None, help="Límite máximo de vacantes a resolver.")
    parser.add_argument("--db", type=str, default=None, help="Ruta alternativa a jobs.db.")
    args = parser.parse_args()

    if args.db:
        import os
        os.environ["JOBHUNTER_DB_PATH"] = args.db

    database.init_db()
    jobs = database.get_jobs_for_apply_resolution(status="CV Generado")
    total = len(jobs)
    if args.limit and args.limit > 0:
        jobs = jobs[:args.limit]

    print(f"\n[AP-3 Resolver] Iniciando resolución de {len(jobs)} vacantes 'CV Generado' (total pendientes: {total})...\n")

    resolved_count = 0
    auto_count = 0
    manual_count = 0

    for idx, job in enumerate(jobs, 1):
        url = job.get("url")
        title = job.get("title", "")
        company = job.get("company", "")
        print(f"[{idx}/{len(jobs)}] {title[:35]} ({company[:20]}) -> {url}")

        apply_url, ats, apply_mode = resolve(job)
        database.set_job_apply_info(url, apply_url=apply_url, ats=ats, apply_mode=apply_mode)

        if apply_mode == "auto":
            auto_count += 1
            print(f"       -> [AUTO] ATS: {ats} | URL: {apply_url}")
        else:
            manual_count += 1
            print(f"       -> [MANUAL] Solo Easy Apply / sin link externo.")

        resolved_count += 1

    print("\n" + "=" * 60)
    print(f"[AP-3 Resolver] Terminado: {resolved_count} procesadas.")
    print(f"  - Auto (link externo encontrado): {auto_count}")
    print(f"  - Manual (Easy Apply / sin link): {manual_count}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
