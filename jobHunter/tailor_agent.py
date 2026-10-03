import json
import os
import re
import time
import asyncio
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from typing import Optional
from database import init_db, get_approved_jobs, get_low_match_jobs, update_job_status
import profile_paths
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

import llm_chain
import cv_tailoring
from cv_tailoring import Experience, TailoredProfile
from archetypes import classify_archetype, load_template, needs_adjustment, ARCHETYPE_LABELS

# Debajo de este match, no vale la pena gastar tokens generando un CV a medida.
MIN_MATCH_THRESHOLD = 70

# CONFIGURACIÓN LLM — cadena de fallback compartida (llm_chain.py): Gemini -> Groq -> Cerebras ->
# OpenRouter, cada una con su propia cuota diaria gratis. Antes era Ollama local (débil detectando
# mentiras + causaba OOM-kills), luego Groq directo vía OmniRoute (sin fallback real cuando se
# agotaba la cuota, y con bugs de routing propios de OmniRoute nunca resueltos del todo).
#
# Los schemas (TailoredProfile/Experience/ReviewResult) y los prompts del generador/revisor/patch
# viven en cv_tailoring.py — se comparten con generate_archetype_templates.py. tailor_agent.py ya
# no genera el CV desde cero para cada vacante: clasifica la vacante en un arquetipo (AI Engineer /
# Forward Deployed Engineer / QA Automation), parte del template base de ese arquetipo
# (archetype_templates/*.json, generado una vez por generate_archetype_templates.py), y solo llama
# al LLM si el gap_analysis de la vacante trae algo que el template todavía no cubre — y ahí es un
# ajuste liviano (cv_tailoring.patch_from_template), no una regeneración completa. Esto es lo que
# hace que el cupo gratis rinda para muchas más vacantes por día.

TUTOR_SYSTEM_PROMPT = "Eres un Tutor Tcnico Senior. Basado en el Gap Analysis (tecnologas que el candidato NO domina pero necesita para esta vacante), escrbele una gua de estudio intensiva de fin de semana (Crash Course). Se directo, claro y enfocado en pasar la prueba tcnica."
TUTOR_HUMAN_TEMPLATE = "VACANTE: {job_title}\nGAP ANALYSIS: {gap_analysis}"

# HERRAMIENTAS CORE

def _safe_filename(s: str) -> str:
    """Sanea un nombre de empresa/vacante para usarlo en un path de archivo. Nombres reales
    como 'Reviva | Deorganising Crime ™' rompen open() en Windows (| es carácter reservado,
    ™ no es ASCII) — nos quedamos solo con letras/números/guión/guión bajo/punto."""
    s = s.replace(' ', '_')
    s = re.sub(r'[^\w\-.]', '', s)
    return s or "empresa"


# Plan de estudio solo para matches de 50 a 89%: a los de 90+ les basta ver los gaps en el dashboard.
STUDY_MIN, STUDY_MAX = 50, 90


def generate_study_guide(job_title: str, company: str, gap_analysis: str, job_id):
    if not gap_analysis or gap_analysis.strip() == "":
        return
    os.makedirs("study_guides", exist_ok=True)
    tutor_filename = f"study_guides/STUDY_GUIDE_{_safe_filename(company)}_{job_id}.txt"
    if os.path.exists(tutor_filename):
        return
    print(f"[Tutor] Generando Crash Course para {company}...")
    try:
        text = llm_chain.invoke_text(
            system_prompt=TUTOR_SYSTEM_PROMPT,
            human_template=TUTOR_HUMAN_TEMPLATE,
            variables={"job_title": job_title, "gap_analysis": gap_analysis},
            temperature=0.2,
            local_only=True,  # una guía por vacante no vale cupo de nube: la hace el modelo del homelab
        )
    except llm_chain.AllProvidersExhausted:
        print("      [!] Los 4 proveedores LLM se quedaron sin cupo — se omite la guía de estudio para este job.")
        return
    with open(tutor_filename, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"      - Guía guardada en: {tutor_filename}")

