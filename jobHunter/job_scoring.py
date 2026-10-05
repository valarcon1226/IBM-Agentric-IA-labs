"""
Evaluación de vacantes en dos pasos (2026-09-25):
  1. El LLM solo EXTRAE hechos objetivos de la JD (JobFacts): si es rol técnico, años pedidos,
     skills obligatorias/deseables, restricciones de país, presencialidad, idiomas.
  2. Python calcula el match de forma determinística contra master_profile.json.

Por qué: pedirle a un modelo chico (qwen3:4b en el homelab) un "match %" holístico daba 85% a
casi todo (75 de 97 vacantes), incluso roles de marketing. Extraer hechos es algo que los modelos
chicos hacen bien, y el puntaje queda igual sin importar qué proveedor de llm_chain respondió.
"""
import json
import re
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

import llm_chain
import profile_paths
import user_settings

# Técnicas y de negocio: jobHunter sirve para cualquier profesión; cada persona elige las suyas (user_settings).
RoleFamily = Literal["ai_engineer", "forward_deployed", "fullstack", "backend", "frontend",
                     "qa_automation", "data", "devops", "other_technical",
                     "sales_business_development", "account_management", "marketing", "operations", "finance",
                     "product", "consulting", "customer_success", "human_resources", "non_technical"]


class JobFacts(BaseModel):
    is_technical_engineering_role: bool = Field(description="True only for hands-on engineering work (software, AI/ML, QA automation, data, DevOps). False for sales, marketing, operations, analyst/admin, support, recruiting, content, consulting-only roles, even if they mention AI or tools.")
    role_family: RoleFamily = Field(description="Closest role family for the job. data = data/BI analysts, data engineers and scientists. "
                                    "sales_business_development = sales, business development, partnerships, commercial roles. "
                                    "account_management = key account / account managers. non_technical = any other non-technical role.")
    required_years: int = Field(description="Minimum years of experience explicitly required. 0 if not stated.")
    seniority_level: Literal["intern", "junior", "mid", "senior", "lead_or_above", "unspecified"] = Field(description="Seniority stated in the title or description.")
    must_have_skills: List[str] = Field(description="Hard skills, tools, platforms or certifications explicitly REQUIRED (e.g. Python, AWS, React, Salesforce, SAP, Power BI, Excel, B2B sales, negotiation). Short plain names as a person would write them (e.g. 'Power BI', 'consultative selling'), never snake_case. Max 12. ALWAYS in English: translate them if the posting is in Spanish (the candidate profile is in English).")
    nice_to_have_skills: List[str] = Field(description="Hard skills, tools or certifications listed as preferred, a plus, or bonus. Short names only, max 8. ALWAYS in English.")
    country_restricted: bool = Field(description="True if it requires citizenship, a security clearance, work authorization or residency in a specific country (e.g. US-only, EU-only), so a remote candidate in Colombia could not be hired. False if the job is located in Colombia or open to LATAM, even if it asks for work authorization in the country of the posting.")
    onsite_or_hybrid_required: bool = Field(description="True if the job requires working on-site or hybrid at an office.")
    required_human_languages: List[str] = Field(description="Human languages (other than English and Spanish) the candidate must speak. Empty if none.")


_EXTRACT_SYSTEM = """You extract facts from a job posting. Do NOT judge whether anyone fits the job.
Only report what the posting actually says; if something is not stated, use 0, false, "unspecified" or an empty list."""

_EXTRACT_HUMAN = "JOB TITLE: {title}\n\nJOB DESCRIPTION:\n{job_desc}"


def extract_facts(title: str, clean_desc: str, allow_local: bool = True, local_only: bool = False) -> JobFacts:
    return llm_chain.invoke_structured(
        system_prompt=_EXTRACT_SYSTEM,
        human_template=_EXTRACT_HUMAN,
        variables={"title": title, "job_desc": clean_desc[:6000]},  # sin el perfil: el prompt es chico
        pydantic_model=JobFacts,
        temperature=0.0,
        allow_local=allow_local,
        local_only=local_only,
    )


# ---------------------------------------------------------------------------
# Perfil del candidato -> vocabulario de skills
# ---------------------------------------------------------------------------

