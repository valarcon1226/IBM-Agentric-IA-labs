import json
import os
import glob
import re
import datetime
import typing
from typing import List, Optional, Any
from pydantic import BaseModel, Field

import yaml
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv

load_dotenv()

import profile_paths
import llm_chain

# ==========================================
# 1. ESQUEMAS DE DATOS (PYDANTIC)
# ==========================================

class PersonalInfo(BaseModel):
    full_name: str = Field(description="Full name of the candidate")
    email: str = Field(description="Email address")
    number: str = Field(description="Phone number")
    location: str = Field(description="City and Country")
    linkedin_url: str = Field(description="LinkedIn username or URL")
    github_url: str = Field(description="GitHub username or URL")
    visa_sponsorship_needed: Optional[bool] = Field(default=None, description="True if they need visa sponsorship")
    willing_to_relocate: Optional[bool] = Field(default=None, description="True if willing to relocate")

class Personalidad(BaseModel):
    """Perfil de personalidad y estilo, igual para cualquier industria: la IA escribe cartas y respuestas abiertas
    como esta persona en vez de pedirle cada pregunta de cada formulario."""
    muestra_escritura: str = Field(default="", description="A real text the person wrote, copied verbatim")
    tono: str = Field(default="", description="How the person wants to sound when writing")
    evitar: str = Field(default="", description="Words or phrases the person would never use")
    como_trabaja: str = Field(default="", description="How the person works day to day (autonomy, planning, pace)")
    fortalezas: str = Field(default="", description="Strengths, in the person's own words")
    a_mejorar: str = Field(default="", description="A real weakness and what the person does about it")
    motivaciones: str = Field(default="", description="What motivates the person at work")
    valores: str = Field(default="", description="What the person values in a team or company")
    trabajo_en_equipo: str = Field(default="", description="Role the person takes in a team and how they handle disagreement")

class Experience(BaseModel):
    company_name: str
    current_role: str = Field(description="Job title during this period")
    time_period_worked: str = Field(description="Start and end dates, e.g., '2021 - 2023'")
    achievements: List[str] = Field(description="List of bullet points using STAR methodology (Situation, Task, Action, Result) with metrics.")

class TechnicalStack(BaseModel):
    ability: str = Field(description="Broad category, e.g., 'Desarrollo Frontend', 'Desarrollo Backend'")
    ability_description: str = Field(description="Comma separated list of concepts or technologies")

class Certification(BaseModel):
    certification_name: str
    certification_year: str

class Education(BaseModel):
    degree: str
    institution: str
    time_period_studied: str = Field(description="Start and end years, e.g., '2018 - 2023'")
    education_achievements: List[str] = Field(description="Thesis projects, honors, or achievements")

class AdditionalSkill(BaseModel):
    skill_category: str = Field(description="Must be 'frameworks', 'languages', or 'tools'")
    name: str = Field(description="Name of the specific skill, e.g., 'Langchain', 'SQL', 'Docker'")
    description: str = Field(description="A brief explanation of how you use this skill")

class SpokenLanguage(BaseModel):
    language_name: str
    proficiency: str

class Story(BaseModel):
    tema: str = Field(description="Story theme, e.g., 'como_usa_la_ia', 'proyecto_favorito', 'en_que_es_excelente', 'por_que_busca_cambio', 'experiencia_backend_liderazgo'")
    texto: str = Field(description="Narrative story text")

class MasterProfile(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    target_roles: str = Field(default="", description="The main title under the name, e.g., 'IA FULL STACK ENGINEER'")
    professional_summary: str = Field(default="", description="A comprehensive summary paragraph")
    experience: List[Experience] = Field(default_factory=list)
    technical_stacks: List[TechnicalStack] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    additional_skills: List[AdditionalSkill] = Field(default_factory=list)
    spoken_languages: List[SpokenLanguage] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list, description="Inferred soft skills from chat")
    portfolio_projects: List[str] = Field(default_factory=list, description="Short portfolio project blurbs, e.g. added by the GitHub enhancer tool. Carry these forward unchanged if already present.")
    seniority_context: str = Field(default="", description="Candidate's real seniority per discipline, e.g. 'Mid-Level QA (4 years), Junior Developer (1 year)'. Used by the Scout Agent to reject jobs that are too senior.")
    salary_expectation: str = Field(default="", description="Expected salary range and currency, e.g. 'USD 2,500 - 3,500/month'")
    work_model: str = Field(default="", description="Preferred work model, e.g. 'Remote only', 'Hybrid - Bogota', 'Open to relocation'")
    target_companies: List[str] = Field(default_factory=list, description="Specific companies or types of companies the candidate wants to target")
    deal_breakers: List[str] = Field(default_factory=list, description="Things the candidate will NOT accept in a job, e.g. 'No on-call rotations', 'No unpaid overtime'")
    writer_instructions: str = Field(default="", description="Tone/style instructions for the Cover Letter writer, e.g. 'Be direct, avoid corporate buzzwords, mention passion for automation'")
    stories: List[Story] = Field(default_factory=list, description="Key candidate stories for open-ended questions and tailoring")
    personalidad: Personalidad = Field(default_factory=Personalidad, description="Personality and writing style. Carry forward unchanged if already present.")


# ==========================================
# 2. CHECKLIST DETERMINISTA DE GAPS
# ==========================================

