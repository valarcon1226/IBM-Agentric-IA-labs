"""
Lógica de generación/ajuste de CVs, compartida por tailor_agent.py y
generate_archetype_templates.py. Antes vivía duplicada dentro de tailor_agent.py; se extrajo acá
para poder reusar el mismo loop generador-revisor (con su red anti-alucinaciones) tanto para
generar un CV completo desde cero como para el ajuste liviano de un template ya aprobado.
"""
import asyncio
import json
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

import llm_chain


class Experience(BaseModel):
    company_name: str
    current_role: str
    time_period_worked: str
    achievements: List[str]


class TailoredProfile(BaseModel):
    target_role_title: str = Field(description="Título del rol que va bajo el nombre en el CV, DEBE reflejar la vacante real (ej. si la vacante es 'QA Automation Engineer', este campo dice 'QA Automation Engineer'; si es 'Forward Deployed Engineer', dice eso). Es un título aspiracional/objetivo, no una afirmación de experiencia previa.")
    professional_summary: str = Field(description="Summary reescrito para incluir keywords")
    experience: List[Experience] = Field(description="Experiencias con bullet points ajustados (Método STAR)")


class ReviewResult(BaseModel):
    is_approved: bool = Field(description="True si no hay mentiras ni alucinaciones.")
    feedback: str = Field(description="Si es False, explica qué regla rompió o qué mentira dijo.")


# ---------------------------------------------------------------------------
# GENERADOR COMPLETO (desde cero) — se usa para armar los 3 templates base y como
# fallback cuando todavía no existe un template para el archetype de una vacante.
# ---------------------------------------------------------------------------

GENERATOR_SYSTEM_PROMPT = """Eres un Redactor de Marketing Personal y Hacker ATS de lite.
Tu misin: Reescribir el 'professional_summary' y los 'achievements' de experiencia del candidato para que hagan MATCH PERFECTO con la VACANTE.

REGLAS DE ORO (HARVARD FORMAT):
1. PROHIBIDO MENTIR: No inventes ttulos, empresas, aos de experiencia ni herramientas que el candidato no sepa. Solo RE-ENMARCA lo que ya hizo. PROHIBIDO ESPECIALMENTE inventar mtricas numricas (porcentajes, cifras) que NO estn ya presentes textualmente en el perfil original — si el logro original no tiene un nmero, el bullet reescrito TAMPOCO debe tener uno. Ningn nmero nuevo, nunca.
2. MTODO STAR Y VERBOS DE ACCIN: Cada bullet point debe empezar con un verbo fuerte (Ej: Lider, Dise, Automatic). Si el logro original YA tiene una mtrica, consrvala tal cual (mismo nmero). Si NO la tiene, NO inventes una — usa lenguaje cualitativo de impacto (ej. "mejorando la confiabilidad", "reduciendo el tiempo de mantenimiento") en vez de un porcentaje inventado.
3. INYECCIN DE KEYWORDS: Usa las palabras clave del GAP ANALYSIS sutilmente dentro del resumen y la experiencia, PERO SOLO SI TIENEN SENTIDO CON SU HISTORIAL.
4. BREVEDAD: Los bullet points deben tener mximo 2 lneas.
5. NARRATIVA HBRIDA (EL PITCH MID-LEVEL): Usa el campo 'seniority_context' del perfil original (su nivel real de QA vs. AI/Dev, tal como est escrito ah, SIN inventar aos ni cifras nuevas) como VENTAJA TCTICA. En el mundo de la Inteligencia Artificial, el desarrollo y el QA se estn fusionando. Vndela como una ingeniera capaz de construir sistemas y, al mismo tiempo, aplicarles revisin humana, validacin rigurosa y pruebas (su superpoder de QA) — usando SOLO la descripcin de seniority que ya est en el perfil, nunca aos o nmeros que no estn ah.
6. IDIOMA: Todo el texto que generes (professional_summary, target_role_title y cada achievement) debe estar en INGLÉS, sin importar en qué idioma esté la descripción de la vacante. El perfil original ya está en inglés, mantén esa consistencia.
7. TÍTULO OBJETIVO (target_role_title): DEBE reflejar el título REAL de la vacante ({job_title}), no un título genérico fijo. Si la vacante es de QA/Automation, el título dice QA/Automation (ej. "QA Automation Engineer"). Si es Forward Deployed Engineer, dice "Forward Deployed Engineer". Si es AI Engineer, dice "AI Engineer". Puedes ajustarlo levemente para que suene natural, pero SIEMPRE debe coincidir con la disciplina real de la vacante — nunca un título fijo que no cambia entre vacantes. Esto es un título ASPIRACIONAL/OBJETIVO (el puesto al que aplica), NO una afirmación de que ya tuvo ese cargo antes — no es mentira, es la convención estándar de un CV.

Responde ÚNICAMENTE con un JSON con esta forma exacta, sin texto adicional ni el schema:
{{"target_role_title": "...", "professional_summary": "...", "experience": [{{"company_name": "...", "current_role": "...", "time_period_worked": "...", "achievements": ["...", "..."]}}]}}
Incluye TODAS las experiencias del perfil original, en el mismo orden, cada una con su lista de achievements reescrita."""

