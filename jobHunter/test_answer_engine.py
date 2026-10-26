"""Pruebas del motor de respuestas (Fase D de APPLICATOR_PLAN.md).

Se corre con: py test_answer_engine.py
Imprime 'ok' si todas las aserciones pasan.

Verificaciones clave:
1. 30 etiquetas reales tomadas de fixtures/forms/ con la respuesta esperada
   escrita a mano usando Profiles/Valentina Alarcon/answers.yaml.
2. 0 datos duros inventados (preguntas desconocidas -> needs_human=True, value=None).
3. Todo '???' -> needs_human=True.
4. salario.minimo_aceptable JAMÁS aparece como respuesta.
5. Perfil sin answers.yaml -> needs_human=True.
6. learn(label, value) agrega a aprendidas: (probado en copia temporal, nunca toca el real).
7. Emparejamiento de opciones (booleanos sí/no, textos, difflib, sin coincidencia -> needs_human).
8. Clasificador LLM y redactor de texto abierto reemplazables por funciones fijas en el test.
"""
import os
import sys
import tempfile
import yaml
from dataclasses import replace
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Asegurar que el perfil activo para el test sea Valentina Alarcon
os.environ["JOBHUNTER_PROFILE"] = "Valentina Alarcon"

import profile_paths
from form_reader import Field
from answer_engine import (
    Answer,
    CLOSED_BANK_KEYS,
    SYNONYMS,
    _answer_rules as answer,  # las reglas; el envoltorio (opcional sin dato -> en blanco) se prueba al final
    answer as answer_final,
    learn,
    match_option,
    normalize_label,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "forms"
JOB_FIXTURE = {
    "cv_path": "CVs_Listos/Valentina_Alarcon.pdf",
    "company": "Supermove",
    "title": "QA Automation Engineer",
    "description": "Looking for a QA engineer with Python, Playwright and agent experience.",
    "cover_letter": "Estimado equipo de contratación, adjunto mi postulación...",
}

# ---------------------------------------------------------------------------
# 1. 30 etiquetas reales tomadas directamente de fixtures/forms/
# Respuestas esperadas escritas a mano según Profiles/Valentina Alarcon/answers.yaml
# y master_profile.json
# ---------------------------------------------------------------------------

CASES_30 = [
    # custom_form.html
    {
        "fixture": "custom_form.html",
        "field": Field(key="applicant_name", kind="text", label="Full Name"),
        "expected_value": "Valentina Alarcon Gamboa",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "custom_form.html",
        "field": Field(key="applicant_email", kind="email", label="Email Address"),
        "expected_value": "valarconeur@gmail.com",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "custom_form.html",
        "field": Field(
            key="authorized_us",
            kind="radio",
            label="Are you legally authorized to work in the United States?",
            options=["Yes", "No"],
        ),
        "expected_value": "No",
        "expected_source": "bank",
        "expected_needs_human": False,
    },

    # workable.html
    {
        "fixture": "workable.html",
        "field": Field(key="firstname", kind="text", label="First name"),
        "expected_value": "Valentina",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="lastname", kind="text", label="Last name"),
        "expected_value": "Alarcon Gamboa",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="email", kind="email", label="Email"),
        "expected_value": "valarconeur@gmail.com",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="phone", kind="tel", label="Phone"),
        "expected_value": "+57 305 772 8718",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="ca_10933", kind="text", label="Desired Monthly Salary in USD"),
        "expected_value": "USD 3,750 per month",  # 45000 USD/año / 12
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="ca_10934", kind="text", label="Country of Residence"),
        "expected_value": "Colombia",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(
            key="qa_12636128",
            kind="radio",
            label="¿Certificas que no tienes condenas por delitos graves y autorizas a DEVSU para verificar tus referencias laborales, académicas y antecedentes criminales durante el proceso de selección? *Seleccionar 'No' significa que tienes condenas por delitos graves o no autorizas la verificación de antecedentes.",
            options=["YES", "NO"],
        ),
        "expected_value": "YES",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "workable.html",
        "field": Field(key="input_files_input_excsfbdokmr9qofv", kind="file", label="Choose file"),
        "expected_value": "CVs_Listos/Valentina_Alarcon.pdf",
        "expected_source": "file",
        "expected_needs_human": False,
    },

    # lever.html
    {
        "fixture": "lever.html",
        "field": Field(key="name", kind="text", label="Full name"),
        "expected_value": "Valentina Alarcon Gamboa",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="email", kind="email", label="Email"),
        "expected_value": "valarconeur@gmail.com",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="phone", kind="text", label="Phone"),
        "expected_value": "+57 305 772 8718",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="org", kind="text", label="Current company"),
        "expected_value": "Quorum Software",
        "expected_source": "profile",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="urls_linkedin", kind="text", label="LinkedIn URL"),
        "expected_value": "https://linkedin.com/in/valentinaalarcon",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="urls_github", kind="text", label="GitHub URL"),
        "expected_value": "https://github.com/valarcon1226",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(key="urls_portfolio", kind="text", label="Portfolio URL"),
        "expected_value": "https://github.com/valarcon1226",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "lever.html",
        "field": Field(
            key="resume",
            kind="file",
            label="Resume/CV ✱ Couldn't auto-read resume. Analyzing resume... Success!",
        ),
        "expected_value": "CVs_Listos/Valentina_Alarcon.pdf",
        "expected_source": "file",
        "expected_needs_human": False,
    },

    # ashby.html
    {
        "fixture": "ashby.html",
        "field": Field(key="systemfield_name", kind="text", label="Name"),
        "expected_value": "Valentina Alarcon Gamboa",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "ashby.html",
        "field": Field(key="systemfield_email", kind="email", label="Email"),
        "expected_value": "valarconeur@gmail.com",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "ashby.html",
        "field": Field(key="systemfield_resume", kind="file", label="Resume"),
        "expected_value": "CVs_Listos/Valentina_Alarcon.pdf",
        "expected_source": "file",
        "expected_needs_human": False,
    },
    {
        "fixture": "ashby.html",
        "field": Field(key="e766fd01_b436_4c9b_b18c_c59da463c2a3", kind="text", label="LinkedIn"),
        "expected_value": "https://linkedin.com/in/valentinaalarcon",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "ashby.html",
        "field": Field(key="9663c78d_37a2_4e78_bcb6_5b08c3c0c742", kind="text", label="Website/Portfolio"),
        "expected_value": "https://github.com/valarcon1226",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "ashby.html",
        "field": Field(key="524b6eed_b978_43d6_9a24_b97aab0f69b9", kind="text", label="How did you hear about this role?"),
        "expected_value": "LinkedIn",
        "expected_source": "bank",
        "expected_needs_human": False,
    },

    # iframe_form.html (Greenhouse embed)
    {
        "fixture": "iframe_form.html",
        "field": Field(key="first_name", kind="text", label="First Name"),
        "expected_value": "Valentina",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "iframe_form.html",
        "field": Field(key="last_name", kind="text", label="Last Name"),
        "expected_value": "Alarcon Gamboa",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "iframe_form.html",
        "field": Field(key="candidate_location", kind="combobox", label="Location (City)"),
        "expected_value": "Bogotá",
        "expected_source": "bank",
        "expected_needs_human": False,
    },
    {
        "fixture": "iframe_form.html",
        "field": Field(key="school_0", kind="combobox", label="School"),
        "expected_value": "Pontificia Universidad Javeriana",
        "expected_source": "profile",
        "expected_needs_human": False,
    },
    {
        "fixture": "iframe_form.html",
        "field": Field(key="gender", kind="combobox", label="Gender"),
        "expected_value": "Female",  # formulario en inglés sin opciones: se traduce
        "expected_source": "bank",
        "expected_needs_human": False,
    },
]