CHECKLIST: List[dict] = [
    # --- Datos Personales ---
    {
        "tema": "datos_personales",
        "archivo": "profile",
        "clave": "personal_info.email",
        "para": ["cv", "responder"],
        "pista": "Correo electrónico de contacto",
    },
    {
        "tema": "datos_personales",
        "archivo": "profile",
        "clave": "personal_info.number",
        "para": ["cv", "responder"],
        "pista": "Número de teléfono",
    },
    {
        "tema": "datos_personales",
        "archivo": "profile",
        "clave": "personal_info.location",
        "para": ["buscar", "responder"],
        "pista": "Ciudad y país de residencia",
    },
    {
        "tema": "datos_personales",
        "archivo": "bank",
        "clave": "datos_personales.github",
        "para": ["responder", "cv"],
        "pista": "URL o usuario de perfil de GitHub",
    },
    {
        "tema": "datos_personales",
        "archivo": "bank",
        "clave": "datos_personales.gitlab",
        "para": ["responder"],
        "pista": "URL o usuario de perfil de GitLab",
    },

    # --- Perfil Profesional ---
    {
        "tema": "perfil_profesional",
        "archivo": "profile",
        "clave": "target_roles",
        "para": ["buscar", "cv"],
        "pista": "Rol o título principal objetivo (ej. AI Full Stack Engineer)",
    },
    {
        "tema": "perfil_profesional",
        "archivo": "profile",
        "clave": "professional_summary",
        "para": ["cv"],
        "pista": "Resumen profesional global",
    },
    {
        "tema": "perfil_profesional",
        "archivo": "profile",
        "clave": "seniority_context",
        "para": ["buscar"],
        "pista": "Nivel real de seniority por disciplina (ej. Mid QA, Junior Dev)",
    },

    # --- Estrategia de Búsqueda ---
    {
        "tema": "estrategia_busqueda",
        "archivo": "profile",
        "clave": "salary_expectation",
        "para": ["buscar"],
        "pista": "Rango salarial esperado general en MasterProfile (ej. USD 3000-4000/mes)",
    },
    {
        "tema": "estrategia_busqueda",
        "archivo": "profile",
        "clave": "work_model",
        "para": ["buscar"],
        "pista": "Modalidad de trabajo preferida (ej. Solo remoto, Híbrido Bogotá)",
    },
    {
        "tema": "estrategia_busqueda",
        "archivo": "profile",
        "clave": "target_companies",
        "para": ["buscar"],
        "pista": "Empresas o tipos de empresas objetivo",
    },
    {
        "tema": "estrategia_busqueda",
        "archivo": "profile",
        "clave": "deal_breakers",
        "para": ["buscar"],
        "pista": "Condiciones no negociables (cosas que NO acepta en un trabajo)",
    },

    # --- Personalidad y estilo (master_profile.json): la IA escribe cartas y respuestas abiertas como la persona.
    # Genérico para cualquier industria; lo específico de cada formulario lo redacta la IA a partir de esto.
    *({"tema": "personalidad", "archivo": "profile", "clave": f"personalidad.{k}", "para": ["responder", "cv"],
       "pista": pista} for k, pista in (
        ("muestra_escritura", "Un texto real escrito por la persona (correo, post, mensaje a un cliente). "
                              "Cópialo TAL CUAL, sin resumirlo"),
        ("tono", "Cómo quiere sonar al escribir (ej. directa y cercana, sin frases corporativas)"),
        ("evitar", "Palabras o frases que nunca usaría (ej. 'apasionada', 'sinergia')"),
        ("como_trabaja", "Cómo trabaja en el día a día (autonomía, planeación, ritmo)"),
        ("fortalezas", "Sus fortalezas, en sus propias palabras"),
        ("a_mejorar", "Una debilidad real y qué hace al respecto"),
        ("motivaciones", "Qué la motiva en el trabajo"),
        ("valores", "Qué valora en un equipo o empresa"),
        ("trabajo_en_equipo", "Qué rol toma en un equipo y cómo maneja los desacuerdos"),
    )),

    # --- Salario ---
    {
        "tema": "salario",
        "archivo": "bank",
        "clave": "salario.expectativa_mensual_cop",
        "para": ["responder"],
        "pista": "Expectativa salarial mensual en pesos colombianos (COP)",
    },
    {
        "tema": "salario",
        "archivo": "bank",
        "clave": "salario.expectativa_anual_usd",
        "para": ["responder", "buscar"],
        "pista": "Expectativa salarial anual en dólares (USD)",
    },

    # --- Situación Laboral ---
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.empleada_actualmente",
        "para": ["responder"],
        "pista": "¿Está empleada actualmente?",
    },
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.jefe_sabe_que_busca",
        "para": ["responder"],
        "pista": "¿Su jefe o empleador actual sabe que está buscando trabajo?",
    },
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.acuerdos_no_competencia",
        "para": ["responder"],
        "pista": "¿Tiene acuerdos de no competencia vigentes?",
    },
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.negocios_externos",
        "para": ["responder"],
        "pista": "¿Tiene negocios externos, sociedades o consultorías paralelas?",
    },
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.empresas_donde_trabajo",
        "para": ["responder"],
        "pista": "Lista de empresas donde ha trabajado anteriormente",
    },
    {
        "tema": "situacion_laboral",
        "archivo": "bank",
        "clave": "situacion_laboral.nombre_jefe_actual",
        "para": ["responder"],
        "pista": "Nombre de su jefe actual (algunos formularios lo piden; 'no aplica' si no tiene)",
    },

    # --- Autorización de Trabajo ---
    {
        "tema": "autorizacion_de_trabajo",
        "archivo": "bank",
        "clave": "autorizacion_de_trabajo.ciudadanias",
        "para": ["responder"],
        "pista": "Nacionalidades o ciudadanías legales que posee",
    },
    {
        "tema": "autorizacion_de_trabajo",
        "archivo": "bank",
        "clave": "autorizacion_de_trabajo.paises_con_permiso",
        "para": ["responder"],
        "pista": "Países donde cuenta con permiso de trabajo legal vigente",
    },
    {
        "tema": "autorizacion_de_trabajo",
        "archivo": "bank",
        "clave": "autorizacion_de_trabajo.tiene_security_clearance",
        "para": ["responder"],
        "pista": "¿Tiene alguna habilitación de seguridad (security clearance) vigente de EE.UU. o Reino Unido? (sí/no)",
    },
    {
        "tema": "autorizacion_de_trabajo",
        "archivo": "bank",
        "clave": "autorizacion_de_trabajo.puede_obtener_security_clearance",
        "para": ["responder"],
        "pista": "¿Podría obtener una security clearance de EE.UU./Reino Unido? (normalmente exige esa ciudadanía; sí/no)",
    },
    {
        "tema": "autorizacion_de_trabajo",
        "archivo": "bank",
        "clave": "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
        "para": ["responder"],
        "pista": "¿Requiere patrocinio de visa para trabajar en otros países?",
    },

    # --- Disponibilidad ---
    {
        "tema": "disponibilidad",
        "archivo": "bank",
        "clave": "disponibilidad.preaviso",
        "para": ["responder"],
        "pista": "Tiempo de preaviso para empezar (ej. 1 semana, 2 semanas)",
    },
    {
        "tema": "disponibilidad",
        "archivo": "bank",
        "clave": "disponibilidad.dias_oficina_maximo",
        "para": ["responder", "buscar"],
        "pista": "Máximo de días por semana dispuesto a ir a oficina presencial",
    },
    {
        "tema": "disponibilidad",
        "archivo": "bank",
        "clave": "disponibilidad.ciudades_para_mudarse",
        "para": ["responder", "buscar"],
        "pista": "Ciudades a las que estaría dispuesto a mudarse por trabajo",
    },
    {
        "tema": "disponibilidad",
        "archivo": "bank",
        "clave": "disponibilidad.puede_viajar",
        "para": ["responder"],
        "pista": "Disponibilidad para viajar por motivos laborales",
    },

    # --- Idiomas ---
    {
        "tema": "idiomas",
        "archivo": "bank",
        "clave": "idiomas.ingles",
        "para": ["responder", "cv"],
        "pista": "Nivel de dominio del idioma inglés (ej. C1, B2)",
    },
    {
        "tema": "idiomas",
        "archivo": "bank",
        "clave": "idiomas.espanol",
        "para": ["responder", "cv"],
        "pista": "Nivel de dominio del idioma español (ej. Nativo)",
    },

    # --- Preguntas Frecuentes ---
    {
        "tema": "preguntas_frecuentes",
        "archivo": "bank",
        "clave": "preguntas_frecuentes.tiene_familiares_en_la_empresa",
        "para": ["responder"],
        "pista": "¿Tiene familiares vinculados a la empresa postulante?",
    },

    # --- Políticas ---
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.acepta_avisos_privacidad",
        "para": ["responder"],
        "pista": "¿Acepta avisos de privacidad y tratamiento de datos personales?",
    },
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.acepta_grabacion_ia",
        "para": ["responder"],
        "pista": "¿Acepta grabación de entrevistas y evaluación por IA?",
    },
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.acepta_contacto_futuro",
        "para": ["responder"],
        "pista": "¿Acepta que le contacten para futuras vacantes y oportunidades?",
    },
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.acepta_compartir_cv_con_socios",
        "para": ["responder"],
        "pista": "¿Acepta compartir su CV con socios o clientes aliados?",
    },
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.certifica_veracidad",
        "para": ["responder"],
        "pista": "¿Autoriza que el aplicador firme por ella (iniciales o nombre) que la información enviada es verdadera? (sí/no)",
    },
    {
        "tema": "politicas",
        "archivo": "bank",
        "clave": "politicas.acepta_terminos_para_postular",
        "para": ["responder"],
        "pista": "¿Acepta los términos y condiciones que piden los formularios para poder postular? (sí/no)",
    },

    # --- Respuestas Modelo ---
    {
        "tema": "respuestas_modelo",
        "archivo": "bank",
        "clave": "respuestas_modelo.por_que_te_interesa_este_tipo_de_rol",
        "para": ["responder"],
        "pista": "¿Por qué te interesa este tipo de rol profesional?",
    },
    {
        "tema": "respuestas_modelo",
        "archivo": "bank",
        "clave": "respuestas_modelo.tu_mayor_logro_profesional",
        "para": ["responder"],
        "pista": "¿Cuál consideras tu mayor logro profesional?",
    },
    {
        "tema": "respuestas_modelo",
        "archivo": "bank",
        "clave": "respuestas_modelo.por_que_buscas_cambio",
        "para": ["responder"],
        "pista": "¿Por qué estás buscando un cambio de trabajo?",
    },
    {
        "tema": "respuestas_modelo",
        "archivo": "bank",
        "clave": "respuestas_modelo.cuentame_de_ti_en_3_lineas",
        "para": ["responder"],
        "pista": "Cuéntame de ti en 3 líneas",
    },
    {
        "tema": "respuestas_modelo",
        "archivo": "bank",
        "clave": "respuestas_modelo.que_te_diferencia",
        "para": ["responder"],
        "pista": "¿Qué te diferencia de otros candidatos?",
    },

    # --- Historias ---
    {
        "tema": "historias",
        "archivo": "profile",
        "clave": "stories.como_usa_la_ia",
        "para": ["cv", "responder"],
        "pista": "Historia: Cómo usa herramientas de inteligencia artificial en su día a día técnico",
    },
    {
        "tema": "historias",
        "archivo": "profile",
        "clave": "stories.proyecto_favorito",
        "para": ["cv", "responder"],
        "pista": "Historia: Su proyecto favorito, qué reto resolvió y su impacto",
    },
    {
        "tema": "historias",
        "archivo": "profile",
        "clave": "stories.en_que_es_excelente",
        "para": ["cv", "responder"],
        "pista": "Historia: En qué área técnica o habilidad es excelente / sobresaliente",
    },
    {
        "tema": "historias",
        "archivo": "profile",
        "clave": "stories.por_que_busca_cambio",
        "para": ["cv", "responder"],
        "pista": "Historia: Por qué busca un cambio profesional en este momento",
    },
    {
        "tema": "historias",
        "archivo": "profile",
        "clave": "stories.experiencia_backend_liderazgo",
        "para": ["cv", "responder"],
        "pista": "Historia: Experiencia en arquitectura backend y/o liderazgo técnico",
    },
]