# alias normalizados -> skill canónica. Todo lo que aparezca en el perfil (stacks, skills,
# proyectos) queda como skill que la candidata TIENE.
_ALIASES = {
    "llm": "llm", "llms": "llm", "large language models": "llm", "generative ai": "llm", "genai": "llm",
    "gen ai": "llm", "openai": "llm", "openai api": "llm", "claude": "llm", "anthropic": "llm",
    "gpt": "llm", "prompt engineering": "llm", "ai": "llm", "artificial intelligence": "llm",
    "langchain": "langchain", "langgraph": "langchain", "llamaindex": "langchain",
    "rag": "rag", "retrieval augmented generation": "rag", "retrieval-augmented generation": "rag",
    "vector databases": "vectordb", "vector database": "vectordb", "chromadb": "vectordb", "pinecone": "vectordb",
    "faiss": "vectordb", "weaviate": "vectordb", "qdrant": "vectordb", "pgvector": "vectordb",
    "agents": "agents", "ai agents": "agents", "agentic": "agents", "agentic workflows": "agents",
    "tool calling": "agents", "function calling": "agents", "multi-agent": "agents", "mcp": "agents",
    "python": "python", "sql": "sql", "mysql": "sql", "postgresql": "sql", "postgres": "sql",
    "javascript": "javascript", "js": "javascript", "typescript": "javascript", "ts": "javascript",
    "node": "node", "node.js": "node", "nodejs": "node", "html": "html", "css": "html",
    "react": "react", "react.js": "react", "reactjs": "react", "next.js": "nextjs", "nextjs": "nextjs",
    "wordpress": "wordpress", "elementor": "wordpress", "woocommerce": "wordpress",
    # herramientas de desarrollo asistido por IA (las vacantes las piden por nombre)
    "claude code": "claude code", "codex": "codex", "openai codex": "codex", "gemini cli": "gemini cli",
    "copilot": "copilot", "github copilot": "copilot", "antigravity": "antigravity", "cursor": "cursor",
    "ai-assisted development tools": "ai dev tools", "ai coding assistants": "ai dev tools",
    "ai coding tools": "ai dev tools", "ai-assisted development": "ai dev tools",
    # nombres genéricos que los gigs usan para lo que ya hace (agentes, n8n, automatizaciones)
    "chatbot": "agents", "chatbots": "agents", "ai chatbot": "agents", "chatbot development": "agents",
    "ai chatbot development": "agents", "automation": "n8n", "workflow automation": "n8n",
    "process automation": "n8n", "business automation": "n8n",
    "django": "django", "fastapi": "fastapi", "flask": "fastapi", "rest": "api", "rest api": "api",
    "rest apis": "api", "api": "api", "apis": "api", "webhooks": "api", "postman": "api",
    "docker": "docker", "git": "git", "github": "git", "elasticsearch": "elasticsearch",
    "selenium": "selenium", "playwright": "playwright", "puppeteer": "playwright",
    "test automation": "qa", "qa automation": "qa", "automated testing": "qa", "regression testing": "qa",
    "qa": "qa", "testing": "qa", "api testing": "qa", "pytest": "qa", "jira": "jira", "scrum": "jira",
    "agile": "jira", "n8n": "n8n", "zapier": "n8n", "make": "n8n", "web scraping": "scraping",
    "beautifulsoup": "scraping", "scraping": "scraping", "azure": "azure", "power bi": "powerbi",
    "vba": "vba", "machine learning": "ml", "ml": "ml", "predictive modeling": "ml",
    "ci/cd": "cicd", "github actions": "cicd", "cicd": "cicd",
    "chroma": "vectordb", "embeddings": "vectordb",
    # básicos de Python que el modelo lista como "obligatorios" y nunca aparecen literales en el perfil
    "json": "python", "regex": "python", "regular expressions": "python", "pandas": "python",
    "google sheets": "vba", "excel": "vba", "google apps script": "javascript",
    "csv": "python", "pdf": "python", "http": "api", "jwt": "api", "oauth": "api", "websocket": "api",
    "websockets": "api", "email": "api", "smtp": "api", "linux": "docker", "vps": "docker",
}

# skills vecinas: tener una da crédito parcial (0.5) por la otra
_ADJACENT = {
    "aws": {"azure"}, "gcp": {"azure"}, "cypress": {"playwright", "selenium"},
    "vue": {"react"}, "angular": {"react"}, "java": {"python"}, "go": {"python"},
    "kubernetes": {"docker"}, "pytorch": {"ml"}, "tensorflow": {"ml"}, "mongodb": {"sql"},
    "webflow": {"wordpress"}, "wix": {"wordpress"}, "shopify": {"wordpress"},
    "nlp": {"llm"}, "natural language processing": {"llm"},
    "cursor": {"claude code", "copilot"},  # mismo tipo de herramienta que ya usa
}

# años aproximados por disciplina, según el seniority_context del perfil

# El tipo de rol es un REQUISITO, no suma puntos: fuera de estas familias la vacante se descarta.
# (Las variantes — ML/LLM/AI full-stack engineer, solutions/deployment engineer, SDET — el
# extractor ya las clasifica dentro de estas familias.)

_SPOKEN_OK = {"english", "ingles", "inglés", "spanish", "español", "espanol"}


def _norm_skill(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", (s or "").lower()).strip(" .-")
    if s in _ALIASES:
        return _ALIASES[s]
    # "Fast API", "Lang-Graph", "Chroma DB" -> "fastapi", "langgraph", "chromadb"
    return _ALIASES.get(re.sub(r"[\s\-_]+", "", s), s)


_candidate_cache: Optional[set] = None


def candidate_skills() -> set:
    global _candidate_cache
    if _candidate_cache is None:
        with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
            p = json.load(f)
        text = json.dumps(p, ensure_ascii=False).lower()
        # cualquier alias que aparezca literalmente en el perfil cuenta como skill que tiene
        _candidate_cache = {canon for alias, canon in _ALIASES.items()
                            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text)}
    return _candidate_cache


