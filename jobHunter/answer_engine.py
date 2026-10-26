"""Motor de respuestas para el Agente Aplicador (Fase D de APPLICATOR_PLAN.md).

Orden estricto de resolución:
1. Banco (profile_paths.resolve("answers.yaml")) con tabla de sinónimos es/en y difflib.
2. aprendidas: del mismo YAML (dashboard / HITL).
3. master_profile.json (experiencia, estudios, cargos).
4. Clasificador LLM con lista CERRADA de claves (el valor sale del banco, nunca del LLM).
5. Texto abierto con LLM (perfil + vacante + respuestas_modelo como guía de voz).
6. needs_human = True (datos ausentes, vacíos, '???' o no identificados).

Reglas duras:
- salario.minimo_aceptable JAMÁS sale como respuesta.
- Valor '???', vacío o ausente -> needs_human = True.
- Sin answers.yaml -> todo lo del banco termina en needs_human = True.
"""
from dataclasses import dataclass, replace
import datetime
import difflib
import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
import unicodedata
import yaml


from form_reader import Field
import profile_paths

logger = logging.getLogger("answer_engine")


@dataclass
class Answer:
    value: Any
    source: str       # 'bank', 'learned', 'profile', 'llm', 'file', 'none'
    needs_human: bool


def normalize_label(text: str) -> str:
    """Normaliza texto para comparación: minúsculas, sin acentos, sin puntuación extra."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = no_accents.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _detect_currency(text: str) -> Optional[str]:
    """Detecta la moneda mencionada en un texto o etiqueta (USD, EUR, COP, GBP, etc.)."""
    if not text:
        return None
    raw = str(text).lower()

    # 1. COP
    if re.search(r"\b(cop|pesos?(\s+colombianos?)?)\b", raw):
        return "COP"

    # 2. EUR
    if "€" in raw or re.search(r"\b(eur|euros?)\b", raw):
        return "EUR"

    # 3. GBP
    if "£" in raw or re.search(r"\b(gbp|pounds?|libras?)\b", raw):
        return "GBP"

    # 4. USD
    if "us$" in raw or "$" in raw or re.search(r"\b(usd|dollars?|dolares?)\b", raw):
        return "USD"

    return None


# ---------------------------------------------------------------------------
# Tabla de sinónimos es/en (etiqueta normalizada -> ruta de clave o clave virtual)
# ---------------------------------------------------------------------------
_RAW_SYNONYMS: Dict[str, str] = {
    # Nombre y apellidos
    "first name": "nombre",
    "what would you like us to call you": "nombre",
    "name you d prefer us to use": "nombre",
    "firstname": "nombre",
    "primer nombre": "nombre",
    "given name": "nombre",
    "forename": "nombre",
    "last name": "apellidos",
    "lastname": "apellidos",
    "apellidos": "apellidos",
    "apellido": "apellidos",
    "surname": "apellidos",
    "family name": "apellidos",
    "full name": "datos_personales.nombre_legal",
    "fullname": "datos_personales.nombre_legal",
    "nombre completo": "datos_personales.nombre_legal",
    "nombre legal": "datos_personales.nombre_legal",
    "legal name": "datos_personales.nombre_legal",
    "applicant name": "datos_personales.nombre_legal",
    "name": "datos_personales.nombre_legal",
    "nombre": "datos_personales.nombre_legal",
    "your name": "datos_personales.nombre_legal",
    "tu nombre": "datos_personales.nombre_legal",

    # Email
    "email": "datos_personales.email",
    "email address": "datos_personales.email",
    "applicant email": "datos_personales.email",
    "correo": "datos_personales.email",
    "correo electronico": "datos_personales.email",
    "e mail": "datos_personales.email",

    # Teléfono
    "phone": "datos_personales.telefono",
    "phone number": "datos_personales.telefono",
    "mobile phone": "datos_personales.telefono",
    "mobile": "datos_personales.telefono",
    "celular": "datos_personales.telefono",
    "telefono": "datos_personales.telefono",
    "numero de telefono": "datos_personales.telefono",
    "contact number": "datos_personales.telefono",

    # Ubicación / Ciudad / País
    "city": "datos_personales.ciudad",
    "city do you reside in": "datos_personales.ciudad",
    "city and state do you reside in": "datos_personales.ciudad",
    "ciudad": "datos_personales.ciudad",
    "location city": "datos_personales.ciudad",
    "candidate location": "datos_personales.ciudad",
    "country": "datos_personales.pais",
    "pais": "datos_personales.pais",
    "country of residence": "datos_personales.pais",
    "pais de residencia": "datos_personales.pais",
    "in which country do you currently work": "datos_personales.pais",
    "for payroll tax purposes": "datos_personales.pais",  # Ramp "Where do you plan on working from (for payroll tax purposes)?"
    "current country": "datos_personales.pais",
    "nationality": "datos_personales.pais",
    "nacionalidad": "datos_personales.pais",
    "please indicate your nationality": "datos_personales.pais",
    "timezone": "datos_personales.zona_horaria",
    "time zone": "datos_personales.zona_horaria",
    "zona horaria": "datos_personales.zona_horaria",
    "location": "datos_personales.ciudad",
    "ubicacion": "datos_personales.ciudad",
    "current location": "datos_personales.ciudad",

    # Enlaces y redes
    "linkedin": "datos_personales.linkedin",
    "linkedin url": "datos_personales.linkedin",
    "linkedin profile": "datos_personales.linkedin",
    "perfil de linkedin": "datos_personales.linkedin",
    "url de linkedin": "datos_personales.linkedin",
    "github": "datos_personales.github",
    "github url": "datos_personales.github",
    "github profile": "datos_personales.github",
    "perfil de github": "datos_personales.github",
    "url de github": "datos_personales.github",
    "portfolio": "datos_personales.portafolio",
    "portfolio url": "datos_personales.portafolio",
    "website portfolio": "datos_personales.portafolio",
    "portafolio": "datos_personales.portafolio",
    "website": "datos_personales.portafolio",
    "personal website": "datos_personales.portafolio",
    "other website": "datos_personales.portafolio",
    "pronouns": "datos_personales.pronombres",
    "pronombres": "datos_personales.pronombres",

    # Autorización de trabajo y visas
    "authorized to work in the united states": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "are you legally authorized to work in the united states": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "legally authorized to work in the united states": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "are you authorized to work in the us": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "authorized to work in the us": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "autorizada para trabajar en estados unidos": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "autorizado para trabajar en estados unidos": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "work authorization us": "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "authorized to work in colombia": "autorizacion_de_trabajo.autorizada_para_trabajar_en_colombia",
    "autorizada para trabajar en colombia": "autorizacion_de_trabajo.autorizada_para_trabajar_en_colombia",
    "authorized to work in the eu": "autorizacion_de_trabajo.autorizada_para_trabajar_en_la_ue",
    "authorized to work in the european union": "autorizacion_de_trabajo.autorizada_para_trabajar_en_la_ue",
    "autorizada para trabajar en la ue": "autorizacion_de_trabajo.autorizada_para_trabajar_en_la_ue",
    "sponsorship": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "visa sponsorship": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "require sponsorship": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "will you now or in the future require sponsorship for employment visa status": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "do you require visa sponsorship": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "to sponsor an immigration case": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "necesita patrocinio de visa": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "requiere patrocinio de visa": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "willing to relocate": "autorizacion_de_trabajo.dispuesta_a_mudarse",
    "dispuesta a mudarse": "autorizacion_de_trabajo.dispuesta_a_mudarse",
    "dispuesto a reubicarse": "autorizacion_de_trabajo.dispuesta_a_mudarse",
    "relocation": "autorizacion_de_trabajo.dispuesta_a_mudarse",
    "work modality": "autorizacion_de_trabajo.modalidad",
    "modalidad": "autorizacion_de_trabajo.modalidad",
    "contractor": "autorizacion_de_trabajo.trabaja_como_contractor",
    "trabaja como contractor": "autorizacion_de_trabajo.trabaja_como_contractor",

    # Salario
    "desired salary": "salario.expectativa_anual_usd",
    "desired annual salary": "salario.expectativa_anual_usd",
    "desired annual salary in usd": "salario.expectativa_anual_usd",
    "desired annual salary usd": "salario.expectativa_anual_usd",
    "annual salary": "salario.expectativa_anual_usd",
    "annual salary in usd": "salario.expectativa_anual_usd",
    "annual salary usd": "salario.expectativa_anual_usd",
    "annual salary expectation": "salario.expectativa_anual_usd",
    "annual salary expectation in usd": "salario.expectativa_anual_usd",
    "annual salary expectation usd": "salario.expectativa_anual_usd",
    "yearly salary": "salario.expectativa_anual_usd",
    "yearly salary in usd": "salario.expectativa_anual_usd",
    "desired yearly salary": "salario.expectativa_anual_usd",
    "desired yearly salary in usd": "salario.expectativa_anual_usd",
    "salary expectation": "salario.expectativa_anual_usd",
    "salary expectation usd": "salario.expectativa_anual_usd",
    "salary expectation in usd": "salario.expectativa_anual_usd",
    "expectativa salarial": "salario.expectativa_anual_usd",
    "expectativa salarial anual": "salario.expectativa_anual_usd",
    "expectativa salarial anual en usd": "salario.expectativa_anual_usd",
    "expectativa salarial anual usd": "salario.expectativa_anual_usd",
    "expectativa anual": "salario.expectativa_anual_usd",
    "expectativa anual en usd": "salario.expectativa_anual_usd",
    "salario anual": "salario.expectativa_anual_usd",
    "salario anual en usd": "salario.expectativa_anual_usd",
    "desired monthly salary": "salario.expectativa_mensual",
    "desired monthly salary in usd": "salario.expectativa_mensual",
    "desired monthly salary in eur": "salario.expectativa_mensual",
    "monthly salary": "salario.expectativa_mensual",
    "monthly salary in usd": "salario.expectativa_mensual",
    "monthly salary in eur": "salario.expectativa_mensual",
    "monthly salary expectation": "salario.expectativa_mensual",
    "monthly salary expectation in usd": "salario.expectativa_mensual",
    "monthly salary expectation in eur": "salario.expectativa_mensual",
    "expectativa mensual": "salario.expectativa_mensual",
    "expectativa mensual en usd": "salario.expectativa_mensual",
    "expectativa mensual en eur": "salario.expectativa_mensual",
    "expectativa salarial mensual": "salario.expectativa_mensual",
    "expectativa salarial mensual en usd": "salario.expectativa_mensual",
    "expectativa salarial mensual en eur": "salario.expectativa_mensual",
    "current salary": "salario.salario_actual",
    "salario actual": "salario.salario_actual",

    # Disponibilidad
    "notice period": "disponibilidad.preaviso",
    "preaviso": "disponibilidad.preaviso",
    "earliest start date": "disponibilidad.fecha_de_inicio_mas_temprana",
    "start date": "disponibilidad.fecha_de_inicio_mas_temprana",
    "fecha de inicio mas temprana": "disponibilidad.fecha_de_inicio_mas_temprana",
    "availability to start": "disponibilidad.fecha_de_inicio_mas_temprana",
    "cuando puedes empezar": "disponibilidad.fecha_de_inicio_mas_temprana",
    "hours overlap with us": "disponibilidad.horas_de_solapamiento_con_EEUU",
    "horas de solapamiento con eeuu": "disponibilidad.horas_de_solapamiento_con_EEUU",
    "european hours": "disponibilidad.puede_trabajar_horario_europeo",
    "puede trabajar horario europeo": "disponibilidad.puede_trabajar_horario_europeo",

    # Idiomas
    "english": "idiomas.ingles",
    "english level": "idiomas.ingles",
    "english proficiency": "idiomas.ingles",
    "nivel de ingles": "idiomas.ingles",
    "spanish": "idiomas.espanol",
    "spanish level": "idiomas.espanol",
    "nivel de espanol": "idiomas.espanol",
    "french": "idiomas.frances",
    "frances": "idiomas.frances",
    "italian": "idiomas.italiano",
    "italiano": "idiomas.italiano",

    # Experiencia
    "years of experience": "experiencia.anos_totales_profesional",
    "post college work experience": "experiencia.anos_totales_profesional",
    "total years of experience": "experiencia.anos_totales_profesional",
    "anos de experiencia": "experiencia.anos_totales_profesional",
    "anos de experiencia profesional": "experiencia.anos_totales_profesional",
    "years of qa automation": "experiencia.anos_qa_automation",
    "anos de qa automation": "experiencia.anos_qa_automation",
    "years of python": "experiencia.anos_python",
    "anos de python": "experiencia.anos_python",
    "years of playwright": "experiencia.anos_playwright",
    "anos de playwright": "experiencia.anos_playwright",
    "years of selenium": "experiencia.anos_selenium",
    "anos de selenium": "experiencia.anos_selenium",
    "years of ai agents": "experiencia.anos_llms_agentes_ia",
    "years of llms": "experiencia.anos_llms_agentes_ia",
    "anos de llms agentes ia": "experiencia.anos_llms_agentes_ia",
    "years of javascript": "experiencia.anos_javascript_typescript",
    "years of typescript": "experiencia.anos_javascript_typescript",
    "anos de javascript typescript": "experiencia.anos_javascript_typescript",
    "education level": "experiencia.nivel_educativo",
    "highest education level": "experiencia.nivel_educativo",
    "nivel educativo": "experiencia.nivel_educativo",

    # Preguntas frecuentes
    "how did you hear about this role": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "how you heard about this opportunity": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "how did you hear about this position": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "how did you hear about us": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "como se entero de la vacante": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "como te enteraste de esta vacante": "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "have you ever been fired": "preguntas_frecuentes.la_han_despedido_alguna_vez",
    "la han despedido alguna vez": "preguntas_frecuentes.la_han_despedido_alguna_vez",
    "have you previously worked at this company": "preguntas_frecuentes.trabajo_antes_en_esta_empresa",
    "have you worked here before": "preguntas_frecuentes.trabajo_antes_en_esta_empresa",
    "trabajo antes en esta empresa": "preguntas_frecuentes.trabajo_antes_en_esta_empresa",
    "do you have relatives working here": "preguntas_frecuentes.tiene_familiares_en_la_empresa",
    "tiene familiares en la empresa": "preguntas_frecuentes.tiene_familiares_en_la_empresa",
    "background check": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "acepta verificacion de antecedentes": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "autorizas la verificacion de antecedentes": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "verificacion de antecedentes": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "certificas que no tienes condenas por delitos graves y autorizas": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "certificas que no tienes condenas por delitos graves": "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "are you 18 or older": "preguntas_frecuentes.mayor_de_18",
    "are you at least 18 years old": "preguntas_frecuentes.mayor_de_18",
    "mayor de 18": "preguntas_frecuentes.mayor_de_18",
    "family or personal connection": "preguntas_frecuentes.tiene_familiares_en_la_empresa",
    "family members relatives or personal relationships": "preguntas_frecuentes.tiene_familiares_en_la_empresa",
    "worked at or consulted for": "preguntas_frecuentes.trabajo_antes_en_esta_empresa",
    "have you been employed by": "preguntas_frecuentes.trabajo_antes_en_esta_empresa",

    # Situación laboral (las pregunta la entrevista; antes frenaban el aplicador)
    "are you currently employed": "situacion_laboral.empleada_actualmente",
    "trabajas actualmente": "situacion_laboral.empleada_actualmente",
    "name of your current manager": "situacion_laboral.nombre_jefe_actual",
    "notified your current manager": "situacion_laboral.jefe_sabe_que_busca",
    "does your current employer know": "situacion_laboral.jefe_sabe_que_busca",
    "employment agreements and or post employment restrictions": "situacion_laboral.acuerdos_no_competencia",
    "non compete": "situacion_laboral.acuerdos_no_competencia",
    "acuerdo de no competencia": "situacion_laboral.acuerdos_no_competencia",
    "outside business activity": "situacion_laboral.negocios_externos",
    "outside business activities": "situacion_laboral.negocios_externos",
    "active us security clearance": "autorizacion_de_trabajo.tiene_security_clearance",
    "active uk security clearance": "autorizacion_de_trabajo.tiene_security_clearance",
    "hold an active security clearance": "autorizacion_de_trabajo.tiene_security_clearance",
    "eligible to obtain the security clearance": "autorizacion_de_trabajo.puede_obtener_security_clearance",
    "eligible to obtain a security clearance": "autorizacion_de_trabajo.puede_obtener_security_clearance",

    # Políticas: consentimientos que la persona ya decidió en la entrevista
    "ai notetakers": "politicas.acepta_grabacion_ia",
    "record the interview": "politicas.acepta_grabacion_ia",
    "share my resume and contact information with external": "politicas.acepta_compartir_cv_con_socios",
    "contact you about future opportunities": "politicas.acepta_contacto_futuro",
    "considered for future opportunities": "politicas.acepta_contacto_futuro",

    # EEO / Diversidad
    "gender": "eeo_voluntario.genero",
    "genero": "eeo_voluntario.genero",
    "which gender do you identify as": "eeo_voluntario.genero",
    "gender identity": "eeo_voluntario.genero",
    "identification of gender": "eeo_voluntario.genero",  # Twilio "Voluntary Self-Identification of Gender"
    "systemfield eeoc gender": "eeo_voluntario.genero",  # Ashby: la etiqueta no se lee, el key sí
    "systemfield eeoc race": "eeo_voluntario.raza_etnicidad",
    "race": "eeo_voluntario.raza_etnicidad",
    "ethnicity": "eeo_voluntario.raza_etnicidad",
    "race or ethnicity": "eeo_voluntario.raza_etnicidad",
    "race ethnicity": "eeo_voluntario.raza_etnicidad",
    "please indicate your race or ethnicity": "eeo_voluntario.raza_etnicidad",
    "are you hispanic latino": "eeo_voluntario.raza_etnicidad",
    "hispanic ethnicity": "eeo_voluntario.raza_etnicidad",
    "raza etnicidad": "eeo_voluntario.raza_etnicidad",
    "veteran": "eeo_voluntario.veterano",
    "veteran status": "eeo_voluntario.veterano",
    "veterano": "eeo_voluntario.veterano",
    "disability": "eeo_voluntario.discapacidad",
    "disability status": "eeo_voluntario.discapacidad",
    "discapacidad": "eeo_voluntario.discapacidad",

    # Respuestas modelo (preguntas fijas de voz)
    "por que te interesa este tipo de rol": "respuestas_modelo.por_que_te_interesa_este_tipo_de_rol",
    "why are you interested in this role": "respuestas_modelo.por_que_te_interesa_este_tipo_de_rol",
    "tu mayor logro profesional": "respuestas_modelo.tu_mayor_logro_profesional",
    "biggest professional achievement": "respuestas_modelo.tu_mayor_logro_profesional",
    "por que buscas cambio": "respuestas_modelo.por_que_buscas_cambio",
    "why are you looking for a change": "respuestas_modelo.por_que_buscas_cambio",
    "cuentame de ti en 3 lineas": "respuestas_modelo.cuentame_de_ti_en_3_lineas",
    "tell us about yourself in 3 lines": "respuestas_modelo.cuentame_de_ti_en_3_lineas",
    "que te diferencia": "respuestas_modelo.que_te_diferencia",
    "what differentiates you": "respuestas_modelo.que_te_diferencia",
}

SYNONYMS: Dict[str, str] = {normalize_label(k): v for k, v in _RAW_SYNONYMS.items()}

# Lista CERRADA de claves válidas para el clasificador LLM (sin salario.minimo_aceptable)
CLOSED_BANK_KEYS: List[str] = [
    "nombre",
    "apellidos",
    "datos_personales.nombre_legal",
    "datos_personales.email",
    "datos_personales.telefono",
    "datos_personales.ciudad",
    "datos_personales.pais",
    "datos_personales.zona_horaria",
    "datos_personales.linkedin",
    "datos_personales.github",
    "datos_personales.portafolio",
    "datos_personales.pronombres",
    "autorizacion_de_trabajo.autorizada_para_trabajar_en_colombia",
    "autorizacion_de_trabajo.autorizada_para_trabajar_en_estados_unidos",
    "autorizacion_de_trabajo.autorizada_para_trabajar_en_la_ue",
    "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
    "autorizacion_de_trabajo.dispuesta_a_mudarse",
    "autorizacion_de_trabajo.modalidad",
    "autorizacion_de_trabajo.trabaja_como_contractor",
    "salario.expectativa_mensual",
    "salario.expectativa_anual_usd",
    "salario.salario_actual",
    "disponibilidad.preaviso",
    "disponibilidad.fecha_de_inicio_mas_temprana",
    "disponibilidad.horas_de_solapamiento_con_EEUU",
    "disponibilidad.puede_trabajar_horario_europeo",
    "idiomas.espanol",
    "idiomas.ingles",
    "idiomas.frances",
    "idiomas.italiano",
    "experiencia.anos_totales_profesional",
    "experiencia.anos_qa_automation",
    "experiencia.anos_python",
    "experiencia.anos_playwright",
    "experiencia.anos_selenium",
    "experiencia.anos_llms_agentes_ia",
    "experiencia.anos_javascript_typescript",
    "experiencia.nivel_educativo",
    "preguntas_frecuentes.como_se_entero_de_la_vacante",
    "preguntas_frecuentes.la_han_despedido_alguna_vez",
    "preguntas_frecuentes.trabajo_antes_en_esta_empresa",
    "preguntas_frecuentes.tiene_familiares_en_la_empresa",
    "preguntas_frecuentes.acepta_verificacion_de_antecedentes",
    "preguntas_frecuentes.mayor_de_18",
    "situacion_laboral.empleada_actualmente",
    "situacion_laboral.jefe_sabe_que_busca",
    "situacion_laboral.acuerdos_no_competencia",
    "situacion_laboral.negocios_externos",
    "situacion_laboral.nombre_jefe_actual",
    "autorizacion_de_trabajo.tiene_security_clearance",
    "autorizacion_de_trabajo.puede_obtener_security_clearance",
    "eeo_voluntario.genero",
    "eeo_voluntario.raza_etnicidad",
    "eeo_voluntario.veterano",
    "eeo_voluntario.discapacidad",
]


# ---------------------------------------------------------------------------
# Helpers para extracción y resolución
# ---------------------------------------------------------------------------

def _find_synonym_key(norm_label: str) -> Optional[str]:
    """Busca la clave en SYNONYMS: exacto -> regla salarial anual -> frase contenida -> difflib."""
    norm_label = " ".join(re.sub(r"\b(optional|opcional)\b", " ", norm_label or "").split())  # "GitHub (optional) URL"
    if not norm_label:
        return None
    if norm_label in SYNONYMS:
        return SYNONYMS[norm_label]

    # Regla AP-2b: Etiqueta anual/yearly/annual en USD -> salario.expectativa_anual_usd
    if any(w in norm_label for w in ("annual", "yearly", "anual")) and any(w in norm_label for w in ("salary", "salario", "expectation", "expectativa", "compensation")) and any(c in norm_label for c in ("usd", "$")):
        return "salario.expectativa_anual_usd"

    # Frases contenidas con límites de palabra (de más larga a más corta)
    for syn_key, path in sorted(SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True):
        if len(syn_key) >= 7:
            pattern = r"(?:^|\s)" + re.escape(syn_key) + r"(?:$|\s)"
            if re.search(pattern, norm_label):
                return path

    # difflib como respaldo con corte estricto para evitar falsos positivos
    matches = difflib.get_close_matches(norm_label, list(SYNONYMS.keys()), n=1, cutoff=0.85)
    if matches:
        return SYNONYMS[matches[0]]

    return None


def _get_name_parts(bank: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extrae primer nombre y apellidos desde claves directas o partiendo nombre_legal."""
    datos = bank.get("datos_personales", {}) if isinstance(bank, dict) else {}
    first_name = datos.get("nombre")
    last_name = datos.get("apellidos") or datos.get("apellido")

    if first_name and last_name:
        return str(first_name).strip(), str(last_name).strip()

    nombre_legal = datos.get("nombre_legal")
    if not nombre_legal or str(nombre_legal).strip() in ("", "???"):
        return first_name, last_name

    parts = str(nombre_legal).strip().split()
    if not first_name and parts:
        first_name = parts[0]
    if not last_name and len(parts) > 1:
        last_name = " ".join(parts[1:])
    return first_name, last_name


