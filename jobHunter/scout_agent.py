import json
import database
import profile_paths
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
from typing import List
from pydantic import BaseModel, Field
from job_scraper import autonomous_job_search, clean_job_description
from dotenv import load_dotenv

load_dotenv()

import llm_chain
import job_filters
import job_scoring

# ==========================================
# 1. ESQUEMAS DE DATOS
# ==========================================

class ViabilityReport(BaseModel):
    is_viable: bool = Field(description="True if candidate meets the minimum threshold to be considered for the job.")
    match_percentage: int = Field(description="Estimated match percentage (0-100).")
    missing_skills_to_study: List[str] = Field(description="Gap Analysis: What the candidate MUST study before the technical interview.")
    reasoning: str = Field(description="Brief explanation of why they are viable or not.")

# ==========================================
# 2. LAS TOOLS DEL SCOUT
# (el LLM en si -- Gemini/Groq/Cerebras/OpenRouter, con fallback automatico entre los 4 -- vive en llm_chain.py)
# ==========================================

_EVALUATOR_SYSTEM_PROMPT = """You are a practical Technical Recruiter AI. You evaluate if a candidate meets the MINIMUM requirements for a job.
CRITICAL SENIORITY RULE: The candidate's seniority profile is: "{seniority_context}".
- MIXED SENIORITY: If the candidate has different years of experience in different roles (e.g. 4 years in QA, but only 1 year in Dev), evaluate the role appropriately! They are a Mid-Level QA, but a JUNIOR Developer. Do not average their years. If applying for a Dev role, treat them as a Junior.
- If the job requires a SIGNIFICANTLY HIGHER level of seniority for the specific discipline (e.g. asking for 8-10 years, or Executive/VP), YOU MUST REJECT THEM (is_viable: false).
- HOWEVER, if the job is Junior, Entry-Level, or requires LESS experience than the candidate has in that discipline, ACCEPT THEM. Being overqualified or applying to simpler roles is 100% FINE.

STRICT ENGINEERING DOMAIN RULE:
- Even though simpler roles are allowed, THEY MUST BE STRICTLY TECHNICAL ENGINEERING ROLES (Software Development, QA Automation, AI, Data, DevOps, IT Support).
- If the role is non-technical, administrative, customer support, sales, data entry, or generic "Content Reviewer", YOU MUST REJECT IT IMMEDIATELY (is_viable: false). Do not accept clerical jobs just because they are "easy".

ELIGIBILITY RULE (candidate is based in Colombia, remote-only, no visa sponsorship needed/available):
- If the job explicitly requires "U.S. Citizens only", "must be a U.S. citizen", a Green Card, or otherwise restricts eligibility to a specific country's citizens/residents that excludes Colombia, YOU MUST REJECT IT (is_viable: false).
- If the job requires obtaining or holding a security clearance (Confidential, Secret, Top Secret, Public Trust), even if worded as "preferred" rather than "required", YOU MUST REJECT IT (is_viable: false) — clearances require being a U.S. citizen/resident in practice, which the candidate is not.
- If the job explicitly says it does NOT offer visa sponsorship AND also requires being physically located/based in a specific country other than where the candidate is (not simply remote), YOU MUST REJECT IT (is_viable: false).
- Being remote, worldwide, or open to LatAm/international candidates is FINE and should be treated as a positive signal, not a rejection reason.

They do NOT need 100% technical match. If they lack a specific tool, they are viable, just list the tool in 'missing_skills_to_study'.
Analyze the job description against the Candidate's Relevant Experience.

EXAMPLE OUTPUT FOR A ROLE THAT IS TOO SENIOR:
{{
  "is_viable": false,
  "match_percentage": 10,
  "missing_skills_to_study": [],
  "reasoning": "Rejected based on Seniority. Role requires 10 years, but candidate has 4."
}}"""

_EVALUATOR_HUMAN_TEMPLATE = "JOB TITLE: {title}\n\nJOB DESCRIPTION:\n{job_desc}\n\nCANDIDATE MASTER PROFILE (JSON):\n{candidate_exp}"

def evaluate_viability_and_gaps(job_title: str, clean_job_desc: str, candidate_context: str, seniority_context: str) -> ViabilityReport:
    """Evalúa en dos pasos (job_scoring.py): el LLM solo extrae hechos de la JD y Python calcula el match
    contra master_profile.json. El match holístico del LLM (_EVALUATOR_SYSTEM_PROMPT) daba 85% a casi todo.
    Si todos los proveedores fallan por cuota, AllProvidersExhausted sube hasta run_scout_agent()."""
    facts = job_scoring.extract_facts(job_title, clean_job_desc)
    viable, pct, missing, reasoning = job_scoring.score(facts)
    return ViabilityReport(is_viable=viable, match_percentage=pct,
                           missing_skills_to_study=missing, reasoning=reasoning)

from database import save_job

def export_curated_jobs_to_queue(job: dict, report: ViabilityReport):
    """Guarda los trabajos viables en SQLite (jobs.db) para el Agente 3 (Tailor)"""
    gap_str = ", ".join(report.missing_skills_to_study)

    save_job(
        url=job['url'],
        title=job['title'],
        company=job['company'],
        status="Aprobado",
        scraped_content=job['description'],
        match_percentage=report.match_percentage,
        gap_analysis=gap_str
    )

# ==========================================
# 3. ORQUESTACIÓN DEL SCOUT (AGENTE 2)
# ==========================================

class SearchQueries(BaseModel):
    queries: List[str] = Field(description="Lista exacta de 3 términos de búsqueda. Cero texto conversacional.")

