import json
import os
import glob
import datetime
from typing import List, Optional, TypedDict
from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyPDFLoader
from langgraph.graph import StateGraph, END
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
    visa_sponsorship_needed: Optional[bool] = Field(description="True if they need visa sponsorship")
    willing_to_relocate: Optional[bool] = Field(description="True if willing to relocate")

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

# ==========================================
# 2. CONFIGURACIÓN DEL LLM
# ==========================================
# Una sola entrevista completa puede hacer 15-20+ llamadas al LLM, así que agotar la cuota
# de un solo proveedor a mitad de entrevista es común. llm_chain.py prueba Gemini -> Groq ->
# Cerebras -> OpenRouter en cada llamada individual, sin crashear ni perder el hilo.

# ==========================================
# 3. ESTADO DE LANGGRAPH
# ==========================================
class InterviewerState(TypedDict):
    cv_text: str
    chat_history: str
    profile: Optional[MasterProfile]
    missing_gaps: str
    draft_questions: str
    final_questions: str
    user_response: str
    iteration_count: int
    is_complete: bool

# ==========================================
# 4. FUNCIONES DE AYUDA (TOOLS)
# ==========================================

def extract_text_from_document() -> str:
    cv_text = ""
    # Busca dentro de la carpeta del perfil activo (Profiles/<nombre>) si hay uno seteado,
    # o en la raíz del repo si no (comportamiento legacy).
    search_dir = profile_paths.profile_dir() or os.path.dirname(os.path.abspath(__file__))
    # Intentar buscar especificamente el CV actual primero
    current_cv_matches = glob.glob(os.path.join(search_dir, "*Current CV*.pdf"))
    all_pdfs = glob.glob(os.path.join(search_dir, "*.pdf"))

    if current_cv_matches:
        pdf_target = current_cv_matches[0]
    else:
        pdf_target = next((f for f in all_pdfs if "Tailored" not in f), None)

    if pdf_target:
        print(f"\n[Sistema] Leyendo CV: {pdf_target} ...")
        loader = PyPDFLoader(pdf_target)
        cv_text = "\n".join([doc.page_content for doc in loader.load()])
    elif os.path.exists(os.path.join(search_dir, "cv.txt")):
        print("\n[Sistema] Leyendo cv.txt ...")
        with open(os.path.join(search_dir, "cv.txt"), "r", encoding="utf-8") as f:
            cv_text = f.read()
    else:
        print(f"\n[Sistema] No se encontró CV base en PDF ni cv.txt dentro de {search_dir}.")
    return cv_text

def evaluate_soft_skills_from_chat(chat_history: str) -> List[str]:
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
        print("\n[CUOTA AGOTADA] Los 4 proveedores se quedaron sin cupo evaluando soft skills. Se omite este paso.")
        return []
    return [s.strip() for s in text.split(',')]