def _resolve_bank_path(bank: dict, key_path: str) -> Tuple[Any, bool]:
    """Extrae un valor del banco siguiendo la ruta de clave.

    Reglas duras:
    - salario.minimo_aceptable jamás sale como respuesta (retorna None, False).
    - ???, ausente o vacío retorna (None, False).
    """
    if not bank or not isinstance(bank, dict):
        return None, False

    # Regla dura: salario.minimo_aceptable JAMÁS sale como respuesta
    if "minimo_aceptable" in key_path:
        return None, False

    if key_path == "nombre":
        first, _ = _get_name_parts(bank)
        if not first or str(first).strip() in ("", "???"):
            return None, False
        return first, True

    if key_path == "apellidos":
        _, last = _get_name_parts(bank)
        if not last or str(last).strip() in ("", "???"):
            return None, False
        return last, True

    keys = key_path.split(".")
    val = bank
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None, False

    if val is None:
        return None, False
    if isinstance(val, str) and (val.strip() == "" or val.strip() == "???"):
        return None, False
    if isinstance(val, (list, dict)) and len(val) == 0:
        return None, False

    return val, True


def match_option(val: Any, options: Optional[List[str]]) -> Tuple[Optional[str], bool]:
    """Empareja un valor (booleano o texto) contra field.options.

    Retorna (opción elegida, éxito). Si no hay coincidencia suficiente, retorna (None, False).
    """
    if not options:  # desplegable sin opciones leíbles (React): un booleano se escribe Yes/No, no True/False
        return ("Yes" if val else "No") if isinstance(val, bool) else val, True

    # 1. Booleano -> sí/yes o no/no
    if isinstance(val, bool):
        for opt in options:
            norm_opt = normalize_label(opt)
            if val:
                if norm_opt in ("yes", "si", "true", "s", "y") or norm_opt.startswith(("yes ", "si ")):
                    return opt, True
            else:
                if norm_opt in ("no", "false", "n") or norm_opt.startswith(("no ", "false ")):
                    return opt, True
        return None, False

    val_str = str(val).strip()
    norm_val = normalize_label(val_str)

    # 2. Coincidencia exacta tras normalizar
    for opt in options:
        if normalize_label(opt) == norm_val:
            return opt, True

    # 2b. Nivel MCER: "C1 (avanzado)" -> "C1 (Advanced): Can express ideas fluently..."
    cefr = re.match(r"([abc][12])\b", norm_val)
    if cefr:
        for opt in options:
            if normalize_label(opt).startswith(cefr.group(1) + " ") or normalize_label(opt) == cefr.group(1):
                return opt, True

    # 3. Mapeo semántico de opciones comunes (género, demografía, etc.)
    EQUIVALENTS = {
        "mujer": ["female", "woman", "mujer", "femenino"],
        "hombre": ["male", "man", "hombre", "masculino"],
        "prefiero no decir": [
            "decline to self identify", "prefer not to say", "decline to state",
            "prefiero no decir", "i do not wish to answer", "decline", "do not want to answer", "don t wish to answer",
            "prefer not to answer"
        ],
        "no soy veterana": [
            "i am not a protected veteran", "i am not a veteran", "not a veteran",
            "no soy veterana", "no soy veterano", "no"
        ],
    }
    for canonical, syns in EQUIVALENTS.items():
        if norm_val == canonical or norm_val in syns:
            for opt in options:
                norm_opt = normalize_label(opt)
                if any(s in norm_opt or norm_opt in s for s in syns):
                    return opt, True

    norm_opts_map = {normalize_label(opt): opt for opt in options}

    # 4. Inclusión de palabra / subcadena exacta (ej. 'pregrado' en 'pregrado universitario')
    for norm_opt, opt in norm_opts_map.items():
        if len(norm_val) >= 3 and (norm_val in norm_opt or norm_opt in norm_val):
            return opt, True

    # 5. difflib contra field.options
    matches = difflib.get_close_matches(norm_val, list(norm_opts_map.keys()), n=1, cutoff=0.7)
    if matches:
        return norm_opts_map[matches[0]], True

    return None, False