assert len(CASES_30) == 30, f"Esperaba 30 casos de prueba, obtuve {len(CASES_30)}"

for i, tc in enumerate(CASES_30, 1):
    f = tc["field"]
    ans = answer(f, job=JOB_FIXTURE)
    assert ans.value == tc["expected_value"], (
        f"Caso {i} ({tc['fixture']} / '{f.label}'): valor '{ans.value}' != '{tc['expected_value']}'"
    )
    assert ans.source == tc["expected_source"], (
        f"Caso {i} ({tc['fixture']} / '{f.label}'): fuente '{ans.source}' != '{tc['expected_source']}'"
    )
    assert ans.needs_human == tc["expected_needs_human"], (
        f"Caso {i} ({tc['fixture']} / '{f.label}'): needs_human {ans.needs_human} != {tc['expected_needs_human']}"
    )


# ---------------------------------------------------------------------------
# 2. Regla dura: salario.minimo_aceptable JAMÁS sale como respuesta
# ---------------------------------------------------------------------------
ans_min_label = answer(Field(key="sal_min", kind="text", label="Salario mínimo aceptable", required=True), job=JOB_FIXTURE)
assert ans_min_label.value != "1500 USD/mes", "minimo_aceptable no debe salir jamás"
assert ans_min_label.needs_human is True, "Debe requerir humano"

ans_min_key = answer(Field(key="salario_minimo_aceptable", kind="text", label="Minimum acceptable salary", required=True), job=JOB_FIXTURE)
assert ans_min_key.value != "1500 USD/mes", "minimo_aceptable no debe salir jamás por key"
assert ans_min_key.needs_human is True, "Debe requerir humano"


# ---------------------------------------------------------------------------
# 3. Regla dura: todo '???' -> needs_human = True
# ---------------------------------------------------------------------------
ans_qm = answer(
    Field(key="why_role", kind="text", label="Por qué te interesa este tipo de rol"),
    job=JOB_FIXTURE,
)
assert ans_qm.needs_human is True, "Las respuestas_modelo con '???' deben terminar en needs_human"
assert ans_qm.value is None or ans_qm.value != "???", "Nunca debe devolver la cadena '???'"

ans_achieve = answer(
    Field(key="achievement", kind="text", label="Tu mayor logro profesional"),
    job=JOB_FIXTURE,
)
assert ans_achieve.needs_human is True, "Logro con '???' debe requerir humano"
assert ans_achieve.value is None, "Valor debe ser None"


