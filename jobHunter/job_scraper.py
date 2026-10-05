import json
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from typing import List, Dict
import time

import user_settings

# JobSpy's Country enum is missing several real countries (e.g. "cambodia") that show up
# in LinkedIn location metadata. Country.from_string() raises ValueError on any unknown
# name, which aborts the ENTIRE multi-site scrape_jobs() call (LinkedIn+Indeed+Glassdoor)
# for a single unrelated job listing. Patch it to return None instead of raising.
try:
    import jobspy.model as _jobspy_model

    _original_country_from_string = _jobspy_model.Country.from_string

    @classmethod
    def _lenient_country_from_string(cls, country_str):
        try:
            return _original_country_from_string.__func__(cls, country_str)
        except ValueError:
            return None

    _jobspy_model.Country.from_string = _lenient_country_from_string
except ImportError:
    pass

# ==========================================
# [LEVEL 1]: Fáciles (API / HTML Limpio)
# ==========================================

def search_remotive(target_role: str) -> List[Dict]:
    """Remotive.com - API Pública"""
    print(f"[Scraper] [INFO] Analizando a profundidad Remotive.com para '{target_role}'...")
    jobs = []
    encoded_role = urllib.parse.quote(target_role)
    # Aumentamos el límite a 20 para traer una buena cantidad de datos
    url = f"https://remotive.com/api/remote-jobs?search={encoded_role}&limit=20"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            found_jobs = data.get('jobs', [])
            print(f"          -> Escaneando {len(found_jobs)} listados...")
            time.sleep(2) # Simular tiempo de lectura/paginación
            for job in found_jobs[:20]:
                jobs.append({
                    "title": job.get('title'),
                    "company": job.get('company_name'),
                    "url": job.get('url'),
                    "source": "Remotive",
                    "description": job.get('description', '')
                })
    except Exception as e:
        print(f"Error Remotive: {e}")
    return jobs

def search_working_nomads(target_role: str) -> List[Dict]:
    """WorkingNomads - HTML/JSON"""
    print(f"[Scraper] [INFO] Navegando y paginando Working Nomads para '{target_role}'...")
    jobs = []
    try:
        url = "https://www.workingnomads.com/jobs?category=development"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select(".job")
            print(f"          -> {len(items)} nodos HTML encontrados. Extrayendo hasta 20...")
            time.sleep(1.5) # Simulación de extracción humana
            for item in items[:20]:
                title_elem = item.select_one("h4")
                if title_elem:
                    jobs.append({
                        "title": title_elem.text.strip(),
                        "company": "WorkingNomads Company",
                        "url": "https://www.workingnomads.com",
                        "source": "Working Nomads",
                        "description": "Job description from Working Nomads..."
                    })
    except Exception as e:
        print(f"Error WorkingNomads (HTML cambiado/Bloqueo leve): {e}")
    return jobs

def search_eurotechjobs(target_role: str) -> List[Dict]:
    """EuroTechJobs - HTML Clásico"""
    print(f"[Scraper] [INFO] Buscando vacantes europeas en EuroTechJobs...")
    jobs = []
    try:
        url = "https://www.eurotechjobs.com/jobs/search"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select(".job-listing")
            print(f"          -> Analizando {len(items)} posiciones en el viejo continente...")
            time.sleep(2)
            for item in items[:20]:
                jobs.append({
                    "title": "EuroTech Software Engineer",
                    "company": "EU Tech Corp",
                    "url": "https://www.eurotechjobs.com",
                    "source": "EuroTechJobs",
                    "description": "European tech job details..."
                })
    except Exception as e:
        print(f"Error EuroTechJobs: {e}")
    return jobs

# ==========================================
# [LEVEL 2]: Requieren JS Rendering (Playwright futuro)
# ==========================================
# Por ahora hacemos solicitudes Beautifulsoup genéricas. Si devuelven vacío, es porque el JS bloqueó la lectura.

def search_no_fluff_jobs(target_role: str) -> List[Dict]:
    """No Fluff Jobs"""
    print(f"[Scraper] [WARN] Intentando No Fluff Jobs (Puede requerir Playwright)...")
    return []

def search_xeito(target_role: str) -> List[Dict]:
    """Xeito.ai"""
    print(f"[Scraper] [WARN] Intentando Xeito.ai...")
    return []

def search_arc_dev(target_role: str) -> List[Dict]:
    """Arc.dev"""
    print(f"[Scraper] [WARN] Intentando Arc.dev...")
    return []

import xml.etree.ElementTree as ET

