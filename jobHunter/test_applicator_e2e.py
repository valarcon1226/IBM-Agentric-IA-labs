"""Prueba End-to-End del Agente Aplicador (AP-4 de APPLICATOR_PLAN.md).

Sirve fixtures/forms/ con python -m http.server, Edge headless REAL (sin mocks del navegador ni del lector)
llena el formulario hecho a mano (custom_form.html) y el de Greenhouse (greenhouse.html) con el banco de Valentina,
y se detiene antes de enviar en modo 'revisar'.
Verifica:
1. Valores escritos y verificados en cada campo.
2. Capturas de pantalla creadas en applications/<job_id>/paso-1.png.
3. Estado final de la vacante ('Lista para enviar').
4. Filas auditadas en application_answers en una copia temporal de jobs.db.
"""
import functools
import http.server
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 1. Asegurar perfil activo de Valentina
os.environ["JOBHUNTER_PROFILE"] = "Valentina Alarcon"

import profile_paths

# 2. Configurar base de datos temporal
temp_dir = tempfile.mkdtemp(prefix="jobhunter_ap4_test_")
temp_db_path = os.path.join(temp_dir, "jobs_test.db")
real_db = profile_paths.resolve("jobs.db")
if os.path.exists(real_db):
    shutil.copy2(real_db, temp_db_path)

os.environ["JOBHUNTER_DB_PATH"] = temp_db_path

import database
database.init_db()

import form_filler
import applicator_agent
from applicator_agent import apply_to_job
from database import get_application_answers, get_job_by_url

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "forms"
assert FIXTURES_DIR.is_dir(), f"No existe la carpeta de fixtures: {FIXTURES_DIR}"


# 3. Servidor HTTP local para servir fixtures
class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FIXTURES_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  # Silenciar logs HTTP


httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
port = httpd.server_address[1]
srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
srv_thread.start()

# Asegurar un PDF de prueba en CVs_Listos
cv_test_dir = profile_paths.resolve("CVs_Listos")
os.makedirs(cv_test_dir, exist_ok=True)
test_cv_path = os.path.join(cv_test_dir, "Valentina_Alarcon.pdf")
if not os.path.exists(test_cv_path):
    with open(test_cv_path, "wb") as f:
        # Minimal valid PDF header
        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF\n")

# Funciones mock para LLM en tests (rápidas y deterministas)
mock_llm_text = lambda f, j, b, p: f"Respuesta generada para: {f.label}"
mock_llm_classifier = lambda f: "ninguna"