# ---------------------------------------------------------------------------
# 4. Regla dura: Perfil sin answers.yaml -> needs_human = True
# ---------------------------------------------------------------------------
ans_nobank = answer(
    Field(key="first_name", kind="text", label="First Name"),
    job=JOB_FIXTURE,
    answers_path="ruta_inexistente/answers.yaml",
)
assert ans_nobank.needs_human is True, "Sin answers.yaml debe retornar needs_human=True"
assert ans_nobank.value is None


# ---------------------------------------------------------------------------
# 5. Regla dura: 0 datos duros inventados (pregunta desconocida -> needs_human)
# ---------------------------------------------------------------------------
ans_invent = answer(
    Field(key="constellation", kind="text", label="What is your favorite astronomical constellation?"),
    job=JOB_FIXTURE,
    llm_classifier_fn=lambda f: "ninguna",
    llm_text_fn=lambda f, j, b, p: None,
)
assert ans_invent.needs_human is True, "Preguntas no registradas no deben inventarse"
assert ans_invent.value is None


# ---------------------------------------------------------------------------
# 6. learn(label, value) agrega a aprendidas: (copia temporal)
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    tmp_yaml = os.path.join(td, "answers.yaml")
    # Inicializar copia temporal sin sección aprendidas
    with open(tmp_yaml, "w", encoding="utf-8") as f:
        yaml.dump({"datos_personales": {"nombre_legal": "Valentina Alarcon"}}, f)

    learn("herramienta favorita de qa", "Playwright", answers_path=tmp_yaml)

    # Comprobar que quedó guardado en el archivo
    with open(tmp_yaml, "r", encoding="utf-8") as f:
        saved_data = yaml.safe_load(f)
    assert "aprendidas" in saved_data
    assert saved_data["aprendidas"].get("herramienta favorita de qa") == "Playwright"

    # Comprobar que answer() lo resuelve con source='learned'
    ans_learned = answer(
        Field(key="fav_tool", kind="text", label="Herramienta favorita de QA"),
        job=JOB_FIXTURE,
        answers_path=tmp_yaml,
    )
    assert ans_learned.value == "Playwright"
    assert ans_learned.source == "learned"
    assert ans_learned.needs_human is False

# Verificar que el answers.yaml real de Valentina NO fue alterado
real_answers_path = profile_paths.resolve("answers.yaml")
with open(real_answers_path, "r", encoding="utf-8") as f:
    real_content = f.read()
assert "herramienta favorita de qa" not in real_content, "El answers.yaml real no debe ser editado por pruebas"


# ---------------------------------------------------------------------------
# 7. Emparejamiento de opciones (select, radio, combobox)
# ---------------------------------------------------------------------------
# 7.1 Booleano positivo a opción 'Yes' / 'YES' / 'Sí'
opt_yes, ok_yes = match_option(True, ["No", "Yes"])
assert ok_yes and opt_yes == "Yes", f"Esperaba 'Yes', obtuve {opt_yes}"

opt_si, ok_si = match_option(True, ["No", "Sí"])
assert ok_si and opt_si == "Sí", f"Esperaba 'Sí', obtuve {opt_si}"

# 7.2 Booleano negativo a opción 'No' / 'NO'
opt_no, ok_no = match_option(False, ["YES", "NO"])
assert ok_no and opt_no == "NO", f"Esperaba 'NO', obtuve {opt_no}"

# 7.3 Texto exacto
opt_txt, ok_txt = match_option("Colombia", ["Argentina", "Colombia", "Chile"])
assert ok_txt and opt_txt == "Colombia", opt_txt

# 7.4 difflib contra opciones parecidas
opt_diff, ok_diff = match_option("Pregrado", ["Pregrado Universitario", "Postgrado", "Doctorado"])
assert ok_diff and opt_diff == "Pregrado Universitario", opt_diff

# 7.5 Sin coincidencia suficiente -> éxito es False
opt_fail, ok_fail = match_option("Python", ["Java", "Rust", "Go"])
assert not ok_fail and opt_fail is None


# ---------------------------------------------------------------------------
# 8. Sustitución de LLM por funciones fijas (clasificador y texto abierto)
# ---------------------------------------------------------------------------
# 8.1 Clasificador LLM redirige a clave cerrada del banco
def mock_classifier(field):
    if "aviso previo" in field.label.lower():
        return "disponibilidad.preaviso"
    return "ninguna"

ans_llm_c = answer(
    Field(key="notice", kind="text", label="¿Cuánto tiempo de aviso previo necesitas?"),
    job=JOB_FIXTURE,
    llm_classifier_fn=mock_classifier,
)
assert ans_llm_c.value == "1 semana", ans_llm_c
assert ans_llm_c.source == "bank"
assert ans_llm_c.needs_human is False

# 8.2 Redactor de texto abierto para preguntas libres
def mock_text_generator(field, job, bank, profile):
    return "Tengo más de 3 años de experiencia en QA Automation y desarrollo de agentes de IA."

