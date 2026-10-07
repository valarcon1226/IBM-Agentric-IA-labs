import os
import re
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

import database
import llm_chain
import job_filters
import job_scoring
from freelance_scraper import fetch_all_gigs

# ==========================================
# AGENTE: Freelance Hunter
# Busca proyectos PEQUEÑOS que la candidata pueda hacer sola y que le dejen las dos cosas que
# busca: plata y una pieza mostrable en el portafolio (agente de IA, automatización, scraper,
# chatbot/RAG, suite de QA, dashboard). Distinto del job hunter (9-5): acá es una tarea puntual.
# ==========================================

MIN_BUDGET_USD = int(os.environ.get("FREELANCE_MIN_BUDGET_USD", "50"))
# 2026-10-02: también le interesan proyectos grandes (productos enteros, varias semanas): tope alto
MAX_BUDGET_USD = int(os.environ.get("FREELANCE_MAX_BUDGET_USD", "50000"))
MIN_HOURLY_USD = int(os.environ.get("FREELANCE_MIN_HOURLY_USD", "15"))
MAX_COMPETITION = int(os.environ.get("FREELANCE_MAX_BIDS", "60"))
MIN_PORTFOLIO_VALUE = int(os.environ.get("FREELANCE_MIN_PORTFOLIO_VALUE", "5"))
MAX_EVALS_PER_RUN = int(os.environ.get("FREELANCE_MAX_EVALS", "80"))  # tope de llamadas al modelo local por corrida

_BLOCKLIST = re.compile(
    r"\b(crypto|blockchain|web3|nft|casino|gambling|betting|binary options?|quotex|pocket option|adult|onlyfans|commission|"
    r"cold call(er|ing)?|appointment setters?|deal closers?|closers?|sales reps?|telemarketing|"
    r"lead generation|seo backlinks?|unpaid|equity only|write (my|an?) (essay|thesis|assignment)|homework|"
    r"data entry|transcri\w*|copy[ -]?paste|leads list|ad views|auto[ -]?clicker|fake (reviews?|followers|views)|"
    r"(pdf|word|excel)[ -]to[ -](pdf|word|excel)|email campaign|newsletter|"
    # automatización industrial/hardware: la skill "Automation" de Freelancer trae mucho de esto
    r"plcs?|pcb|scada|siemens|tia portal|mechatronics?|arduino|circuit breaker|hmi|"
    r"cnc|fanuc|haas|g-?code|crestron|robotics?|robot arm|kuka)\b",
    re.IGNORECASE,
)

# La búsqueda de Freelancer es laxa (con "python automation" devuelve fotografía o grabación de
# voz). Sin al menos una de estas señales técnicas, ni vale la pena gastar una llamada al LLM.
_TECH_SIGNALS = re.compile(
    r"python|automat|scrap|crawler|\bapi\b|\bbots?\b|\bai\b|\bllm|gpt|openai|claude|gemini|agent|"
    r"n8n|zapier|make\.com|playwright|selenium|cypress|\bqa\b|\btest(ing|s)?\b|dashboard|react|"
    r"fastapi|django|flask|\bsql\b|postgres|mongodb|\bscripts?\b|integrat|pipeline|\brag\b|langchain|"
    r"chatbot|webhook|\betl\b|excel (macro|automation)|google sheets|"
    # páginas web
    r"website|web ?site|web ?page|landing|wordpress|webflow|shopify|wix|elementor|html|css|javascript|"
    r"next\.?js|frontend|front-end|full ?stack|p[aá]gina web|sitio web|tienda (online|virtual)",
    re.IGNORECASE,
)

MAX_BOUNTIES_PER_REPO = 3  # algunos repos publican decenas de bounties idénticos (parecen granjas)


def prefilter_reason(gig: Dict) -> Optional[str]:
    """Descartes baratos, sin LLM. None si el gig pasa."""
    text = f"{gig['title']} {gig['description']}"
    if _BLOCKLIST.search(text):
        return f"fuera de rubro ({_BLOCKLIST.search(text).group(0)})"
    if not _TECH_SIGNALS.search(f"{text} {' '.join(gig.get('skills', []))}"):
        return "no es un proyecto técnico"
    declared = (gig.get("language") or "").lower()[:2]  # Freelancer lo informa ("en", "id", ...)
    if declared and declared not in job_filters.allowed_langs():
        return f"idioma: {declared}"
    lang = job_filters.detect_language(text)
    if lang and lang not in job_filters.allowed_langs():
        return f"idioma: {lang}"
    kind, lo, hi = gig.get("project_type"), gig.get("budget_min_usd", 0), gig.get("budget_max_usd", 0)
    if kind == "hourly" and hi and hi < MIN_HOURLY_USD:
        return f"paga poco (${hi}/h)"
    if kind in ("fixed", "bounty"):
        if hi < MIN_BUDGET_USD:
            return f"presupuesto muy bajo (${hi})"
        if lo > MAX_BUDGET_USD:
            return f"proyecto demasiado grande (${lo}+)"
    if gig.get("competition", 0) > MAX_COMPETITION:
        return f"demasiada competencia ({gig['competition']})"
    return None