_PROFILE_QUESTION_CATEGORIES: Dict[str, str] = {
    # Universidad / Institución
    "school": "universidad",
    "university": "universidad",
    "universidad": "universidad",
    "institution": "universidad",
    "institucion": "universidad",
    "school name": "universidad",
    "university name": "universidad",
    "nombre de la universidad": "universidad",
    "nombre de la institucion": "universidad",

    # Título / Grado
    "degree": "titulo",
    "titulo": "titulo",
    "degree name": "titulo",
    "titulo universitario": "titulo",
    "titulo obtenido": "titulo",

    # Disciplina / Área de estudio / Carrera
    "discipline": "disciplina",
    "major": "disciplina",
    "carrera": "disciplina",
    "area de estudio": "disciplina",
    "campo de estudio": "disciplina",

    # Empresa actual
    "current company": "empresa_actual",
    "empresa actual": "empresa_actual",
    "compania actual": "empresa_actual",
    "company name": "empresa_actual",
    "current employer": "empresa_actual",
    "org": "empresa_actual",

    # Cargo actual
    "current title": "cargo_actual",
    "cargo actual": "cargo_actual",
    "current role": "cargo_actual",
    "puesto actual": "cargo_actual",
    "job title": "cargo_actual",

    # Resumen profesional
    "professional summary": "resumen_profesional",
    "resumen profesional": "resumen_profesional",
}

PROFILE_SYNONYMS: Dict[str, str] = {normalize_label(k): v for k, v in _PROFILE_QUESTION_CATEGORIES.items()}


def _find_profile_key(norm_label: str) -> Optional[str]:
    """Busca la pregunta en PROFILE_SYNONYMS por coincidencia exacta o difflib.

    Regla AP-2b: El perfil solo responde etiquetas que SON la pregunta
    (School/University/Universidad, Degree/Título, Discipline/Major/Carrera,
    Current company/Empresa actual, Current title/Cargo actual), por diccionario
    exacto/difflib como el banco, nunca por palabra suelta dentro de una pregunta larga.
    """
    if not norm_label:
        return None

    # 1. Coincidencia exacta
    if norm_label in PROFILE_SYNONYMS:
        return PROFILE_SYNONYMS[norm_label]

    # 2. difflib contra el diccionario cerrado de preguntas permitidas
    matches = difflib.get_close_matches(norm_label, list(PROFILE_SYNONYMS.keys()), n=1, cutoff=0.85)
    if matches:
        return PROFILE_SYNONYMS[matches[0]]

    return None