ans_llm_t = answer(
    Field(key="why_join", kind="textarea", label="Why do you want to join us?"),
    job=JOB_FIXTURE,
    llm_classifier_fn=lambda f: "ninguna",
    llm_text_fn=mock_text_generator,
)
assert "más de 3 años" in ans_llm_t.value
assert ans_llm_t.source == "llm"
assert ans_llm_t.needs_human is False


# ---------------------------------------------------------------------------
# 9. Verificaciones de AP-2b:
# 9.1 Etiquetas reales de Greenhouse con palabras sueltas ('school', 'university', 'degree')
#     NO deben responder datos del perfil (master_profile.json) -> needs_human=True
# 9.2 Salario mensual en USD cuando banco está en EUR -> needs_human=True
# 9.3 Salario anual en USD hecho a mano -> '45000' (salario.expectativa_anual_usd)
# ---------------------------------------------------------------------------

# 9.1 Etiquetas reales copiadas de fixtures/forms/greenhouse.html
gh_profile_trap_fields = [
    Field(
        key="question_67587849",
        kind="combobox",
        label="How did you perform in mathematics at high school?",
    ),
    Field(
        key="question_67587850",
        kind="combobox",
        label="How did you perform in your native language at high school?",
    ),
    Field(
        key="question_67587851",
        kind="textarea",
        label=(
            "Please share your rationale or evidence for the high school performance selections above. "
            "Make reference to provincial, state or nation-wide scoring systems, rankings, or recognition "
            "awards, or to competitive or selective college entrance results such as SAT or ACT scores, "
            "JAMB, matriculation results, IB results etc. We recognise every system is different but we "
            "will ask you to justify your selections above."
        ),
    ),
    Field(
        key="question_67587852",
        kind="textarea",
        label=(
            "What was your bachelor's university degree result, or expected result if you have not yet graduated? "
            "Please include the grading system to help us understand your result e.g. ‘85 out of 100’, "
            "‘2:1 (Grading system: first class, 2:1, 2:2, third class)’ or ‘GPA score of 3.8/4.0 (predicted)’. "
            "We have hired outstanding individuals who did not attend or complete university. If this describes you, "
            "please continue with your application and enter ‘no degree’."
        ),
    ),
    Field(
        key="question_67587854",
        kind="combobox",
        label=(
            "In the past ten years, looking only at the time since you graduated your first undergraduate degree, "
            "how many companies have you worked for?"
        ),
    ),
]

for f_trap in gh_profile_trap_fields:
    res = answer(
        f_trap,
        job=JOB_FIXTURE,
        llm_classifier_fn=lambda *a, **k: None,
        llm_text_fn=lambda *a, **k: None,
    )
    assert res.needs_human is True, f"'{f_trap.label[:40]}' debe terminar en needs_human=True"
    assert res.value is None, f"'{f_trap.label[:40]}' no debe tener valor inventado ni del perfil, obtuvo: {res.value}"
    assert res.value != "Pontificia Universidad Javeriana"
    assert res.source != "profile", f"No debe responder desde master_profile por palabra suelta: {res.source}"

# 9.2 Salario mensual en USD: sale de la anual en USD / 12, con moneda y periodo (no del mensual en EUR)
f_sal_mes_usd = Field(key="ca_10933", kind="text", label="Desired Monthly Salary in USD")
ans_sal_mes = answer(f_sal_mes_usd, job=JOB_FIXTURE)
assert ans_sal_mes.value == "USD 3,750 per month", ans_sal_mes
assert ans_sal_mes.source == "bank"

# 9.3 Salario anual en USD hecho a mano -> '45000' (salario.expectativa_anual_usd)
f_sal_anual_1 = Field(key="annual_salary", kind="text", label="Desired Annual Salary in USD")
ans_sal_anual_1 = answer(f_sal_anual_1, job=JOB_FIXTURE)
assert ans_sal_anual_1.value == "USD 45,000 per year", f"Esperaba 'USD 45,000 per year', obtuvo {ans_sal_anual_1.value}"
assert ans_sal_anual_1.source == "bank"
assert ans_sal_anual_1.needs_human is False

f_sal_anual_2 = Field(key="annual_exp_usd", kind="text", label="Annual salary expectation in USD")
ans_sal_anual_2 = answer(f_sal_anual_2, job=JOB_FIXTURE)
assert ans_sal_anual_2.value == "USD 45,000 per year", f"Esperaba 'USD 45,000 per year', obtuvo {ans_sal_anual_2.value}"
assert ans_sal_anual_2.source == "bank"
assert ans_sal_anual_2.needs_human is False


# 10. Pedidos de Valentina 2026-10-16 (etiquetas reales de ashby/lever). LLM fijo: aquí se prueba el enrutamiento.
NO_LLM = dict(llm_classifier_fn=lambda *a, **k: None, llm_text_fn=lambda *a, **k: None)
# 10.1 Redes sociales en blanco (no needs_human); "X years of experience" NO es la red X
for lbl in ("X", "Twitter URL", "Instagram", "TikTok handle"):
    r = answer(Field(key="s", kind="text", label=lbl), job=JOB_FIXTURE, **NO_LLM)
    assert (r.value, r.source, r.needs_human) == ("", "skip", False), (lbl, r)