# ==========================================
# 3. FUNCIONES AUXILIARES DE LECTURA Y VALIDACIÓN
# ==========================================

def extract_text_from_document() -> str:
    """Lee el CV base de la persona (PDF o cv.txt)."""
    cv_text = ""
    search_dir = profile_paths.profile_dir() or os.path.dirname(os.path.abspath(__file__))
    current_cv_matches = glob.glob(os.path.join(search_dir, "*Current CV*.pdf"))
    all_pdfs = glob.glob(os.path.join(search_dir, "*.pdf"))
    pdf_targets = current_cv_matches[:1] or [f for f in all_pdfs if "Tailored" not in f]

    if pdf_targets:
        for pdf_target in pdf_targets:
            print(f"  -> Leyendo CV: {pdf_target} ...")
            try:
                pages = "\n".join(doc.page_content for doc in PyPDFLoader(pdf_target).load())
                cv_text += f"\n\n===== {os.path.basename(pdf_target)} =====\n{pages}"
            except Exception as e:
                print(f"  -> Error cargando PDF {pdf_target}: {e}")
        cv_text = re.sub(r"\s*\[cite: \d+\]", "", cv_text)
    elif os.path.exists(os.path.join(search_dir, "cv.txt")):
        print("  -> Leyendo cv.txt ...")
        with open(os.path.join(search_dir, "cv.txt"), "r", encoding="utf-8") as f:
            cv_text = f.read()
    else:
        print(f"  -> No se encontró CV base en PDF ni cv.txt dentro de {search_dir}.")
    return cv_text