async def render_pdf(profile_data: dict, tailored_data: TailoredProfile, company: str, job_id) -> str:
    """Inyecta datos en HTML y usa Playwright para exportar a PDF."""
    with open("CV_TEMPLATE/cv_template.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Reemplazos básicos
    personal_info = profile_data.get('personal_info') or {}

    def _short_link(url: str) -> str:
        return url.replace("https://", "").replace("http://", "").rstrip("/")

    html = html.replace("{{FULL_NAME}}", personal_info.get('full_name', 'Tu Nombre'))
    html = html.replace("{{TARGET_ROLE}}", tailored_data.target_role_title or profile_data.get('target_roles', 'Ingeniero'))
    html = html.replace("{{LOCATION}}", personal_info.get('location', 'Ubicación'))
    html = html.replace("{{EMAIL}}", personal_info.get('email', 'email@ejemplo.com'))
    html = html.replace("{{PHONE}}", personal_info.get('number', ''))
    html = html.replace("{{LINKEDIN}}", _short_link(personal_info.get('linkedin_url', '')))
    html = html.replace("{{GITHUB}}", _short_link(personal_info.get('github_url', '')))
    html = html.replace("{{PROFESSIONAL_SUMMARY}}", tailored_data.professional_summary)

    # Habilidades Técnicas
    skills_html = ""
    for stack in profile_data.get('technical_stacks', []):
        skills_html += f"""<div class='skill-item'>
            <p class='skill-label'><b>{stack['ability']}</b></p>
            <p class='skill-desc'>{stack['ability_description']}</p>
        </div>"""
    html = html.replace("{{SKILLS_HTML}}", skills_html)

    # Skills Adicionales (frameworks/languages/tools) — agrupadas por categoría, formato compacto
    # en línea (igual que Technical Skills) para no inflar el CV a 3 páginas.
    addskills_by_cat = {}
    for sk in profile_data.get('additional_skills', []):
        addskills_by_cat.setdefault(sk['skill_category'], []).append(sk['name'])
    cat_labels = {"frameworks": "Frameworks", "languages": "Languages", "tools": "Tools"}
    addskills_html = ""
    for cat in ["frameworks", "languages", "tools"]:
        names = addskills_by_cat.get(cat)
        if names:
            addskills_html += f"""<div class='addskill-item'>
                <p class='addskill-desc'><b>{cat_labels[cat]}:</b> {', '.join(names)}.</p>
            </div>"""
    html = html.replace("{{ADDITIONAL_SKILLS_HTML}}", addskills_html)

    # Certificaciones
    cert_html = ""
    for cert in profile_data.get('certifications', []):
        cert_html += f"""<div class='cert-item'>
            <div class='cert-header'><b>{cert['certification_name']}</b><span class='cert-date'>{cert['certification_year']}</span></div>
        </div>"""
    html = html.replace("{{CERTIFICATIONS_HTML}}", cert_html)

    # Educación
    edu_html = ""
    for edu in profile_data.get('education', []):
        edu_html += f"""<div class='edu-item'>
            <div class='edu-header'><span><b>{edu['degree']}</b> | {edu['institution']}</span><span class='edu-date'>{edu['time_period_studied']}</span></div>
            <ul>"""
        for ach in edu.get('education_achievements', []):
            edu_html += f"<li>{ach}</li>"
        edu_html += "</ul></div>"
    html = html.replace("{{EDUCATION_HTML}}", edu_html)

    # Portafolio de Proyectos
    portfolio_html = ""
    for proj in profile_data.get('portfolio_projects', []):
        portfolio_html += f"<p class='portfolio-item'>{proj}</p>"
    html = html.replace("{{PORTFOLIO_HTML}}", portfolio_html)

    # Idiomas
    languages_html = " &nbsp;&bull;&nbsp; ".join(
        f"{lang['language_name']} ({lang['proficiency']})" for lang in profile_data.get('spoken_languages', [])
    )
    html = html.replace("{{LANGUAGES_HTML}}", languages_html)

    # Construir HTML de Experiencia Dinámicamente
    exp_html = ""
    for exp in tailored_data.experience:
        exp_html += f"""
        <div class='job'>
            <div class='job-header'>
                <span class='role-company'><b>{exp.current_role}</b> | {exp.company_name}</span>
                <span class='job-date'>{exp.time_period_worked}</span>
            </div>
            <ul>
        """
        for ach in exp.achievements:
            exp_html += f"<li>{ach}</li>"
        exp_html += "</ul></div>"

    html = html.replace("{{EXPERIENCE_HTML}}", exp_html)
    
    temp_html_path = f"CV_TEMPLATE/temp_{_safe_filename(company)}_{job_id}.html"
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    cvs_dir = profile_paths.resolve("CVs_Listos")
    os.makedirs(cvs_dir, exist_ok=True)
    first_name = profile_data.get("personal_info", {}).get("full_name", "Candidato").split()[0]
    # job_id garantiza nombre único: dos vacantes de la misma empresa ya no se pisan el CV entre sí.
    pdf_path = os.path.abspath(os.path.join(cvs_dir, f"CV_{first_name}_{_safe_filename(company)}_{job_id}.pdf"))
    
    # PLAYWRIGHT MAGIA INVISIBLE
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        file_url = "file:///" + os.path.abspath(temp_html_path).replace("\\", "/")
        await page.goto(file_url)
        await page.pdf(path=pdf_path, format="A4", print_background=True)
        await browser.close()
        
    os.remove(temp_html_path)
    return pdf_path

# 5. EL ORQUESTADOR DEL SASTRE (BUCLE GENERADOR-REVISOR)

async def run_tailor_agent():
    print("====================================================")
    print(" Iniciando Tailor Agent (Sastre & Tutor)")
    print("====================================================\n")

    init_db()
    
    # 1. Leer Master Profile
    try:
        with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
            master_json_str = f.read()
            master_profile = json.loads(master_json_str)
    except Exception:
        print("[ERROR] No se encontr master_profile.json")
        return
        
    # 1b. Sin CV pero alcanzables (50-69%): solo plan de estudio, con el modelo local (gratis).
    for job in get_low_match_jobs(STUDY_MIN, MIN_MATCH_THRESHOLD):
        generate_study_guide(job['title'], job['company'], job['gap_analysis'], job['id'])

    # 2. Obtener trabajos aprobados
    jobs = get_approved_jobs()
    if not jobs:
        print("[INFO] No hay trabajos con estado 'Aprobado' en jobs.db.")
        return
        
    print(f"[INFO] Encontrados {len(jobs)} trabajos aprobados. Iniciando confeccin...\n")
    llm_chain.print_budget_status()
    print()

    processed = 0
    quota_exhausted = False

    for job in jobs:
        print(f">>> Procesando: {job['title']} en {job['company']}")

        if (job['match_percentage'] or 0) < MIN_MATCH_THRESHOLD:
            print(f"   [SKIP] Match {job['match_percentage']}% por debajo del umbral "
                  f"({MIN_MATCH_THRESHOLD}%). No se genera CV.")
            update_job_status(job['url'], "Match Insuficiente")
            continue

        # ARQUETIPO + TEMPLATE — en vez de regenerar el CV completo, se parte del template base
        # del arquetipo (AI Engineer / Forward Deployed Engineer / QA Automation) y solo se llama
        # al LLM si el gap_analysis trae algo que el template todavía no cubre.
        archetype = classify_archetype(job['title'])
        label = ARCHETYPE_LABELS[archetype]
        template = load_template(archetype)

        try:
            if template and not needs_adjustment(template, job['gap_analysis'], master_json_str):
                print(f"   [TEMPLATE] {label} — el template ya cubre el gap analysis, sin llamar al LLM.")
                tailored_result = TailoredProfile(
                    target_role_title=job['title'],
                    professional_summary=template['professional_summary'],
                    experience=[Experience(**e) for e in template['experience']],
                )
            elif template:
                print(f"   [AJUSTE] {label} — partiendo del template, ajuste liviano por gap_analysis...")
                tailored_result, _ = await cv_tailoring.patch_from_template(
                    template=template,
                    job_title=job['title'],
                    job_desc=job['scraped_content'][:2000] if job['scraped_content'] else "N/A",
                    gap_analysis=job['gap_analysis'],
                    master_json_str=master_json_str,
                )
            else:
                print(f"   [SIN TEMPLATE] {label} — no existe template todavía (corré "
                      f"generate_archetype_templates.py). Generando CV completo por esta vez.")
                tailored_result, _ = await cv_tailoring.generate_full(
                    job_title=job['title'],
                    job_company=job['company'],
                    job_desc=job['scraped_content'][:4000] if job['scraped_content'] else "N/A",
                    gap_analysis=job['gap_analysis'],
                    master_json_str=master_json_str,
                    master_profile=master_profile,
                )
        except llm_chain.AllProvidersExhausted:
            print("\n[CUOTA AGOTADA] Los proveedores gratis se quedaron sin cupo por hoy. "
                  "Deteniendo el Tailor de forma segura — los jobs restantes siguen en Aprobado.")
            quota_exhausted = True
            break

        tailored_result.target_role_title = job['title']  # siempre el título real y exacto de la vacante

        # Red de seguridad: un error inesperado acá (encoding raro, Playwright, disco lleno...)
        # NO debe tumbar el resto del batch — se loguea, el job queda en 'Aprobado' para
        # reintentar en la próxima corrida, y se sigue con el siguiente. Esto es lo que permite
        # que el watchdog 24/7 no quede atascado reintentando el mismo job roto para siempre.
        try:
            # Generar Gua de Estudio (El Tutor)
            if (job['match_percentage'] or 0) < STUDY_MAX:
                generate_study_guide(job['title'], job['company'], job['gap_analysis'], job['id'])

            # Generar PDF con Playwright
            print(f"   [Imprimiendo] Renderizando HTML a PDF con Playwright...")
            pdf_path = await render_pdf(master_profile, tailored_result, job['company'], job['id'])
            print(f"    PDF Guardado en: {pdf_path}")

            # Actualizar Base de Datos para el Agente 4 (guarda tailored_json para poder re-renderizar
            # el PDF con una plantilla nueva en el futuro sin tener que volver a llamar al LLM)
            update_job_status(job['url'], "CV Generado", cv_path=pdf_path, tailored_json=tailored_result.model_dump_json())
            processed += 1
        except Exception as e:
            print(f"   [ERROR] Falla inesperada generando el PDF/guía para {job['company']}: {e}. "
                  f"Este job queda en 'Aprobado' para reintentar — sigue con el resto.")
            continue

    print(f"\n==================== RESUMEN ====================")
    print(f" CVs generados: {processed}/{len(jobs)}")
    if quota_exhausted:
        remaining = len(jobs) - processed
        print(f" Cupo diario agotado — quedan {remaining} en 'Aprobado', listos para la próxima corrida "
              f"cuando las cuotas reseteen (normalmente a medianoche de cada proveedor).")
    llm_chain.print_budget_status()
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(run_tailor_agent())