assert answer(Field(key="x", kind="text", label="X years of experience"), job=JOB_FIXTURE, **NO_LLM).source != "skip"
# 10.2 Link del CV en Drive para campos de texto; el input file sigue subiendo el PDF
drive = {**JOB_FIXTURE, "cv_link": "https://drive.google.com/open?id=abc"}
r = answer(Field(key="r", kind="text", label="Link to your resume"), job=drive, **NO_LLM)
assert r.value == "https://drive.google.com/open?id=abc" and not r.needs_human, r
assert answer(Field(key="r", kind="file", label="Resume"), job=drive, **NO_LLM).value == JOB_FIXTURE["cv_path"]
# 10.3 Carta de presentación: la guardada en la vacante; si no hay, la escribe el agente (source cover_letter)
r = answer(Field(key="c", kind="textarea", label="Cover letter"), job={**JOB_FIXTURE, "cover_letter": "Dear team, ..."}, **NO_LLM)
assert (r.value, r.source) == ("Dear team, ...", "cover_letter"), r
r = answer(Field(key="c", kind="textarea", label="Cover letter"), job=JOB_FIXTURE,
           llm_classifier_fn=lambda *a, **k: None, llm_text_fn=lambda *a, **k: "Dear Supermove team, I build agents...")
assert (r.source, r.needs_human) == ("cover_letter", False), r
# 10.4 "Location" a secas = ciudad + país; "Location (City)" = ciudad
assert answer(Field(key="l", kind="text", label="Location"), job=JOB_FIXTURE, **NO_LLM).value == "Bogotá, Colombia"
assert answer(Field(key="l", kind="text", label="Location (City)"), job=JOB_FIXTURE, **NO_LLM).value == "Bogotá"
# 10.5 El agente contesta campos con opciones (checkbox/radio), pero solo con una opción válida; NO_SE -> needs_human
yn = Field(key="q", kind="radio", label="Do you have professional experience designing for web?", options=["Yes", "No"])
assert answer(yn, job=JOB_FIXTURE, llm_classifier_fn=lambda *a, **k: None, llm_text_fn=lambda *a, **k: "No").value == "No"
assert answer(yn, job=JOB_FIXTURE, llm_classifier_fn=lambda *a, **k: None, llm_text_fn=lambda *a, **k: "Maybe").needs_human
ref = Field(key="q", kind="text", label="Has someone at Linear referred you for this role? If so, please share their name.")
assert answer(replace(ref, required=True), job=JOB_FIXTURE, llm_classifier_fn=lambda *a, **k: None, llm_text_fn=lambda *a, **k: "NO_SE").needs_human
assert answer(ref, job=JOB_FIXTURE, **NO_LLM).value == ""  # "If so, ..." opcional: en blanco

# ---------------------------------------------------------------------------
# 11. Errores vistos en formularios reales (Greenhouse/Lever de vacantes con CV)
# ---------------------------------------------------------------------------
_no_ai = dict(llm_classifier_fn=lambda *_: None, llm_text_fn=lambda *_: None)
_job_co = {**JOB_FIXTURE, "description": "Remote role for engineers based in Colombia.", "cover_letter": None}
def _a(label, kind="text", options=None, key="q", job=_job_co):
    return answer(Field(key=key, kind=kind, label=label, options=options), job=job, **_no_ai)

# salario: nunca la IA; COP sin dato en COP -> persona; número -> solo dígitos; sin moneda -> USD con periodo
assert _a("¿Cuál es tu aspiración salarial? (COP)").needs_human
assert _a("What is your gross monthly salary expectation (COP)?").needs_human
assert _a("What is your desired salary? Please include currency as well.").value == "USD 45,000 per year"
assert _a("Desired salary", kind="number").value == "45000"
assert _a("Is the salary range of 30k acceptable?").needs_human
# Greenhouse rotula "Attach" el CV y la carta: la carta no recibe el CV
assert _a("Attach", kind="file", key="cover_letter").value == ""  # opcional sin carta: en blanco
assert _a("Attach", kind="file", key="resume").value == JOB_FIXTURE.get("cv_path")
# booleano del banco en un desplegable sin opciones leíbles -> Yes/No
assert _a("Do you now or will you in the future require immigration sponsorship by the company?", kind="combobox").value == "No"
# inglés: sí/no y escala MCER
assert _a("Are you fluent in English?", kind="combobox").value == "Yes"
_cefr = ["Select...", "B2 (Upper Intermediate): Can interact", "C1 (Advanced): Can express ideas fluently", "C2 (Proficient)"]
assert _a("Please assess your English proficiency.", kind="select", options=_cefr).value == _cefr[2]
# firmas/consentimientos -> persona
assert _a("CERTIFICATION AND CONFIDENTIALITY: By initialing below, you hereby agree").needs_human
# autorización "en el país de la vacante": Colombia en la vacante -> Yes; sin país conocido -> persona
assert _a("Are you currently authorized to work for all employers in the country where this job is based?", kind="combobox").value == "Yes"
assert _a("Are you currently authorized to work for all employers in the country where this job is based?", kind="combobox",
          job={**_job_co, "description": "Hybrid role in Austin, Texas."}).needs_human
