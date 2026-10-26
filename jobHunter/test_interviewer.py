"""Pruebas del Agente Entrevistador (IN-1).

Se corre con: py test_interviewer.py
Imprime 'ok' si todas las aserciones pasan.

Verificaciones:
1. find_gaps con perfil+banco falsos devuelve las claves esperadas.
2. merge_bank no pisa valores y descarta claves desconocidas.
3. Una entrevista de 1 ronda con input simulado escribe answers.yaml,
   master_profile.json y gaps_pendientes.json correctos sin tocar Profiles/Valentina Alarcon.
4. El estilo de escritura entra al banco y la tabla de --campos marca qué falta.
"""
import builtins
import json
import os
import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import profile_paths
import llm_chain
from interviewer_agent import (
    CHECKLIST,
    MasterProfile,
    PersonalInfo,
    Story,
    find_gaps,
    merge_bank,
    extract_facts,
    run_interview,
    print_fields,
    _update_profile_field,
)


def test_find_gaps():
    """1. find_gaps con perfil+banco falsos devuelve las claves esperadas."""
    fake_profile = MasterProfile(
        personal_info=PersonalInfo(
            full_name="Candidata Test",
            email="test@example.com",
            number="+57 300 000 0000",
            location="",  # GAP esperado
            linkedin_url="https://linkedin.com/in/test",
            github_url="https://github.com/test",
        ),
        target_roles="QA Automation Engineer",
        professional_summary="Resumen profesional amplio",
        seniority_context="",  # GAP esperado
        salary_expectation="USD 3,000/mes",
        work_model="Solo remoto",
        target_companies=["Supermove"],
        deal_breakers=[],  # GAP esperado
        writer_instructions="Directo y profesional",
        stories=[
            Story(tema="como_usa_la_ia", texto="Uso herramientas como Antigravity a diario"),
            Story(tema="proyecto_favorito", texto="???"),  # GAP esperado (es '???')
            # Faltan: en_que_es_excelente, por_que_busca_cambio, experiencia_backend_liderazgo
        ],
    )

    fake_bank = {
        "salario": {
            "expectativa_anual_usd": "45000",
            "expectativa_mensual_cop": "???",  # GAP esperado
        },
        "situacion_laboral": {
            "empleada_actualmente": True,
            "jefe_sabe_que_busca": "???",  # GAP esperado
            "acuerdos_no_competencia": False,
            "negocios_externos": False,
            "empresas_donde_trabajo": ["Empresa A"],
        },
        "autorizacion_de_trabajo": {
            "ciudadanias": ["Colombiana"],
            "paises_con_permiso": ["Colombia"],
            # necesita_patrocinio_de_visa ausente -> GAP esperado
        },
        "disponibilidad": {
            "preaviso": "2 semanas",
            "dias_oficina_maximo": 0,
            "ciudades_para_mudarse": [],  # GAP esperado
            "puede_viajar": "no",
        },
        "datos_personales": {
            "github": "https://github.com/test",
            "gitlab": "",  # GAP esperado
        },
        "idiomas": {
            "ingles": "C1",
            "espanol": "Nativo",
        },
        "preguntas_frecuentes": {
            "tiene_familiares_en_la_empresa": False,
        },
        "politicas": {
            "acepta_avisos_privacidad": True,
            "acepta_grabacion_ia": True,
            "acepta_contacto_futuro": True,
            "acepta_compartir_cv_con_socios": True,
        },
        "respuestas_modelo": {
            "por_que_te_interesa_este_tipo_de_rol": "Me apasiona el testing",
            "tu_mayor_logro_profesional": "Reduje tiempos 60%",
            "por_que_buscas_cambio": "???",  # GAP esperado
            "cuentame_de_ti_en_3_lineas": "Ingeniera con foco en calidad",
            "que_te_diferencia": "???",  # GAP esperado
        },
    }

    gaps = find_gaps(fake_profile, fake_bank)
    gap_keys = {g["clave"] for g in gaps}

    # Verificar que las claves esperadas están presentes en los gaps
    expected_missing = [
        "personal_info.location",
        "seniority_context",
        "deal_breakers",
        "stories.proyecto_favorito",
        "stories.en_que_es_excelente",
        "stories.por_que_busca_cambio",
        "stories.experiencia_backend_liderazgo",
        "salario.expectativa_mensual_cop",
        "situacion_laboral.jefe_sabe_que_busca",
        "autorizacion_de_trabajo.necesita_patrocinio_de_visa",
        "disponibilidad.ciudades_para_mudarse",
        "datos_personales.gitlab",
        "respuestas_modelo.por_que_buscas_cambio",
        "respuestas_modelo.que_te_diferencia",
    ]
    for key in expected_missing:
        assert key in gap_keys, f"Se esperaba que '{key}' fuera detectado como gap, pero no está."

    # Verificar que los campos llenos NO están en los gaps
    expected_present = [
        "personal_info.email",
        "personal_info.number",
        "target_roles",
        "professional_summary",
        "salary_expectation",
        "work_model",
        "target_companies",
        "writer_instructions",
        "stories.como_usa_la_ia",
        "salario.expectativa_anual_usd",
        "situacion_laboral.empleada_actualmente",
        "situacion_laboral.acuerdos_no_competencia",
        "disponibilidad.preaviso",
        "disponibilidad.dias_oficina_maximo",
        "datos_personales.github",
        "idiomas.ingles",
        "idiomas.espanol",
        "preguntas_frecuentes.tiene_familiares_en_la_empresa",
        "politicas.acepta_avisos_privacidad",
        "respuestas_modelo.por_que_te_interesa_este_tipo_de_rol",
        "respuestas_modelo.tu_mayor_logro_profesional",
    ]
    for key in expected_present:
        assert key not in gap_keys, f"'{key}' está lleno, pero fue erróneamente marcado como gap."

    # Verificar formato de cada gap
    for g in gaps:
        assert "tema" in g and isinstance(g["tema"], str)
        assert "archivo" in g and g["archivo"] in ("profile", "bank")
        assert "clave" in g and isinstance(g["clave"], str)
        assert "para" in g and isinstance(g["para"], list)
        assert "pista" in g and isinstance(g["pista"], str)