def export_final_candidate_json(completed_profile: MasterProfile):
    print("\n[Sistema] Guardando master_profile.json...")
    final_json_str = completed_profile.model_dump_json(indent=4)
    
    with open(profile_paths.resolve("master_profile.json"), "w", encoding="utf-8") as f:
        f.write(final_json_str)
        
    test_dir = profile_paths.resolve("perfiles_de_prueba")  # copias dentro de la carpeta de cada persona
    os.makedirs(test_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(test_dir, f"master_profile_{timestamp}.json")
    
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(final_json_str)
        
    print(f"Perfil guardado con éxito! (Copia en: {backup_path})\n")
    print("======================================================")
    print(" ESTE ES TU JSON MAESTRO FINAL:")
    print("======================================================")
    print(final_json_str)
    print("======================================================\n")
    print("\nFase 1 terminada. El master_profile está listo.")

# ==========================================
# 5. NODOS DE LANGGRAPH
# ==========================================

def analyze_and_draft_node(state: InterviewerState) -> InterviewerState:
    print("\n--- [Nodo: Analyze & Draft] ---")
    cv_text = state.get("cv_text", "")
    chat_history = state.get("chat_history", "")
    
    print("Analizando perfil y estructurando JSON...")

    # 1. Parsea el perfil (Gemini -> Groq -> Cerebras -> OpenRouter, llm_chain.py)
    parse_system_prompt = """You are an expert data extraction assistant. Map the provided resume and chat history to the strict JSON schema in ENGLISH.
TRANSLATE EVERY TEXT FIELD TO ENGLISH even if the resume is in Spanish or another language: professional_summary, target_roles,
current_role, achievements, abilities, degrees, seniority_context, everything. Keep proper names (people, companies, products) as they are.
CRITICAL INSTRUCTION: You MUST extract ALL sections of the resume, particularly 'PROFESSIONAL EXPERIENCE'. DO NOT LEAVE ARRAYS EMPTY IF DATA EXISTS.
Pay special attention to the 'Candidate Initial Context' in the chat history to adapt the professional_summary if needed."""
    try:
        profile = llm_chain.invoke_structured(
            system_prompt=parse_system_prompt,
            human_template="Resume:\n{cv_text}\n\nChat History / Context:\n{chat_history}",
            variables={"cv_text": cv_text, "chat_history": chat_history},
            pydantic_model=MasterProfile,
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted as e:
        print(f"\n[CUOTA AGOTADA] Los 4 proveedores se quedaron sin cupo estructurando el perfil ({e}). "
              f"Se usa un perfil vacío para este intento — volvé a correr la entrevista cuando la cuota reponga.")
        profile = MasterProfile()
    except Exception as e:
        print(f"Error parseando schema: {e}")
        profile = MasterProfile()

    # 2. Identifica gaps
    print("Evaluando deficiencias (falta de métricas STAR, roles vacíos)...")
    try:
        missing_gaps = llm_chain.invoke_text(
            system_prompt=("Eres un analizador estricto. Revisa el siguiente JSON. Identifica campos vitales vacíos (ej. email, idiomas) "
                            "y revisa 'experience'. Si los 'achievements' no tienen métricas cuantificables o no explican el 'cómo' (STAR), repórtalo. "
                            "ADEMÁS, estos campos son OBLIGATORIOS para que el Scout Agent y el Applicator Agent funcionen bien y casi nunca vienen en el CV, "
                            "así que si están vacíos SIEMPRE repórtalos como gap a preguntar directamente: "
                            "'seniority_context' (su nivel real por disciplina, ej. Mid QA / Junior Dev), 'salary_expectation' (rango salarial esperado), "
                            "'work_model' (remoto/híbrido/presencial y si está abierta a reubicarse), 'target_companies' (empresas o tipos de empresa objetivo), "
                            "'deal_breakers' (cosas que NO acepta en un trabajo), 'writer_instructions' (tono que quiere en su carta de presentación). "
                            "Devuelve una lista concisa en ESPAÑOL de lo que falta."),
            human_template="{profile_json}",
            variables={"profile_json": profile.model_dump_json()},
            temperature=0.1,
        )
    except llm_chain.AllProvidersExhausted:
        missing_gaps = "(No se pudo evaluar — los 4 proveedores LLM se quedaron sin cupo.)"

    # 3. Borrador de preguntas inicial
    print("Generando borrador de preguntas...")
    try:
        draft_questions = llm_chain.invoke_text(
            system_prompt=("Eres un reclutador experto en el área del candidato (sea técnica, comercial, financiera u otra). "
                            "Basado en estos gaps, genera una serie de preguntas para el candidato. "
                            "Pide herramientas, ejemplos numéricos, resultados o tiempos reducidos si faltan. "
                            "No te preocupes por el tono aún, solo lista las preguntas necesarias."),
            human_template="Gaps:\n{missing_gaps}",
            variables={"missing_gaps": missing_gaps},
            temperature=0.6,
        )
    except llm_chain.AllProvidersExhausted:
        draft_questions = ""

    return {
        "profile": profile,
        "missing_gaps": missing_gaps,
        "draft_questions": draft_questions
    }

def review_node(state: InterviewerState) -> InterviewerState:
    print("\n--- [Nodo: Review] ---")
    print("Revisando coherencia y cruzando contra CV para evitar redundancias...")
    
    is_first = (state["iteration_count"] == 0)
    greeting_instruction = ("Dado que es la PRIMERA interacción, preséntate brevemente como reclutador experto en su área." 
                            if is_first else 
                            "NO saludes. Empieza directamente con la pregunta de transición.")

    review_system_prompt = f"""Eres el Reviewer Final del ReAct Agent.
Tu trabajo es revisar las 'Draft Questions' cruzando la información con el 'CV Text' original y el 'Chat History'.
REGLA CRÍTICA: SI LA RESPUESTA A LA PREGUNTA YA EXISTE EN EL CV O EN EL CHAT HISTORY, ELIMINA ESA PREGUNTA.
Si quedan demasiadas preguntas, selecciona MÁXIMO 3 preguntas clave y formúlalas en un solo párrafo amable y conversacional.
Eres empático pero riguroso en pedir impacto y métricas.
{greeting_instruction}

Si después de cruzar la info te das cuenta de que el perfil ya tiene excelentes métricas o que las 'Draft Questions' no tienen sentido porque el CV ya las responde, devuelve EXACTAMENTE la palabra: 'PERFIL_COMPLETO'."""

    try:
        final_questions = llm_chain.invoke_text(
            system_prompt=review_system_prompt,
            human_template="CV Text:\n{cv_text}\n\nChat History:\n{chat_history}\n\nDraft Questions:\n{draft_questions}",
            variables={
                "cv_text": state["cv_text"],
                "chat_history": state["chat_history"],
                "draft_questions": state["draft_questions"],
            },
            temperature=0.6,
        )
    except llm_chain.AllProvidersExhausted:
        print("\n[CUOTA AGOTADA] Los 4 proveedores se quedaron sin cupo revisando preguntas. Se da por completo el perfil con lo que hay hasta ahora.")
        final_questions = "PERFIL_COMPLETO"

    return {"final_questions": final_questions}

def human_node(state: InterviewerState) -> InterviewerState:
    print("\n======================================================")
    final_q = state["final_questions"]
    
    if "PERFIL_COMPLETO" in final_q.upper() or state["iteration_count"] >= 3:
        if "PERFIL_COMPLETO" in final_q.upper():
            print("\nRecruiter: ¡Tu perfil está increíble y 100% optimizado! No tengo más preguntas.")
        else:
            print("\nRecruiter: Hemos avanzado bastante, guardaremos el perfil con la info hasta ahora.")
        return {"is_complete": True}
        
    print(f"\nRecruiter: {final_q}")
    print("\nTú (puedes escribir/pegar múltiples líneas. Escribe 'salir' en una línea nueva para terminar. Presiona Enter dos veces para enviar):")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    user_input = "\n".join(lines)
    
    user_input_lower = user_input.strip().lower()
    if user_input_lower in ['salir', 'exit', 'quit'] or "no mas preguntas" in user_input_lower or "no más preguntas" in user_input_lower:
        print("\nRecruiter: Entendido. Guardaré el perfil.")
        return {"is_complete": True}
        
    return {"user_response": user_input, "is_complete": False}

def update_node(state: InterviewerState) -> InterviewerState:
    print("\n--- [Nodo: Update] ---")
    print("Procesando tu respuesta y traduciéndola a metodología STAR...")
    
    try:
        star_text = llm_chain.invoke_text(
            system_prompt=("Transforma la respuesta del usuario en texto estilo STAR, resaltando el impacto, en inglés. "
                            "Si la respuesta es muy corta, solo mejórala un poco."),
            human_template="{user_response}",
            variables={"user_response": state["user_response"]},
            temperature=0.6,
        )
    except llm_chain.AllProvidersExhausted:
        print("\n[CUOTA AGOTADA] Los 4 proveedores se quedaron sin cupo. Se guarda tu respuesta tal cual, sin reescribir a STAR.")
        star_text = state["user_response"]

    new_chat = state["chat_history"] + f"\nAgent: {state['final_questions']}\nCandidate: {state['user_response']}\nTranslated Impact: {star_text}\n"
    
    return {
        "chat_history": new_chat,
        "iteration_count": state["iteration_count"] + 1
    }

def should_continue(state: InterviewerState) -> str:
    if state["is_complete"]:
        return END
    return "update_node"

# ==========================================
# 6. ORQUESTACIÓN (CONSTRUIR GRAFO)
# ==========================================
def run_interview():
    print("======================================================")
    print(" Iniciando ReAct Profiler Agent (LangGraph + Gemini)")
    print("======================================================\n")
    
    raw_cv = extract_text_from_document()

    chat_history = ""
    existing_profile_path = profile_paths.resolve("master_profile.json")
    if os.path.exists(existing_profile_path):
        print("\n[Sistema] Encontré un master_profile.json existente. Voy a partir de esa info (no se perderá lo ya guardado, ej. portfolio_projects, salary_expectation, etc.).")
        with open(existing_profile_path, "r", encoding="utf-8") as f:
            existing_profile_str = f.read()
        chat_history += ("Previously Captured Master Profile (CARRY FORWARD every field here unless the new CV/context "
                          "explicitly contradicts it — especially 'portfolio_projects', 'target_companies', "
                          "'salary_expectation', 'work_model', 'deal_breakers', 'seniority_context', 'writer_instructions'):\n"
                          f"{existing_profile_str}\n\n")

    print("\n[Contexto Inicial] ¿Hay algún cambio de carrera o contexto general que deba saber?")
    print("Escribe o pega tu contexto (acepta múltiples líneas). Presiona Enter dos veces seguidas para enviar, o solo Enter una vez para omitir:")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    initial_context = "\n".join(lines)
    if initial_context.strip():
        chat_history += f"Candidate Initial Context: {initial_context}\n"
    
    initial_state: InterviewerState = {
        "cv_text": raw_cv,
        "chat_history": chat_history,
        "profile": None,
        "missing_gaps": "",
        "draft_questions": "",
        "final_questions": "",
        "user_response": "",
        "iteration_count": 0,
        "is_complete": False
    }
    
    # Construir Grafo
    builder = StateGraph(InterviewerState)
    builder.add_node("analyze_and_draft_node", analyze_and_draft_node)
    builder.add_node("review_node", review_node)
    builder.add_node("human_node", human_node)
    builder.add_node("update_node", update_node)
    
    builder.set_entry_point("analyze_and_draft_node")
    builder.add_edge("analyze_and_draft_node", "review_node")
    builder.add_edge("review_node", "human_node")
    
    builder.add_conditional_edges(
        "human_node",
        should_continue,
        {
            END: END,
            "update_node": "update_node"
        }
    )
    
    builder.add_edge("update_node", "analyze_and_draft_node")
    
    graph = builder.compile()
    
    # Ejecutar Grafo
    final_state = graph.invoke(initial_state)
    
    # Al finalizar, guardamos y calculamos soft skills
    print("\nFinalizando y exportando...")
    profile = final_state.get("profile")
    if profile:
        profile.soft_skills = evaluate_soft_skills_from_chat(final_state["chat_history"])
        export_final_candidate_json(profile)
    else:
        print("No se pudo generar el perfil.")

if __name__ == "__main__":
    run_interview()
