"""Pruebas del resolutor de URLs de postulación y ATS (Fase B de APPLICATOR_PLAN.md).

Se corre con: py test_apply_resolver.py
Imprime 'ok' si todas las aserciones pasan.
"""
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from apply_resolver import classify_ats, extract_apply_info, resolve, unwrap_redirect_url

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "resolver"


def load_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    assert path.is_file(), f"No existe el archivo de fixture: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Clasificación por dominio de 10 URLs de ejemplo (Fase B)
# ---------------------------------------------------------------------------
domain_cases = [
    ("https://boards.greenhouse.io/acme/jobs/101", "greenhouse"),
    ("https://jobs.lever.co/globex/202", "lever"),
    ("https://jobs.ashbyhq.com/umbrella/303", "ashby"),
    ("https://apply.workable.com/stark/j/404/", "workable"),
    ("https://jobs.smartrecruiters.com/wayne/505", "smartrecruiters"),
    ("https://cyberdyne.myworkdayjobs.com/en-US/careers/job/606", "workday"),
    ("https://initech.bamboohr.com/careers/707", "bamboohr"),
    ("https://massive-dynamic.teamtailor.com/jobs/808", "teamtailor"),
    ("https://acme-corp.com/careers/software-engineer", "generico"),
    ("https://startuphub.io/apply/direct-candidate", "generico"),
]

for url, expected_ats in domain_cases:
    actual = classify_ats(url)
    assert actual == expected_ats, f"Error en clasificación de {url}: esperado '{expected_ats}', obtenido '{actual}'"

# Caso borde: URL None o vacía
assert classify_ats(None) is None, "classify_ats(None) debe ser None"
assert classify_ats("") is None, "classify_ats('') debe ser None"


# ---------------------------------------------------------------------------
# 2. Desenvolver URLs con redirección embebida en query parameters
# ---------------------------------------------------------------------------
wrapped = "https://www.linkedin.com/jobs/view/externalApply/12345?url=https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F999"
unwrapped = unwrap_redirect_url(wrapped)
assert unwrapped == "https://boards.greenhouse.io/acme/jobs/999", f"Fallo al desenvolver: {unwrapped}"


# ---------------------------------------------------------------------------
# 3. Fixtures reales de ofertas (5 casos sin mocks del parser)
# ---------------------------------------------------------------------------

# 3.1 LinkedIn con enlace externo (Greenhouse)
html_li_ext = load_fixture("linkedin_external.html")
url_li_ext, ats_li_ext, mode_li_ext = extract_apply_info(html_li_ext, follow_redirects_online=False)
assert url_li_ext == "https://boards.greenhouse.io/enterprisetech/jobs/4012345", f"URL incorrecta: {url_li_ext}"
assert ats_li_ext == "greenhouse", f"ATS incorrecto: {ats_li_ext}"
assert mode_li_ext == "auto", f"Modo incorrecto: {mode_li_ext}"

# También probamos llamando a resolve() con el dict que incluye html
job_li_ext = {"url": "https://www.linkedin.com/jobs/view/4012345", "html": html_li_ext}
r_url, r_ats, r_mode = resolve(job_li_ext, follow_redirects_online=False)
assert r_url == "https://boards.greenhouse.io/enterprisetech/jobs/4012345"
assert r_ats == "greenhouse"
assert r_mode == "auto"

# 3.2 LinkedIn solo Easy Apply (sin enlace externo)
html_li_easy = load_fixture("linkedin_easy_apply.html")
url_li_easy, ats_li_easy, mode_li_easy = extract_apply_info(html_li_easy, follow_redirects_online=False)
assert url_li_easy is None, f"Easy Apply no debe tener apply_url externa: {url_li_easy}"
assert ats_li_easy is None, f"Easy Apply no debe tener ATS: {ats_li_easy}"
assert mode_li_easy == "manual", f"Easy Apply debe tener apply_mode='manual': {mode_li_easy}"

job_li_easy = {"url": "https://www.linkedin.com/jobs/view/4468340762", "html": html_li_easy}
r_url_e, r_ats_e, r_mode_e = resolve(job_li_easy, follow_redirects_online=False)
assert r_url_e is None
assert r_ats_e is None
assert r_mode_e == "manual"

# 3.3 Indeed con enlace externo (Lever)
html_indeed = load_fixture("indeed_external.html")
url_ind, ats_ind, mode_ind = extract_apply_info(html_indeed, follow_redirects_online=False)
assert url_ind == "https://jobs.lever.co/omnitech/88271a3c-b01f-4ef2-9e23", f"URL incorrecta: {url_ind}"
assert ats_ind == "lever", f"ATS incorrecto: {ats_ind}"
assert mode_ind == "auto", f"Modo incorrecto: {mode_ind}"

# 3.4 Remotive con enlace externo (Workable)
html_remotive = load_fixture("remotive.html")
url_rem, ats_rem, mode_rem = extract_apply_info(html_remotive, follow_redirects_online=False)
assert url_rem == "https://apply.workable.com/cloudscale/j/CS778899/", f"URL incorrecta: {url_rem}"
assert ats_rem == "workable", f"ATS incorrecto: {ats_rem}"
assert mode_rem == "auto", f"Modo incorrecto: {mode_rem}"

# 3.5 Working Nomads con enlace externo (Ashby)
html_wn = load_fixture("working_nomads.html")
url_wn, ats_wn, mode_wn = extract_apply_info(html_wn, follow_redirects_online=False)
assert url_wn == "https://jobs.ashbyhq.com/nextgen/712398", f"URL incorrecta: {url_wn}"
assert ats_wn == "ashby", f"ATS incorrecto: {ats_wn}"
assert mode_wn == "auto", f"Modo incorrecto: {mode_wn}"


# ---------------------------------------------------------------------------
# 4. Job con apply_url previo (ej. job_url_direct de JobSpy)
# ---------------------------------------------------------------------------
job_direct = {
    "url": "https://www.linkedin.com/jobs/view/99999",
    "apply_url": "https://company.smartrecruiters.com/careers/job/123",
}
r_url_d, r_ats_d, r_mode_d = resolve(job_direct, follow_redirects_online=False)
assert r_url_d == "https://company.smartrecruiters.com/careers/job/123"
assert r_ats_d == "smartrecruiters"
assert r_mode_d == "auto"


# ---------------------------------------------------------------------------
# 5. Búsqueda web (Jobright / Jungle): se salta portales, prefiere el ATS con el cargo
# ---------------------------------------------------------------------------
from apply_resolver import pick_search_result

ddg = """
<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fjobright.ai%2Fjobs%2Finfo%2F1">QA Automation Engineer - Acme</a>
<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fjobs%2Fview%2F2">QA Automation Engineer Acme</a>
<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fjob-boards.greenhouse.io%2Facme%2Fjobs%2F9">Data Analyst at Acme</a>
<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fjobs.lever.co%2Facme%2Fabc">Acme - QA Automation Engineer</a>
"""
assert pick_search_result(ddg, "Acme Inc", "QA Automation Engineer") == ("https://jobs.lever.co/acme/abc", "lever")
own = '<a class="result-link" href="https://careers.acme.com/jobs/77">QA Automation Engineer | Acme Careers</a>'
assert pick_search_result(own, "Acme", "QA Automation Engineer") == ("https://careers.acme.com/jobs/77", "generico")
assert pick_search_result(ddg, "Acme", "Head of Sales") == (None, None)

print("ok")