def test_merge_bank():
    """2. merge_bank no pisa valores y descarta claves desconocidas."""
    bank = {
        "salario": {
            "expectativa_anual_usd": "45000",
            "expectativa_mensual_cop": "???",
        },
        "situacion_laboral": {
            "empleada_actualmente": True,
        },
        "politicas": {
            "acepta_avisos_privacidad": "",
        },
    }

    facts = {
        # Claves conocidas que NO deben sobreescribir valores existentes
        "salario.expectativa_anual_usd": "99999",
        "situacion_laboral.empleada_actualmente": False,
        # Claves conocidas que SÍ deben escribirse (estaban en '???' o vacías o ausentes)
        "salario.expectativa_mensual_cop": "15000000 COP",
        "situacion_laboral.jefe_sabe_que_busca": False,
        "politicas.acepta_avisos_privacidad": True,
        # Claves desconocidas que DEBEN ser descartadas
        "clave_inventada_desconocida": "valor_invalido",
        "otra_seccion.campo_no_existente": 12345,
    }

    res = merge_bank(bank, facts)

    # Verificaciones de no-sobreescritura
    assert res["salario"]["expectativa_anual_usd"] == "45000", "merge_bank no debe sobreescribir valores existentes."
    assert res["situacion_laboral"]["empleada_actualmente"] is True, "merge_bank no debe sobreescribir booleano existente."

    # Verificaciones de escritura en campos vacíos / ??? / ausentes
    assert res["salario"]["expectativa_mensual_cop"] == "15000000 COP", "merge_bank debe reemplazar '???'."
    assert res["situacion_laboral"]["jefe_sabe_que_busca"] is False, "merge_bank debe escribir campos ausentes."
    assert res["politicas"]["acepta_avisos_privacidad"] is True, "merge_bank debe escribir campos con string vacío."

    # Verificaciones de descarte de claves desconocidas
    assert "clave_inventada_desconocida" not in res, "merge_bank debe descartar claves desconocidas."
    assert "otra_seccion" not in res, "merge_bank debe descartar secciones desconocidas."