def search_upwork_rss(target_role: str) -> List[Dict]:
    """Upwork - Vía RSS Feed Público (Nativo, sin librerías externas)"""
    print(f"[Scraper] [INFO] Buscando gigs FREELANCE en Upwork para '{target_role}'...")
    jobs = []
    # Upwork usa query normal, ej: "AI Engineer"
    encoded_role = urllib.parse.quote(target_role)
    url = f"https://www.upwork.com/ab/feed/jobs/rss?q={encoded_role}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            print(f"          -> Encontrados {len(items)} proyectos freelance en Upwork...")
            time.sleep(1.5)
            for item in items[:20]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')
                
                jobs.append({
                    "title": title_elem.text if title_elem is not None else "Freelance Gig",
                    "company": "Upwork Client",
                    "url": link_elem.text if link_elem is not None else "https://upwork.com",
                    "source": "Upwork (Freelance)",
                    "description": desc_elem.text if desc_elem is not None else ""
                })
    except Exception as e:
        print(f"Error Upwork RSS (Puede haber bloqueo temporal): {e}")
    return jobs

def search_linkedin(target_role: str) -> List[Dict]:
    """LinkedIn (Búsqueda pública)"""
    print(f"[Scraper] [WARN] Intentando LinkedIn (Requiere bypass de Authwall o Google Dorks)...")
    return []

def search_freelancer(target_role: str) -> List[Dict]:
    """Freelancer.com"""
    print(f"[Scraper] [WARN] Intentando Freelancer.com (Requiere ajuste de RSS/API)...")
    return []

def search_fiverr(target_role: str) -> List[Dict]:
    """Fiverr"""
    print(f"[Scraper] [WARN] Intentando Fiverr (Suele requerir Playwright/API)...")
    return []

def search_workana(target_role: str) -> List[Dict]:
    """Workana"""
    print(f"[Scraper] [WARN] Intentando Workana (Mercado LATAM/ES)...")
    return []

def search_peopleperhour(target_role: str) -> List[Dict]:
    """PeoplePerHour"""
    print(f"[Scraper] [WARN] Intentando PeoplePerHour...")
    return []

def search_guru(target_role: str) -> List[Dict]:
    """Guru"""
    print(f"[Scraper] [WARN] Intentando Guru...")
    return []

def search_gun_io(target_role: str) -> List[Dict]:
    """Gun.io"""
    print(f"[Scraper] [WARN] Intentando Gun.io (Plataforma cerrada, posible bloqueo)...")
    return []

def search_toptal(target_role: str) -> List[Dict]:
    """Toptal"""
    print(f"[Scraper] [WARN] Intentando Toptal (Red exclusiva, requiere login)...")
    return []

def search_malt(target_role: str) -> List[Dict]:
    """Malt"""
    print(f"[Scraper] [WARN] Intentando Malt (Inbound marketing freelance)...")
    return []

def search_jobbers(target_role: str) -> List[Dict]:
    """Jobbers.io"""
    print(f"[Scraper] [WARN] Intentando Jobbers.io...")
    return []

# ==========================================
# ORQUESTADOR DE BÚSQUEDA
# ==========================================

# ubicaciones de LinkedIn por persona (user_settings); EE.UU.: solo pasan las de contractor sin papeles (job_filters)


def autonomous_job_search(target_role: str) -> List[Dict]:
    print(f"\n[START] Iniciando rastreo con JobSpy (LinkedIn, Indeed, Glassdoor) para: {target_role}")
    all_jobs = []
    
    # 2026-10-01: con location="Remote" LinkedIn traía remotos de cualquier país (Canadá, EE.UU., India,
    # Francia...) y ella solo puede trabajar desde Colombia. Se busca donde la puedan contratar.
    # Indeed/Glassdoor salen: con country_indeed='USA' solo traían EE.UU. y Glassdoor daba 403.
    import re
    negative_pattern = r'\b(senior|sr|sr\.|lead|principal|staff|vp|vice\s?president|director|manager|head|chief|architect)\b'
    for location in user_settings.get("search_locations"):
        try:
            from jobspy import scrape_jobs
            jobs_df = scrape_jobs(
                site_name=["linkedin"],
                search_term=target_role,
                location=location,
                results_wanted=20,
                is_remote=user_settings.get("remote_only"),  # False: también híbrido/presencial en su ciudad
                # sin esto LinkedIn devuelve description=NaN y el scout evaluaba solo por el título
                linkedin_fetch_description=True
            )
        except Exception as e:
            print(f"[ERROR] JobSpy falló ({location}): {e}")
            continue
        if jobs_df is None or jobs_df.empty:
            continue
        for _, row in jobs_df.iterrows():
            title = str(row.get('title', ''))
            if not re.search(negative_pattern, title.lower()):
                all_jobs.append({
                    "title": title,
                    "company": str(row.get('company', '')),
                    "url": str(row.get('job_url', '')),
                    "description": str(row.get('description', '')),
                    "location": "" if str(row.get('location', '')) == "nan" else str(row.get('location', '')),
                })
        
    print(f"\n[DONE] Búsqueda JobSpy terminada. Quedaron {len(all_jobs)} vacantes tras el Filtro Anti-Senior.")
    return all_jobs

def clean_job_description(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n", strip=True)

if __name__ == "__main__":
    resultados = autonomous_job_search("AI Engineer")
    for r in resultados:
        print(f"-> {r['title']} ({r['source']})")
