"""Pruebas unitarias de mail_triage y mail_reader (Fases 1-3 de FOLLOWUP_PLAN.md).

Se corre con: py test_mail_triage.py
Sin red ni IMAP. Imprime 'ok' si todas las aserciones pasan.
"""
import glob
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import database
import mail_reader
import mail_triage

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "mail"


# ===========================================================================
# 1. PRUEBAS DE CLASIFICACION (25 correos .eml anonimizados)
# ===========================================================================

def test_classification():
    eml_files = sorted(glob.glob(str(FIXTURES_DIR / "*.eml")))
    assert len(eml_files) >= 25, f"Se esperaban al menos 25 fixtures .eml, encontrados {len(eml_files)}"

    correct = 0
    total = len(eml_files)
    missed_interviews = 0
    category_counts = {}

    for path in eml_files:
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            raw_bytes = f.read()

        parsed = mail_reader.parse_email_message(raw_bytes)
        cat, facts = mail_triage.classify_email(parsed, allow_llm=False)

        # Determinar categoría esperada por prefijo de archivo
        expected = None
        for prefix in ("confirmacion", "rechazo", "entrevista", "prueba", "pide_info", "recruiter", "alerta", "otro"):
            if filename.startswith(prefix):
                expected = "prueba_tecnica" if prefix == "prueba" else ("recruiter_nuevo" if prefix == "recruiter" else ("alerta_vacantes" if prefix == "alerta" else prefix))
                break

        assert expected is not None, f"No se pudo determinar categoria esperada para {filename}"
        category_counts[expected] = category_counts.get(expected, 0) + 1

        if cat == expected:
            correct += 1
        else:
            print(f"   [FALLO CLASIFICACION] {filename}: esperado '{expected}', obtenido '{cat}'")

        if expected == "entrevista" and cat != "entrevista":
            missed_interviews += 1
            print(f"   [ALERTA CRITICA] Entrevista perdida en archivo: {filename}")

    accuracy = correct / total
    print(f"Precision de clasificacion: {correct}/{total} ({accuracy:.1%})")

    # Requisitos: >=90% bien clasificados y 0 entrevistas perdidas
    assert accuracy >= 0.90, f"Precision insuficiente: {accuracy:.1%} < 90%"
    assert missed_interviews == 0, f"Error critico: se perdieron {missed_interviews} entrevistas!"
    assert len(category_counts) >= 8, f"Deben existir fixtures para las 8 categorias: {category_counts}"
    for cat_name, cnt in category_counts.items():
        assert cnt >= 3 or (cat_name == "alerta_vacantes" and cnt >= 4), f"Categoria {cat_name} tiene menos de 3 fixtures ({cnt})"


# ===========================================================================
# 2. PRUEBAS DE EMPAREJAMIENTO (SECCION 4 DE FOLLOWUP_PLAN)
# ===========================================================================

