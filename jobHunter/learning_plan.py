"""Plan de aprendizaje: junta los gaps de las vacantes visibles agrupados por SKILL + TIPO DE ROL (la misma skill se
estudia distinto según el rol: Java para QA = Selenium/TestNG, Java para IA = Spring AI/LangChain4j), ordena los grupos
por cuántas vacantes desbloquean y genera para cada uno qué aprender y cuántas horas toma llegar al mínimo viable de una
prueba técnica, a partir de CÓMO lo piden esas vacantes (las frases de la descripción que mencionan la skill).
Escribe learning_plan.json, que el dashboard muestra en la pestaña "Aprender".
Uso: python learning_plan.py (también lo llama trend_spotter_agent cada hora)."""
import datetime
import json
import os
import re
import sqlite3
from collections import defaultdict
from typing import List

from pydantic import BaseModel, Field

import job_scoring
import llm_chain
import profile_paths
from archetypes import ARCHETYPE_LABELS, classify_archetype
from job_scraper import clean_job_description

TOP_PER_ROLE = 12
CLOUD_TOP = 15        # los grupos más pedidos se generan con el modelo grande; el resto con el local
SNIPPETS_PER_GROUP = 8
OUTPUT = profile_paths.resolve("learning_plan.json")  # en la carpeta del perfil (el dashboard lo lee ahí)
# Freelance cuenta como un "rol" más: skills que faltan en gigs, ordenadas por demanda x pago promedio
ROLE_LABELS = {**ARCHETYPE_LABELS, "freelance": "Freelance"}
_BUDGET = re.compile(r"\$(\d+)(?:-(\d+))? USD")
CURATED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_estimates_curated.json")


class SkillEstimate(BaseModel):
    hours_to_mvp: int = Field(description="Horas de estudio + práctica para pasar una prueba técnica básica de esta skill PARA ESTE ROL, dado el perfil")
    what_to_learn: List[str] = Field(description="3 a 6 temas concretos, lo mínimo para la prueba técnica de este rol, en orden")
    practice_project: str = Field(description="Un mini proyecto de 1-2 tardes que demuestre la skill en este rol y sirva de portafolio")
    free_resources: List[str] = Field(description="2 a 3 recursos gratis (documentación oficial, curso o tutorial conocido)")


_SYSTEM = """Eres mentor técnico. Estimas cuánto le toma a ESTA candidata llegar al MÍNIMO VIABLE en una skill para pasar
la prueba técnica de un TIPO DE ROL concreto (no dominio total). Lo que debe aprender depende de cómo usan la skill esas
vacantes: básate en las frases de las descripciones. Ten en cuenta lo que ya sabe: si se parece a algo que domina, el
tiempo es menor. Sé realista y concreto. Responde en español.

MÍNIMO VIABLE = lo justo para resolver una prueba técnica o defenderlo en la entrevista, no un curso completo.
Ya domina: Python, LangGraph y sistemas multi-agente, RAG, Docker, FastAPI, GitHub Actions, Playwright/Selenium, SQL.
Referencias de calibración (respétalas):
- Framework parecido a algo que domina (CrewAI, AutoGen, Cypress, LangChain): 4-10 h
- Herramienta o plataforma nueva con conceptos que ya conoce (CI/CD, desplegar un contenedor en la nube, MCP): 4-10 h
- Plataforma amplia nueva (AWS, Azure, Kubernetes, Appium): 12-25 h
- Lenguaje nuevo (Java, Go, C#) llevado a lo que pide el rol: 30-45 h
Nunca más de 50 h."""
_HUMAN = ("PERFIL DE LA CANDIDATA:\n{profile}\n\nTIPO DE ROL: {role}\nSKILL QUE LE FALTA: {skill}\n"
          "PUESTOS: {titles}\nCÓMO LA PIDEN LAS VACANTES:\n{snippets}")