# Evaluación en 2 pasos, igual que job_scoring.py para vacantes (2026-09-25): el LLM solo EXTRAE
# hechos del gig (sin el perfil -> ~500 tokens) y Python calcula match y valor de portafolio.
# Antes el LLM daba un juicio holístico con el perfil completo (~3.5k tokens): Ollama aprobaba todo
# con 85%, así que freelance quedó solo-APIs y casi nunca llegaba a evaluar (9 de 343 gigs).
# Extraer hechos lo hace bien el modelo local, así que ahora la corrida nunca se frena por cupo.

GigCategory = Literal["ai_agent", "chatbot_rag", "automation_integration", "web_scraping", "qa_testing",
                      "data_pipeline", "dashboard_webapp", "website", "full_product", "bug_fix_maintenance",
                      "non_technical", "other"]


class GigFacts(BaseModel):
    category: GigCategory = Field(description="What the client actually wants built. website = a website, landing page or small online store (WordPress, Webflow, Shopify, React/Next.js), including redesigns. full_product = a whole SaaS/marketplace/app from scratch. bug_fix_maintenance = fixing or tweaking an existing system. non_technical = sales, marketing, design, writing, admin, even if it mentions AI.")
    required_skills: List[str] = Field(description="Frameworks, platforms or services the gig explicitly needs (e.g. Python, n8n, React, OpenAI, HubSpot). Short names, max 8. Do NOT list human languages, file formats (CSV, PDF), operating systems, standard-library modules or generic words like 'automation' or 'report'.")
    scope_is_clear: bool = Field(description="True if the post says concretely what must be delivered. False for vague, one-line or spammy posts.")
    estimated_days: int = Field(description="Realistic working days for one developer to deliver it.")
    deliverable: str = Field(description="One sentence, in Spanish: what would be built, phrased as a portfolio item.")


class GigFitReport(BaseModel):
    category: str = ""
    missing_skills: List[str] = []
    is_good_fit: bool
    match_percentage: int
    portfolio_value: int
    estimated_days: int
    deliverable: str
    reasoning: str


_EXTRACT_SYSTEM = """You extract facts from a freelance gig post. Do NOT judge whether anyone fits it.
Only report what the post says; if something is not stated, make the most conservative guess."""

_EXTRACT_HUMAN = "PLATFORM: {platform}\nTITLE: {title}\nDESCRIPTION:\n{description}"

# 0-10: qué tan mostrable queda como pieza de portafolio
PORTFOLIO_VALUE = {"ai_agent": 9, "chatbot_rag": 9, "automation_integration": 8, "web_scraping": 7,
                   "qa_testing": 7, "data_pipeline": 7, "dashboard_webapp": 7, "website": 8, "other": 4,
                   "bug_fix_maintenance": 3, "full_product": 7, "non_technical": 0}
MAX_GIG_DAYS = int(os.environ.get("FREELANCE_MAX_DAYS", "90"))


def _budget_str(gig: Dict) -> str:
    lo, hi, kind = gig.get("budget_min_usd", 0), gig.get("budget_max_usd", 0), gig.get("project_type", "")
    if not hi:
        return "no indicado"
    rng = f"${lo}" if lo == hi else f"${lo}-{hi}"
    return f"{rng} USD/h" if kind == "hourly" else f"{rng} USD ({kind})"


def extract_gig_facts(gig: Dict) -> GigFacts:
    """Solo modelo local: extraer hechos de cientos de gigs es volumen, y la nube se agotaba en horas.
    AllProvidersExhausted (Ollama caído) sube hasta main()."""
    return llm_chain.invoke_structured(
        system_prompt=_EXTRACT_SYSTEM,
        human_template=_EXTRACT_HUMAN,
        variables={"platform": gig["platform"], "title": gig["title"], "description": gig["description"][:1500]},
        pydantic_model=GigFacts,
        temperature=0.0,
        local_only=True,
    )


def score_gig(gig: Dict, facts: GigFacts) -> GigFitReport:
    """Puntaje determinístico: cobertura de skills (vocabulario de job_scoring) + valor de portafolio."""
    pv = PORTFOLIO_VALUE[facts.category]
    if gig["platform"] == "GitHub Bounty" and pv:
        pv = min(10, pv + 3)  # un PR mergeado en un repo público es portafolio verificable

    def report(ok: bool, pct: int, why: str) -> GigFitReport:
        return GigFitReport(category=facts.category, is_good_fit=ok, match_percentage=pct, portfolio_value=pv,
                            estimated_days=facts.estimated_days, deliverable=facts.deliverable, reasoning=why)

    if facts.category == "non_technical":
        return report(False, 5, "No es un proyecto técnico.")
    if facts.estimated_days > MAX_GIG_DAYS:
        return report(False, 15, f"Demasiado grande (~{facts.estimated_days} días).")

    have = job_scoring.candidate_skills()
    skills = facts.required_skills[:6]
    cov = (sum(job_scoring._skill_credit(s, have) for s in skills) / len(skills)) if skills else 0.6
    missing = [s for s in skills if job_scoring._skill_credit(s, have) < 1.0]
    pct = round(100 * (0.7 * cov + 0.3 * pv / 10)) - (0 if facts.scope_is_clear else 15)
    pct = max(0, min(100, pct))
    why = (f"{facts.category}; " + (f"skills cubiertas {cov:.0%} de {len(skills)}" if skills else "sin skills declaradas")
           + (f" (falta: {', '.join(missing)})" if missing else "")
           + ("" if facts.scope_is_clear else "; alcance poco claro"))
    r = report(pct >= 50, pct, why)
    r.missing_skills = missing
    return r