def test_matching():
    candidate_jobs = [
        {
            "id": 101,
            "company": "Acme Corp",
            "title": "Senior QA Engineer",
            "apply_url": "https://boards.greenhouse.io/acmeproducts/jobs/101",
            "ats": "greenhouse",
            "applied_at": "2026-10-01 10:00:00",
        },
        {
            "id": 102,
            "company": "Globex",
            "title": "Frontend Developer",
            "apply_url": "https://globex.com/careers/frontend",
            "ats": "generico",
            "applied_at": "2026-10-05 11:00:00",
        },
        {
            "id": 103,
            "company": "Stark Industries",
            "title": "Python Backend Engineer",
            "apply_url": "https://jobs.lever.co/stark/103",
            "ats": "lever",
            "applied_at": "2026-10-10 12:00:00",
        },
        {
            "id": 104,
            "company": "MercadoLibre",
            "title": "Tech Lead",
            "apply_url": "https://mercadolibre.com/jobs/104",
            "ats": "generico",
            "applied_at": "2026-10-12 14:00:00",
        },
        # Caso de ambigüedad: misma empresa, dos vacantes distintas
        {
            "id": 105,
            "company": "Doppelganger LLC",
            "title": "Site Reliability Engineer",
            "apply_url": "https://doppel.com/jobs/sre",
            "ats": "generico",
            "applied_at": "2026-10-15 09:00:00",
        },
        {
            "id": 106,
            "company": "Doppelganger LLC",
            "title": "Data Platform Engineer",
            "apply_url": "https://doppel.com/jobs/data",
            "ats": "generico",
            "applied_at": "2026-10-15 09:00:00",
        },
    ]

    # Regla 1: Dominio de remitente = dominio de apply_url / empresa
    email_globex = {
        "sender": "David Miller <dmiller@globex.com>",
        "sender_domain": "globex.com",
        "reply_to": "",
        "reply_to_domain": "",
        "subject": "Interview schedule update",
        "body_text": "Let us connect next week.",
    }
    match_1 = mail_triage.match_email_to_job(email_globex, candidate_jobs)
    assert match_1 == 102, f"Esperado 102 (Globex por dominio), obtenido {match_1}"

    # Regla 2: Remitente de ATS conocido + empresa en asunto/cuerpo
    email_greenhouse = {
        "sender": "Acme Talent <no-reply@greenhouse-mail.io>",
        "sender_domain": "greenhouse-mail.io",
        "reply_to": "",
        "reply_to_domain": "",
        "subject": "Thank you for applying to Acme Corp",
        "body_text": "We received your application for Acme Corp.",
    }
    match_2 = mail_triage.match_email_to_job(email_greenhouse, candidate_jobs)
    assert match_2 == 101, f"Esperado 101 (Acme Corp por ATS), obtenido {match_2}"

    # Regla 3: Nombre de la empresa en asunto
    email_meli = {
        "sender": "Seleccion <talento@external-hr.com>",
        "sender_domain": "external-hr.com",
        "reply_to": "",
        "reply_to_domain": "",
        "subject": "Tu postulación en MercadoLibre",
        "body_text": "Queremos actualizarte sobre el proceso.",
    }
    match_3 = mail_triage.match_email_to_job(email_meli, candidate_jobs)
    assert match_3 == 104, f"Esperado 104 (MercadoLibre en asunto), obtenido {match_3}"

    # Regla 4: Varias candidatas (empresa con 2 vacantes y asunto genérico) -> None ('Sin emparejar')
    email_ambiguo = {
        "sender": "HR <recruiting@doppel.com>",
        "sender_domain": "doppel.com",
        "reply_to": "",
        "reply_to_domain": "",
        "subject": "Update on your application",
        "body_text": "Thank you for interviewing with Doppelganger LLC.",
    }
    match_4 = mail_triage.match_email_to_job(email_ambiguo, candidate_jobs)
    assert match_4 is None, f"Esperado None (Sin emparejar por ambigüedad), obtenido {match_4}"

    # Regla 4: Empresa desconocida -> None
    email_desconocido = {
        "sender": "Hiring <jobs@desconocido.xyz>",
        "sender_domain": "desconocido.xyz",
        "reply_to": "",
        "reply_to_domain": "",
        "subject": "Your application",
        "body_text": "No match here.",
    }
    match_5 = mail_triage.match_email_to_job(email_desconocido, candidate_jobs)
    assert match_5 is None, f"Esperado None para empresa desconocida, obtenido {match_5}"


# ===========================================================================
# 3. PRUEBAS DE EXTRACCION DE ALERTAS (Jobright y Welcome to the Jungle)
# ===========================================================================

