"""
Clasificación de vacantes en 3 arquetipos de rol, y templates de CV base (uno por arquetipo)
para no regenerar el CV completo desde cero en cada vacante. Ver generate_archetype_templates.py
para (re)generar los 3 templates, y tailor_agent.py para cómo se usan.
"""
import json
import os
import re

ARCHETYPES = ["ai_engineer", "forward_deployed_engineer", "qa_automation"]

ARCHETYPE_LABELS = {
    "ai_engineer": "AI Engineer",
    "forward_deployed_engineer": "Forward Deployed Engineer",
    "qa_automation": "QA Automation Engineer (Mid-level)",
}

# JDs GENÉRICAS (no vacantes reales) — se usan UNA sola vez para generar cada template base
# corriendo el mismo generador+revisor de siempre. Si el perfil del candidato cambia mucho,
# corré generate_archetype_templates.py de nuevo para refrescarlos.
ARCHETYPE_GENERIC_JD = {
    "ai_engineer": (
        "We are looking for an AI Engineer to design, build and ship production LLM-powered "
        "applications: agentic workflows, RAG pipelines, tool-calling systems, evaluation "
        "harnesses, and integrations with vector databases and cloud APIs. Strong Python, "
        "experience with LangChain/LLM SDKs, prompt engineering, and shipping reliable AI "
        "features end to end."
    ),
    "forward_deployed_engineer": (
        "We are looking for a Forward Deployed Engineer to work directly with enterprise "
        "clients, translating ambiguous business problems into scoped technical solutions, "
        "building and deploying AI agents/integrations in production, and owning delivery "
        "end to end — architecture, implementation, client communication, and iteration based "
        "on real usage."
    ),
    "qa_automation": (
        "We are looking for a mid-level QA Automation Engineer to design, build and maintain "
        "automated test suites (UI, API, regression), integrate tests into CI/CD pipelines, "
        "and partner with developers to keep release quality high. Experience with automation "
        "frameworks (Playwright/Cypress/Selenium), test strategy, and AI-assisted testing tools "
        "is a plus."
    ),
}


# Con qué identidad abre el professional_summary de cada template. Sin esto el generador tomaba
# el seniority_context ("Mid-level QA/Automation Engineer...") como apertura también para los
# roles de IA, y el CV se leía como de QA aunque la vacante fuera AI/FDE.
ARCHETYPE_POSITIONING = {
    "ai_engineer": (
        "The professional_summary MUST open by presenting the candidate as an AI Full Stack Engineer "
        "who designs and ships production multi-agent LLM systems. Her QA Automation background goes "
        "AFTER that, framed as a differentiator (rigorous testing/validation of agent inputs and outputs), "
        "never as her main identity."
    ),
    "forward_deployed_engineer": (
        "The professional_summary MUST open by presenting the candidate as an AI Full Stack Engineer "
        "who takes ambiguous business problems to deployed AI agents/integrations in production. Her QA "
        "Automation background goes AFTER that, framed as a differentiator (reliability and validation "
        "discipline in client deployments), never as her main identity."
    ),
    "qa_automation": (
        "The professional_summary MUST open by presenting the candidate as a mid-level QA Automation "
        "Engineer; her AI/agentic work is a differentiator (AI-assisted testing, test agents)."
    ),
}


def classify_archetype(job_title: str) -> str:
    """Clasificador gratis (sin LLM) por palabras clave del título. Basado en los patrones
    reales observados en jobs.db: 'Forward Deployed...' siempre es FDE; títulos con señal
    explícita de QA/Testing van a QA; todo lo demás (AI Engineer, Full Stack AI, Data Engineer,
    Software Engineer genérico, AI Native Builder...) cae en el catch-all 'ai_engineer', que es
    el perfil primario del candidato."""
    t = (job_title or "").lower().replace("-", " ")

    if "forward deployed" in t:
        return "forward_deployed_engineer"

    # 2026-10-02: "SDET", "QA Engineer", "Automatizador de Pruebas"... caían en ai_engineer
    qa_signals = ["qa automation", "test automation", "test engineer", "automation tester", "software test",
                  "sdet", "engineer in test", "quality engineer", "quality assurance", "tester", "pruebas",
                  "automatizador"]
    if any(sig in t for sig in qa_signals) or re.search(r"\bqa\b|\bqe\b", t):
        return "qa_automation"

    if "automation engineer" in t and "ai" not in t:
        return "qa_automation"

    return "ai_engineer"


def _templates_dir() -> str:
    # con perfil activo (main.py <nombre>) cada persona tiene los suyos; los de la raíz son de Valentina
    import profile_paths
    return profile_paths.resolve("archetype_templates")


def template_path(archetype: str) -> str:
    return os.path.join(_templates_dir(), f"{archetype}.json")


def load_template(archetype: str):
    """Devuelve el dict del template (professional_summary + experience), o None si todavía
    no se generó (corré generate_archetype_templates.py)."""
    path = template_path(archetype)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_template(archetype: str, profile_dict: dict):
    os.makedirs(_templates_dir(), exist_ok=True)
    with open(template_path(archetype), "w", encoding="utf-8") as f:
        json.dump(profile_dict, f, ensure_ascii=False, indent=2)


def needs_adjustment(template: dict, gap_analysis: str, master_json_str: str) -> bool:
    """True solo si el gap_analysis trae una keyword que ella SÍ tiene (aparece en el master
    profile) pero el template no menciona — ahí un ajuste liviano suma. El gap_analysis lista
    skills que le FALTAN: esas no se pueden meter sin mentir (el revisor las rechaza y se
    terminaba mandando el template igual, tras gastar 2-5 llamadas), así que no disparan ajuste."""
    if not gap_analysis or not gap_analysis.strip():
        return False
    haystack = (
        template.get("professional_summary", "") + " " +
        " ".join(ach for exp in template.get("experience", []) for ach in exp.get("achievements", []))
    ).lower()
    master = master_json_str.lower()
    keywords = [g.strip().lower() for g in gap_analysis.split(",") if g.strip()]
    return any(kw in master and kw not in haystack for kw in keywords)