# "(optional)" no impide encontrar la clave; nombre preferido = legal
assert _a("GitHub (optional) URL").value == "https://github.com/valarcon1226"
assert _a("Is your preferred name the same as your legal name?", kind="checkbox", options=["Yes", "No"]).value == "Yes"

# oficina: lo decide la modalidad del banco ("Solo remoto" -> No), no la IA; "Custom" de pronombres sin marcar
assert answer(Field(key="q", kind="combobox", label="Are you willing to work in the office 5-days a week?"), job=_job_co,
              llm_classifier_fn=lambda *_: None, llm_text_fn=lambda *_: "Yes").value == "No"
assert _a("Custom", kind="checkbox", key="custompronounsoption").value == ""

# confirmaciones y compromisos en español también los decide la persona
for _q in ("Entiendo que esta posición es de forma remota desde cualquier lugar de LATAM.",
           "Estoy de acuerdo con que es una posición híbrida en la ciudad QUITO/ ECUADOR.",
           "En caso de no contar con certificaciones en la nube, estoy dispuesto a obtenerlas."):
    assert answer(Field(key="q", kind="radio", label=_q, options=["YES", "NO"]), job=_job_co,
                  llm_classifier_fn=lambda *_: None, llm_text_fn=lambda *_: "NO").needs_human, _q

# 12. Segunda ronda con IA real
def _ai(label, out, kind="text", options=None, required=True):
    return answer(Field(key="q", kind=kind, label=label, options=options, required=required), job=_job_co,
                  llm_classifier_fn=lambda *_: None, llm_text_fn=lambda *_: out)
# copiaba la instrucción del prompt en un desplegable sin opciones; y aceptar una política es consentimiento
assert _ai("Preferred start month", "write the answer", kind="combobox").needs_human
assert _ai("Please confirm that you have read and agree to Canonical's Recruitment Privacy Notice", "Yes",
           kind="combobox").needs_human
# notas/colegio: "no degree" y un puntaje del SABER inventado -> persona
assert _ai("What was your bachelor's university degree result?", "no degree", kind="textarea").needs_human
assert _ai("Please share your rationale or evidence for the high school performance selections above.",
           "I scored in the top 10% of the SABER exam.", kind="textarea").needs_human
# "Cumplo con la experiencia requerida": No -> persona, Yes se acepta
assert _ai("Cumplo con la experiencia requerida.", "NO", kind="radio", options=["YES", "NO"]).needs_human
assert _ai("Cumplo con la experiencia requerida.", "YES", kind="radio", options=["YES", "NO"]).value == "YES"
# seguimiento opcional en blanco; carta en archivo opcional sin carta -> en blanco, obligatoria -> persona
assert _ai('If you selected "No", please enter your preferred name.', "x", required=False).value == ""
assert answer(Field(key="cover_letter", kind="file", label="Attach", required=False), job=_job_co, **_no_ai).value == ""
assert answer(Field(key="cover_letter", kind="file", label="Attach", required=True), job=_job_co, **_no_ai).needs_human

# 13. Tercera ronda: 34 formularios reales (GitLab, Okta, Palantir, Notion, Ramp, Twilio, Linear...)
assert _a("Are you legally authorized to work in the country in which this role is located?", kind="combobox").value == "Yes"
assert _a("Are you legally authorized to work in the country you reside?", kind="select", options=["Choose", "Yes", "No"],
          job={**_job_co, "description": "Remote, United States"}).value == "Yes"
assert _a("Do you have 2+ years of experience in QA/Test Automation?", kind="combobox").value == "Yes"
assert _a("Do you have a minimum of 30 years of experience building software?", kind="checkbox").value == ""  # no cumple -> sin marcar
assert _a("Are you based in a US or equivalent timezone?", kind="checkbox").value == "Yes"  # UTC-5
assert _a("Notion Website", kind="checkbox").value == ""
assert _a("Notice Period", ).value in ("1 week", "2 weeks", "1 month") or _a("Notice Period").needs_human
assert _a("Voluntary Self-Identification of Gender", kind="combobox").value == "Female"
assert _a("x", kind="radio", key="5940e1ad__systemfield_eeoc_race",
          options=["Hispanic or Latino", "White", "Decline to self-identify"]).value != "Hispanic or Latino"
assert _a("Name Pronunciation | How do you pronounce your name?").value == ""
assert _a("Additional information", kind="textarea").value == ""
assert _ai("Do you have hands-on experience with Playwright or Selenium?", "Yes, I have used both.", kind="combobox").value == "Yes"
assert _ai("Have you notified your current manager that you are applying to this role?", "No", kind="combobox").needs_human
assert _ai("Do you have a 30-day notice to serve?", "1 week", kind="combobox").value == "No"  # preaviso 1 semana
assert _ai("Language Skill(s) (Check all that apply)", "English (ENG)", kind="checkbox",
           options=["English (ENG)", "Spanish (SPA)"]).needs_human