def evaluate_gig_fit(gig: Dict) -> GigFitReport:
    return score_gig(gig, extract_gig_facts(gig))


def main():
    print("====================================================")
    print(" FREELANCE HUNTER AGENT - Proyectos pequeños: plata + portafolio")
    print("====================================================\n")

    try:
        job_scoring.candidate_skills()  # lee master_profile.json una vez
    except Exception:
        print("[ERROR] No se encontró master_profile.json")
        return

    database.init_db()

    all_gigs = fetch_all_gigs()
    if not all_gigs:
        print("[-] No se pudo recolectar data de mercado. Abortando.")
        return

    known_urls = database.get_known_gig_urls()
    new_gigs = [g for g in all_gigs if g["url"] not in known_urls]
    print(f"\n[!] {len(all_gigs)} gigs vistos, {len(new_gigs)} son nuevos (no evaluados antes).")

    to_evaluate = []
    per_repo = {}
    for gig in new_gigs:
        reason = prefilter_reason(gig)
        if not reason and gig["platform"] == "GitHub Bounty":
            repo = gig["title"].split("]")[0].lstrip("[")
            per_repo[repo] = per_repo.get(repo, 0) + 1
            if per_repo[repo] > MAX_BOUNTIES_PER_REPO:
                reason = f"repo con demasiados bounties ({repo})"
        if reason:
            # se guarda igual para no volver a mirarlo en la próxima corrida
            database.save_gig(url=gig["url"], platform=gig["platform"], title=gig["title"],
                              description=gig["description"], status="Descartado",
                              match_percentage=0, reasoning=f"[Filtro] {reason}",
                              posted_at=gig.get("posted_at"), closes_at=gig.get("closes_at"))
        else:
            to_evaluate.append(gig)
    # primero los que tienen menos competencia (más chance real de ganarlos); el resto queda sin
    # guardar y se reconsidera en la próxima corrida
    passed = len(to_evaluate)
    to_evaluate.sort(key=lambda g: g.get("competition", 0))
    to_evaluate = to_evaluate[:MAX_EVALS_PER_RUN]
    print(f"[i] {len(new_gigs) - passed} descartados sin LLM (presupuesto/rubro/idioma/competencia), "
          f"{passed} pasan el filtro, se evalúan {len(to_evaluate)} en esta corrida.")
    print(f"[i] Proveedores LLM disponibles ahora: {', '.join(llm_chain.active_providers())}\n")

    new_applicable = []
    for i, gig in enumerate(to_evaluate, 1):
        print(f"[{i}/{len(to_evaluate)}] Evaluando: {gig['title'][:60]} ({gig['platform']}, {_budget_str(gig)})")
        try:
            fit = evaluate_gig_fit(gig)
        except llm_chain.AllProvidersExhausted:
            print(f"\n[CUOTA AGOTADA] Todos los proveedores fallaron. Deteniendo de forma segura con lo "
                  f"evaluado hasta ahora ({len(new_applicable)} aplicables nuevos).")
            break
        applicable = (fit.is_good_fit and fit.match_percentage >= 50
                      and fit.portfolio_value >= MIN_PORTFOLIO_VALUE)
        status = "Aplicable" if applicable else "Descartado"
        # la tabla no tiene columnas para esto: va al inicio del reasoning, que el dashboard ya muestra
        summary = (f"[Portafolio {fit.portfolio_value}/10 · ~{fit.estimated_days} días · {_budget_str(gig)} · "
                   f"{gig.get('competition', '?')} propuestas] Entregable: {fit.deliverable} — {fit.reasoning}")
        database.save_gig(
            url=gig["url"], platform=gig["platform"], title=gig["title"],
            description=gig["description"], status=status,
            match_percentage=fit.match_percentage, reasoning=summary, category=fit.category,
            missing_skills=", ".join(fit.missing_skills), posted_at=gig.get("posted_at"), closes_at=gig.get("closes_at"),
        )
        mark = "[V] APLICABLE" if applicable else "[X] Descartado"
        print(f"   {mark} ({fit.match_percentage}%, portafolio {fit.portfolio_value}/10): {fit.deliverable}")
        if applicable:
            new_applicable.append(gig)

    total_applicable = len(database.get_applicable_gigs())
    print(f"\n====================================================")
    print(f" Listo. {len(new_applicable)} gigs nuevos aplicables esta corrida.")
    print(f" Total histórico de gigs aplicables en jobs.db: {total_applicable}")
    print(f"====================================================")


if __name__ == "__main__":
    main()