GENERATOR_HUMAN_TEMPLATE = """VACANTE: {job_title} en {job_company}
DESCRIPCIN DE LA VACANTE: {job_desc}
GAP ANALYSIS (Keywords que el ATS buscar): {gap_analysis}

PERFIL ORIGINAL DEL CANDIDATO (Verdad Absoluta):
{original_profile}

Reescribe target_role_title, professional_summary y experience. (Devuelve JSON estricto).
"""

REVIEWER_SYSTEM_PROMPT = """Eres un Polica Anti-Alucinaciones de RRHH. Tu nico trabajo es comparar el Perfil Original con el Perfil Generado por la IA y detectar MENTIRAS REALES, no cambios de redaccin.

ESTO NO ES UNA MENTIRA (apruébalo, is_approved=true):
- Empezar un bullet con un verbo de accin ms fuerte (ej. "Migr" -> "Lider la migracin de").
- Reordenar, combinar o acortar frases sin cambiar el significado ni los hechos.
- Agregar una mtrica o palabra clave del Gap Analysis SIEMPRE que sea consistente con lo que ya hizo (ej. mencionar una tecnologa que s aparece en el perfil original, aunque en otras palabras).
- Cambiar el tono para sonar ms seguro/profesional, sin agregar hechos nuevos.
- INFERIR UN RESULTADO TPICO Y ESPERABLE de una accin que el candidato s hizo (ej. si migr un test suite, es razonable decir que eso "mejor la confiabilidad" o "redujo el tiempo de ejecucin" aunque el original no lo diga explcitamente literal por palabra — eso es marketing normal de CV, NO una mentira). Esto aplica mientras no invente un NMERO especfico no mencionado (ej. "40% ms rpido" s sera mentira si ese nmero no est en el original).
- El campo 'target_role_title' que diga un ttulo distinto al de la experiencia laboral del perfil original (ej. "Forward Deployed Engineer" cuando su rol actual es "QA Engineer"). ES EL TTULO OBJETIVO DE LA VACANTE A LA QUE APLICA, no una afirmacin de que ya tuvo ese cargo. Nunca reprobar solo por esto.

ESTO S ES UNA MENTIRA REAL (reprubalo, is_approved=false):
1. Invent un ttulo universitario, maestra o empresa que NO existe en absoluto en el original.
2. Invent aos de experiencia, un rol, o dominio de una tecnologa PESADA que no est mencionada en ninguna parte del original.
3. Cambi un hecho verificable (ej. el nombre real de una empresa, una fecha, un ttulo de rol) por otro diferente.
4. Invent una mtrica numrica especfica (porcentajes, cifras de dinero, cantidad de usuarios/sistemas) que no aparece en el original.

Eres un revisor de RRHH pragmtico, no un abogado buscando tecnicismos. Todo CV profesional usa lenguaje de impacto razonable sobre logros reales.
Si dudas y el cambio es de redaccin, nfasis, o una inferencia de resultado razonable y no cuantificada, aprueba (is_approved=true). Reprueba SOLO ante una fabricacin de hecho, ttulo, fecha o nmero concreto.

Responde NICAMENTE con un JSON con esta forma exacta, sin texto adicional ni el schema, solo los valores:
{{"is_approved": true, "feedback": "texto breve"}}
"""