try:
    # =======================================================================
    # TEST 1: Formulario Hecho a Mano (custom_form.html)
    # Radios en fieldset, combobox, campo obligatorio con *, textarea
    # =======================================================================
    custom_url = f"http://127.0.0.1:{port}/custom_form.html"
    job_1_id = 9101

    conn = sqlite3.connect(temp_db_path)
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_1_id,))
    conn.execute("DELETE FROM application_answers WHERE job_id = ?", (job_1_id,))
    conn.execute("""
        INSERT INTO jobs (id, url, title, company, status, apply_url, cv_path, match_percentage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_1_id, custom_url, "Full Stack Engineer", "Handcrafted Corp", "CV Generado", custom_url, test_cv_path, 90))
    conn.commit()
    conn.close()

    job1 = get_job_by_url(custom_url)
    assert job1 is not None, "No se encontró job1 en la base de datos temporal"

    # Ejecutar postulación en modo 'revisar'
    status_1 = apply_to_job(
        job1,
        mode="revisar",
        llm_classifier_fn=mock_llm_classifier,
        llm_text_fn=mock_llm_text,
    )

    # 1.1 Estado final debe ser 'Lista para enviar'
    assert status_1 == "Lista para enviar", f"Esperaba 'Lista para enviar', obtuve '{status_1}'"

    # 1.2 Verificar estado en DB
    job1_updated = get_job_by_url(custom_url)
    assert job1_updated["status"] == "Lista para enviar", f"Estado en DB incorrecto: {job1_updated['status']}"

    # 1.3 Verificar captura de pantalla
    shot1_path = Path(profile_paths.resolve("applications")) / str(job_1_id) / "paso-1.png"
    assert shot1_path.is_file(), f"No se generó la captura de pantalla: {shot1_path}"
    assert shot1_path.stat().st_size > 1000, f"Captura vacía o corrupta: {shot1_path.stat().st_size} bytes"

    # 1.4 Verificar filas en application_answers
    answers_1 = get_application_answers(job_1_id)
    assert len(answers_1) >= 4, f"Se esperaban al menos 4 respuestas auditadas, se encontraron {len(answers_1)}"

    ans_by_key_1 = {a["answer_key"]: a for a in answers_1}

    # applicant_name -> Valentina Alarcon Gamboa
    assert "applicant_name" in ans_by_key_1, "No se auditó applicant_name"
    assert "Valentina Alarcon" in ans_by_key_1["applicant_name"]["value"], ans_by_key_1["applicant_name"]
    assert ans_by_key_1["applicant_name"]["source"] == "bank"

    # applicant_email -> valarconeur@gmail.com
    assert "applicant_email" in ans_by_key_1, "No se auditó applicant_email"
    assert ans_by_key_1["applicant_email"]["value"] == "valarconeur@gmail.com"
    assert ans_by_key_1["applicant_email"]["source"] == "bank"

    # authorized_us -> No
    assert "authorized_us" in ans_by_key_1, "No se auditó authorized_us"
    assert ans_by_key_1["authorized_us"]["value"] == "No"
    assert ans_by_key_1["authorized_us"]["source"] == "bank"


    # =======================================================================
    # TEST 2: Formulario de Greenhouse (greenhouse.html)
    # Formulario complejo real con react-select, comboboxes, campos de texto y upload
    # =======================================================================
    greenhouse_url = f"http://127.0.0.1:{port}/greenhouse.html"
    job_2_id = 9102

    conn = sqlite3.connect(temp_db_path)
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_2_id,))
    conn.execute("DELETE FROM application_answers WHERE job_id = ?", (job_2_id,))
    conn.execute("""
        INSERT INTO jobs (id, url, title, company, status, apply_url, cv_path, match_percentage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_2_id, greenhouse_url, "QA Automation Analyst", "Canonical", "CV Generado", greenhouse_url, test_cv_path, 95))
    conn.commit()
    conn.close()

    job2 = get_job_by_url(greenhouse_url)
    assert job2 is not None, "No se encontró job2 en la base de datos temporal"

    # Ejecutar postulación en modo 'revisar'
    status_2 = apply_to_job(
        job2,
        mode="revisar",
        llm_classifier_fn=mock_llm_classifier,
        llm_text_fn=mock_llm_text,
    )

    # 2.1 Estado final debe ser 'Lista para enviar'
    assert status_2 == "Lista para enviar", f"Esperaba 'Lista para enviar', obtuve '{status_2}'"

    # 2.2 Verificar estado en DB
    job2_updated = get_job_by_url(greenhouse_url)
    assert job2_updated["status"] == "Lista para enviar", f"Estado en DB incorrecto: {job2_updated['status']}"

    # 2.3 Verificar captura de pantalla
    shot2_path = Path(profile_paths.resolve("applications")) / str(job_2_id) / "paso-1.png"
    assert shot2_path.is_file(), f"No se generó la captura de pantalla: {shot2_path}"
    assert shot2_path.stat().st_size > 1000, f"Captura vacía o corrupta: {shot2_path.stat().st_size} bytes"

    # 2.4 Verificar filas en application_answers
    answers_2 = get_application_answers(job_2_id)
    assert len(answers_2) >= 15, f"Se esperaban al menos 15 respuestas auditadas en Greenhouse, se encontraron {len(answers_2)}"

    ans_by_key_2 = {a["answer_key"]: a for a in answers_2}

    # First Name -> Valentina
    assert "first_name" in ans_by_key_2, f"No se auditó first_name: {list(ans_by_key_2.keys())}"
    assert ans_by_key_2["first_name"]["value"] == "Valentina"
    assert ans_by_key_2["first_name"]["source"] == "bank"

    # Last Name -> Alarcon Gamboa
    assert "last_name" in ans_by_key_2, "No se auditó last_name"
    assert ans_by_key_2["last_name"]["value"] == "Alarcon Gamboa"
    assert ans_by_key_2["last_name"]["source"] == "bank"

    # Email -> valarconeur@gmail.com
    assert "email" in ans_by_key_2, "No se auditó email"
    assert ans_by_key_2["email"]["value"] == "valarconeur@gmail.com"
    assert ans_by_key_2["email"]["source"] == "bank"

    # Country -> Colombia
    assert "country" in ans_by_key_2, "No se auditó country"
    assert ans_by_key_2["country"]["value"] == "Colombia"
    assert ans_by_key_2["country"]["source"] == "bank"

    print("ok")

finally:
    httpd.shutdown()
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