def test_alert_extraction():
    # Jobright 1
    jr_path_1 = FIXTURES_DIR / "alerta_jobright_1.eml"
    with open(jr_path_1, "rb") as f:
        parsed_jr1 = mail_reader.parse_email_message(f.read())
    jobs_jr1 = mail_triage.extract_alert_jobs_from_email(parsed_jr1)
    assert len(jobs_jr1) == 2, f"Esperadas 2 vacantes en alerta_jobright_1, obtenidas {len(jobs_jr1)}"
    assert jobs_jr1[0]["title"] == "Senior QA Automation Engineer"
    assert jobs_jr1[0]["company"] == "CloudScale"
    assert jobs_jr1[0]["url"] == "https://jobright.ai/jobs/info/cs-101"
    assert jobs_jr1[1]["title"] == "Python Backend Developer"
    assert jobs_jr1[1]["company"] == "DataStream"
    assert jobs_jr1[1]["url"] == "https://jobright.ai/jobs/info/ds-202"

    # Jobright 2
    jr_path_2 = FIXTURES_DIR / "alerta_jobright_2.eml"
    with open(jr_path_2, "rb") as f:
        parsed_jr2 = mail_reader.parse_email_message(f.read())
    jobs_jr2 = mail_triage.extract_alert_jobs_from_email(parsed_jr2)
    assert len(jobs_jr2) >= 1, f"Esperada al menos 1 vacante en alerta_jobright_2, obtenidas {len(jobs_jr2)}"
    assert jobs_jr2[0]["title"] == "DevOps Engineer"
    assert jobs_jr2[0]["company"] == "KubeSys"
    assert jobs_jr2[0]["url"] == "https://jobright.ai/jobs/info/ks-303"

    # Welcome to the Jungle 1
    wttj_path_1 = FIXTURES_DIR / "alerta_jungle_1.eml"
    with open(wttj_path_1, "rb") as f:
        parsed_wttj1 = mail_reader.parse_email_message(f.read())
    jobs_wttj1 = mail_triage.extract_alert_jobs_from_email(parsed_wttj1)
    assert len(jobs_wttj1) == 2, f"Esperadas 2 vacantes en alerta_jungle_1, obtenidas {len(jobs_wttj1)}"
    assert jobs_wttj1[0]["title"] == "Fullstack Software Engineer"
    assert jobs_wttj1[0]["company"] == "Doctolib"
    assert jobs_wttj1[0]["url"] == "https://www.welcometothejungle.com/en/companies/doctolib/jobs/fullstack-eng-1"
    assert jobs_wttj1[1]["title"] == "QA Lead"
    assert jobs_wttj1[1]["company"] == "PayFit"
    assert jobs_wttj1[1]["url"] == "https://www.welcometothejungle.com/en/companies/payfit/jobs/qa-lead-2"

    # Welcome to the Jungle 2
    wttj_path_2 = FIXTURES_DIR / "alerta_jungle_2.eml"
    with open(wttj_path_2, "rb") as f:
        parsed_wttj2 = mail_reader.parse_email_message(f.read())
    jobs_wttj2 = mail_triage.extract_alert_jobs_from_email(parsed_wttj2)
    assert len(jobs_wttj2) >= 1, f"Esperada al menos 1 vacante en alerta_jungle_2, obtenidas {len(jobs_wttj2)}"
    assert jobs_wttj2[0]["title"] == "Data Engineer"
    assert jobs_wttj2[0]["company"] == "Alan"
    assert jobs_wttj2[0]["url"] == "https://www.welcometothejungle.com/en/companies/alan/jobs/data-eng-3"


# ===========================================================================
# 4. PRUEBAS DE ESTADOS 'LOS ESTADOS SOLO SUBEN' Y BASE DE DATOS
# ===========================================================================