REVIEWER_HUMAN_TEMPLATE = """PERFIL ORIGINAL:
{original_profile}

PERFIL GENERADO (PARA REVISIN):
{generated_profile}
"""


# ---------------------------------------------------------------------------
# AJUSTE LIVIANO (patch) — parte de un template YA aprobado y solo lo toca si
# el gap analysis de la vacante trae algo que el template no cubre. Llamada mucho
# más chica que el generador completo: no vuelve a pasar el perfil original entero,
# solo el template + lo puntual de esta vacante.
# ---------------------------------------------------------------------------

PATCH_SYSTEM_PROMPT = """Eres un editor de CVs quirrgico. Te doy un CV YA aprobado (perfil base validado para este tipo de rol) y el Gap Analysis de UNA vacante especfica. Tu NICO trabajo es hacer AJUSTES MNIMOS para incorporar las keywords del Gap Analysis que tengan sentido con la experiencia real del candidato — nada ms.

REGLAS:
1. NO reescribas todo. Cambia como mximo 1-2 frases del professional_summary y 1-2 achievements EXISTENTES. Nunca agregues achievements nuevos ni borres experiencias — devuelve TODAS las experiencias del CV base, tal cual, salvo los 1-2 bullets que ajustes.
2. PROHIBIDO MENTIR (mismas reglas de siempre): no inventes tecnologas, ttulos, empresas, aos, ni mtricas numricas nuevas.
3. Si una keyword del Gap Analysis NO tiene ningn lugar honesto donde encajar (no hay experiencia real relacionada), NO la fuerces — djala fuera. Es preferible un CV sin esa keyword que uno con una mentira.
4. Todo el texto en INGLS.
5. Devuelve el perfil COMPLETO (target_role_title igual al del CV base, todas las experiencias con su lista completa de achievements), aunque no hayas tocado casi nada.

Responde NICAMENTE con un JSON con esta forma exacta, sin texto adicional ni el schema:
{{"target_role_title": "...", "professional_summary": "...", "experience": [{{"company_name": "...", "current_role": "...", "time_period_worked": "...", "achievements": ["...", "..."]}}]}}
"""

PATCH_HUMAN_TEMPLATE = """VACANTE: {job_title}
GAP ANALYSIS A INCORPORAR SI TIENE SENTIDO: {gap_analysis}
DESCRIPCIN BREVE DE LA VACANTE (contexto, no hace falta citarla): {job_desc}

CV BASE YA APROBADO (punto de partida — cmbialo lo mnimo posible):
{base_profile}

Devuelve el CV ajustado (JSON estricto, perfil completo)."""


async def _run_review(tailored_result: TailoredProfile, master_json_str: str) -> Tuple[bool, str]:
    review = llm_chain.invoke_structured(
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        human_template=REVIEWER_HUMAN_TEMPLATE,
        variables={
            "original_profile": master_json_str,
            "generated_profile": tailored_result.model_dump_json(),
        },
        pydantic_model=ReviewResult,
        temperature=0.0,
    )
    return review.is_approved, review.feedback