# 14. Cuarta ronda (regresiones y modelo local)
assert _a("Are you Hispanic/Latino?", kind="combobox").value
assert _a("In what country are you located?").value == "Colombia"
assert _a("Preferred Name | What would you like us to call you?").value == "Valentina"
assert _a("Please tell us how you heard about this opportunity.").value == "LinkedIn"
assert _a("d6bf2576-9239_b0a5aba8", kind="radio", key="d6bf_b0a5", options=["He/Him", "She/Her", "They/Them", "Prefer not to say"]).value == "She/Her"
assert _a("Resume", kind="radio", options=["Upload PDF", "Paste"]).value == "Upload PDF"
assert _a("Yes", kind="checkbox").needs_human
assert _ai("What has been your favorite project?", "We are filling a textarea field: the question...", kind="textarea").needs_human
assert _ai("Do you have experience with Kotlin?", "Do you have experience with Kotlin?\nField: checkbox\n\nYes", kind="combobox").needs_human  # openhermes repite el prompt
assert _ai("Here's some text encoded in a common format. Figure out the correct secret.", "abc", kind="textarea").needs_human

print("ok")

# --- 15. ronda 4: ciudad, discapacidad de Palantir, Resume/Cover en texto de Okta ---
_r4 = lambda lab, kind="text", opts=None, req=True: answer(
    Field(key="q", label=lab, kind=kind, options=opts or [], required=req), job=JOB_FIXTURE, **NO_LLM)
assert _r4("What city do you reside in?").value == "Bogotá"
assert _r4("What city and state do you reside in?").value == "Bogotá"
assert _r4("Disability status", "select", ["Select ...", "Yes, I have a disability, or have had one in the past",
           "No, I do not have a disability and have not had one in the past", "I do not want to answer"]).value == "I do not want to answer"
assert _r4("Resume/CV", "textarea", req=False).value == ""
assert _r4("Cover Letter", "radio", ["Upload PDF", "Paste"], req=False).value == ""
print("ok")

# --- 16. muestra: raya larga y texto que se descalifica solo ---
assert _ai("Why us?", "I built agents—like a QA agent—that test.", kind="textarea").value == "I built agents, like a QA agent, that test."
assert _ai("Describe your backend experience", "I have no experience designing backend services.", kind="textarea").needs_human
print("ok")

# --- 17. IA sobre las preguntas únicas: consentimientos, fecha, patrocinio ---
import datetime as _dt
assert _r4("As part of our interview process, we may use AI notetakers to transcribe conversations for accuracy",
           "radio", ["Yes, I consent", "No, I do not consent"]).needs_human
assert _r4("Please share my resume and contact information with external Palantir partners for job seeking purposes.",
           "radio", ["Yes", "No"]).needs_human
assert _r4("Acknowledge", "checkbox").value == "Yes"                    # aviso de privacidad (Twilio)
assert _r4("I acknowledge and agree to the processing of my personal data in accordance with Okta's privacy policy",
           "checkbox").value == "Yes"
assert _r4("I certify that the information above is true and complete", "checkbox").needs_human
assert _r4("Date").value == _dt.date.today().strftime("%m/%d/%Y")
assert _r4("Will you now or in the future require Notion to sponsor an immigration case in order to employ you?",
           "checkbox", req=False).source == "bank"
print("ok")

# --- 18. Preferencias del banco responden solas; un opcional sin dato nunca frena ---
_co = {**JOB_FIXTURE, "location": "Bogotá, Colombia"}
_us = {**JOB_FIXTURE, "location": "San Francisco, CA"}
_f = lambda lab, kind="combobox", opts=None, req=True, job=_co: answer_final(
    Field(key="q", label=lab, kind=kind, options=opts or [], required=req), job=job, **NO_LLM)
assert _f("Are you willing to work in the office 5-days a week?").value == "No"            # modalidad: Solo remoto
assert _f("Are you open to hybrid working, 3 days work from the office ?").value == "No"
assert _f("This role is expected to be on site Monday, Wednesday and Thursday. Are you able to commit to that schedule?",
          "select", ["Select...", "Yes", "No"]).value == "No"
assert _f("If you are not located in the city where this role is based, are you able to relocate?",
          "select", ["Select...", "Yes", "No"]).value == "No"                             # dispuesta_a_mudarse: false
assert _f("Do you have a 30-day notice to serve?").value == "No"                            # preaviso: 1 semana
assert _f("Are you based in a US or equivalent timezone?", "checkbox", req=False).value == "Yes"  # UTC-5
assert _f("Are you based in a EU or equivalent timezone?", "checkbox", req=False).value == ""
assert _f("Are you currently based in Bangalore, India?", "text").value == "No"
assert _f("Are you currently based in {location}?", job={**JOB_FIXTURE, "location": "Bengaluru, India"}).value == "No"  # plantilla rota: lugar de la vacante
assert _f("Are you currently based in {location}?", job={**JOB_FIXTURE, "location": ""}).needs_human
assert _f("Are you legally authorized to work in the country in which this role is located?", job=_us).value == "No"
assert _f("Are you legally authorized to work in the country in which this role is located?",
          job={**JOB_FIXTURE, "location": ""}).needs_human                                  # sin ubicación: decides tú