def test_status_progression():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db_path = tmp.name

    old_db_path = os.environ.get("JOBHUNTER_DB_PATH")
    os.environ["JOBHUNTER_DB_PATH"] = test_db_path

    try:
        database.init_db()
        database.init_email_events_table()

        # Crear vacante de prueba
        conn = sqlite3.connect(test_db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO jobs (url, title, company, status, applied_at)
            VALUES ('https://example.com/test-job', 'Test Job', 'Test Corp', 'Aplicada', '2026-10-01 10:00:00')
        """)
        job_id = cur.lastrowid
        conn.commit()
        conn.close()

        # 1. Aplicada -> Confirmada (sube: True)
        ok = database.update_job_status_followup(job_id, "Confirmada")
        assert ok is True
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Confirmada"

        # 2. Confirmada -> Entrevista (sube: True)
        ok = database.update_job_status_followup(job_id, "Entrevista")
        assert ok is True
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Entrevista"

        # 3. Entrevista -> Confirmada (NO baja: False)
        ok = database.update_job_status_followup(job_id, "Confirmada")
        assert ok is False
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Entrevista"

        # 4. Entrevista -> Prueba técnica (NO baja: False)
        ok = database.update_job_status_followup(job_id, "Prueba técnica")
        assert ok is False
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Entrevista"

        # 5. Entrevista -> Rechazada (sube a estado terminal: True)
        ok = database.update_job_status_followup(job_id, "Rechazada")
        assert ok is True
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Rechazada"

        # 6. Rechazada solo se cambia a mano (NO vuelve a Entrevista ni Confirmada)
        ok = database.update_job_status_followup(job_id, "Entrevista")
        assert ok is False
        ok2 = database.update_job_status_followup(job_id, "Confirmada")
        assert ok2 is False
        row = database.get_job_by_url("https://example.com/test-job")
        assert row["status"] == "Rechazada"

        # Guardar evento de correo en email_events
        saved = database.save_email_event(
            job_id=job_id,
            gig_id=None,
            message_id="msg-12345",
            sender="Recruiter <rec@test.com>",
            subject="Entrevista técnica",
            received_at="2026-10-23 12:00:00",
            category="entrevista",
            summary="Invitacion a entrevista",
            action_needed=1,
            due_at="2026-10-25 15:00 UTC",
            link="https://mail.google.com/mail/u/0/#all/123",
        )
        assert saved is True
        # Idempotencia: el mismo message_id debe ignorarse
        saved_again = database.save_email_event(
            job_id=job_id,
            message_id="msg-12345",
            subject="Duplicado",
        )
        assert saved_again is False

        events = database.get_email_events(job_id=job_id)
        assert len(events) == 1
        assert events[0]["category"] == "entrevista"

        action_needed = database.get_action_needed_email_events()
        assert len(action_needed) == 1
        assert action_needed[0]["action_needed"] == 1

    finally:
        if old_db_path is not None:
            os.environ["JOBHUNTER_DB_PATH"] = old_db_path
        else:
            os.environ.pop("JOBHUNTER_DB_PATH", None)
        try:
            os.remove(test_db_path)
        except Exception:
            pass


# ===========================================================================
# 5. PRUEBAS DE AVISO INMEDIATO (DRY RUN)
# ===========================================================================

def test_dry_run_alerts():
    os.environ["FOLLOWUP_DRY_RUN"] = "1"
    try:
        facts = {
            "category": "entrevista",
            "interview_at": "2026-10-29 15:00 UTC",
            "scheduling_link": "https://calendly.com/sample",
            "summary_es": "Entrevista con Acme",
        }
        email_data = {
            "subject": "Invitación a entrevista técnica",
            "link": "https://mail.google.com/sample",
            "sender_name": "Sarah",
            "sender_email": "sarah@acme.com",
        }
        job = {"company": "Acme Corp", "title": "Senior QA Engineer"}

        sent = mail_triage.send_immediate_alert(email_data, facts, job)
        assert sent is True, "En modo DRY_RUN send_immediate_alert debe retornar True sin enviar"
    finally:
        os.environ.pop("FOLLOWUP_DRY_RUN", None)


# ===========================================================================
# 6. PRUEBA INTEGRAL DE alert_jobs() CON FILTRO DE URLs EXISTENTES (OFFLINE)
# ===========================================================================

def test_alert_jobs_filter():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db_path = tmp.name

    old_db_path = os.environ.get("JOBHUNTER_DB_PATH")
    os.environ["JOBHUNTER_DB_PATH"] = test_db_path

    try:
        database.init_db()

        # Insertar una URL ya vista
        database.save_job(
            url="https://jobright.ai/jobs/info/cs-101",
            title="Senior QA",
            company="CloudScale",
            status="Aprobado",
        )

        jr_path_1 = FIXTURES_DIR / "alerta_jobright_1.eml"
        with open(jr_path_1, "rb") as f:
            parsed = mail_reader.parse_email_message(f.read())

        # Mocking offline: sin red ni IMAP
        import apply_resolver
        from edge_fetchers import Fetcher

        orig_resolve = apply_resolver.resolve
        orig_get = Fetcher.get

        class DummyResp:
            status = 200
            body = b"<html><body>DataStream Python Backend role responsibilities and requirements</body></html>"

        apply_resolver.resolve = lambda j, **kw: ("https://datastream.io/apply/202", "generico", "auto")
        Fetcher.get = lambda url, **kw: DummyResp()

        try:
            # alert_jobs() debe omitir cs-101 porque ya está en jobs.db, y solo procesar ds-202
            jobs = mail_triage.alert_jobs(emails=[parsed])
            assert len(jobs) == 1, f"Esperada 1 vacante no vista (ds-202), obtenidas {len(jobs)}"
            assert jobs[0]["url"] == "https://jobright.ai/jobs/info/ds-202"
            assert jobs[0]["company"] == "DataStream"
            assert jobs[0]["apply_url"] == "https://datastream.io/apply/202"
            assert "DataStream Python Backend" in jobs[0]["description"]
        finally:
            apply_resolver.resolve = orig_resolve
            Fetcher.get = orig_get

    finally:
        if old_db_path is not None:
            os.environ["JOBHUNTER_DB_PATH"] = old_db_path
        else:
            os.environ.pop("JOBHUNTER_DB_PATH", None)
        try:
            os.remove(test_db_path)
        except Exception:
            pass


if __name__ == "__main__":
    print("Iniciando pruebas de mail_triage...")
    test_classification()
    print(" -> test_classification OK")
    test_matching()
    print(" -> test_matching OK")
    test_alert_extraction()
    print(" -> test_alert_extraction OK")
    test_status_progression()
    print(" -> test_status_progression OK")
    test_dry_run_alerts()
    print(" -> test_dry_run_alerts OK")
    test_alert_jobs_filter()
    print(" -> test_alert_jobs_filter OK")
    print("ok")
