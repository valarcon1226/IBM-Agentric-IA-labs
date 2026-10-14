"""AEO (Answer Engine Optimization / Artificial Engine Optimization) checks and scoring."""

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.config import DEFAULT_CONFIG

QUESTION_WORDS_ES = (
    "¿",
    "que",
    "qué",
    "como",
    "cómo",
    "cuando",
    "cuándo",
    "donde",
    "dónde",
    "por que",
    "por qué",
    "porque",
    "cuanto",
    "cuánto",
    "cuantos",
    "cuántos",
    "cual",
    "cuál",
    "cuales",
    "cuáles",
    "quien",
    "quién",
    "existe",
    "tienen",
    "hacen",
    "puedo",
    "donde queda",
)

QUESTION_WORDS_EN = (
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "which",
    "is",
    "are",
    "can",
    "do",
    "does",
    "should",
)


def is_question_text(text: str) -> bool:
    """Determine if a header string represents a direct question."""
    t = text.strip().lower()
    if not t:
        return False
    if "?" in t or "¿" in t:
        return True

    words = re.findall(r"\b\w+\b", t)
    if words:
        first_word = words[0]
        if first_word in QUESTION_WORDS_ES or first_word in QUESTION_WORDS_EN:
            return True
        if len(words) > 1 and f"{words[0]} {words[1]}" in ("por que", "por qué", "donde queda"):
            return True
    return False


def find_answer_paragraph(header_tag: Tag) -> str | None:
    """Find the direct answer text immediately following a header element."""
    curr = header_tag.next_sibling
    while curr:
        if isinstance(curr, Tag):
            # If we hit another heading, there is no direct answer paragraph
            if re.match(r"^h[1-6]$", curr.name, re.I):
                break
            if curr.name in ("p", "div", "li"):
                txt = curr.get_text().strip()
                if txt:
                    return txt
        curr = curr.next_sibling
    return None


def extract_contact_and_hours_text(soup: BeautifulSoup) -> dict[str, Any]:
    """Inspect body text for readable contact information and opening hours."""
    body = soup.find("body") or soup
    body_text = body.get_text(separator=" ").lower()

    # Phone pattern
    phone_pattern = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
    has_phone = bool(phone_pattern.search(body_text)) or "teléfono" in body_text or "whatsapp" in body_text or "celular" in body_text

    # Email pattern
    email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    has_email = bool(email_pattern.search(body_text))

    # Address keywords
    address_keywords = ("calle", "carrera", "av.", "avenida", "cr", "cll", "dirección", "ubicación", "address", "street", "bogotá", "medellín")
    has_address = any(kw in body_text for kw in address_keywords)

    # Opening hours keywords
    hours_keywords = (
        "horario",
        "lunes a",
        "lunes",
        "martes",
        "miércoles",
        "miercoles",
        "jueves",
        "viernes",
        "sábado",
        "sabado",
        "domingo",
        "abierto",
        "horas",
        "hours",
        "open daily",
        "am -",
        "pm -",
    )
    has_hours = any(kw in body_text for kw in hours_keywords)

    return {
        "has_phone": has_phone,
        "has_email": has_email,
        "has_address": has_address,
        "has_contact_info": (has_phone or has_email or has_address),
        "has_hours": has_hours,
    }