# Práctica gratis en la web para cada grupo (INDEX 0 no se puede instalar en el PC del trabajo).
# ponytail: mapeo por palabras clave de la skill; agregar reglas si aparece un tipo de skill nuevo.
_DSA = "NeetCode.io: 1 problema al día del roadmap gratis (intenta 20 min antes de ver la solución)"
_SD = "System Design Primer (github.com/donnemartin/system-design-primer)"
_PRACTICE_RULES = [
    (r"crewai|autogen|langgraph|langchain|llamaindex|agent|mcp|rag|llm|openai|claude|gemini|hugging ?face|fine-tun|prompt|vector|embedding",
     ["DeepLearning.AI (gratis): el curso corto de este framework o tema",
      _SD + ": colas, reintentos y costos, aplicado a un sistema multi-agente",
      "Entrevista simulada con el prompt de abajo: explica en voz alta tu mini proyecto"]),
    (r"aws|gcp|azure|cloud|kubernetes|docker|cicd|jenkins|terraform|devops|deployment|serverless|lambda",
     [_SD + ": despliegue, escalado, balanceo y observabilidad",
      "Entrevista simulada con el prompt de abajo: que pregunten cómo desplegaste tu proyecto"]),
    (r"java|go|golang|typescript|javascript|c#|kotlin|rust|scala",
     [_DSA.replace("1 problema al día", "1 problema al día en este lenguaje"),
      "Entrevista simulada con el prompt de abajo"]),
    (r"pytorch|tensorflow|scikit|machine learning|ml|statistic|numpy|pandas",
     ["DeepLearning.AI (gratis): fundamentos de ML", _DSA]),
]


def web_practice(skill: str, role: str) -> List[str]:
    """Práctica gratis en la web para este grupo. Siempre termina con la entrevista simulada."""
    for pattern, steps in _PRACTICE_RULES:
        if re.search(pattern, skill, re.IGNORECASE):
            return steps
    if role == "qa_automation":
        return ["Test Automation University (gratis): el curso de esta herramienta",
                "Entrevista simulada con el prompt de abajo"]
    return [_DSA, "Entrevista simulada con el prompt de abajo"]


def interview_prompt(skill: str, role_label: str) -> str:
    """Prompt para pegar en Claude o Gemini y practicar la entrevista técnica de este grupo."""
    return (f"Actúa como entrevistador técnico de una empresa que contrata un {role_label} remoto nivel mid. "
            f"Hazme una entrevista técnica centrada en {skill}, como en una prueba real: una pregunta a la vez, "
            "empieza por conceptos y sube a un caso práctico de diseño o código. No me des la respuesta: si me "
            "trabo, dame una pista corta. Repregunta cuando mi respuesta sea vaga. Al final (después de unas 8 "
            "preguntas) califícame de 1 a 10 en conocimiento, claridad y criterio práctico, y dime exactamente "
            "qué repasar. Empieza con la primera pregunta.")


def _snippets(text: str, raw_skill: str) -> List[str]:
    """Frases de la descripción que mencionan la skill (cómo la usa el rol)."""
    if not raw_skill:
        return []
    pat = re.compile(re.escape(raw_skill), re.IGNORECASE)
    return [s.strip()[:220] for s in re.split(r"(?<=[.!?\n])\s+", text) if pat.search(s)][:2]


def gaps_by_group(conn) -> dict:
    """(skill normalizada, arquetipo) -> {'jobs': [...], 'snippets': [...]} de vacantes visibles sin aplicar."""
    groups = defaultdict(lambda: {"jobs": [], "snippets": []})
    # los gaps guardados pueden ser viejos (de antes de ampliar el perfil o el vocabulario): se revisan
    # contra el perfil actual y se ignora lo que ya sabe
    have = job_scoring.candidate_skills()
    rows = conn.execute("SELECT id, title, company, match_percentage, gap_analysis, scraped_content FROM jobs "
                        "WHERE applied_at IS NULL AND status IN ('CV Generado', 'Aprobado', 'Match Insuficiente')").fetchall()
    for jid, title, company, match, gaps, content in rows:
        role = classify_archetype(title)
        text = clean_job_description(content or "")
        for raw in (gaps or "").split(","):
            skill = job_scoring._norm_skill(raw)
            if not skill or job_scoring._skill_credit(raw, have) >= 1.0:
                continue
            g = groups[(skill, role)]
            g["jobs"].append({"id": jid, "title": title, "company": company, "match": match or 0})
            if len(g["snippets"]) < SNIPPETS_PER_GROUP:
                g["snippets"] += _snippets(text, raw.strip())
    # gigs freelance evaluados (no los descartados por el filtro barato ni los no técnicos)
    gigs = conn.execute("SELECT id, title, platform, match_percentage, missing_skills, reasoning, description FROM freelance_gigs "
                        "WHERE missing_skills IS NOT NULL AND missing_skills != '' AND applied_at IS NULL "
                        "AND COALESCE(category, '') NOT IN ('non_technical')").fetchall()
    for gid, title, platform, match, missing, reasoning, desc in gigs:
        b = _BUDGET.search(reasoning or "")
        budget = int(b.group(2) or b.group(1)) if b else 0
        for raw in missing.split(","):
            skill = job_scoring._norm_skill(raw)
            if not skill or job_scoring._skill_credit(raw, have) >= 1.0:
                continue
            g = groups[(skill, "freelance")]
            g["jobs"].append({"id": f"g{gid}", "title": title, "company": platform, "match": match or 0, "budget": budget})
            if len(g["snippets"]) < SNIPPETS_PER_GROUP:
                g["snippets"] += _snippets(desc or "", raw.strip())
    return groups