def _resolve_master_profile(profile: dict, norm_label: str) -> Tuple[Any, bool]:
    """Resuelve preguntas contra master_profile.json (experiencia, educación, roles)."""
    if not profile or not isinstance(profile, dict):
        return None, False

    category = _find_profile_key(norm_label)
    if not category:
        return None, False

    if category == "empresa_actual":
        exp = profile.get("experience", [])
        if exp and isinstance(exp, list) and isinstance(exp[0], dict):
            comp = exp[0].get("company_name", "")
            clean = re.split(r"\s+(?:Bogot|Colombia|USA|EEUU)", comp, flags=re.IGNORECASE)[0].strip()
            return clean or comp, True

    elif category == "cargo_actual":
        exp = profile.get("experience", [])
        if exp and isinstance(exp, list) and isinstance(exp[0], dict):
            role = exp[0].get("current_role")
            if role:
                return role, True

    elif category == "universidad":
        edu = profile.get("education", [])
        if edu and isinstance(edu, list) and isinstance(edu[0], dict):
            inst = edu[0].get("institution", "")
            clean = re.split(r"\s+(?:Bogot|Colombia|USA|EEUU)", inst, flags=re.IGNORECASE)[0].strip()
            return clean or inst, True

    elif category == "titulo":
        edu = profile.get("education", [])
        if edu and isinstance(edu, list) and isinstance(edu[0], dict):
            deg = edu[0].get("degree")
            if deg:
                return deg, True

    elif category == "disciplina":
        # el perfil no tiene campo aparte: la carrera va en "degree" después del guion ("BE – Industrial Engineering")
        edu = profile.get("education", [])
        if edu and isinstance(edu, list) and isinstance(edu[0], dict) and edu[0].get("degree"):
            return re.split(r"\s+[–—-]\s+", edu[0]["degree"], maxsplit=1)[-1], True

    elif category == "resumen_profesional":
        summary = profile.get("professional_summary")
        if summary:
            return summary, True

    return None, False


# ---------------------------------------------------------------------------
# Clasificador LLM y Generación de Texto Abierto
# ---------------------------------------------------------------------------

def _classify_with_llm(field: Field, llm_fn: Optional[Callable] = None) -> Optional[str]:
    """Clasificador inyectable (tests) contra CLOSED_BANK_KEYS. Sin función no llama a la IA: el agente
    (_generate_open_text) ya recibe el banco, y un clasificador aparte gastaba una llamada extra por campo."""
    return llm_fn(field) if llm_fn else None


def _is_open_text_field(field: Field, norm_label: str) -> bool:
    """Detecta si un campo corresponde a una pregunta abierta (textarea, why..., tell us...)."""
    if field.options:
        return False
    if field.kind in ("textarea", "textbox", "contenteditable"):
        return True
    open_keywords = (
        "why", "tell us", "describe", "explain", "share your",
        "por que", "cuentanos", "cuentame", "explica", "describe",
        "cover letter", "cover note", "message to hiring manager",
        "rationale", "evidence"
    )
    return any(kw in norm_label for kw in open_keywords)


_SIN_CUPO = False  # se prende al primer AllProvidersExhausted de la corrida
_OPEN_CACHE = {}


def _answer_language(field: Field, job: Optional[dict]) -> str:
    """Idioma de la respuesta: el de la pregunta si es claro; si no (etiquetas cortas como "Projects"), el de la
    vacante. Por defecto inglés."""
    if _is_spanish(field.label):
        return "Spanish"
    if len(re.findall(r"[a-zA-Z]+", field.label or "")) >= 4:
        return "English"
    from job_filters import detect_language
    return "Spanish" if detect_language(str((job or {}).get("description", ""))) == "es" else "English"


def _generate_open_text(
    field: Field,
    job: Optional[dict],
    bank: dict,
    profile: dict,
    llm_text_fn: Optional[Callable] = None
) -> Optional[str]:
    """Genera texto abierto con LLM usando perfil + vacante + respuestas_modelo como guía."""
    if llm_text_fn:
        return llm_text_fn(field, job, bank, profile)

    global _SIN_CUPO
    if _SIN_CUPO:  # ya se agotaron todos los proveedores en esta corrida: no reintentar 11 proveedores por campo
        return None
    try:
        import llm_chain
        lang = _answer_language(field, job)
        model_answers = bank.get("respuestas_modelo", {}) if isinstance(bank, dict) else {}
        valid_guides = {k: v for k, v in model_answers.items() if v and str(v).strip() != "???"}
        # Al LLM solo lo que puede necesitar: sin datos de contacto ni diversidad (esos se llenan sin IA), sin el
        # salario mínimo (nunca sale), sin reglas internas.
        public_bank = {k: v for k, v in (bank or {}).items()
                       if k not in ("datos_personales", "eeo_voluntario", "respuestas_modelo", "salario", "reglas",
                                    "aprendidas", "estilo_escritura", "situacion_laboral")}
        # personalidad y estilo (master_profile.json, de la entrevista): la carta y las respuestas abiertas suenan a
        # la persona. estilo_escritura del banco: perfiles que aún no repiten la entrevista (ahí se migra)
        style = {k: v for k, v in ((profile or {}).get("personalidad") or (bank or {}).get("estilo_escritura")
                                   or {}).items() if v and str(v).strip() not in ("???", "no aplica")}
        for k in ("muestra_escritura", "muestra"):
            if style.get(k):
                style[k] = str(style[k])[:1500]
        if isinstance(bank, dict) and isinstance(bank.get("salario"), dict):
            public_bank["salario"] = {k: v for k, v in bank["salario"].items() if k != "minimo_aceptable"}
        name = (profile or {}).get("personal_info", {}).get("full_name") or "the candidate"

        # Todo en inglés salvo el idioma de salida: el perfil y casi todas las vacantes están en inglés, y un prompt
        # en español empujaba al modelo a contestar en español formularios en inglés.
        system_prompt = (
            f"You are {name}, filling in a job application form. Write ONLY the text that goes into the field.\n"
            f"OUTPUT LANGUAGE: {lang}. Always, even if the profile or these instructions are in another language.\n"
            "Rules:\n"
            "- First person. Plain, direct, specific. No filler ('I am excited', 'passionate', 'thrilled'), "
            "no em dashes, no markdown, no placeholders like [Company].\n"
            "- Never invent experience, titles, numbers or dates. Use only the profile and the answer bank below; "
            "copy facts from them exactly.\n"
            "- Field with options: reply with EXACTLY one of the options, nothing else.\n"
            "- Short field (text, select, radio, checkbox): only the value, no sentence.\n"
            "- Yes/No about experience: Yes only if the profile shows EXACTLY that experience. Similar but different "
            "(designing vs developing, agency vs software company, using a tool vs administering it) is No. "
            "When in doubt, No. 'A or B' (e.g. Java or Python): Yes if the profile shows either one.\n"
            "- Commitments, consent and availability (accept terms or policies, travel, office or hybrid, schedule, "
            "extra interviews, 'use only my own words'): reply only NO_SE. The person decides those.\n"
            "- Personal data that is not in the profile or bank (ID number, who referred you, dates, grades, GPA, "
            "exam scores): reply only NO_SE. A missing fact is NO_SE, never 'no degree' or 'none'.\n"
            "- Open question: 2 to 5 sentences with one real achievement from the profile that fits this job. "
            "If the profile lacks that exact experience, describe the closest real one (e.g. testing that kind of "
            "system); never write 'I have no experience'.\n"
            "- Cover letter: greeting 'Dear <company> team,' (or 'Dear Hiring Team,' if the company is unknown), "
            "3 short paragraphs (why this role, 1-2 achievements that match the job, closing), then the name. "
            "No address, no date.\n"
        )
        human_template = (
            "Form question: {question}\n"
            "Field type: {kind}. Options: {options}\n\n"
            "Candidate profile:\n{profile_summary}\n"
            "Answer bank: {bank}\n"
            "Candidate voice examples (match this tone): {guides}\n"
            "Candidate personality and writing style (write like the sample, follow the tone, never use the 'evitar' "
            "words; use how they work, strengths, motivations and values for 'about you', 'why us' and behavioral "
            "questions, and for answers not covered elsewhere): {style}\n\n"
            "Job:\n{job_info}\n\n"
            "{final_instruction}"
        )
        profile_summary = ""
        if profile:
            profile_summary = (
                f"Summary: {profile.get('professional_summary', '')}\n"
                f"Target roles: {profile.get('target_roles', '')}\n"
                f"Experience: {json.dumps(profile.get('experience', []), ensure_ascii=False)[:3000]}\n"
                f"Projects: {json.dumps(profile.get('portfolio_projects', []), ensure_ascii=False)[:1500]}\n"
                # sin esto contestó "no degree" a "What was your bachelor's degree result?"
                f"Education: {json.dumps(profile.get('education', []), ensure_ascii=False)[:800]}\n"
                # historias de la entrevista (proyecto favorito, en qué es excelente...): material para preguntas abiertas
                f"Stories: {json.dumps(profile.get('stories', []), ensure_ascii=False)[:2500]}"
            )
        job_info = ""
        if job:
            job_info = (f"Company: {job.get('company', '')}\nTitle: {job.get('title', '')}\n"
                        f"Description: {str(job.get('description', ''))[:2500]}")
        variables = {
            "question": field.label or field.key,
            "kind": field.kind,
            # casilla suelta (sin opciones): Yes = marcarla, No = dejarla sin marcar
            "options": (", ".join(field.options) if field.options
                        # "none, write the answer" lo copiaban tal cual en un desplegable sin opciones leídas
                        # desplegable de sí/no cuyas opciones no se leyeron: contestaba "Yes, I have hands-on experience..."
                        else "Yes, No" if field.kind == "checkbox" or (field.kind in ("combobox", "select", "radio")
                                                                       and _YESNO.search(normalize_label(field.label)))
                        else "free text"),
            "profile_summary": profile_summary,
            # van como variables (no dentro del prompt): sus llaves {} romperían la plantilla
            "bank": json.dumps(public_bank, ensure_ascii=False, default=str)[:2000],
            "guides": json.dumps(valid_guides, ensure_ascii=False) if valid_guides else "none",
            "style": json.dumps(style, ensure_ascii=False) if style else "none",
            "job_info": job_info,
            "final_instruction": ("Responde solo en español." if lang == "Spanish"
                                  else "Answer only in English."),
        }
        # misma pregunta en la misma vacante (formularios que repiten el bloque): una sola llamada
        cache_key = (variables["question"], field.kind, variables["options"], job_info[:200], lang)
        if cache_key not in _OPEN_CACHE:
            res = llm_chain.invoke_text(system_prompt, human_template, variables)
            _OPEN_CACHE[cache_key] = res.strip() if res else None
        return _OPEN_CACHE[cache_key]
    except Exception as e:
        if type(e).__name__ == "AllProvidersExhausted":
            _SIN_CUPO = True
            logger.warning("Sin cupo en todos los proveedores: el resto de campos de esta corrida queda para la persona.")
        else:
            logger.warning(f"Generación de texto abierto falló: {e}")

    return None