_profile_text_cache: Optional[str] = None


def _profile_text() -> str:
    global _profile_text_cache
    if _profile_text_cache is None:
        with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
            _profile_text_cache = json.dumps(json.load(f), ensure_ascii=False).lower()
    return _profile_text_cache


def _skill_credit(skill: str, have: set) -> float:
    s = _norm_skill(skill)
    if s in have:
        return 1.0
    # fuera del vocabulario (Salesforce, SAP, negociación...): vale si aparece tal cual en el perfil
    raw = re.sub(r"\(.*?\)", "", (skill or "").lower()).replace("_", " ").strip(" .-")  # "power_bi" -> "power bi"
    if len(raw) >= 3 and re.search(rf"(?<![a-z]){re.escape(raw)}(?![a-z])", _profile_text()):
        return 1.0
    # habilidades de negocio cambian de forma (negotiate/negotiation, selling/sales): por raíz de cada palabra
    # ponytail: raíz = primeras 5 letras; cambiar por un stemmer real si da falsos positivos
    # solo palabras largas: con cortas la raíz da falsos positivos ("java" dentro de "javascript")
    words = [w for w in re.findall(r"[a-z0-9+#]+", raw) if len(w) >= 6]
    if words:
        hits = sum(1 for w in words if re.search(rf"(?<![a-z]){re.escape(w[:5])}", _profile_text()))
        if hits == len(words):
            return 1.0
        if hits * 2 >= len(words):
            return 0.5
    if any(n in have for n in _ADJACENT.get(s, ())):
        return 0.5
    return 0.0


def score(facts: JobFacts) -> Tuple[bool, int, List[str], str]:
    """(is_viable, match_percentage, missing_skills, reasoning) — determinístico."""
    if facts.role_family not in user_settings.get("role_families"):
        return False, 5, [], f"Rol {facts.role_family}: no es de los tipos de rol que buscas."
    if facts.country_restricted:
        return False, 10, [], "Restringido a ciudadanos/residentes de otro país (o pide clearance)."
    if facts.onsite_or_hybrid_required and user_settings.get("remote_only"):
        return False, 10, [], "Requiere presencialidad/híbrido y el perfil es solo remoto."
    langs = [l for l in facts.required_human_languages if l.strip().lower() not in _SPOKEN_OK]
    if langs:
        return False, 10, [], f"Pide idioma(s) que no habla a nivel laboral: {', '.join(langs)}."
    if facts.seniority_level in ("senior", "lead_or_above") and facts.required_years >= 5:
        return False, 15, [], f"Rol {facts.seniority_level} con {facts.required_years}+ años."

    have = candidate_skills()
    # el modelo tiende a meter 12-22 "obligatorias" (todo lo que nombra la JD); las primeras suelen
    # ser las centrales, y con listas largas la cobertura se hundía aunque encajara bien
    must = facts.must_have_skills[:6]
    nice = facts.nice_to_have_skills[:8]
    must_cov = (sum(_skill_credit(s, have) for s in must) / len(must)) if must else 0.7
    nice_cov = (sum(_skill_credit(s, have) for s in nice) / len(nice)) if nice else 0.5
    missing = [s for s in must + nice if _skill_credit(s, have) < 1.0]

    years = user_settings.get("years_by_family")  # años reales por disciplina (search_settings.json de la persona)
    cand_years = years.get(facts.role_family, years.get("default", 2))
    gap_years = max(0, facts.required_years - cand_years)
    if gap_years >= 3:
        return False, 20, missing, f"Pide {facts.required_years} años; el perfil tiene ~{cand_years} en esta disciplina."
    seniority_penalty = 12 * gap_years + (10 if facts.seniority_level == "senior" else 0)

    # 100% técnico: requisitos de la vacante vs lo que ella sabe. Sin deseables, cuentan solo las obligatorias.
    # Sin skills extraídas no hay con qué medir: 50 = visible sin CV (antes quedaba en 70 y generaba CV a ciegas).
    if must and nice:
        tech = 0.8 * must_cov + 0.2 * nice_cov
    elif must or nice:
        tech = must_cov if must else nice_cov
    else:
        tech = 0.5
    pct = round(100 * tech) - seniority_penalty
    pct = max(0, min(100, pct))
    reasoning = (f"{facts.role_family}; obligatorias cubiertas {must_cov:.0%} de {len(must)}, "
                 f"deseables {nice_cov:.0%}; pide {facts.required_years} años ({facts.seniority_level}).")
    return True, pct, missing, reasoning  # qué hacer según el % lo decide el scout (70+ CV, 40-69 visible, <40 oculta)