def _rank(kv) -> tuple:
    """Vacantes: por cantidad. Freelance: por cantidad x pago promedio (lo que más se pide y mejor paga)."""
    (skill, role), g = kv
    if role == "freelance":
        budgets = [j["budget"] for j in g["jobs"] if j["budget"]]
        return (len(g["jobs"]) * (sum(budgets) / len(budgets) if budgets else 0), len(g["jobs"]))
    return (len(g["jobs"]), sum(j["match"] for j in g["jobs"]))


def update() -> int:
    conn = sqlite3.connect(profile_paths.resolve("jobs.db"))
    conn.execute("CREATE TABLE IF NOT EXISTS skill_estimates (skill TEXT PRIMARY KEY, data TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    groups = gaps_by_group(conn)
    ranked = sorted(groups.items(), key=_rank, reverse=True)
    # los más pedidos DE CADA ROL: si no, los roles con pocas vacantes (FDE) quedaban sin plan
    # en freelance un gig suelto no es demanda: mínimo 2 gigs pidiendo la skill
    ranked = [kv for kv in ranked if kv[0][1] != "freelance" or len(kv[1]["jobs"]) >= 2]
    top = [kv for role in ROLE_LABELS for kv in [kv for kv in ranked if kv[0][1] == role][:TOP_PER_ROLE]]
    top.sort(key=lambda kv: len(kv[1]["jobs"]), reverse=True)
    known = {s: json.loads(d) for s, d in conn.execute("SELECT skill, data FROM skill_estimates")}
    # Escritas a mano: herramientas que ya usa (aplican igual a cualquier rol)
    with open(CURATED, encoding="utf-8") as f:
        curated = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    with open(profile_paths.resolve("master_profile.json"), encoding="utf-8") as f:
        p = json.load(f)
    profile = json.dumps({k: p.get(k) for k in ("professional_summary", "seniority_context", "technical_stacks")}, ensure_ascii=False)[:3000]

    new = 0
    plan = []
    for rank, ((skill, role), g) in enumerate(top):
        key = f"{skill}|{role}"
        est = curated.get(skill) or known.get(key)
        if est is None:
            try:
                est = llm_chain.invoke_structured(
                    system_prompt=_SYSTEM, human_template=_HUMAN, pydantic_model=SkillEstimate,
                    local_only=rank >= CLOUD_TOP,
                    variables={"profile": profile, "skill": skill,
                               "role": "Proyectos freelance (lo que hay que saber para entregarle el trabajo al cliente)" if role == "freelance" else ARCHETYPE_LABELS[role],
                               "titles": ", ".join(sorted({j["title"] for j in g["jobs"]})[:5]),
                               "snippets": "\n".join(f"- {s}" for s in g["snippets"]) or "(las descripciones no la detallan)"},
                ).model_dump()
                conn.execute("INSERT OR REPLACE INTO skill_estimates (skill, data) VALUES (?, ?)", (key, json.dumps(est, ensure_ascii=False)))
                conn.commit()
                new += 1
            except llm_chain.AllProvidersExhausted:
                print("[-] Sin modelo disponible; los grupos que faltan se generan en la próxima corrida.")
                est = {}
            except Exception as e:
                print(f"   [-] No se pudo generar {key}: {e}")
                est = {}
        plan.append({
            "skill": skill, "role": role, "role_label": ROLE_LABELS[role],
            "avg_budget": round(sum(j.get("budget", 0) for j in g["jobs"]) / max(1, sum(1 for j in g["jobs"] if j.get("budget")))) if role == "freelance" else None,
            "jobs": sorted(g["jobs"], key=lambda j: j["match"], reverse=True),
            "near_cv": sum(1 for j in g["jobs"] if 50 <= j["match"] < 70),  # aprenderla las acerca al 70% (CV)
            # herramientas que ya usa: nada que practicar
            "practice": [] if skill in curated else web_practice(skill, role),
            "interview_prompt": "" if skill in curated or role == "freelance" else interview_prompt(skill, ARCHETYPE_LABELS[role]),
            **est,
        })
    conn.close()

    with open(OUTPUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.datetime.now().isoformat(timespec="minutes"), "skills": plan}, f, ensure_ascii=False)
    os.replace(OUTPUT + ".tmp", OUTPUT)
    print(f"[+] Plan de aprendizaje: {len(plan)} grupos skill+rol ({new} generados nuevos) -> {OUTPUT}")
    return new


if __name__ == "__main__":
    update()