def analyze_aeo(
    url: str,
    html: str,
    json_ld_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluate Answer Engine Optimization (AEO) readiness:
    1. Questions as headings (25 pts)
    2. Concise answers under headings (25 pts)
    3. FAQ / HowTo / LocalBusiness Schema (25 pts)
    4. Readable contact and opening hours text (25 pts)
    Total score: 0 to 100 with criteria explanations.
    """
    soup = BeautifulSoup(html, "html.parser")
    json_ld_types = json_ld_types or []

    issues: list[dict[str, Any]] = []
    good_points: list[str] = []

    criteria_breakdown = []

    # 1. Questions as headings (25 pts)
    headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
    question_headings: list[dict[str, Any]] = []

    for h in headings:
        txt = h.get_text().strip()
        if is_question_text(txt):
            ans = find_answer_paragraph(h)
            ans_len = len(ans) if ans else 0
            question_headings.append({
                "tag": h.name,
                "text": txt,
                "answer_text": ans,
                "answer_length": ans_len,
                "is_concise": bool(ans and 20 <= ans_len <= DEFAULT_CONFIG.aeo_concise_answer_max_chars),
            })

    num_questions = len(question_headings)
    if num_questions >= 2:
        score_questions = 25
        desc_q = f"Excelente: se encontraron {num_questions} encabezados planteados como preguntas directas."
        good_points.append(desc_q)
    elif num_questions == 1:
        score_questions = 15
        desc_q = "Parcial: se encontró solo 1 encabezado con formato de pregunta. Se recomienda añadir más secciones Q&A."
        issues.append({
            "code": "AEO_FEW_QUESTION_HEADINGS",
            "category": "Optimización para IA (AEO)",
            "severity": "LOW",
            "message": "Pocas preguntas en encabezados para capturar consultas de IA.",
            "url": url,
            "fix": "Formula al menos 3 encabezados <h2> o <h3> como preguntas frecuentes de tus clientes (ej. '¿Qué horario tienen?', '¿Cómo hacer un pedido?').",
        })
    else:
        score_questions = 0
        desc_q = "Insuficiente: no se detectaron encabezados en formato de pregunta."
        issues.append({
            "code": "AEO_NO_QUESTION_HEADINGS",
            "category": "Optimización para IA (AEO)",
            "severity": "MEDIUM",
            "message": "No se encontraron encabezados que respondan preguntas directas de usuarios o IAs.",
            "url": url,
            "fix": "Estructura secciones clave usando preguntas directas (con '¿' y '?') en <h2> o <h3> para facilitar respuestas en ChatGPT y Perplexity.",
        })

    criteria_breakdown.append({
        "criterion": "Preguntas como encabezados",
        "points": score_questions,
        "max_points": 25,
        "details": desc_q,
    })

    # 2. Concise answers under headings (25 pts)
    if num_questions == 0:
        score_answers = 0
        desc_ans = "Sin preguntas formuladas para evaluar respuestas concisas."
    else:
        concise_count = sum(1 for q in question_headings if q["is_concise"])
        if concise_count == num_questions:
            score_answers = 25
            desc_ans = f"Excelente: las {num_questions} preguntas tienen respuestas directas y concisas (< 300 caracteres)."
            good_points.append(desc_ans)
        elif concise_count > 0:
            score_answers = 15
            desc_ans = f"Parcial: {concise_count} de {num_questions} preguntas cuentan con respuestas concisas inmediatas."
            issues.append({
                "code": "AEO_INCONSISTENT_ANSWERS",
                "category": "Optimización para IA (AEO)",
                "severity": "LOW",
                "message": "Algunas preguntas carecen de un párrafo breve de respuesta directa.",
                "url": url,
                "fix": "Asegúrate de colocar un párrafo de 40 a 60 palabras directamente debajo de cada pregunta con la respuesta definitiva antes de profundizar.",
            })
        else:
            score_answers = 5
            desc_ans = "Las respuestas son demasiado extensas o no están situadas inmediatamente bajo la pregunta."
            issues.append({
                "code": "AEO_LONG_ANSWERS",
                "category": "Optimización para IA (AEO)",
                "severity": "MEDIUM",
                "message": "Las respuestas superan los 300 caracteres, reduciendo la probabilidad de ser citadas por motores de IA.",
                "url": url,
                "fix": "Resume la primera frase tras el encabezado en una afirmación directa de menos de 300 caracteres (formato fragmento destacado).",
            })

    criteria_breakdown.append({
        "criterion": "Respuestas concisas bajo cada pregunta",
        "points": score_answers,
        "max_points": 25,
        "details": desc_ans,
    })

    # 3. Schema FAQ / HowTo / LocalBusiness (25 pts)
    types_set = {t.lower() for t in json_ld_types}
    high_value_aeo_schemas = {
        "faqpage",
        "howto",
        "localbusiness",
        "restaurant",
        "foodestablishment",
        "cafeorcoffeeshop",
        "store",
    }
    general_schemas = {"organization", "website", "webpage", "product", "article"}

    if high_value_aeo_schemas.intersection(types_set):
        score_schema = 25
        matched = list(high_value_aeo_schemas.intersection(types_set))
        desc_schema = f"Excelente: schema de alto impacto AEO detectado ({', '.join(matched)})."
        good_points.append(desc_schema)
    elif general_schemas.intersection(types_set):
        score_schema = 15
        matched = list(general_schemas.intersection(types_set))
        desc_schema = f"Parcial: schema básico presente ({', '.join(matched)}), pero carece de FAQPage o LocalBusiness específico."
        issues.append({
            "code": "AEO_SCHEMA_NOT_SPECIFIC",
            "category": "Datos Estructurados para IA",
            "severity": "LOW",
            "message": "El marcado schema existente es general y no explota FAQPage o LocalBusiness.",
            "url": url,
            "fix": "Implementa schema FAQPage para tus preguntas frecuentes y LocalBusiness/Restaurant con datos de ubicación exacta.",
        })
    else:
        score_schema = 0
        desc_schema = "Insuficiente: no se detectó schema FAQ, HowTo ni LocalBusiness."
        issues.append({
            "code": "AEO_MISSING_TARGET_SCHEMA",
            "category": "Datos Estructurados para IA",
            "severity": "HIGH",
            "message": "Ausencia de marcado schema especializado para IA (FAQPage, LocalBusiness o HowTo).",
            "url": url,
            "fix": "Inyecta un JSON-LD con schema 'LocalBusiness' o 'FAQPage' para que los agentes inteligentes verifiquen tu negocio sin alucinaciones.",
        })

    criteria_breakdown.append({
        "criterion": "Schema FAQ / HowTo / LocalBusiness",
        "points": score_schema,
        "max_points": 25,
        "details": desc_schema,
    })

    # 4. Contact info and opening hours legible as text (25 pts)
    contact_data = extract_contact_and_hours_text(soup)
    has_contact = contact_data["has_contact_info"]
    has_hours = contact_data["has_hours"]

    if has_contact and has_hours:
        score_contact = 25
        desc_contact = "Excelente: datos de contacto y horarios comerciales legibles directamente en el texto HTML."
        good_points.append(desc_contact)
    elif has_contact or has_hours:
        score_contact = 15
        missing = "horarios de atención" if not has_hours else "datos de contacto (teléfono/email)"
        desc_contact = f"Parcial: se detectaron {'contactos' if has_contact else 'horarios'}, pero faltan {missing} legibles como texto plano."
        issues.append({
            "code": "AEO_PARTIAL_CONTACT_HOURS",
            "category": "Accesibilidad de Datos de Negocio",
            "severity": "MEDIUM",
            "message": f"Faltan {missing} en texto plano para que asistentes de IA respondan sobre el negocio.",
            "url": url,
            "fix": "Incluye tanto teléfono/email como los días y rangos horarios explícitos en el pie de página o sección de contacto.",
        })
    else:
        score_contact = 0
        desc_contact = "Insuficiente: no se encontraron datos de contacto ni horarios en texto plano accesible."
        issues.append({
            "code": "AEO_NO_CONTACT_HOURS_TEXT",
            "category": "Accesibilidad de Datos de Negocio",
            "severity": "HIGH",
            "message": "Datos de contacto y horarios no legibles en texto plano (podrían estar incrustados en imágenes).",
            "url": url,
            "fix": "Evita poner teléfonos y horarios en imágenes o botones cerrados; escríbelos en texto plano indexable.",
        })

    criteria_breakdown.append({
        "criterion": "Contacto y horarios legibles como texto",
        "points": score_contact,
        "max_points": 25,
        "details": desc_contact,
    })

    total_aeo_score = score_questions + score_answers + score_schema + score_contact

    return {
        "score": total_aeo_score,
        "max_score": 100,
        "questions_count": num_questions,
        "question_headings": question_headings,
        "contact_info_detected": has_contact,
        "hours_detected": has_hours,
        "criteria_breakdown": criteria_breakdown,
        "issues": issues,
        "good_points": good_points,
    }