_src_opts = ["Citizen or permanent resident where this role is listed", "Valid visa with permission to work with any employer where this role is listed", "I do not currently have an unlimited right to work where this role is listed and will require sponsorship"]
assert "sponsorship" in _f("What is the source of your right to work where this role is listed?", opts=_src_opts, job={**JOB_FIXTURE, "location": "Remote - India"}).value
assert _f("What is the source of your right to work where this role is listed?", job={**JOB_FIXTURE, "location": "Remote - Mexico"}).value == "sponsorship"  # sin opciones
assert _f("What is the source of your right to work where this role is listed?", opts=_src_opts).value.startswith("Citizen")                         # vacante en Colombia
assert _f("Do you have a minimum of 7 years of experience building software?", "checkbox").value == ""  # 3.5 años
assert _f("GitLab Username", "text", req=False).value == ""                                  # opcional sin dato
assert _f("GitLab Username", "text").needs_human                                             # obligatorio sin dato
print("ok")
assert _f("It is important to us to create an accessible and inclusive interview experience. Please let us know if there "
          "are any accommodations we can make", "text").value == "No, thank you."
print("ok")

# IN-2: lo que la entrevista guarda (situación laboral, políticas, clearance, estilo) lo usa el aplicador sin preguntar
import answer_engine
import llm_chain
with tempfile.TemporaryDirectory() as td:
    _bank_path = os.path.join(td, "answers.yaml")
    yaml.safe_dump({
        "datos_personales": {"ciudad": "Bogota", "pais": "Colombia"},
        "preguntas_frecuentes": {"tiene_familiares_en_la_empresa": False},
        "situacion_laboral": {"jefe_sabe_que_busca": False, "acuerdos_no_competencia": False,
                              "negocios_externos": False, "nombre_jefe_actual": "no aplica"},
        "autorizacion_de_trabajo": {"tiene_security_clearance": False, "puede_obtener_security_clearance": False},
        "politicas": {"acepta_grabacion_ia": True, "acepta_compartir_cv_con_socios": False},
        "estilo_escritura": {"muestra": "Hola equipo, les cuento rapido: armé el bot en dos tardes.",
                             "tono": "directa y cercana", "evitar": "apasionada"},
    }, open(_bank_path, "w", encoding="utf-8"), allow_unicode=True)
    _yn = ["Yes", "No"]

    def _b(label, kind="radio", opts=_yn, **kw):
        return answer(Field(key="q", kind=kind, label=label, options=opts, required=True), job=JOB_FIXTURE,
                      answers_path=_bank_path, master_profile_path="no_existe.json", **NO_LLM, **kw)

    assert _b("Do you have any family or personal connection with current or former employees at PayJoy?").value == "No"
    assert _b("Have you notified your current manager that you are applying to this role?").value == "No"
    assert _b("Are you subject to any employment agreements and/or post-employment restrictions with your current employer?").value == "No"
    assert _b("Do you have any outside business activity(ies) (advisory, consulting, or board roles)?").value == "No"
    assert _b("Do you currently hold an active US security clearance?").value == "No"
    assert _b("Are you eligible to obtain the security clearance specified in the job description?").value == "No"
    assert _b("What is the name of your current manager?", kind="text", opts=None).value == "N/A"
    assert _b("Are you a resident of California?").value == "No"
    # consentimientos ya decididos en la entrevista; firmas e iniciales siguen siendo de la persona
    assert _b("As part of our interview process, we may use AI notetakers to transcribe conversations. Do you consent?").value == "Yes"
    assert _b("Please share my resume and contact information with external Palantir partners", kind="checkbox", opts=None).value == ""
    assert _b("Certification: by initialing below, you hereby agree that all information is true", kind="text", opts=None).needs_human

    # la carta y las respuestas abiertas reciben la muestra, el tono y lo que hay que evitar
    _seen = {}
    _orig = llm_chain.invoke_text
    llm_chain.invoke_text = lambda s, h, v, *a, **k: _seen.update(v) or "Dear Supermove team, I built the bot in two afternoons."
    try:
        answer(Field(key="cover_letter_text", kind="textarea", label="Cover letter (IN-2 style test)", required=True),
               job={**JOB_FIXTURE, "cover_letter": None}, answers_path=_bank_path, master_profile_path="no_existe.json",
               llm_classifier_fn=lambda *a, **k: None)
    finally:
        llm_chain.invoke_text = _orig
    assert "armé el bot en dos tardes" in _seen.get("style", "") and "directa y cercana" in _seen["style"], _seen.get("style")
    assert "apasionada" in _seen["style"] and "estilo_escritura" not in _seen["bank"] and "jefe" not in _seen["bank"]
print("ok - IN-2")