async def generate_full(job_title: str, job_company: str, job_desc: str, gap_analysis: str,
                         master_json_str: str, master_profile: dict, max_retries: int = 3) -> Tuple[TailoredProfile, bool]:
    """Genera un CV tailoreado desde cero (perfil completo), con el loop generador-revisor
    (hasta max_retries intentos). Si el revisor rechaza todos los intentos, devuelve el perfil
    ORIGINAL sin tailorear — más seguro que arriesgar una mentira en el PDF.
    Propaga llm_chain.AllProvidersExhausted si se agota el cupo a mitad de camino."""
    is_approved = False
    tailored_result: Optional[TailoredProfile] = None
    feedback_history = ""

    for attempt in range(1, max_retries + 1):
        print(f"   [Intento {attempt}/{max_retries}] Generando CV completo...")
        try:
            tailored_result = llm_chain.invoke_structured(
                system_prompt=GENERATOR_SYSTEM_PROMPT,
                human_template=GENERATOR_HUMAN_TEMPLATE,
                variables={
                    "job_title": job_title,
                    "job_company": job_company,
                    "job_desc": job_desc,
                    "gap_analysis": gap_analysis,
                    "original_profile": master_json_str + "\nFEEDBACK DEL REVISOR (intentos anteriores, corrige TODO esto):\n" + feedback_history,
                },
                pydantic_model=TailoredProfile,
                temperature=0.2,
            )
        except llm_chain.AllProvidersExhausted:
            raise
        except Exception as e:
            print(f"   [ERROR] LLM Generador falló: {e}. Reintentando en 3s...")
            await asyncio.sleep(3)
            continue

        print(f"   [Revisor] Analizando posibles alucinaciones...")
        try:
            approved, feedback = await _run_review(tailored_result, master_json_str)
            if approved:
                print(f"    APROBADO por el Revisor. Ninguna alucinacin detectada.")
                is_approved = True
                break
            else:
                print(f"    RECHAZADO por el Revisor. Razn: {feedback}")
                feedback_history += f"\n- Intento {attempt}: {feedback}"
        except llm_chain.AllProvidersExhausted:
            raise
        except Exception as e:
            print(f"   [ERROR] LLM Revisor falló: {e}")
            continue

    if not is_approved:
        print(f"   [WARNING] El Revisor rechazó los {max_retries} intentos (posible alucinación). "
              f"Se usa el perfil ORIGINAL sin tailorear — más seguro que arriesgar una mentira en el PDF.")
        tailored_result = TailoredProfile(
            target_role_title=job_title or master_profile.get("target_roles", "Engineer"),
            professional_summary=master_profile.get("professional_summary", ""),
            experience=[
                Experience(
                    company_name=e.get("company_name", ""),
                    current_role=e.get("current_role", ""),
                    time_period_worked=e.get("time_period_worked", ""),
                    achievements=e.get("achievements", [])
                )
                for e in master_profile.get("experience", [])
            ]
        )
    return tailored_result, is_approved


async def patch_from_template(template: dict, job_title: str, job_desc: str, gap_analysis: str,
                               master_json_str: str, max_retries: int = 2) -> Tuple[TailoredProfile, bool]:
    """Ajusta un template YA aprobado con las keywords puntuales de esta vacante — mucho más
    liviano que generate_full (no repite el perfil original completo, solo el template + lo
    específico de este job). Si el revisor rechaza todos los intentos, devuelve el TEMPLATE tal
    cual, sin ajustar (nunca arriesga una mentira con tal de meter una keyword).
    Propaga llm_chain.AllProvidersExhausted si se agota el cupo a mitad de camino."""
    base_json = json.dumps(template, ensure_ascii=False)
    is_approved = False
    patched: Optional[TailoredProfile] = None
    feedback_history = ""

    for attempt in range(1, max_retries + 1):
        print(f"   [Intento {attempt}/{max_retries}] Ajustando template (patch liviano)...")
        try:
            patched = llm_chain.invoke_structured(
                system_prompt=PATCH_SYSTEM_PROMPT,
                human_template=PATCH_HUMAN_TEMPLATE,
                variables={
                    "job_title": job_title,
                    "job_desc": job_desc,
                    "gap_analysis": gap_analysis,
                    "base_profile": base_json + (f"\nFEEDBACK DEL REVISOR (intentos anteriores):\n{feedback_history}" if feedback_history else ""),
                },
                pydantic_model=TailoredProfile,
                temperature=0.2,
            )
        except llm_chain.AllProvidersExhausted:
            raise
        except Exception as e:
            print(f"   [ERROR] LLM Patch falló: {e}. Reintentando en 3s...")
            await asyncio.sleep(3)
            continue

        try:
            approved, feedback = await _run_review(patched, master_json_str)
            if approved:
                print(f"    APROBADO por el Revisor.")
                is_approved = True
                break
            else:
                print(f"    RECHAZADO por el Revisor. Razn: {feedback}")
                feedback_history += f"\n- Intento {attempt}: {feedback}"
        except llm_chain.AllProvidersExhausted:
            raise
        except Exception as e:
            print(f"   [ERROR] LLM Revisor falló: {e}")
            continue

    if not is_approved:
        print(f"   [WARNING] El ajuste no pasó revisión — se usa el TEMPLATE sin ajustar (más seguro).")
        patched = TailoredProfile(
            target_role_title=job_title,
            professional_summary=template.get("professional_summary", ""),
            experience=[Experience(**e) for e in template.get("experience", [])],
        )
    return patched, is_approved