def read_additional_info_files() -> str:
    """Lee cualquier archivo .txt, .md o .pdf en Profiles/<persona>/info_adicional/ si existe."""
    search_dir = profile_paths.profile_dir()
    if not search_dir:
        return ""
    info_dir = os.path.join(search_dir, "info_adicional")
    if not os.path.isdir(info_dir):
        return ""

    contents = []
    patterns = [
        os.path.join(info_dir, "*.txt"),
        os.path.join(info_dir, "*.md"),
        os.path.join(info_dir, "*.pdf"),
    ]
    found_files = []
    for pat in patterns:
        found_files.extend(glob.glob(pat))

    for filepath in sorted(found_files):
        ext = os.path.splitext(filepath)[1].lower()
        fname = os.path.basename(filepath)
        if ext in [".txt", ".md"]:
            print(f"  -> Leyendo archivo de info adicional: {fname} ...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    contents.append(f"===== {fname} =====\n{text}")
            except Exception as e:
                print(f"  -> Error leyendo {fname}: {e}")
        elif ext == ".pdf":
            print(f"  -> Leyendo PDF de info adicional: {fname} ...")
            try:
                pages = "\n".join(doc.page_content for doc in PyPDFLoader(filepath).load())
                pages = re.sub(r"\s*\[cite: \d+\]", "", pages).strip()
                if pages:
                    contents.append(f"===== {fname} =====\n{pages}")
            except Exception as e:
                print(f"  -> Error leyendo PDF {fname}: {e}")

    return "\n\n".join(contents)


def _role_types_rule() -> str:
    """Si la persona tiene sus propios tipos de rol (archetypes.json), la entrevista no se da por completa
    hasta tener material para un CV de cada uno."""
    try:
        import archetypes
        if not archetypes.CUSTOM:
            return ""
        return (" ADEMÁS, se va a escribir un CV distinto para CADA UNO de estos tipos de rol: "
                + "; ".join(archetypes.ARCHETYPE_LABELS.values())
                + ". Para cada tipo, reporta como gap si el perfil no tiene experiencias con logros concretos, "
                  "herramientas y cifras que sostengan ese CV por sí solo, nombrando el tipo de rol al que le falta.")
    except Exception:
        return ""


def _is_empty_or_placeholder(val: Any) -> bool:
    """Retorna True si el valor está ausente, vacío, None o es '???'."""
    if val is None:
        return True
    if isinstance(val, str):
        s = val.strip()
        return s == "" or s == "???"
    if isinstance(val, (list, tuple, dict, set)):
        return len(val) == 0
    return False


def _get_nested_val(data: Any, key_path: str) -> Any:
    """Navega una estructura de diccionarios con claves separadas por puntos."""
    if not isinstance(data, dict):
        return None
    parts = key_path.split(".")
    curr = data
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return None
    return curr


def _get_profile_val(profile: Any, key_path: str) -> Any:
    """Navega los atributos de un MasterProfile o diccionario."""
    if profile is None:
        return None
    parts = key_path.split(".")
    curr = profile
    for p in parts:
        if curr is None:
            return None
        if isinstance(curr, dict):
            curr = curr.get(p)
        else:
            curr = getattr(curr, p, None)
    return curr


# ==========================================
# 4. FIND GAPS Y QUALITY GAPS
# ==========================================

def find_quality_gaps(profile: Any) -> List[dict]:
    """Usa IA para evaluar logros sin métricas STAR en la experiencia."""
    if not profile:
        return []
    exp_list = profile.get("experience", []) if isinstance(profile, dict) else getattr(profile, "experience", [])
    if not exp_list:
        return []

    try:
        raw_text = llm_chain.invoke_text(
            system_prompt=(
                "Eres un analizador riguroso de CVs. Revisa la lista de experiencias y logros del candidato. "
                "Si encuentras logros que no explican el 'cómo' (metodología STAR) o carecen de métricas cuantificables "
                "(números, porcentajes, tiempos), repórtalo en un párrafo breve en español. "
                "Si los logros están adecuadamente respaldados con métricas, responde exactamente: 'SIN_GAPS'."
                + _role_types_rule()
            ),
            human_template="{exp_json}",
            variables={
                "exp_json": json.dumps(
                    exp_list if (not exp_list or isinstance(exp_list[0], dict))
                    else [e.model_dump() for e in exp_list]
                )
            },
            temperature=0.1,
        )
        if raw_text and "SIN_GAPS" not in raw_text.upper():
            return [{
                "tema": "experiencia",
                "archivo": "profile",
                "clave": "experience.achievements",
                "para": ["cv", "gaps"],
                "pista": raw_text.strip(),
            }]
    except llm_chain.AllProvidersExhausted:
        pass
    except Exception as e:
        print(f"  -> Error evaluando calidad de logros con IA: {e}")

    return []


def _bank_holes(bank: Any, prefix: str = "") -> List[str]:
    """Rutas del banco cuyo valor es '???' (los huecos de la plantilla answers.yaml)."""
    if not isinstance(bank, dict):
        return []
    holes = []
    for k, v in bank.items():
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            holes += _bank_holes(v, path + ".")
        elif isinstance(v, str) and v.strip() == "???":
            holes.append(path)
    return holes


# campo viejo (writer_instructions pasó a personalidad), historias (las pide la CHECKLIST por tema) o ya lo pregunta
# el banco (visa, reubicación)
_SCHEMA_SKIP = {"writer_instructions", "stories",
                "personal_info.visa_sponsorship_needed", "personal_info.willing_to_relocate"}


def schema_gaps(profile: Any) -> List[dict]:
    """Campos vacíos del esquema MasterProfile, con la descripción del campo como pista. Listas de objetos: vacía
    = un hueco para toda la lista; con elementos = los campos vacíos de cada uno (ej. experience.0.achievements)."""
    if isinstance(profile, dict):
        try:
            profile = MasterProfile.model_validate(profile)
        except Exception:
            return []
    if not isinstance(profile, BaseModel):
        return []
    gaps = []

    def walk(obj: BaseModel, prefix: str, tema: str, label: str):
        for name, info in type(obj).model_fields.items():
            clave, val = f"{prefix}{name}", getattr(obj, name)
            if clave in _SCHEMA_SKIP:
                continue
            t = tema or name
            if isinstance(val, BaseModel):
                walk(val, clave + ".", t, label)
            elif isinstance(val, list) and val and isinstance(val[0], BaseModel):
                for i, item in enumerate(val):
                    first = next((str(v) for v in item.model_dump().values() if isinstance(v, str) and v), "")
                    walk(item, f"{clave}.{i}.", t, f"{name} #{i + 1} ({first[:60]}): ")
            elif _is_empty_or_placeholder(val):
                gaps.append({"tema": t, "archivo": "profile", "clave": clave, "para": ["cv", "responder"],
                             "pista": f"{label}{info.description or name.replace('_', ' ')}"})

    walk(profile, "", "", "")
    return gaps


def find_gaps(profile: Any = None, bank: Any = None, check_quality: bool = False) -> List[dict]:
    """Evalúa determinísticamente la CHECKLIST sobre profile y bank.
    Falta = vacío, '???' o ausente.
    Opcionalmente la IA agrega gaps de calidad (logros sin métricas/STAR)."""
    gaps: List[dict] = []

    # 1. Recorrido determinista de CHECKLIST
    for item in CHECKLIST:
        archivo = item.get("archivo")
        clave = item.get("clave", "")

        if archivo == "bank":
            val = _get_nested_val(bank, clave)
            if _is_empty_or_placeholder(val):
                gaps.append(dict(item))
        elif archivo == "profile":
            if clave.startswith("stories."):
                story_tema = clave.split(".", 1)[1]
                stories = _get_profile_val(profile, "stories") or []
                found = False
                for s in stories:
                    t = s.get("tema") if isinstance(s, dict) else getattr(s, "tema", None)
                    txt = s.get("texto") if isinstance(s, dict) else getattr(s, "texto", None)
                    if t == story_tema and not _is_empty_or_placeholder(txt):
                        found = True
                        break
                if not found:
                    gaps.append(dict(item))
            else:
                val = _get_profile_val(profile, clave)
                if _is_empty_or_placeholder(val):
                    gaps.append(dict(item))

    # 2. Todo hueco '???' de la plantilla del banco (respuestas_modelo, idiomas o cualquier sección nueva)
    known = {g["clave"] for g in gaps}
    for clave in _bank_holes(bank):
        if clave not in known:
            tema = clave.split(".")[0]
            gaps.append({"tema": tema, "archivo": "bank", "clave": clave,
                         "para": ["responder", "cv"] if tema == "idiomas" else ["responder"],
                         "pista": clave.split(".", 1)[-1].replace("_", " ")})

    # 2b. Todo campo vacío del esquema del perfil (lo que el LLM sacó de la hoja de vida), no solo la CHECKLIST
    known = {g["clave"] for g in gaps} | {item["clave"] for item in CHECKLIST}
    gaps.extend(g for g in schema_gaps(profile) if g["clave"] not in known)

    # 3. Gaps de calidad con IA
    if check_quality and profile:
        gaps.extend(find_quality_gaps(profile))

    return gaps


# ==========================================
# 5. EXTRACT FACTS Y MERGE BANK / PROFILE
# ==========================================

def _parse_json_obj(raw: str) -> dict:
    """El objeto JSON de una respuesta del LLM (con o sin ```json, con texto alrededor); {} si no hay."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    for candidate in (text, (re.search(r"\{.*\}", text, re.DOTALL) or [None])[0]):
        try:
            data = json.loads(candidate) if candidate else None
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def plan_questions(profile: Any, bank: dict, gaps: List[dict]) -> tuple:
    """El LLM revisa cada campo pendiente contra TODO el perfil y el banco, y decide como lo haría un reclutador:
    preguntar, deducir (el dato ya está en el perfil/banco con otro nombre) u omitir (no aplica a esta persona).
    Devuelve (deducidos {clave: valor}, omitidos {clave: motivo}). Si el LLM falla, todo se pregunta."""
    if not gaps:
        return {}, {}
    profile_json = profile.model_dump_json() if hasattr(profile, "model_dump_json") else json.dumps(profile or {})
    campos = "\n".join(f"- {g['clave']}: {g.get('pista', '')}" for g in gaps)
    system_prompt = (
        "Eres un reclutador senior preparando la entrevista de onboarding de un candidato para que un agente postule "
        "por él a vacantes. Piensa campo por campo, mirando el perfil y el banco COMPLETOS, y decide qué hacer con "
        "cada campo pendiente:\n"
        "- 'preguntar': el dato solo lo puede dar la persona y sirve para postular o escribir por ella.\n"
        "- 'deducir': el dato YA está en el perfil o el banco (con otro nombre o en otro campo). 'valor' es ese dato "
        "copiado tal cual. NUNCA inventes ni supongas: si no está escrito, es 'preguntar'.\n"
        "- 'omitir': no aplica a esta persona según su perfil (ej. una cuenta o plataforma que su perfil no muestra "
        "y que es opcional, algo que contradice lo que ya contó). 'motivo' explica por qué en una frase.\n"
        "Ante la duda entre omitir y preguntar, pregunta.\n"
        "Devuelve SOLO un JSON: {\"clave\": {\"accion\": \"preguntar|deducir|omitir\", \"valor\": ..., "
        "\"motivo\": \"...\"}} con TODAS las claves listadas."
    )
    try:
        raw = llm_chain.invoke_text(
            system_prompt=system_prompt,
            human_template="Campos pendientes:\n{campos}\n\nPerfil:\n{perfil}\n\nBanco:\n{banco}",
            variables={"campos": campos, "perfil": profile_json[:12000],
                       "banco": json.dumps(bank or {}, ensure_ascii=False, default=str)[:6000]},
            temperature=0.1,
        )
    except Exception as e:  # sin cupo o error: se pregunta todo, como antes
        print(f"  -> No se pudo revisar qué preguntar ({e.__class__.__name__}); se pregunta todo.")
        return {}, {}
    keys = {g["clave"] for g in gaps}
    deducidos, omitidos = {}, {}
    for k, d in _parse_json_obj(raw).items():
        if k not in keys or not isinstance(d, dict):
            continue
        if d.get("accion") == "deducir" and not _is_empty_or_placeholder(d.get("valor")):
            deducidos[k] = d["valor"]
        elif d.get("accion") == "omitir":
            omitidos[k] = str(d.get("motivo") or "no aplica")
    return deducidos, omitidos


def extract_facts(respuesta: str, gaps_preguntados: List[dict]) -> dict:
    """Pide a la IA un JSON {clave: valor} SOLO con claves de esos gaps.
    Descarta claves que no estén en la CHECKLIST."""
    if not respuesta or not respuesta.strip() or not gaps_preguntados:
        return {}

    valid_checklist_keys = {item["clave"] for item in CHECKLIST}
    pistas_str = "\n".join(f"- Clave: '{g['clave']}' | Detalle: {g.get('pista', '')}" for g in gaps_preguntados)

    system_prompt = (
        "Eres un extractor estricto de datos. Analiza la respuesta del candidato y extrae "
        "los datos correspondientes ÚNICAMENTE a estas claves:\n"
        f"{pistas_str}\n\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. Devuelve EXCLUSIVAMENTE un objeto JSON plano donde cada clave sea una de las claves listadas arriba.\n"
        "2. Formato: {\"clave\": valor}. Tipos permitidos: string, number, boolean, o list de strings.\n"
        "3. Si el candidato no respondió o no mencionó información para alguna clave, NO la incluyas.\n"
        "4. NO inventes datos. NO agregues claves adicionales bajo ninguna circunstancia.\n"
        "   Si dice que no tiene eso, que no aplica o que prefiere no decirlo, usa el valor 'no aplica' (así no se "
        "le vuelve a preguntar).\n"
        "5. Devuelve SOLO el JSON sin texto introductorio, explicaciones ni formato markdown.\n"
        "6. Si el detalle trae '(opciones: ...)', el valor es EXACTAMENTE una de esas opciones, copiada tal cual.\n"
        "7. Preguntas de sí/no: el valor es true o false."
    )

    human_template = "Respuesta del candidato:\n{respuesta}"

    try:
        raw_out = llm_chain.invoke_text(
            system_prompt=system_prompt,
            human_template=human_template,
            variables={"respuesta": respuesta},
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted:
        print("\n[CUOTA AGOTADA] Sin cupo para extraer hechos. Se continuará con los datos disponibles.")
        return {}
    except Exception as e:
        print(f"  -> Error llamando a LLM para extraer hechos: {e}")
        return {}

    data = _parse_json_obj(raw_out)
    asked = {g["clave"] for g in gaps_preguntados}  # incluye campos del esquema y huecos '???' del banco
    facts = {}
    for k, v in data.items():
        if (k in valid_checklist_keys or k in asked or k.startswith(("respuestas_modelo.", "idiomas.")))                and not _is_empty_or_placeholder(v):
            facts[k] = v

    return facts


def merge_bank(bank: dict, facts: dict) -> dict:
    """Escribe solo en claves vacías o '???' del bank. Nunca pisa valores existentes
    y descarta claves desconocidas (que no pertenezcan a los ítems tipo 'bank' de CHECKLIST
    ni sean extensiones válidas del banco)."""
    if bank is None:
        bank = {}
    if not facts or not isinstance(facts, dict):
        return bank

    valid_bank_keys = {item["clave"] for item in CHECKLIST if item.get("archivo") == "bank"}

    for raw_clave, val in facts.items():
        if _is_empty_or_placeholder(val):
            continue

        is_valid = (
            raw_clave in valid_bank_keys
            or raw_clave in _bank_holes(bank)  # cualquier hueco ??? de la plantilla
            or raw_clave.startswith("respuestas_modelo.")
            or raw_clave.startswith("idiomas.")
            or raw_clave in (
                "salario.expectativa_mensual", "salario.minimo_aceptable", "salario.salario_actual",
                "datos_personales.nombre_legal", "datos_personales.email", "datos_personales.telefono",
                "datos_personales.ciudad", "datos_personales.pais", "datos_personales.zona_horaria",
                "datos_personales.linkedin", "datos_personales.portafolio", "datos_personales.pronombres"
            )
        )
        if not is_valid:
            continue

        parts = raw_clave.split(".")
        if len(parts) == 1:
            curr = bank.get(parts[0])
            if _is_empty_or_placeholder(curr):
                bank[parts[0]] = val
        elif len(parts) == 2:
            sec, field = parts
            if sec not in bank or not isinstance(bank[sec], dict):
                bank[sec] = {}
            curr = bank[sec].get(field)
            if _is_empty_or_placeholder(curr):
                bank[sec][field] = val
        elif len(parts) == 3:
            s1, s2, field = parts
            if s1 not in bank or not isinstance(bank[s1], dict):
                bank[s1] = {}
            if s2 not in bank[s1] or not isinstance(bank[s1][s2], dict):
                bank[s1][s2] = {}
            curr = bank[s1][s2].get(field)
            if _is_empty_or_placeholder(curr):
                bank[s1][s2][field] = val

    return bank


def _upsert_story(profile: Any, tema: str, texto: str):
    """Guarda o actualiza una historia en profile.stories sin pisar historias existentes."""
    if not profile or not texto or _is_empty_or_placeholder(texto):
        return
    if isinstance(profile, dict):
        if "stories" not in profile or not isinstance(profile["stories"], list):
            profile["stories"] = []
        for s in profile["stories"]:
            if isinstance(s, dict) and s.get("tema") == tema:
                if _is_empty_or_placeholder(s.get("texto")):
                    s["texto"] = texto
                return
        profile["stories"].append({"tema": tema, "texto": texto})
    else:
        if not hasattr(profile, "stories") or profile.stories is None:
            profile.stories = []
        for s in profile.stories:
            if getattr(s, "tema", None) == tema:
                if _is_empty_or_placeholder(getattr(s, "texto", None)):
                    s.texto = texto
                return
        profile.stories.append(Story(tema=tema, texto=texto))


def _update_profile_field(profile: Any, clave: str, val: Any):
    """Actualiza un campo en profile solo si estaba vacío o no definido."""
    if not profile or _is_empty_or_placeholder(val):
        return
    if isinstance(profile, dict):
        if "." in clave:
            parts = clave.split(".")
            curr = profile
            for p in parts[:-1]:
                if p not in curr or not isinstance(curr[p], dict):
                    curr[p] = {}
                curr = curr[p]
            if _is_empty_or_placeholder(curr.get(parts[-1])):
                curr[parts[-1]] = val
        else:
            if _is_empty_or_placeholder(profile.get(clave)):
                profile[clave] = val
    else:
        # rutas del esquema con índices de lista, ej. experience.0.achievements o personalidad.tono
        parts = clave.split(".")
        if parts[0] == "personal_info" and profile.personal_info is None:
            profile.personal_info = PersonalInfo(
                full_name="", email="", number="", location="", linkedin_url="", github_url=""
            )
        obj = profile
        for p in parts[:-1]:
            if isinstance(obj, list):
                obj = obj[int(p)] if p.isdigit() and int(p) < len(obj) else None
            else:
                obj = getattr(obj, p, None)
            if obj is None:
                return
        info = type(obj).model_fields.get(parts[-1]) if isinstance(obj, BaseModel) else None
        if info is None or not _is_empty_or_placeholder(getattr(obj, parts[-1])):
            return
        args = typing.get_args(info.annotation)
        if typing.get_origin(info.annotation) is list:
            if args and args[0] is not str:
                return  # lista de objetos (certificaciones, estudios...): la arma el LLM al re-armar el perfil
            setattr(obj, parts[-1], [str(x) for x in val] if isinstance(val, list) else [str(val)])
        elif info.annotation is str:
            setattr(obj, parts[-1], ", ".join(map(str, val)) if isinstance(val, list) else str(val))
        else:
            setattr(obj, parts[-1], val)


def evaluate_soft_skills_from_chat(chat_history: str) -> List[str]:
    """Infiere soft skills profesionales a partir de la conversación."""
    if not chat_history:
        return []
    try:
        text = llm_chain.invoke_text(
            system_prompt="Analiza el chat del usuario. Infiere 3 soft skills profesionales basadas en su tono (ej. Comunicación Efectiva, Resiliencia, Pensamiento Analítico). Devuelve SOLO los nombres separados por comas.",
            human_template="{chat}",
            variables={"chat": chat_history},
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted:
        print("\n[CUOTA AGOTADA] Sin cupo para evaluar soft skills. Se omite este paso.")
        return []
    except Exception as e:
        print(f"  -> Error evaluando soft skills: {e}")
        return []
    return [s.strip() for s in text.split(',') if s.strip()]


def export_final_candidate_json(completed_profile: MasterProfile):
    """Guarda master_profile.json y una copia de respaldo con timestamp."""
    print("  -> Guardando master_profile.json...")
    final_json_str = completed_profile.model_dump_json(indent=4)
    target_path = profile_paths.resolve("master_profile.json")

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(final_json_str)

    test_dir = profile_paths.resolve("perfiles_de_prueba")
    os.makedirs(test_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(test_dir, f"master_profile_{timestamp}.json")

    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(final_json_str)

    print(f"  -> Perfil guardado (Copia en: {backup_path})\n")


# ==========================================
# 6. FLUJO PRINCIPAL DE ENTREVISTA
# ==========================================

def _apply_facts(profile: Any, bank: dict, facts: dict, gaps: List[dict]):
    """Cada dato a su sitio: historias, campos del perfil (master_profile.json) o el banco (answers.yaml)."""
    for k, v in facts.items():
        if k.startswith("stories."):
            _upsert_story(profile, k.split(".", 1)[1], str(v))
        elif any(g["clave"] == k and g["archivo"] == "profile" for g in gaps):
            _update_profile_field(profile, k, v)
    merge_bank(bank, facts)


_LLM_NOISE = re.compile(r"^\s*\[(PRESUPUESTO|FALLBACK|ESPERA)\]")


def _quiet(fn, *args, **kwargs):
    """Llama fn sin los avisos de proveedores de llm_chain ([FALLBACK], [PRESUPUESTO]...): ensucian la entrevista.
    El resto de lo que imprime (errores, cuota agotada) sí se muestra."""
    import contextlib
    import io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*args, **kwargs)
    finally:
        for line in buf.getvalue().splitlines():
            if line.strip() and not _LLM_NOISE.match(line):
                print(line)


def _format_questions(text: str, gaps: List[dict]) -> List[str]:
    """Las preguntas del LLM siempre en el mismo formato: una por línea, sin numeración ni viñetas, máximo 3.
    Si el modelo devuelve un párrafo, se parte en cada '?'; si no sale nada, se usa la pista de cada campo."""
    text = re.sub(r"[*_`#]", "", text or "")
    # "¿...?" aunque vengan en un párrafo con saludo; sin signo de apertura, cada línea que termine en '?'
    questions = [q.strip() for q in re.findall(r"¿[^¿?]+\?", text)] or [
        re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", l).strip() for l in text.splitlines() if l.strip().endswith("?")]
    return questions[:3] or [f"¿{g['pista']}?" for g in gaps]


def _round_header(n: int, tema: str, pendientes: int) -> str:
    title = f" Ronda {n} · {tema.replace('_', ' ').capitalize()} · faltan {pendientes} campos"
    return f"\n{'=' * 64}\n{title}\n{'=' * 64}"


def run_interview():
    print(f"{'=' * 64}\n Entrevista JobHunter\n{'=' * 64}")

    # 1. Leer el CV
    raw_cv = extract_text_from_document()

    # 2. Pedir información adicional
    info_files_text = read_additional_info_files()

    print(_round_header(0, "contexto inicial", 0).replace(" · faltan 0 campos", ""))
    print("  1. ¿Hay algún cambio de carrera o contexto general que deba saber?")
    print("\n  Tu respuesta (Enter dos veces para enviar · Enter una vez para omitir):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    initial_context = "\n".join(lines).strip()

    # 3. Armar perfil con CV + info + master_profile previo y cargar answers.yaml
    chat_history = ""
    existing_profile_path = profile_paths.resolve("master_profile.json")
    existing_profile = None
    if os.path.exists(existing_profile_path):
        print("  -> Encontré un master_profile.json existente.")
        try:
            with open(existing_profile_path, "r", encoding="utf-8") as f:
                existing_profile_str = f.read()
                existing_profile = MasterProfile.model_validate_json(existing_profile_str)
            chat_history += (
                "Previously Captured Master Profile (CARRY FORWARD every field here unless the new CV/context "
                "explicitly contradicts it — especially 'portfolio_projects', 'target_companies', "
                "'salary_expectation', 'work_model', 'deal_breakers', 'seniority_context', 'stories'):\n"
                f"{existing_profile_str}\n\n"
            )
        except Exception as e:
            print(f"  -> Error cargando master_profile.json previo: {e}")

    if info_files_text:
        chat_history += f"Additional Info Files:\n{info_files_text}\n\n"
    if initial_context:
        chat_history += f"Candidate Initial Context:\n{initial_context}\n\n"

    print("  -> Analizando perfil inicial y estructurando datos...")
    parse_system_prompt = """You are an expert data extraction assistant. Map the provided resume, additional info files, and chat history to the strict JSON schema in ENGLISH.
TRANSLATE EVERY TEXT FIELD TO ENGLISH even if the resume is in Spanish or another language: professional_summary, target_roles,
current_role, achievements, abilities, degrees, seniority_context, everything. Keep proper names (people, companies, products) as they are.
CRITICAL INSTRUCTION: You MUST extract ALL sections of the resume, particularly 'PROFESSIONAL EXPERIENCE'. DO NOT LEAVE ARRAYS EMPTY IF DATA EXISTS.
Pay special attention to the 'Candidate Initial Context' in the chat history to adapt the professional_summary if needed."""

    try:
        profile = _quiet(
            llm_chain.invoke_structured,
            system_prompt=parse_system_prompt,
            human_template="Resume:\n{cv_text}\n\nChat History / Context:\n{chat_history}",
            variables={"cv_text": raw_cv, "chat_history": chat_history},
            pydantic_model=MasterProfile,
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted as e:
        print(f"  -> [CUOTA AGOTADA] Los proveedores se quedaron sin cupo estructurando el perfil ({e}).")
        profile = existing_profile or MasterProfile()
    except Exception as e:
        print(f"  -> Error estructurando perfil inicial: {e}")
        profile = existing_profile or MasterProfile()
    if existing_profile:  # el parser traduce todo al inglés: la muestra de escritura debe quedar tal cual
        profile.personalidad = existing_profile.personalidad

    # Cargar answers.yaml actual
    answers_path = profile_paths.resolve("answers.yaml")
    bank = {}
    if os.path.exists(answers_path):
        print(f"  -> Cargando answers.yaml existente...")
        try:
            with open(answers_path, "r", encoding="utf-8") as f:
                bank = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"  -> Error leyendo answers.yaml: {e}")
            bank = {}
    # el estilo que antes vivía en el banco (estilo_escritura) o en writer_instructions pasa a profile.personalidad
    old_style = bank.pop("estilo_escritura", None) or {}
    for k, v in (("muestra_escritura", old_style.get("muestra")), ("evitar", old_style.get("evitar")),
                 ("tono", old_style.get("tono") or profile.writer_instructions)):
        _update_profile_field(profile, f"personalidad.{k}", v)

    # 4. find_gaps DETERMINISTA inicial
    initial_gaps = find_gaps(profile, bank, check_quality=False)
    # logros sin métricas / tipos de rol sin material: la IA los evalúa una vez; se preguntan como un tema más
    quality_gaps = find_quality_gaps(profile)
    print(f"  -> Se identificaron {len(initial_gaps) + len(quality_gaps)} campos pendientes en la checklist.")

    # 5. Rondas de entrevista
    # 0 = sin tope: sigue hasta cubrir todo o hasta que la persona escriba salir (son ~13 rondas de 3 preguntas)
    max_rounds_env = os.environ.get("INTERVIEW_MAX_ROUNDS", "0").strip()
    try:
        max_rounds = int(max_rounds_env)
    except ValueError:
        max_rounds = 0

    distinct_temas = []
    for item in CHECKLIST:
        t = item["tema"]
        if t not in distinct_temas:
            distinct_temas.append(t)

    distinct_temas += [g["tema"] for g in quality_gaps if g["tema"] not in distinct_temas]
    asked_temas = set()
    # lo ya contestado no se vuelve a preguntar, tampoco en otra entrevista (ej. "no tengo certificaciones")
    answered_path = profile_paths.resolve("entrevista_respondidas.json")
    try:
        with open(answered_path, encoding="utf-8") as f:
            answered = set(json.load(f))
    except (OSError, ValueError, TypeError):
        answered = set()

    # antes de preguntar, el modelo revisa cada campo pendiente contra el perfil: lo que ya sabe o no aplica, no sale
    pending = [g for g in initial_gaps + quality_gaps if g["clave"] not in answered]
    deducidos, omitidos = _quiet(plan_questions, profile, bank, pending)
    _apply_facts(profile, bank, deducidos, pending)
    answered |= set(deducidos) | set(omitidos)
    print(f"  -> Revisé {len(pending)} campos: {len(pending) - len(deducidos) - len(omitidos)} por preguntar, "
          f"{len(deducidos)} deducidos del perfil, {len(omitidos)} no aplican.")
    for k, v in deducidos.items():
        print(f"     deducido  {k} = {str(v)[:70]}")
    for k, motivo in omitidos.items():
        print(f"     omitido   {k}: {motivo[:90]}")
    round_count = 0
    qa_chat = ""

    while True:
        current_gaps = [g for g in find_gaps(profile, bank, check_quality=False) + quality_gaps
                        if g["clave"] not in answered]
        if not current_gaps:
            print("  -> ¡Excelente! No quedan gaps pendientes en el banco.")
            break

        if max_rounds and round_count >= max_rounds:
            print(f"  -> Se alcanzó el límite de rondas ({max_rounds}). Guardando progreso...")
            break

        selected_tema = None
        for t in distinct_temas:
            if t not in asked_temas and any(g["tema"] == t for g in current_gaps):
                selected_tema = t
                break

        if not selected_tema:
            asked_temas.clear()
            for t in distinct_temas:
                if any(g["tema"] == t for g in current_gaps):
                    selected_tema = t
                    break

        if not selected_tema:
            selected_tema = current_gaps[0]["tema"]

        asked_temas.add(selected_tema)
        gaps_for_topic = [g for g in current_gaps if g["tema"] == selected_tema][:3]

        round_count += 1

        pistas_str = "\n".join(f"- {g['pista']} (campo: {g['clave']})" for g in gaps_for_topic)
        system_prompt = (
            "Eres un reclutador senior, cercano y profesional. Escribe en español UNA pregunta por cada aspecto "
            "faltante indicado (máximo 3).\n"
            "FORMATO OBLIGATORIO: solo las preguntas, una por línea, cada una entre ¿?. Sin saludo, sin introducción, "
            "sin numeración, sin viñetas, sin markdown, sin cierre.\n"
            "Cada pregunta: corta, natural (no de formulario burocrático), con un ejemplo breve entre paréntesis si "
            "ayuda.\n"
            "NUNCA repitas algo que ya se preguntó o que la persona ya contó en la conversación de abajo."
        )
        human_template = "Aspectos a consultar:\n{pistas}\n\nConversación hasta ahora:\n{chat}"

        try:
            questions_text = _quiet(
                llm_chain.invoke_text,
                system_prompt=system_prompt,
                human_template=human_template,
                variables={"pistas": pistas_str, "chat": qa_chat[-4000:] or "(ninguna)"},
                temperature=0.6,
            )
        except llm_chain.AllProvidersExhausted:
            print("  -> [CUOTA AGOTADA] Sin cupo de LLM para formular preguntas. Guardando progreso...")
            break
        except Exception as e:
            print(f"  -> Error generando preguntas: {e}")
            break

        questions = _format_questions(questions_text, gaps_for_topic)
        questions_text = "\n".join(questions)
        print(_round_header(round_count, selected_tema, len(current_gaps)))
        for i, q in enumerate(questions, 1):
            print(f"  {i}. {q}")
        print("\n  Tu respuesta (Enter dos veces para enviar · 'salir' en una línea sola para guardar y terminar):")
        user_lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line:
                break
            user_lines.append(line)
        user_response = "\n".join(user_lines).strip()

        # solo 'salir' en su propia línea: "no quiero salir de Bogotá" es una respuesta
        if user_lines and user_lines[-1].strip().lower() in ("salir", "exit", "quit"):
            user_response = "\n".join(user_lines[:-1]).strip()
            stop = True
        else:
            stop = False

        if user_response:
            qa_chat += f"\nRecruiter ({selected_tema}): {questions_text}\nCandidate: {user_response}\n"
            if selected_tema in {g["tema"] for g in quality_gaps}:
                quality_gaps = [g for g in quality_gaps if g["tema"] != selected_tema]  # va al perfil al re-armarlo
        elif not stop:
            print("  -> Sin respuesta, sigo con el siguiente tema.")
            continue

        if stop and not user_response:
            print("  -> Entendido. Guardando perfil y respuestas...")
            break

        # Extraer hechos
        # contra TODOS los huecos, no solo los del tema: si de paso contó su ciudad o una fortaleza, ya no se pregunta
        extracted = _quiet(extract_facts, user_response, current_gaps)
        print(f"  -> {len(extracted)} dato(s) guardado(s).")

        _apply_facts(profile, bank, extracted, current_gaps)
        # lo contestado no se repite aunque no quepa en un campo (ej. certificaciones: las arma el LLM al final)
        answered |= set(extracted)
        if stop:
            print("  -> Entendido. Guardando perfil y respuestas...")
            break

    # 6. Al final: guardar master_profile.json, answers.yaml y gaps_pendientes.json
    print("  -> Finalizando entrevista y guardando archivos...")
    if qa_chat:
        # lo que contó en la entrevista (métricas, logros, contexto) se integra al perfil: experiencia, resumen, etc.
        stories, personalidad = profile.stories, profile.personalidad  # el LLM no reescribe el texto literal
        try:
            profile = llm_chain.invoke_structured(
                system_prompt=parse_system_prompt,
                human_template="Resume:\n{cv_text}\n\nChat History / Context:\n{chat_history}",
                variables={"cv_text": raw_cv, "chat_history": (
                    "Previously Captured Master Profile (CARRY FORWARD every field unless the interview below "
                    f"contradicts it):\n{profile.model_dump_json()}\n\nInterview:\n{qa_chat}")},
                pydantic_model=MasterProfile,
                temperature=0.1,
            )
            profile.stories, profile.personalidad = stories, personalidad
        except Exception as e:
            print(f"  -> No se pudo re-armar el perfil con la entrevista ({e}); se guarda el anterior.")
    # las que dijo la persona se quedan; las inferidas del chat se suman sin repetir
    soft_skills = evaluate_soft_skills_from_chat(chat_history + qa_chat)
    profile.soft_skills += [s for s in soft_skills if s.lower() not in {x.lower() for x in profile.soft_skills}]

    export_final_candidate_json(profile)

    with open(answers_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(bank, f, allow_unicode=True, sort_keys=False)
    print(f"  -> Banco guardado en: {answers_path}")

    final_gaps = [g for g in find_gaps(profile, bank, check_quality=False) if g["clave"] not in answered]
    with open(answered_path, "w", encoding="utf-8") as f:
        json.dump(sorted(answered), f, indent=1, ensure_ascii=False)
    gaps_path = profile_paths.resolve("gaps_pendientes.json")
    pending_records = [
        {"tema": g["tema"], "clave": g["clave"], "para": g["para"]}
        for g in final_gaps
    ]
    with open(gaps_path, "w", encoding="utf-8") as f:
        json.dump(pending_records, f, indent=4, ensure_ascii=False)
    print(f"  -> Gaps pendientes ({len(pending_records)}) guardados en: {gaps_path}\n")
    print("  -> Entrevista completada.")


def print_fields(profile: Any, bank: Any):
    """Tabla de la CHECKLIST: de qué campo saca cada agente lo que necesita y si ya está lleno. Sin LLM."""
    gaps = find_gaps(profile, bank)
    pending = {g["clave"] for g in gaps}
    extra = [g for g in gaps if g["clave"] not in {item["clave"] for item in CHECKLIST}]
    print(f"{len(extra)} huecos del perfil (esquema sacado de la hoja de vida) y del banco (???) fuera de la tabla:")
    for g in extra:
        print(f"  {g['archivo']:<8} {g['clave']:<45} {g['pista'][:90]}")
    print()
    print(f"{'tema':<24} {'clave':<58} {'archivo':<8} {'para':<20} lleno")
    for item in CHECKLIST:
        print(f"{item['tema']:<24} {item['clave']:<58} {item['archivo']:<8} {','.join(item['para']):<20} "
              f"{'no' if item['clave'] in pending else 'sí'}")
    missing = sum(item["clave"] in pending for item in CHECKLIST)
    print(f"\n{missing} de {len(CHECKLIST)} campos pendientes (para = buscar: scout · cv: tailor · responder: aplicador).")


if __name__ == "__main__":
    import sys
    # la consola de Windows (cp1252) no imprime algunos caracteres que devuelve el LLM (ej. espacio fino)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # avisos de librerías (temperature ignorada, AFC de google-genai) en medio de las preguntas: no le sirven a la persona
    import logging
    import warnings
    warnings.filterwarnings("ignore")
    logging.getLogger("google_genai").setLevel(logging.ERROR)
    if not os.environ.get("JOBHUNTER_PROFILE"):
        sys.exit("Falta el perfil. En PowerShell: $env:JOBHUNTER_PROFILE='Tu Nombre'; py interviewer_agent.py")
    if "--campos" in sys.argv:
        paths = profile_paths.resolve("master_profile.json"), profile_paths.resolve("answers.yaml")
        prof = json.load(open(paths[0], encoding="utf-8")) if os.path.exists(paths[0]) else {}
        bnk = (yaml.safe_load(open(paths[1], encoding="utf-8")) or {}) if os.path.exists(paths[1]) else {}
        print_fields(prof, bnk)
    else:
        run_interview()