# ---------------------------------------------------------------------------
# API Principal: answer() y learn()
# ---------------------------------------------------------------------------

def _load_bank(answers_path: Optional[str] = None) -> dict:
    """answers.yaml del perfil activo (o el indicado); {} si no existe o está mal formado."""
    if answers_path is None:
        answers_path = profile_paths.resolve("answers.yaml")
    if answers_path and os.path.exists(answers_path):
        try:
            with open(answers_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Error cargando answers.yaml de {answers_path}: {e}")
    return {}


def _answer_raw(
    field: Field,
    job: Optional[dict] = None,
    answers_path: Optional[str] = None,
    master_profile_path: Optional[str] = None,
    llm_classifier_fn: Optional[Callable] = None,
    llm_text_fn: Optional[Callable] = None,
) -> Answer:
    """Determina la respuesta para un campo según el orden estricto de la Fase D:

    1. Archivos (resume/cv -> job['cv_path']).
    2. Banco (answers.yaml con sinónimos es/en y difflib).
    3. aprendidas: del mismo YAML.
    4. master_profile.json.
    5. Clasificador LLM con lista CERRADA de claves (el valor sale del banco).
    6. Texto abierto con LLM (perfil + vacante + respuestas_modelo).
    7. needs_human = True (datos ausentes, '???', no identificados).
    """
    job = job or {}
    norm_label = normalize_label(field.label or field.key)
    norm_key = normalize_label(field.key)

    # -----------------------------------------------------------------------
    # 0. Archivos (resume / cv / cover letter)
    # -----------------------------------------------------------------------
    if field.kind == "file":
        # la carta primero: Greenhouse rotula "Attach" tanto el CV como la carta (solo cambia el key: cover_letter)
        is_cover_file = any(w in norm_label or w in norm_key for w in ("cover", "letter", "carta"))
        is_resume = not is_cover_file and any(w in norm_label or w in norm_key for w in ("resume", "cv", "curriculum", "autofill", "attach"))
        if is_resume or not any(w in norm_label or w in norm_key for w in ("cover", "letter", "carta", "portfolio")):
            cv_path = job.get("cv_path")
            if cv_path and str(cv_path).strip():
                return Answer(value=str(cv_path).strip(), source="file", needs_human=False)
            return Answer(value=None, source="file", needs_human=True)

        is_cover = any(w in norm_label or w in norm_key for w in ("cover", "letter", "carta"))
        if is_cover:
            cover_path = job.get("cover_letter_path") or job.get("cover_letter")
            if cover_path and str(cover_path).strip():
                return Answer(value=str(cover_path).strip(), source="file", needs_human=False)
            # carta opcional sin archivo: se deja vacía (Greenhouse siempre pone el campo, casi nunca es obligatorio)
            return Answer(value=None if field.required else "", source="file" if field.required else "skip",
                          needs_human=bool(field.required))

        return Answer(value=None, source="file", needs_human=True)

    bank = _load_bank(answers_path)

    # Cargar master_profile.json
    if master_profile_path is None:
        master_profile_path = profile_paths.resolve("master_profile.json")

    profile = {}
    if master_profile_path and os.path.exists(master_profile_path):
        try:
            with open(master_profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f) or {}
        except Exception as e:
            logger.warning(f"Error cargando master_profile.json de {master_profile_path}: {e}")

    # Regla dura: salario.minimo_aceptable jamás sale como respuesta
    if "minimo_aceptable" in norm_label or "minimo aceptable" in norm_label or "minimum acceptable" in norm_label:
        return Answer(value=None, source="bank", needs_human=True)

    # -----------------------------------------------------------------------
    # 1. Banco (answers.yaml) vía sinónimos y difflib
    # -----------------------------------------------------------------------
    key_path = _find_synonym_key(norm_label) or _find_synonym_key(norm_key)
    if key_path:
        val, ok = _resolve_bank_path(bank, key_path)
        if ok:
            # Comprobación de moneda para preguntas salariales (Regla AP-2b)
            if key_path.startswith("salario.") and key_path != "salario.salario_actual":
                label_curr = _detect_currency(field.label or field.key)
                val_curr = _detect_currency(str(val))
                if not val_curr and "usd" in key_path:
                    val_curr = "USD"
                if label_curr and val_curr and label_curr != val_curr:
                    return Answer(value=None, source="bank", needs_human=True)

            matched_opt, opt_ok = match_option(val, field.options)
            if opt_ok:
                return Answer(value=matched_opt, source="bank", needs_human=False)
            else:
                return Answer(value=None, source="bank", needs_human=True)
        else:
            # Clave identificada pero valor es ???, vacío o ausente en el banco
            return Answer(value=None, source="bank", needs_human=True)

    # -----------------------------------------------------------------------
    # 2. Aprendidas (sección aprendidas: de answers.yaml)
    # -----------------------------------------------------------------------
    learned = bank.get("aprendidas", {}) if isinstance(bank, dict) else {}
    if learned and isinstance(learned, dict):
        norm_learned_map = {normalize_label(k): v for k, v in learned.items()}
        target_val = None
        if norm_label in norm_learned_map:
            target_val = norm_learned_map[norm_label]
        else:
            m = difflib.get_close_matches(norm_label, list(norm_learned_map.keys()), n=1, cutoff=0.75)
            if m:
                target_val = norm_learned_map[m[0]]

        if target_val is not None and str(target_val).strip() not in ("", "???"):
            matched_opt, opt_ok = match_option(target_val, field.options)
            if opt_ok:
                return Answer(value=matched_opt, source="learned", needs_human=False)
            else:
                return Answer(value=None, source="learned", needs_human=True)

    # -----------------------------------------------------------------------
    # 3. master_profile.json
    # -----------------------------------------------------------------------
    prof_val, prof_ok = _resolve_master_profile(profile, norm_label)
    if not prof_ok:
        prof_val, prof_ok = _resolve_master_profile(profile, norm_key)
    if prof_ok and prof_val is not None and str(prof_val).strip() not in ("", "???"):
        matched_opt, opt_ok = match_option(prof_val, field.options)
        if opt_ok:
            return Answer(value=matched_opt, source="profile", needs_human=False)
        else:
            return Answer(value=None, source="profile", needs_human=True)

    # -----------------------------------------------------------------------
    # 4. Clasificador LLM (lista CERRADA de claves del banco, solo si hay banco)
    # -----------------------------------------------------------------------
    if bank and not _is_open_text_field(field, norm_label):  # una pregunta abierta nunca es una clave del banco
        llm_key = _classify_with_llm(field, llm_fn=llm_classifier_fn)
        if llm_key and llm_key in CLOSED_BANK_KEYS and llm_key != "ninguna":
            val, ok = _resolve_bank_path(bank, llm_key)
            if ok:
                if llm_key.startswith("salario.") and llm_key != "salario.salario_actual":
                    label_curr = _detect_currency(field.label or field.key)
                    val_curr = _detect_currency(str(val))
                    if not val_curr and "usd" in llm_key:
                        val_curr = "USD"
                    if label_curr and val_curr and label_curr != val_curr:
                        return Answer(value=None, source="bank", needs_human=True)

                matched_opt, opt_ok = match_option(val, field.options)
                if opt_ok:
                    return Answer(value=matched_opt, source="bank", needs_human=False)
                else:
                    return Answer(value=None, source="bank", needs_human=True)
            else:
                return Answer(value=None, source="bank", needs_human=True)

    # -----------------------------------------------------------------------
    # 5. Texto abierto con LLM
    # -----------------------------------------------------------------------
    # el agente responde cualquier campo que quede (no solo textarea) con perfil + banco + vacante + tono
    open_val = _generate_open_text(field, job, bank, profile, llm_text_fn=llm_text_fn)
    # un campo corto con un párrafo, o un texto que razona en voz alta, es un modelo que no siguió las reglas
    too_long = field.kind not in ("textarea", "textbox", "contenteditable") and len(str(open_val or "")) > 200
    # modelo local razonando en voz alta: "We are filling a textarea field: ..."
    thinking = re.match(r"(we are|we need|let me|okay|ok,|the user|i need to|first,|the field)\b", str(open_val or "").strip(), re.I)
    # ...o que repite el prompt ("Form question: ...\nField type: ...") antes de la respuesta (openhermes)
    thinking = thinking or re.search(r"^(form question|field type|field)\s*:", str(open_val or ""), re.I | re.M)
    # texto que se descalifica solo ("I have no experience designing..."): mejor que lo escriba la persona
    thinking = thinking or (field.kind in ("textarea", "textbox", "contenteditable") and re.match(
        r"(i have no|i don.?t have|i do not have|no tengo)\b", str(open_val or "").strip(), re.I))
    if (open_val and "NO_SE" not in str(open_val) and not too_long and "<think>" not in str(open_val) and not thinking
            and normalize_label(str(open_val)) not in ("ninguna", "none", "n a", "free text", "write the answer")):
        # guiones tipográficos (‑ ‐ –) que algunos modelos meten en "multi‑agent": en un formulario se ven raros
        open_val = re.sub("[‐‑‒–]", "-", str(open_val))
        open_val = re.sub(r"\s*—\s*", ", ", open_val)  # raya larga: el prompt la prohíbe y delata texto de IA
        matched_opt, opt_ok = match_option(open_val, field.options)
        if opt_ok:
            return Answer(value=matched_opt, source="llm", needs_human=False)

    # -----------------------------------------------------------------------
    # 6. No sabe -> needs_human = True
    # -----------------------------------------------------------------------
    return Answer(value=None, source="none", needs_human=True)


# Redes sociales: se dejan en blanco. Solo etiquetas cortas ("X", "Twitter URL"), no "X years of experience".
_SOCIAL = re.compile(r"(twitter|x|instagram|ig|tiktok|facebook|threads|snapchat|bluesky)( (url|handle|profile|username|link|account))?")
_RESUME_LINK = re.compile(r"\b(resume|cv|curriculum|hoja de vida)\b.*\b(link|url|enlace)\b|\b(link|url|enlace)\b.*\b(resume|cv|curriculum|hoja de vida)\b")
_LOCATION = re.compile(r"(current )?location|where are you (based|located)|ubicacion( actual)?")
_COVER = re.compile(r"cover (letter|note)|carta de (presentacion|motivacion)|motivation letter|message to (the )?hiring")
# Valores del banco en español -> inglés cuando el formulario está en inglés y no trae opciones
_ES_TO_EN = {"mujer": "Female", "hombre": "Male", "prefiero no decir": "I don't wish to answer",
             "no soy veterana": "I am not a protected veteran", "no soy veterano": "I am not a protected veteran",
             "no aplica": "N/A"}  # lo que guarda la entrevista cuando algo no aplica (ej. sin jefe actual)


def _is_spanish(text: str) -> bool:
    return bool(re.search(r"[áéíóúñ¿¡]|\b(de|el|la|tu|su|que|por|con|cual|tienes|eres)\b", (text or "").lower()))


# Pregunta de sí/no ("Are you fluent in English?"): el valor del banco ("C1 (avanzado)") no sirve tal cual
# "Where do you plan...", "How did you hear..." no son de sí/no aunque lleven "do you"
_YESNO = re.compile(r"^(?!(\w+ ){0,3}(what|where|which|when|how|why|who|cual|donde|como|cuando)\b)"  # "In what country are you..."
                    r"((is|are|do|does|did|can|could|will|would|have|has)\b|.*\b(are|do|can|have|will|would) you\b|"
                    r"(estas|tienes|puedes|eres|cuentas|es)\b)")
# Firmas, certificaciones y consentimientos: los decide la persona, nunca la IA (escribió iniciales "VA" sola)
_CONSENT = re.compile(r"by initialing|\binitials?\b|i (hereby )?(certify|agree|acknowledge|consent|attest)|"
                      r"\b(acepto|autorizo|certifico|declaro)\b|signature|firma|"
                      r"^(i understand|entiendo que|estoy de acuerdo|confirmo)|read and agree|confirm that you|"
                      # IA que transcribe la entrevista, compartir el CV con terceros, "Acknowledge" suelto
                      r"\bconsent\b|notetaker|transcrib|share my (resume|cv|information)|^acknowledge\b")
# Aceptar el aviso de privacidad para postularse (Twilio/Okta "Acknowledge"): se marca salvo que el banco diga que no.
# Certificaciones, firmas e iniciales siguen siendo de la persona.
_PRIVACY_ACK = re.compile(r"^(i )?acknowledge$|privacy (policy|notice)|processing of my personal data|aviso de privacidad")
_SALARY = re.compile(r"salar|compensation|pay expectation|expected pay|remuneraci|aspiracion")
# "authorized to work ... in the country where this job is based": depende del país de la vacante
_AUTH_HERE = re.compile(r"authori[sz]ed to work.*\b(country (where|in which|for which)|this country|that country)|"
                        r"autorizad[oa] para trabajar en (el|este) pais|right to work where (this|the) role is (listed|based|located)")
# "authorized to work in the country you reside": es el país de la persona, no el de la vacante
_AUTH_HOME = re.compile(r"authori[sz]ed to work in the country (you (reside|live)|where you (reside|live)|of (your )?residence)")
_PREF_NAME = re.compile(r"preferred name.*same as.*legal name")
# Compromisos (oficina, presencialidad, viajes, mudarse, fecha de inicio): el prompt le pide a la IA no contestarlos
# y aun así respondía "No" a "work in the office 5 days a week?" (eso descarta la postulación). Lo decide la persona.
_COMMITMENT = re.compile(r"on ?site|in (the )?office|office \d|hybrid|hibrid|presencial|oficina|relocat|mudar|travel|viaj|"
                         r"dispuest[oa]|willing to|remot[ao] desde|"
                         r"able to commit|willing to work|start date|\bnotice\b|available to start|fecha de inicio|"
                         # datos personales que la IA no sabe ("Have you notified your current manager?" -> "No")
                         r"current manager|employment agreement|non.?compete|post.?employment|"
                         r"check all that apply|select all that apply|"  # elegía solo English en idiomas
                         r"\bsecret\b|encoded")  # retos de Ramp ("figure out the secret"): inventaba una respuesta
# Notas y resultados académicos que no están en el perfil: la IA contestó "no degree" e inventó un puntaje del SABER
_GRADES = re.compile(r"high school|secondary school|colegio|bachillerato|\bgpa\b|\bgrades?\b|degree result|"
                     r"calificaci|promedio|\bscore\b|puntaje")
# "Cumplo con la experiencia requerida": un No de la IA descarta la postulación; si no cumple, que lo marque ella
_MEETS_REQ = re.compile(r"\b(cumplo|cumples|meet|meets)\b.*\b(requ|qualif)|experiencia requerida|required experience")
# Pregunta de seguimiento opcional ("If you selected No, ...", "If so, share their name"): en blanco
# Opcionales que no aportan: la IA repetía un logro en "Additional information"; "Name pronunciation" ponía el nombre
# "Resume/CV" en texto (Okta "Paste") cuando ya va el archivo: en blanco
_OPTIONAL_SKIP = re.compile(r"^additional information|pronunciation|pronounce|^(resume|cv|resume cv)$")
_YES_NO_VALUES = ("yes", "no", "si", "true", "false")
_FOLLOWUP = re.compile(r"^if (you|yes|no|not|so|applicable)\b|\bif so\b|^en caso de|^si (respondiste|seleccionaste|marcaste)")


def _salary_answer(field: Field, bank: dict) -> Answer:
    """Salario según la moneda que pide la etiqueta. Nunca pasa por la IA (respondía EUR a una pregunta en COP).
    COP -> salario.expectativa_mensual_cop · EUR -> salario.expectativa_mensual · USD o sin moneda -> la anual en
    USD (o /12 si pide mensual). Sin el dato en esa moneda: se le pregunta a la persona."""
    sal = (bank or {}).get("salario") or {}
    label = field.label or field.key
    norm = normalize_label(label)
    human = Answer(value=None, source="bank", needs_human=True)
    if _YESNO.search(norm):  # "Is the salary range of X acceptable?" es una decisión, no un monto
        return human
    cur = _detect_currency(label)
    if not cur and re.search(r"local currency|moneda local", norm):
        cur = "COP" if normalize_label(((bank or {}).get("datos_personales") or {}).get("pais", "")) == "colombia" else None
        if not cur:
            return human
    monthly = bool(re.search(r"\b(month|monthly|mensual|mes|mensuales)\b", norm))
    if cur in ("COP", "EUR"):
        val = sal.get("expectativa_mensual_cop" if cur == "COP" else "expectativa_mensual")
        if not val or str(val).strip() == "???" or _detect_currency(str(val)) not in (cur, None) or not monthly and cur == "EUR":
            return human
        return Answer(value=str(val), source="bank", needs_human=False) if not field.options else human
    try:
        annual = int(re.sub(r"[^\d]", "", str(sal.get("expectativa_anual_usd") or "")))
    except ValueError:
        return human
    amount = round(annual / 12) if monthly else annual
    if field.kind == "number":
        return Answer(value=str(amount), source="bank", needs_human=False)
    if field.options:  # rangos ("$40k-$60k"): elegir uno es fácil de errar, mejor que lo marque la persona
        return human
    period = ("al mes" if monthly else "al año") if _is_spanish(label) else ("per month" if monthly else "per year")
    return Answer(value=f"USD {amount:,} {period}", source="bank", needs_human=False)


_OFFICE = re.compile(r"on ?site|in (the )?office|from (the |our )?offices?|out of (our|the) office|office \d|hybrid|"
                     r"anchor days|presencial|hibrid|oficina")
_RELOCATE = re.compile(r"relocat|mudar(te|se)?\b|reubicar")
_NOTICE_DAYS = re.compile(r"(\d+)[ -]?days? (of )?notice")
_BASED_IN = re.compile(r"^are you (currently )?(based (in|out of)|an? resident of|residing in|living in) (.+)")
_TZ = re.compile(r"\b(us|eu|europe\w*)\b.*time ?zone")
_FOREIGN = re.compile(r"\b(united states|usa|u s|united kingdom|england|canada|germany|india|mexico|brazil|brasil|spain|"
                      r"espana|argentina|chile|peru|europe|australia|new york|san francisco|london|"
                      # ponytail: los estados/ciudades de EE.UU. y Canadá más comunes en vacantes, no la lista completa
                      r"texas|austin|california|florida|washington|seattle|boston|chicago|illinois|colorado|denver|"
                      r"atlanta|georgia|virginia|north carolina|new jersey|massachusetts|ontario|toronto)\b")
_US_WORDS = re.compile(r"\b(us|usa|united states|new york|san francisco|california|seattle|austin|boston|chicago)\b")


def _yes_no(field: Field, value: bool) -> Answer:
    """Sí/No en el formato del campo: opción que coincide, casilla marcada o vacía, texto Yes/No (Sí/No en español)."""
    if field.options:
        opt, ok = match_option(value, field.options)
        return Answer(opt, "bank", False) if ok else Answer(None, "bank", True)
    if field.kind == "checkbox":
        return Answer("Yes" if value else "", "bank", False)
    word = ("Sí" if value else "No") if _is_spanish(field.label) else ("Yes" if value else "No")
    return Answer(word, "bank", False)


def _from_preferences(field: Field, norm_label: str, job: dict, bank: dict) -> Optional[Answer]:
    """Preguntas de condiciones que el banco ya contesta: modalidad, mudarse, preaviso, permiso fuera de tu país,
    zona horaria y "¿estás en X?". None = no aplica, sigue el resto de reglas."""
    if field.kind in ("file", "textarea") or (field.options and not all(
            normalize_label(o) in _YES_NO_VALUES or re.match(r"(select|choose)", normalize_label(o)) for o in field.options)):
        return None
    if not (_YESNO.search(norm_label) or field.kind == "checkbox"):
        return None
    auth = bank.get("autorizacion_de_trabajo") or {}
    datos = bank.get("datos_personales") or {}
    modalidad = normalize_label(str(auth.get("modalidad") or ""))
    if _OFFICE.search(norm_label) and "remot" in modalidad:
        return _yes_no(field, False)  # "Solo remoto": oficina, híbrido o días presenciales -> No
    if _RELOCATE.search(norm_label) and isinstance(auth.get("dispuesta_a_mudarse"), bool):
        return _yes_no(field, auth["dispuesta_a_mudarse"])
    notice = _NOTICE_DAYS.search(norm_label)
    have = re.match(r"\s*(\d+)\s*(semana|week|mes|month|dia|day)", normalize_label(str(
        (bank.get("disponibilidad") or {}).get("preaviso") or "")))
    if notice and have:
        days = int(have.group(1)) * {"s": 7, "w": 7, "m": 30, "d": 1}[have.group(2)[0]]
        return _yes_no(field, days == int(notice.group(1)))
    offset = re.search(r"utc\s*([+-]\d+)", str(datos.get("zona_horaria") or "").lower())
    tz = _TZ.search(norm_label)
    if tz and offset:
        hours = int(offset.group(1))
        return _yes_no(field, -10 <= hours <= -4 if tz.group(1) == "us" else -1 <= hours <= 3)
    based = _BASED_IN.match(norm_label)
    home = {normalize_label(str(datos.get(k) or "")) for k in ("ciudad", "pais")} - {""}
    # "based in {location}" (plantilla rota de Dialpad): el lugar es el de la vacante
    where = normalize_label(str(job.get("location") or "")) if "{" in field.label else based and based.group(4)
    if based and where and home:
        return _yes_no(field, any(h in where for h in home))
    return None


def _foreign_authorization(field: Field, norm_label: str, job: dict, bank: dict) -> Optional[Answer]:
    """Permiso de trabajo en el país de la vacante cuando NO es el tuyo: si el banco dice que solo tienes permiso en
    tu país, la respuesta es No. Sin ubicación clara de la vacante -> None (te pregunta)."""
    auth = bank.get("autorizacion_de_trabajo") or {}
    home = normalize_label(str((bank.get("datos_personales") or {}).get("pais") or ""))
    loc = normalize_label(str(job.get("location") or ""))
    if not home or not loc or home in loc or loc in ("remote", "remoto", "anywhere"):
        return None
    others = [v for k, v in auth.items() if k.startswith("autorizada_para_trabajar_en_") and normalize_label(k[28:]) != home]
    if not others or any(v is not False for v in others):
        return None  # tiene (o no dijo) permiso en otro lado: mejor que lo decida la persona
    if "source" in norm_label:  # "What is the source of your right to work there?": la opción de "necesito patrocinio"
        opt = next((o for o in field.options or [] if re.search(r"sponsor|patrocin", normalize_label(o))), None)
        return Answer(opt or "sponsorship", "bank", False)  # sin opciones: el combobox filtra por lo que se escribe
    return _yes_no(field, False)


_CERTIFY = re.compile(r"initial|signature|firma|certify|certifico|attest|declaro|true and (complete|correct|accurate)")
# "Entiendo que es presencial en Quito", "acepto usar solo mis palabras, sin IA": suenan a consentimiento pero son
# compromisos con ESA vacante; los contesta la persona (aprendidas: de la entrevista), nunca "acepto términos"
_CONSENT_COMMITMENT = re.compile(r"tiempo completo|full ?time|disponib|own words|plagiari|propias palabras")


def is_consent(norm_label: str) -> bool:
    """Consentimiento, firma o términos (los decide politicas.* del banco), no un compromiso con la vacante."""
    # "Privacy Notice" no es un preaviso (\bnotice\b de _COMMITMENT)
    return bool(_CONSENT.search(norm_label)) and (bool(_CERTIFY.search(norm_label) or "privacy" in norm_label) or not (
        _COMMITMENT.search(norm_label) or _CONSENT_COMMITMENT.search(norm_label)))


def _consent_answer(field: Field, norm_label: str, bank: dict) -> Answer:
    """Consentimientos y firmas con lo que la persona decidió en la entrevista (politicas.*); sin decisión, te pregunta.
    Certificar que la información es verdadera (iniciales, firma, casilla) -> politicas.certifica_veracidad.
    Un consentimiento con sinónimo propio (grabación con IA, compartir el CV) -> esa clave; cualquier otro "acepto /
    i agree" para postular -> politicas.acepta_terminos_para_postular."""
    pol = bank.get("politicas") or {}
    key = _find_synonym_key(norm_label) or ""
    if _CERTIFY.search(norm_label):
        decided = pol.get("certifica_veracidad")
    elif key.startswith("politicas."):
        decided = pol.get(key.split(".", 1)[1])
    elif re.search(r"privacy|privacidad|personal data|datos personales", norm_label):
        decided = pol.get("acepta_avisos_privacidad")
    else:
        decided = pol.get("acepta_terminos_para_postular")
    if not isinstance(decided, bool):
        return Answer(None, "none", True)
    if field.kind in ("text", "textarea") and not field.options:  # se firma escribiendo: iniciales o nombre legal
        name = str((bank.get("datos_personales") or {}).get("nombre_legal") or "").split()
        if not decided or not name:
            return Answer(None, "bank", True)
        if "initial" in norm_label:
            return Answer("".join(w[0].upper() for w in name), "bank", False)
        return Answer(" ".join(name), "bank", False)
    return _yes_no(field, decided)


_UNIVERSITY = re.compile(r"\b(university|universidad|college|school|institution|institucion)\b")


def _university_answer(field: Field, master_profile_path: Optional[str]) -> Optional[Answer]:
    """Desplegable de universidad: la de la persona (la primera de education en el perfil) o, si no está, la opción
    "Other / not listed". None = no es desplegable o el perfil no la tiene, sigue el resto de reglas."""
    path = master_profile_path or profile_paths.resolve("master_profile.json")
    try:
        edu = (json.load(open(path, encoding="utf-8")) or {}).get("education") or []
    except (OSError, ValueError):
        return None
    inst = str(edu[0].get("institution") or "").split(",")[0].strip() if edu and isinstance(edu[0], dict) else ""
    if not inst or not field.options:  # campo de texto: ya lo contesta el perfil (paso 3 de _answer_raw)
        return None
    norm = normalize_label(inst)
    opts = {normalize_label(o): o for o in field.options}
    hit = next((o for n, o in opts.items() if len(n) >= 10 and (n in norm or norm in n)), None)
    close = difflib.get_close_matches(norm, list(opts), n=1, cutoff=0.8)
    other = next((o for n, o in opts.items() if re.search(r"\bother\b|not listed|\botra\b", n)), None)
    pick = hit or (opts[close[0]] if close else other)
    return Answer(pick, "profile", False) if pick else None


# idiomas del banco (claves en español) -> cómo los nombran los formularios
_LANG_NAMES = {"ingles": "english", "espanol": "spanish", "frances": "french", "italiano": "italian",
               "aleman": "german", "portugues": "portuguese", "japones": "japanese", "chino": "chinese|mandarin"}


def _languages_answer(field: Field, bank: dict) -> Optional[Answer]:
    """'Language skill(s) (check all that apply)': las opciones de los idiomas del banco con nivel B1 o más (lista)."""
    spoken = [_LANG_NAMES.get(normalize_label(k), normalize_label(k)) for k, v in (bank.get("idiomas") or {}).items()
              if re.match(r"\s*(b1|b2|c1|c2|nativ)", str(v).lower())]
    chosen = [o for o in field.options if any(re.search(rf"\b({s})\b", normalize_label(o)) for s in spoken)]
    return Answer(chosen, "bank", False) if chosen else None


def answer(
    field: Field,
    job: Optional[dict] = None,
    answers_path: Optional[str] = None,
    master_profile_path: Optional[str] = None,
    llm_classifier_fn: Optional[Callable] = None,
    llm_text_fn: Optional[Callable] = None,
) -> Answer:
    """_answer_rules + lo que nunca debe frenar una postulación: un campo OPCIONAL sin respuesta se deja en blanco."""
    res = _answer_rules(field, job, answers_path, master_profile_path, llm_classifier_fn, llm_text_fn)
    if res.needs_human and not field.required and field.kind != "file":
        return Answer(value="", source="skip", needs_human=False)
    return res


def _answer_rules(
    field: Field,
    job: Optional[dict] = None,
    answers_path: Optional[str] = None,
    master_profile_path: Optional[str] = None,
    llm_classifier_fn: Optional[Callable] = None,
    llm_text_fn: Optional[Callable] = None,
) -> Answer:
    """_answer_raw (orden de la Fase D) más: redes sociales en blanco, link del CV en Drive, carta de presentación
    (la guardada en la vacante o una nueva del agente; source='cover_letter' para que el aplicador la guarde en la DB)
    y valores del banco traducidos al inglés en formularios en inglés."""
    job = job or {}
    norm_label = normalize_label(field.label or field.key)
    args = (job, answers_path, master_profile_path, llm_classifier_fn, llm_text_fn)
    if norm_label in ("search", "buscar", "search countries"):  # buscador interno de un desplegable (país del teléfono)
        return Answer(value="", source="skip", needs_human=False)
    if field.kind != "file" and _SOCIAL.fullmatch(norm_label):
        return Answer(value="", source="skip", needs_human=bool(field.required))
    if field.kind != "file" and _RESUME_LINK.search(norm_label):
        link = str(job.get("cv_link") or "").strip()
        return Answer(value=link or None, source="file", needs_human=not link)
    if field.kind != "file" and _COVER.search(norm_label):
        if field.options and not field.required:  # Okta "Cover Letter: Upload PDF / Paste" opcional
            return Answer(value="", source="skip", needs_human=False)
        if str(job.get("cover_letter") or "").strip():
            return Answer(value=job["cover_letter"].strip(), source="cover_letter", needs_human=False)
        res = _answer_raw(field, *args)
        return Answer(res.value, "cover_letter", res.needs_human) if res.source == "llm" else res
    if field.kind != "file" and norm_label in ("date", "today s date", "todays date", "fecha", "fecha de hoy"):
        # fecha de firma (formulario de discapacidad de Palantir): hoy; la IA inventaba una fecha
        fmt = "%d/%m/%Y" if _is_spanish(field.label) else "%m/%d/%Y"
        return Answer(value=datetime.date.today().strftime(fmt), source="profile", needs_human=False)
    if field.kind in ("text", "textarea") and re.search(r"accommodat|accessible and inclusive|ajuste razonable", norm_label):
        return Answer("No, gracias." if _is_spanish(field.label) else "No, thank you.", "bank", False)  # ajustes de entrevista
    pref = _from_preferences(field, norm_label, job, _load_bank(answers_path))
    if pref:
        return pref
    if (field.kind == "checkbox" and _PRIVACY_ACK.search(norm_label)
            and not re.search(r"certify|attest|initial|signature|firma|true and (complete|correct)", norm_label)
            and ((_load_bank(answers_path).get("politicas") or {}).get("acepta_avisos_privacidad")) is not False):
        return Answer(field.options[0] if len(field.options or []) == 1 else "Yes", "bank", False)
    if field.kind != "file" and is_consent(norm_label):
        return _consent_answer(field, norm_label, _load_bank(answers_path))
    if (field.kind == "checkbox" and len(field.options or []) > 1 and re.search(r"language|idioma", norm_label)):
        langs = _languages_answer(field, _load_bank(answers_path))
        if langs:
            return langs
    if (field.kind != "file" and _UNIVERSITY.search(norm_label) and not _GRADES.search(norm_label)
            and not re.search(r"degree|major|field of study|graduat|titulo|carrera", norm_label)):
        uni = _university_answer(field, master_profile_path)
        if uni:
            return uni
    if (field.kind != "file" and _SALARY.search(norm_label)
            and not re.search(r"\b(current|actual|present|minimo|minimum|lowest)\b", norm_label)):
        return _salary_answer(field, _load_bank(answers_path))
    if _PREF_NAME.search(norm_label):
        opt, ok = match_option(True, field.options)
        return Answer(opt, "bank", False) if ok else Answer(None, "bank", True)
    if _AUTH_HOME.search(norm_label) or _AUTH_HERE.search(norm_label):
        # solo se sabe para el país de la persona (dónde vive): la pregunta lo dice o la vacante es allá
        bank = _load_bank(answers_path)
        home = normalize_label(((bank.get("datos_personales") or {}).get("pais")) or "")
        where = normalize_label(f"{job.get('location') or ''} {str(job.get('description') or '')[:5000]}")
        authorized = (bank.get("autorizacion_de_trabajo") or {}).get(f"autorizada_para_trabajar_en_{home.replace(' ', '_')}")
        in_home = _AUTH_HOME.search(norm_label) or re.search(rf"\b{re.escape(home)}\b", where)
        # vacante remota que no nombra ningún país (el scout solo deja pasar las que contratan desde LATAM): se trabaja
        # desde tu país. Si nombra otro país, no se asume nada.
        in_home = in_home or (home and not job.get("location") and not _FOREIGN.search(where))
        if home and in_home and isinstance(authorized, bool) and "source" in norm_label and authorized:
            opt = next((o for o in field.options or [] if "citizen" in normalize_label(o)), None)
            return Answer(opt or "Citizen", "bank", False)  # vacante en tu país y tienes permiso: ciudadana
        if home and in_home and isinstance(authorized, bool):
            opt, ok = match_option(authorized, field.options)
            if ok:
                return Answer(opt, "bank", False)
        return _foreign_authorization(field, norm_label, job, bank) or Answer(value=None, source="none", needs_human=True)
    if field.kind == "checkbox" and not field.options and norm_label in ("custom", "other", "otro", "otra"):
        return Answer(value="", source="skip", needs_human=False)  # "Custom" de pronombres: se deja sin marcar
    if field.kind == "checkbox" and not field.options and norm_label in ("yes", "si", "no"):
        return Answer(value=None, source="none", needs_human=True)  # casilla "Yes" sin la pregunta: no se sabe qué acepta
    opts_norm = [normalize_label(o) for o in (field.options or [])]
    if "she her" in opts_norm or "he him" in opts_norm:
        # pronombres con etiqueta ilegible (Ashby pone un uuid): la IA elegía distinto en cada formulario
        return _answer_raw(replace(field, label="Pronouns", key="pronouns"), *args)
    if re.search(r"\b(resume|cv)\b", norm_label) and any(re.search(r"upload|attach", o) for o in opts_norm):
        # Okta "Resume: Upload PDF / Paste": siempre subir el archivo
        return Answer(next(o for o in field.options if re.search(r"upload|attach", o, re.I)), "file", False)
    if (field.kind != "file" and not field.required and _FOLLOWUP.search(norm_label)
            and not _COMMITMENT.search(norm_label)):  # "En caso de no..., estoy dispuesto a" es un compromiso
        return Answer(value="", source="skip", needs_human=False)
    if field.kind != "file" and not field.required and _OPTIONAL_SKIP.search(norm_label):
        return Answer(value="", source="skip", needs_human=False)
    res = _answer_raw(field, *args)
    if res.source == "llm" and (_COMMITMENT.search(norm_label) or _GRADES.search(norm_label) or _CONSENT.search(norm_label)
                                or _MEETS_REQ.search(norm_label) and normalize_label(str(res.value)) == "no"):
        return Answer(value=None, source="none", needs_human=True)
    # "Are you fluent in English?" con el nivel del banco -> Yes/No (B2 o más = Yes)
    cefr = re.match(r"\s*(a1|a2|b1|b2|c1|c2|nativ)", str(res.value or "").lower())
    if not res.needs_human and cefr and _YESNO.search(norm_label):
        res = Answer(match_option(cefr.group(1) in ("b2", "c1", "c2", "nativ"), field.options)[0], res.source,
                     False)
        if res.value is None:
            return Answer(None, "bank", True)
    real_opts = [o for o in (field.options or []) if not re.match(r"(select|choose|elige|selecciona)\b", normalize_label(o))]
    yes_no_field = all(normalize_label(o) in _YES_NO_VALUES for o in real_opts)
    eeo = re.search(r"hispanic|latino|veteran|disab|gender|race|ethnic", norm_label)  # "Are you Hispanic?" -> "I don't wish..."
    if not res.needs_human and _YESNO.search(norm_label) and yes_no_field and field.kind != "textarea" and not eeo:
        val = str(res.value or "")
        first = re.match(r"(yes|no)\b", val, re.I)
        if res.source == "llm" and first and not real_opts:  # "Yes, I have hands-on experience..." -> "Yes"
            res = Answer(first.group(1).capitalize(), res.source, False)
        elif normalize_label(val) not in _YES_NO_VALUES:
            # dato del banco que no es sí/no: "Do you have 4+ years...?" con 4 años -> Yes; "minimum of 7" -> la persona;
            # "Are you based in a US timezone?" con "America/Bogota" -> la persona
            need = re.search(r"(\d+)\s*\+?\s*(years|anos)", norm_label)
            have = re.match(r"\s*(\d+(?:\.\d+)?)", val)
            if need and have:  # "minimum of 7 years" con 3.5 -> No (es la verdad; antes te lo preguntaba)
                yn = _yes_no(field, float(have.group(1)) >= int(need.group(1)))
                res = Answer(yn.value, res.source, yn.needs_human)
            else:
                return Answer(None, res.source, True)
    # casilla suelta: solo marcar o no ("Notion Website" recibía la URL de GitHub)
    if (field.kind == "checkbox" and not field.options and not res.needs_human
            and normalize_label(str(res.value or "")) not in _YES_NO_VALUES + ("",)):
        return Answer("", "skip", False) if not field.required else Answer(None, res.source, True)
    # Yes/No sin opciones en un formulario en español
    if not field.options and res.value in ("Yes", "No") and _is_spanish(field.label):
        res = Answer("Sí" if res.value == "Yes" else "No", res.source, res.needs_human)
    # "Location" a secas: ciudad + país ("Bogotá, Colombia"); "Location (City)" sigue siendo solo la ciudad
    if (_LOCATION.fullmatch(norm_label) and not field.options and res.source == "bank"
            and isinstance(res.value, str) and "," not in res.value):
        country = _answer_raw(replace(field, label="Country", key="country"), *args)
        if not country.needs_human and country.value:
            return Answer(f"{res.value}, {country.value}", "bank", False)
    if (not res.needs_human and not field.options and isinstance(res.value, str)
            and not _is_spanish(field.label) and res.value.strip().lower() in _ES_TO_EN):
        return Answer(_ES_TO_EN[res.value.strip().lower()], res.source, False)
    # plazos del banco en español en un formulario en inglés: "1 semana" -> "1 week"
    span = re.fullmatch(r"(\d+)\s+(semanas?|mes(es)?|dias?)", str(res.value or "").strip().lower())
    if span and not res.needs_human and not field.options and not _is_spanish(field.label):
        n, unit = int(span.group(1)), {"s": "week", "m": "month", "d": "day"}[span.group(2)[0]]
        return Answer(f"{n} {unit}{'s' if n != 1 else ''}", res.source, False)
    return res


def learn(label: str, value: Any, answers_path: Optional[str] = None) -> None:
    """Agrega una respuesta a la sección aprendidas: de answers.yaml."""
    if answers_path is None:
        answers_path = profile_paths.resolve("answers.yaml")

    data = {}
    if answers_path and os.path.exists(answers_path):
        try:
            with open(answers_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Error leyendo {answers_path}: {e}")

    if not isinstance(data, dict):
        data = {}

    if "aprendidas" not in data or not isinstance(data["aprendidas"], dict):
        data["aprendidas"] = {}

    norm_key = normalize_label(label)
    data["aprendidas"][norm_key] = value

    if answers_path:
        os.makedirs(os.path.dirname(os.path.abspath(answers_path)), exist_ok=True)
        with open(answers_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