def test_1_round_interview():
    """3. Una entrevista de 1 ronda con input simulado escribe answers.yaml,
    master_profile.json y gaps_pendientes.json correctos."""
    with tempfile.TemporaryDirectory() as td:
        # Asegurar que profile_paths resuelva exclusivamente a esta carpeta temporal
        os.environ["JOBHUNTER_PROFILE"] = td
        os.environ["INTERVIEW_MAX_ROUNDS"] = "1"

        # Archivo cv.txt de prueba en el directorio temporal
        cv_path = os.path.join(td, "cv.txt")
        with open(cv_path, "w", encoding="utf-8") as f:
            f.write("Valentina Alarcon. QA Automation & AI Engineer. Experiencia con Playwright y Python.")

        # Archivo info adicional opcional
        info_dir = os.path.join(td, "info_adicional")
        os.makedirs(info_dir, exist_ok=True)
        with open(os.path.join(info_dir, "contexto.md"), "w", encoding="utf-8") as f:
            f.write("Información adicional sobre proyectos de inteligencia artificial.")

        # answers.yaml inicial con un campo en ???
        answers_path = os.path.join(td, "answers.yaml")
        initial_bank = {
            "datos_personales": {
                "nombre_legal": "Valentina Alarcon Gamboa",
            },
            "salario": {
                "expectativa_mensual_cop": "???",
            },
        }
        with open(answers_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(initial_bank, f)

        # Mocks para llm_chain
        mock_profile = MasterProfile(
            personal_info=PersonalInfo(
                full_name="Valentina Alarcon Gamboa",
                email="ana@example.com",
                number="+57 300 000 0000",
                location="Bogotá, Colombia",
                linkedin_url="https://linkedin.com/in/valentinaalarcon",
                github_url="https://github.com/valarcon1226",
            ),
            target_roles="AI Full Stack Engineer",
            professional_summary="Ingeniera especializada en automatización y agentes.",
            seniority_context="Mid QA (3.5 años)",
            salary_expectation="USD 3,500/mes",
            work_model="Solo remoto",
            target_companies=["Supermove"],
            deal_breakers=["No overtime"],
            writer_instructions="Tono directo y técnico",
            stories=[],
        )

        def mock_invoke_structured(*args, **kwargs):
            return mock_profile

        def mock_invoke_text(system_prompt="", human_template="", variables=None, **kwargs):
            sys_p = system_prompt.lower()
            # el extractor primero: su prompt lista todos los huecos, incluido soft_skills
            if "extractor" in sys_p:
                assert "soft skills" in sys_p and "salario.expectativa_mensual_cop" in sys_p  # todos, no solo el tema
                return json.dumps({
                    "salario.expectativa_mensual_cop": "15.000.000 COP",
                    "stories.como_usa_la_ia": "Construyo agentes de prueba con Playwright y LLMs diariamente.",
                    "clave_desconocida_que_debe_descartarse": "invalido",
                })
            if "soft skills" in sys_p:
                return "Pensamiento Analítico, Comunicación, Resiliencia"
            # Generador de preguntas
            return "¿Cuál es tu expectativa salarial en COP y cómo aplicas la IA en tu trabajo?"

        # Simulación de entradas del usuario:
        # 1. Contexto inicial: "" (Enter vacío)
        # 2. Respuesta a la ronda 1: texto con datos, luego Enter vacío
        # 3. Ronda 2 (si llegase a pedir): 'salir'
        user_inputs = iter([
            "",  # Contexto inicial omitido
            "Mi expectativa mensual es 15 millones de pesos COP y uso agentes de prueba a diario. No quiero salir de Bogotá.",  # "salir" dentro de una frase no termina
            "",  # Envío de respuesta
            "salir",
            "",
        ])

        def mock_input(prompt=""):
            try:
                return next(user_inputs)
            except StopIteration:
                return "salir"

        with patch("llm_chain.invoke_structured", side_effect=mock_invoke_structured), \
             patch("llm_chain.invoke_text", side_effect=mock_invoke_text), \
             patch("builtins.input", side_effect=mock_input):
            run_interview()

        # 1. Comprobar que master_profile.json se escribió y tiene datos correctos
        master_profile_path = os.path.join(td, "master_profile.json")
        assert os.path.exists(master_profile_path), "master_profile.json debe haber sido creado."
        with open(master_profile_path, "r", encoding="utf-8") as f:
            saved_profile = json.load(f)
        assert saved_profile["target_roles"] == "AI Full Stack Engineer"
        assert len(saved_profile["stories"]) >= 1
        assert saved_profile["stories"][0]["tema"] == "como_usa_la_ia"
        assert "Playwright" in saved_profile["stories"][0]["texto"]
        assert "Pensamiento Analítico" in saved_profile["soft_skills"]
        # lo contestado queda registrado: la próxima entrevista no lo repite
        with open(os.path.join(td, "entrevista_respondidas.json"), encoding="utf-8") as f:
            assert "salario.expectativa_mensual_cop" in json.load(f)

        # Comprobar copia en perfiles_de_prueba
        test_dir = os.path.join(td, "perfiles_de_prueba")
        assert os.path.isdir(test_dir)
        backups = os.listdir(test_dir)
        assert len(backups) >= 1, "Debe existir al menos una copia de respaldo con timestamp."

        # 2. Comprobar que answers.yaml se escribió correctamente y mergeó los datos
        assert os.path.exists(answers_path), "answers.yaml debe existir."
        with open(answers_path, "r", encoding="utf-8") as f:
            saved_bank = yaml.safe_load(f)
        assert saved_bank["datos_personales"]["nombre_legal"] == "Valentina Alarcon Gamboa", "No debió perder el nombre previo."
        assert saved_bank["salario"]["expectativa_mensual_cop"] == "15.000.000 COP", "Debió escribir la expectativa en COP."
        assert "clave_desconocida_que_debe_descartarse" not in saved_bank

        # 3. Comprobar que gaps_pendientes.json se escribió con los campos restantes
        gaps_path = os.path.join(td, "gaps_pendientes.json")
        assert os.path.exists(gaps_path), "gaps_pendientes.json debe haber sido creado."
        with open(gaps_path, "r", encoding="utf-8") as f:
            saved_gaps = json.load(f)
        assert isinstance(saved_gaps, list)
        assert len(saved_gaps) > 0, "Deben quedar gaps pendientes."

        pending_keys = {item["clave"] for item in saved_gaps}
        assert "salario.expectativa_mensual_cop" not in pending_keys, "La clave respondida no debe estar en gaps pendientes."
        assert "stories.como_usa_la_ia" not in pending_keys, "La historia respondida no debe estar en gaps pendientes."

        for item in saved_gaps:
            assert "tema" in item
            assert "clave" in item
            assert "para" in item

        # 4. Verificar que Profiles/Valentina Alarcon NO fue tocado
        val_profile_dir = Path(__file__).resolve().parent / "Profiles" / "Valentina Alarcon"
        if val_profile_dir.exists():
            val_answers = val_profile_dir / "answers.yaml"
            with open(val_answers, "r", encoding="utf-8") as f:
                val_content = f.read()
            assert "15.000.000 COP" not in val_content, "Profiles/Valentina Alarcon NUNCA debe ser modificado por los tests."


def test_estilo_y_campos():
    """4. La personalidad y el estilo van en el perfil (master_profile.json), el estilo viejo del banco se migra al
    entrevistar, y --campos muestra qué falta, sin LLM."""
    import contextlib
    import io
    claves = {g["clave"] for g in find_gaps(MasterProfile(), {})}
    assert {"personalidad.muestra_escritura", "personalidad.tono", "personalidad.fortalezas"} <= claves, claves
    assert not any(c.startswith("estilo_escritura.") for c in claves)
    prof = MasterProfile()
    _update_profile_field(prof, "personalidad.evitar", ["apasionada", "sinergia"])
    assert prof.personalidad.evitar == "apasionada, sinergia"
    _update_profile_field(prof, "personalidad.evitar", "otra")  # no pisa lo que ya hay
    assert prof.personalidad.evitar == "apasionada, sinergia"
    assert "personalidad.evitar" not in {g["clave"] for g in find_gaps(prof, {})}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        print_fields(prof.model_dump(), {})
    row = next(l for l in out.getvalue().splitlines() if "personalidad.evitar" in l)
    assert row.rstrip().endswith("sí") and "responder,cv" in row, row


def test_schema_gaps():
    """5. La entrevista pregunta todo campo vacío del esquema del perfil y todo hueco ??? del banco, y guarda lo
    contestado en su sitio (incluso dentro de una experiencia)."""
    from interviewer_agent import Experience, schema_gaps
    prof = MasterProfile(experience=[Experience(company_name="Acme", current_role="QA", time_period_worked="",
                                                achievements=[])])
    claves = {g["clave"]: g for g in find_gaps(prof, {"eeo": {"genero": "???"}, "idiomas": {"aleman": "???"}})}
    for c in ("experience.0.time_period_worked", "experience.0.achievements", "certifications", "education",
              "eeo.genero", "idiomas.aleman"):
        assert c in claves, c
    assert "Acme" in claves["experience.0.achievements"]["pista"]
    assert "soft_skills" in claves and "experience.0.company_name" not in claves  # blandas también se preguntan
    _update_profile_field(prof, "experience.0.achievements", "Bajé los bugs en producción 40%")
    _update_profile_field(prof, "experience.0.time_period_worked", "2021 - 2023")
    _update_profile_field(prof, "certifications", "ISTQB")  # lista de objetos: queda para el re-armado del LLM
    assert prof.experience[0].achievements == ["Bajé los bugs en producción 40%"] and prof.certifications == []
    assert not any(g["clave"].startswith("experience.0.") for g in schema_gaps(prof))
    assert merge_bank({"eeo": {"genero": "???"}}, {"eeo.genero": "Mujer", "eeo.x": "y"}) == {"eeo": {"genero": "Mujer"}}


def test_plan_questions():
    """6. Antes de preguntar, el modelo decide por campo: preguntar, deducir del perfil u omitir. Claves que no
    estaban pendientes o deducciones vacías se descartan (esas se preguntan); si el LLM falla, se pregunta todo."""
    from interviewer_agent import plan_questions
    gaps = [{"clave": c, "pista": c} for c in (
        "datos_personales.gitlab", "idiomas.ingles", "salario.expectativa_mensual_cop", "personalidad.tono")]
    bank = {"datos_personales": {"github": "https://github.com/ana"}, "nivel_ingles": "C1"}
    raw = json.dumps({
        "datos_personales.gitlab": {"accion": "omitir", "motivo": "solo usa GitHub",
                                    "evidencia": '"github": "https://github.com/ana"'},
        "idiomas.ingles": {"accion": "deducir", "valor": "C1", "evidencia": "\"nivel_ingles\": \"C1\""},
        "personalidad.tono": {"accion": "deducir", "valor": "", "evidencia": "C1"},  # sin valor -> se pregunta
        # "falta el dato" sin cita literal (lo que hizo un modelo real): se pregunta, no se omite
        "salario.expectativa_mensual_cop": {"accion": "omitir", "motivo": "no hay salario", "evidencia": "salario: ???"},
        "clave.inventada": {"accion": "deducir", "valor": "x", "evidencia": "C1"},
    })
    with patch.object(llm_chain, "invoke_text", return_value="```json\n" + raw + "\n```"):
        deducidos, omitidos = plan_questions(MasterProfile(), bank, gaps)
    assert deducidos == {"idiomas.ingles": "C1"}, deducidos
    assert omitidos == {"datos_personales.gitlab": "solo usa GitHub"}, omitidos
    with patch.object(llm_chain, "invoke_text", side_effect=llm_chain.AllProvidersExhausted("sin cupo")):
        assert plan_questions(MasterProfile(), {}, gaps) == ({}, {})


if __name__ == "__main__":
    print("Corriendo pruebas de interviewer_agent...")
    test_find_gaps()
    print("ok - find_gaps")
    test_merge_bank()
    print("ok - merge_bank")
    test_1_round_interview()
    print("ok - 1_round_interview")
    test_estilo_y_campos()
    print("ok - estilo_y_campos")
    test_schema_gaps()
    print("ok - schema_gaps")
    test_plan_questions()
    print("ok - plan_questions")
    print("ok")