_QUERY_SYSTEM_PROMPT = ("You are an AI Job Search Strategist. Read the candidate's JSON profile. "
                         "Determine their seniority based on their experience. "
                         "Return exactly 3 highly targeted job search keywords that fit their exact level and skills. "
                         "IMPORTANT: Return ONLY the raw keywords. NO conversational text, NO greetings.")

def generate_smart_search_queries(profile: dict) -> List[str]:
    """Lee el perfil y genera términos de búsqueda precisos, con el mismo fallback de 4 proveedores."""
    print(f"[INFO] Analizando tu perfil para generar queries de búsqueda exactos...")
    try:
        res = llm_chain.invoke_structured(
            system_prompt=_QUERY_SYSTEM_PROMPT,
            human_template="{profile_str}",
            variables={"profile_str": json.dumps(profile)},
            pydantic_model=SearchQueries,
            temperature=0.7,
        )
        return res.queries[:3]
    except llm_chain.AllProvidersExhausted:
        raise
    except Exception:
        return [profile.get("target_roles", "Software Engineer")]

def run_scout_agent():
    print("======================================================")
    print("Iniciando Scout Agent (Buscador Autónomo 24/7)")
    print("======================================================\n")

    try:
        with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
            profile = json.load(f)
    except Exception:
        print("[ERROR] No se encontró master_profile.json")
        return

    user_seniority = profile.get("seniority_context", "Mid-Level / 2-3 años")
    print(f"[INFO] Contexto de Seniority extraído: {user_seniority}")

    starting_count = len(database.get_approved_jobs()) # Revisar cuántos tenemos ya
    total_viables = starting_count
    new_jobs_goal = int(os.environ.get("SCOUT_NEW_JOBS_GOAL", "40"))
    target_count = starting_count + new_jobs_goal
    max_runtime_hours = float(os.environ.get("SCOUT_MAX_RUNTIME_HOURS", "3"))

    active = llm_chain.active_providers()
    print(f"[INFO] Ya tienes {starting_count} trabajos aprobados. Meta: {new_jobs_goal} vacantes NUEVAS (hasta {target_count} en total), "
          f"tope de {max_runtime_hours}h. Proveedores LLM disponibles ahora: {', '.join(active) if active else 'NINGUNO'} "
          f"(salta automáticamente al siguiente si alguno se queda sin cuota).\n")

    iteration = 1
    start_time = time.time()

    while total_viables < target_count:
        if (time.time() - start_time) > max_runtime_hours * 3600:
            print(f"\n[TIEMPO AGOTADO] Se alcanzó el tope de {max_runtime_hours}h. Deteniendo búsqueda de forma segura.")
            break

        print(f"\n--- [ITERACIÓN {iteration}] Generando nueva estrategia de búsqueda ---")
        try:
            smart_queries = generate_smart_search_queries(profile)
        except llm_chain.AllProvidersExhausted:
            print("\n[CUOTA AGOTADA] Los 4 proveedores (Gemini/Groq/Cerebras/OpenRouter) se quedaron sin cupo. "
                  "Deteniendo el Scout de forma segura.")
            return
        print(f"[TARGET] Nuevas Palabras Clave: {smart_queries}\n")

        for query in smart_queries:
            if total_viables >= target_count:
                break

            print(f"\n>> RASTREANDO: '{query}'")
            raw_jobs = autonomous_job_search(query)

            if not raw_jobs:
                print(f"[INFO] Cero resultados. Pasando a la siguiente...")
                continue

            for i, job in enumerate(raw_jobs, 1):
                if total_viables >= target_count:
                    break

                print(f"[{i}/{len(raw_jobs)}] Evaluando: {job['title']} en {job['company']}")
                clean_desc = clean_job_description(job['description'])

                reason = job_filters.rejection_reason(job, clean_desc)
                if reason:
                    print(f"   [FILTRO] Saltada sin gastar LLM: {reason}")
                    continue

                try:
                    report = evaluate_viability_and_gaps(job['title'], clean_desc, json.dumps(profile), user_seniority)
                except llm_chain.AllProvidersExhausted:
                    print("\n[CUOTA AGOTADA] Los 4 proveedores (Gemini/Groq/Cerebras/OpenRouter) se quedaron sin cupo. "
                          "Deteniendo el Scout de forma segura para no seguir descartando vacantes por error.")
                    return

                # Relajamos el threshold a 50% para permitir que encuentre los 10
                if report.is_viable and report.match_percentage >= 50:
                    gaps_str = ", ".join(report.missing_skills_to_study) if report.missing_skills_to_study else ""

                    is_new = database.save_job(
                        url=job['url'], title=job['title'], company=job['company'],
                        status="Aprobado", scraped_content=job['description'],
                        match_percentage=report.match_percentage, gap_analysis=gaps_str
                    )
                    if is_new:
                        total_viables += 1
                        print(f"   [V] [MATCH VIABLE NUEVO] ({report.match_percentage}%). Guardando. (Progreso: {total_viables}/{target_count})")
                    else:
                        print(f"   [V] [MATCH VIABLE] ({report.match_percentage}%) pero ya estaba en la base de datos. Actualizado, no cuenta como nuevo.")
                else:
                    print(f"   [X] [DESCARTADO] ({report.match_percentage}%). Razón: {report.reasoning}")

        if total_viables < target_count:
            print("\n[PAUSA] Agoté estas palabras clave. Esperando 10 segundos antes de generar nuevas ideas...")
            time.sleep(10)
            iteration += 1

    print(f"\n======================================================")
    print(f" Scout Logró su Meta de {target_count} trabajos viables.")
    print(f"======================================================")

if __name__ == "__main__":
    run_scout_agent()
