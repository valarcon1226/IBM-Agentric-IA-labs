import json
import os
import glob
import re
import datetime
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

    # --- Estilo de escritura (cartas y respuestas abiertas suenan como la persona, no como IA) ---
    {
        "tema": "estilo_escritura",
        "archivo": "bank",
        "clave": "estilo_escritura.muestra",
        "para": ["responder", "cv"],
        "pista": "Un texto real escrito por la persona (correo, post de LinkedIn, mensaje a un cliente). Cópialo TAL CUAL, sin resumirlo",
    },
    {
        "tema": "estilo_escritura",
        "archivo": "bank",
        "clave": "estilo_escritura.tono",
        "para": ["responder", "cv"],
        "pista": "Cómo quiere sonar al escribir (ej. directa y cercana, sin frases corporativas)",
    },
    {
        "tema": "estilo_escritura",
        "archivo": "bank",
        "clave": "estilo_escritura.evitar",
        "para": ["responder", "cv"],
        "pista": "Palabras o frases que nunca usaría (ej. 'apasionada', 'sinergia')",
    },

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
            print(f"\n[Sistema] Leyendo CV: {pdf_target} ...")
            try:
                pages = "\n".join(doc.page_content for doc in PyPDFLoader(pdf_target).load())
                cv_text += f"\n\n===== {os.path.basename(pdf_target)} =====\n{pages}"
            except Exception as e:
                print(f"[Sistema] Error cargando PDF {pdf_target}: {e}")
        cv_text = re.sub(r"\s*\[cite: \d+\]", "", cv_text)
    elif os.path.exists(os.path.join(search_dir, "cv.txt")):
        print("\n[Sistema] Leyendo cv.txt ...")
        with open(os.path.join(search_dir, "cv.txt"), "r", encoding="utf-8") as f:
            cv_text = f.read()
    else:
        print(f"\n[Sistema] No se encontró CV base en PDF ni cv.txt dentro de {search_dir}.")
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
            print(f"\n[Sistema] Leyendo archivo de info adicional: {fname} ...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    contents.append(f"===== {fname} =====\n{text}")
            except Exception as e:
                print(f"[Sistema] Error leyendo {fname}: {e}")
        elif ext == ".pdf":
            print(f"\n[Sistema] Leyendo PDF de info adicional: {fname} ...")
            try:
                pages = "\n".join(doc.page_content for doc in PyPDFLoader(filepath).load())
                pages = re.sub(r"\s*\[cite: \d+\]", "", pages).strip()
                if pages:
                    contents.append(f"===== {fname} =====\n{pages}")
            except Exception as e:
                print(f"[Sistema] Error leyendo PDF {fname}: {e}")

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
        print(f"[Sistema] Error evaluando calidad de logros con IA: {e}")

    return []


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

    # 2. Búsqueda dinámica de campos extras con '???' en bank (respuestas_modelo e idiomas)
    if isinstance(bank, dict):
        if isinstance(bank.get("respuestas_modelo"), dict):
            for k, v in bank["respuestas_modelo"].items():
                clave = f"respuestas_modelo.{k}"
                if _is_empty_or_placeholder(v):
                    if not any(g["clave"] == clave for g in gaps):
                        gaps.append({
                            "tema": "respuestas_modelo",
                            "archivo": "bank",
                            "clave": clave,
                            "para": ["responder"],
                            "pista": f"Respuesta modelo para: {k.replace('_', ' ')}",
                        })
        if isinstance(bank.get("idiomas"), dict):
            for k, v in bank["idiomas"].items():
                clave = f"idiomas.{k}"
                if _is_empty_or_placeholder(v):
                    if not any(g["clave"] == clave for g in gaps):
                        gaps.append({
                            "tema": "idiomas",
                            "archivo": "bank",
                            "clave": clave,
                            "para": ["responder", "cv"],
                            "pista": f"Nivel para idioma: {k}",
                        })

    # 3. Gaps de calidad con IA
    if check_quality and profile:
        gaps.extend(find_quality_gaps(profile))

    return gaps


def form_gaps(profile: Any, bank: dict) -> List[dict]:
    """Preguntas de los formularios ya guardados (fixtures/forms y Profiles/<persona>/forms_real) que el aplicador aún
    no sabría contestar con este banco. Se preguntan una vez en la entrevista y quedan en aprendidas: (answer_engine
    las busca por etiqueta). Las abiertas no: esas las redacta la IA con el perfil, las historias y el estilo."""
    import tempfile
    import answer_engine
    from form_reader import parse_html
    here = os.path.dirname(os.path.abspath(__file__))
    paths = (glob.glob(os.path.join(here, "fixtures", "forms", "*.html"))
             + glob.glob(os.path.join(profile_paths.resolve("forms_real"), "**", "*.html"), recursive=True))
    no_llm = dict(llm_classifier_fn=lambda *_: None, llm_text_fn=lambda *_: None)
    checklist_keys = {item["clave"] for item in CHECKLIST}
    gaps, seen = [], set()
    with tempfile.TemporaryDirectory() as td:  # answer_engine lee de archivos: el banco y perfil de esta entrevista
        bank_path, prof_path = os.path.join(td, "answers.yaml"), os.path.join(td, "master_profile.json")
        with open(bank_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(bank or {}, f, allow_unicode=True)
        with open(prof_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump() if hasattr(profile, "model_dump") else (profile or {}), f, ensure_ascii=False)
        for path in paths:
            with open(path, encoding="utf-8", errors="ignore") as f:
                fields = parse_html(f.read())
            for field in fields:
                norm = answer_engine.normalize_label(field.label or field.key)
                # plantillas rotas ({location}) y retos anti-bots ("figure out the secret") no son datos de la persona
                if (not norm or norm in seen or field.kind == "file" or "{" in (field.label or "")
                        or re.search(r"secret|encoded", norm) or answer_engine._is_open_text_field(field, norm)):
                    continue
                # ya las cubre la CHECKLIST (salario, consentimientos y firmas, claves con sinónimo): no se repiten
                if (answer_engine._find_synonym_key(norm) in checklist_keys or answer_engine.is_consent(norm)
                        or answer_engine._SALARY.search(norm)):
                    continue
                seen.add(norm)
                if answer_engine.answer(field, {}, answers_path=bank_path, master_profile_path=prof_path,
                                        **no_llm).needs_human:
                    opts = f" (opciones: {', '.join(field.options[:12])})" if field.options else ""
                    gaps.append({"tema": "formularios", "archivo": "bank", "clave": f"aprendidas.{norm}",
                                 "para": ["responder"], "pista": f"Pregunta de formulario: {field.label}{opts}"})
    return gaps


# ==========================================
# 5. EXTRACT FACTS Y MERGE BANK / PROFILE
# ==========================================

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
        print(f"[Sistema] Error llamando a LLM para extraer hechos: {e}")
        return {}

    clean_text = raw_out.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text)

    try:
        data = json.loads(clean_text)
    except Exception:
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                return {}
        else:
            return {}

    if not isinstance(data, dict):
        return {}

    asked = {g["clave"] for g in gaps_preguntados}
    facts = {}
    for k, v in data.items():
        if (k in valid_checklist_keys or k.startswith(("respuestas_modelo.", "idiomas.")) or k in asked
                and k.startswith("aprendidas.")) and not _is_empty_or_placeholder(v):
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
            or raw_clave.startswith("respuestas_modelo.")
            or raw_clave.startswith("idiomas.")
            or raw_clave.startswith("aprendidas.")  # preguntas de formularios (form_gaps)
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
        if "." in clave:
            parts = clave.split(".")
            if parts[0] == "personal_info":
                if profile.personal_info is None:
                    profile.personal_info = PersonalInfo(
                        full_name="", email="", number="", location="", linkedin_url="", github_url=""
                    )
                curr_val = getattr(profile.personal_info, parts[1], None)
                if _is_empty_or_placeholder(curr_val):
                    setattr(profile.personal_info, parts[1], val)
        else:
            curr_val = getattr(profile, clave, None)
            if _is_empty_or_placeholder(curr_val):
                if isinstance(curr_val, list) and not isinstance(val, list):
                    setattr(profile, clave, [val])
                else:
                    setattr(profile, clave, val)


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
        print(f"[Sistema] Error evaluando soft skills: {e}")
        return []
    return [s.strip() for s in text.split(',') if s.strip()]


def export_final_candidate_json(completed_profile: MasterProfile):
    """Guarda master_profile.json y una copia de respaldo con timestamp."""
    print("\n[Sistema] Guardando master_profile.json...")
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

    print(f"Perfil guardado con éxito! (Copia en: {backup_path})\n")


# ==========================================
# 6. FLUJO PRINCIPAL DE ENTREVISTA
# ==========================================

def run_interview():
    print("======================================================")
    print(" Iniciando Entrevista Completa (JobHunter)")
    print("======================================================\n")

    # 1. Leer el CV
    raw_cv = extract_text_from_document()

    # 2. Pedir información adicional
    info_files_text = read_additional_info_files()

    print("\n[Contexto Inicial] ¿Hay algún cambio de carrera o contexto general que deba saber?")
    print("Escribe o pega tu contexto (acepta múltiples líneas). Presiona Enter dos veces seguidas para enviar, o solo Enter una vez para omitir:")
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
        print("\n[Sistema] Encontré un master_profile.json existente.")
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
            print(f"[Sistema] Error cargando master_profile.json previo: {e}")

    if info_files_text:
        chat_history += f"Additional Info Files:\n{info_files_text}\n\n"
    if initial_context:
        chat_history += f"Candidate Initial Context:\n{initial_context}\n\n"

    print("\n[Sistema] Analizando perfil inicial y estructurando datos...")
    parse_system_prompt = """You are an expert data extraction assistant. Map the provided resume, additional info files, and chat history to the strict JSON schema in ENGLISH.
TRANSLATE EVERY TEXT FIELD TO ENGLISH even if the resume is in Spanish or another language: professional_summary, target_roles,
current_role, achievements, abilities, degrees, seniority_context, everything. Keep proper names (people, companies, products) as they are.
CRITICAL INSTRUCTION: You MUST extract ALL sections of the resume, particularly 'PROFESSIONAL EXPERIENCE'. DO NOT LEAVE ARRAYS EMPTY IF DATA EXISTS.
Pay special attention to the 'Candidate Initial Context' in the chat history to adapt the professional_summary if needed."""

    try:
        profile = llm_chain.invoke_structured(
            system_prompt=parse_system_prompt,
            human_template="Resume:\n{cv_text}\n\nChat History / Context:\n{chat_history}",
            variables={"cv_text": raw_cv, "chat_history": chat_history},
            pydantic_model=MasterProfile,
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted as e:
        print(f"\n[CUOTA AGOTADA] Los proveedores se quedaron sin cupo estructurando el perfil ({e}).")
        profile = existing_profile or MasterProfile()
    except Exception as e:
        print(f"[Sistema] Error estructurando perfil inicial: {e}")
        profile = existing_profile or MasterProfile()

    # Cargar answers.yaml actual
    answers_path = profile_paths.resolve("answers.yaml")
    bank = {}
    if os.path.exists(answers_path):
        print(f"\n[Sistema] Cargando answers.yaml existente...")
        try:
            with open(answers_path, "r", encoding="utf-8") as f:
                bank = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Sistema] Error leyendo answers.yaml: {e}")
            bank = {}
    # el tono que antes vivía en el perfil (writer_instructions) pasa al banco, que es donde lo lee answer_engine
    if profile.writer_instructions:
        merge_bank(bank, {"estilo_escritura.tono": profile.writer_instructions})

    # 4. find_gaps DETERMINISTA inicial
    initial_gaps = find_gaps(profile, bank, check_quality=False)
    # logros sin métricas / tipos de rol sin material: la IA los evalúa una vez; se preguntan como un tema más
    quality_gaps = find_quality_gaps(profile)
    print(f"\n[Sistema] Se identificaron {len(initial_gaps) + len(quality_gaps)} campos pendientes en la checklist.")

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

    distinct_temas += [g["tema"] for g in quality_gaps if g["tema"] not in distinct_temas] + ["formularios"]
    asked_temas = set()
    round_count = 0
    qa_chat = ""
    pending_forms = None

    while True:
        current_gaps = find_gaps(profile, bank, check_quality=False) + quality_gaps
        if not current_gaps and pending_forms is None:
            # con el banco ya completo, lo que los formularios guardados todavía preguntarían
            pending_forms = form_gaps(profile, bank)
            print(f"\n[Sistema] {len(pending_forms)} preguntas de formularios reales que el banco aún no contesta.")
        current_gaps += [g for g in pending_forms or [] if _is_empty_or_placeholder(_get_nested_val(bank, g["clave"]))]
        if not current_gaps:
            print("\nRecruiter: ¡Excelente! No quedan gaps pendientes en el banco.")
            break

        if max_rounds and round_count >= max_rounds:
            print(f"\nRecruiter: Se alcanzó el límite de rondas ({max_rounds}). Guardando progreso...")
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
        print(f"\n--- [Ronda {round_count}: Tema '{selected_tema}'] ---")

        pistas_str = "\n".join(f"- {g['pista']} (campo: {g['clave']})" for g in gaps_for_topic)
        system_prompt = (
            "Eres un reclutador senior experto, empático y profesional. "
            f"Formula como MÁXIMO 3 preguntas conversadas y fluidas en español sobre el tema '{selected_tema}'. "
            "REGLAS:\n"
            "1. NO suenes a formulario burocrático o lista rígida.\n"
            "2. Pregunta amablemente por los aspectos faltantes indicados.\n"
            "3. Máximo 3 preguntas breves en un solo párrafo o texto bien estructurado."
        )
        human_template = "Aspectos a consultar:\n{pistas}"

        try:
            questions_text = llm_chain.invoke_text(
                system_prompt=system_prompt,
                human_template=human_template,
                variables={"pistas": pistas_str},
                temperature=0.6,
            )
        except llm_chain.AllProvidersExhausted:
            print("\n[CUOTA AGOTADA] Sin cupo de LLM para formular preguntas. Guardando progreso...")
            break
        except Exception as e:
            print(f"[Sistema] Error generando preguntas: {e}")
            break

        print(f"\nRecruiter: {questions_text}")
        print("\nTú (puedes escribir/pegar múltiples líneas. Escribe 'salir' en una línea nueva para terminar. Presiona Enter dos veces para enviar):")
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
            print("[Sistema] Respuesta vacía, pasando a la siguiente consulta.")
            continue

        if stop and not user_response:
            print("\nRecruiter: Entendido. Guardando perfil y respuestas...")
            break

        # Extraer hechos
        print("[Sistema] Extrayendo datos estructurados de tu respuesta...")
        extracted = extract_facts(user_response, gaps_for_topic)

        # Distribuir historias y campos de profile
        valid_checklist_keys = {item["clave"] for item in CHECKLIST}
        for k, v in list(extracted.items()):
            if k.startswith("stories."):
                story_tema = k.split(".", 1)[1]
                _upsert_story(profile, story_tema, str(v))
            elif any(item["clave"] == k and item["archivo"] == "profile" for item in CHECKLIST):
                _update_profile_field(profile, k, v)

        # Merge en bank
        merge_bank(bank, extracted)
        if stop:
            print("\nRecruiter: Entendido. Guardando perfil y respuestas...")
            break

    # 6. Al final: guardar master_profile.json, answers.yaml y gaps_pendientes.json
    print("\n[Sistema] Finalizando entrevista y guardando archivos...")
    if qa_chat:
        # lo que contó en la entrevista (métricas, logros, contexto) se integra al perfil: experiencia, resumen, etc.
        stories = profile.stories
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
            profile.stories = stories
        except Exception as e:
            print(f"[Sistema] No se pudo re-armar el perfil con la entrevista ({e}); se guarda el anterior.")
    soft_skills = evaluate_soft_skills_from_chat(chat_history + qa_chat)
    if soft_skills:
        profile.soft_skills = soft_skills

    export_final_candidate_json(profile)

    with open(answers_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(bank, f, allow_unicode=True, sort_keys=False)
    print(f"[Sistema] Banco guardado en: {answers_path}")

    final_gaps = find_gaps(profile, bank, check_quality=False) + [
        g for g in pending_forms or [] if _is_empty_or_placeholder(_get_nested_val(bank, g["clave"]))]
    gaps_path = profile_paths.resolve("gaps_pendientes.json")
    pending_records = [
        {"tema": g["tema"], "clave": g["clave"], "para": g["para"]}
        for g in final_gaps
    ]
    with open(gaps_path, "w", encoding="utf-8") as f:
        json.dump(pending_records, f, indent=4, ensure_ascii=False)
    print(f"[Sistema] Gaps pendientes ({len(pending_records)}) guardados en: {gaps_path}\n")
    print("Entrevista completada con éxito.")


def print_fields(profile: Any, bank: Any):
    """Tabla de la CHECKLIST: de qué campo saca cada agente lo que necesita y si ya está lleno. Sin LLM."""
    pending = {g["clave"] for g in find_gaps(profile, bank)}
    print(f"{'tema':<24} {'clave':<58} {'archivo':<8} {'para':<20} lleno")
    for item in CHECKLIST:
        print(f"{item['tema']:<24} {item['clave']:<58} {item['archivo']:<8} {','.join(item['para']):<20} "
              f"{'no' if item['clave'] in pending else 'sí'}")
    missing = sum(item["clave"] in pending for item in CHECKLIST)
    print(f"\n{missing} de {len(CHECKLIST)} campos pendientes (para = buscar: scout · cv: tailor · responder: aplicador).")


if __name__ == "__main__":
    import sys
    if "--campos" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        paths = profile_paths.resolve("master_profile.json"), profile_paths.resolve("answers.yaml")
        prof = json.load(open(paths[0], encoding="utf-8")) if os.path.exists(paths[0]) else {}
        bnk = (yaml.safe_load(open(paths[1], encoding="utf-8")) or {}) if os.path.exists(paths[1]) else {}
        print_fields(prof, bnk)
        forms = form_gaps(prof, bnk)
        print(f"{len(forms)} preguntas de formularios guardados que el banco aún no contesta:")
        for g in forms:
            print(f"  - {g['pista'].removeprefix('Pregunta de formulario: ')[:150]}")
    else:
        run_interview()
