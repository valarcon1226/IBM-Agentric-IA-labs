"""Agente 4: Llenador de formularios y servicio de postulación autónomo (Fases E y F).

Orquesta el proceso de postulación con Scrapling + Playwright sobre Microsoft Edge:
1. postular(page, job, mode) navega y llena hasta 8 pasos:
   form_reader lee el DOM -> answer_engine resuelve con el banco de respuestas del perfil ->
   form_filler escribe y verifica -> captura de pantalla en cada paso -> next.
2. Manejo de botones y estados:
   - Captcha detectado -> 'Postular a mano'.
   - Errores de validación persistentes tras reintento -> 'Error al aplicar'.
   - Modo 'revisar' -> captura + 'Lista para enviar' (se detiene antes de enviar).
   - Modo 'auto' -> envía solo si todos los datos obligatorios salieron de
     banco/perfil/aprendidas sin intervención humana, captura confirmación -> 'Aplicada'.
3. Servicio continuo (--loop) con tope diario (25), filtro nunca_postular_a, y ritmo humano (5-15 min).
"""
import argparse
import datetime
import logging
import os
import random
import sqlite3
import sys
import time
from typing import Any, Callable, Dict, List, Optional
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("applicator_agent")

from edge_fetchers import DynamicSession
from form_reader import Field, read_form
from answer_engine import Answer, answer as resolve_answer, normalize_label
from form_filler import fill
import profile_paths
import database
from database import (
    get_applications_count_today,
    get_job_by_url,
    get_jobs_for_applicator,
    mark_job_status_applicator,
    save_application_answer,
)


def _click_button(page: Any, locator_str: str) -> bool:
    """Hace clic en un botón tanto en la página principal como dentro de frames."""
    if not locator_str:
        return False

    targets = [page]
    if hasattr(page, "frames"):
        targets.extend(page.frames)

    for t in targets:
        try:
            loc = t.locator(locator_str).first
            if loc.count() > 0 and loc.is_visible():
                loc.scroll_into_view_if_needed(timeout=2000)
                loc.click(timeout=3000)
                return True
        except Exception:
            continue

    # Respaldo JS
    try:
        page.evaluate(f'document.querySelector("{locator_str}")?.click()')
        return True
    except Exception:
        return False


def check_validation_errors(page: Any) -> List[str]:
    """Detecta si hay mensajes de error o campos con aria-invalid='true' visibles en la página."""
    errors = []
    # 1. aria-invalid="true"
    try:
        invalids = page.locator('[aria-invalid="true"]').all()
        for inv in invalids:
            if inv.is_visible():
                err_id = inv.get_attribute("id") or inv.get_attribute("name") or "campo"
                errors.append(f"Campo inválido: {err_id}")
    except Exception:
        pass

    # 2. Selectores de error comunes
    error_selectors = [
        ".error-message", ".field-error", ".invalid-feedback", ".input-error",
        ".has-error", ".alert-danger", "[role='alert']", ".validation-error"
    ]
    for sel in error_selectors:
        try:
            elems = page.locator(sel).all()
            for el in elems:
                if el.is_visible():
                    txt = el.inner_text().strip()
                    if txt and len(txt) < 200:
                        errors.append(txt)
        except Exception:
            continue
    return errors


def postular(
    page: Any,
    job: Dict[str, Any],
    mode: str = "revisar",
    llm_classifier_fn: Optional[Callable] = None,
    llm_text_fn: Optional[Callable] = None,
) -> str:
    """Acción de página principal: llena el formulario paso a paso.

    Retorna el nuevo estado asignado al job:
    'Lista para enviar' | 'Aplicada' | 'Necesita respuesta' | 'Postular a mano' | 'Error al aplicar'
    """
    job_url = job.get("url") or job.get("apply_url") or ""
    job_id = str(job.get("id") or "job")
    apps_dir = profile_paths.resolve("applications")
    job_shot_dir = os.path.join(apps_dir, job_id)
    os.makedirs(job_shot_dir, exist_ok=True)

    mode = (mode or "revisar").lower()
    logger.info(f"[applicator] Iniciando postulación para '{job.get('title')}' en modo '{mode}'")

    for step in range(1, 9):
        logger.info(f"[applicator] --- Paso {step} ---")

        # 1. Espera de carga y lectura
        try:
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1000)
        except Exception:
            pass

        form_data = read_form(page)
        has_captcha = bool(form_data.get("captcha"))
        fields: List[Field] = form_data.get("fields", [])
        submit_btn = form_data.get("submit_button")
        next_btn = form_data.get("next_button")

        logger.info(f"[applicator] Campos encontrados: {len(fields)} | Next: {next_btn} | Submit: {submit_btn} | Captcha: {has_captcha}")

        if not fields and not submit_btn and not next_btn:
            if has_captcha:
                logger.warning("[applicator] Bloqueado por CAPTCHA sin campos detectados -> Postular a mano.")
                mark_job_status_applicator(job_url, "Postular a mano")
                return "Postular a mano"
            logger.info("[applicator] No se detectaron más campos ni botones de paso.")
            break

        # 3. Resolver y llenar campos
        all_required_from_bank = True
        has_needs_human = False
        has_llm = False

        def _fill_all_fields():
            nonlocal all_required_from_bank, has_needs_human, has_llm
            for field in fields:
                ans = resolve_answer(
                    field,
                    job=job,
                    llm_classifier_fn=llm_classifier_fn,
                    llm_text_fn=llm_text_fn,
                )

                # Auditoría en application_answers
                if job.get("id"):
                    try:
                        save_application_answer(
                            job_id=job["id"],
                            step=step,
                            label=field.label,
                            answer_key=field.key,
                            value=str(ans.value) if ans.value is not None else "",
                            source=ans.source,
                        )
                    except Exception as e:
                        logger.debug(f"[applicator] Error al guardar respuesta auditada: {e}")

                if ans.needs_human:
                    has_needs_human = True
                    if field.required:
                        all_required_from_bank = False

                if ans.source == "llm":
                    has_llm = True

                if field.required and ans.source not in ("bank", "profile", "learned"):
                    all_required_from_bank = False

                fill_ok = fill(page, field, ans)
                if not fill_ok and field.required:
                    logger.warning(f"[applicator] No se pudo completar campo obligatorio: {field.label}")

        _fill_all_fields()

        # 4. Captura de pantalla del paso completado
        shot_path = os.path.join(job_shot_dir, f"paso-{step}.png")
        try:
            page.screenshot(path=shot_path, full_page=True)
            logger.info(f"[applicator] Captura guardada: {shot_path}")
        except Exception as e:
            logger.warning(f"[applicator] No se pudo tomar captura: {e}")

        # 5. Detección y manejo de errores de validación (reintento x1)
        errs = check_validation_errors(page)
        if errs:
            logger.warning(f"[applicator] Errores de validación detectados ({len(errs)}). Reintentando paso...")
            _fill_all_fields()
            page.wait_for_timeout(1000)
            errs2 = check_validation_errors(page)
            if errs2:
                logger.error(f"[applicator] Errores de validación persistentes: {errs2}")
                mark_job_status_applicator(job_url, "Error al aplicar")
                return "Error al aplicar"

        # 6. Evaluación de botones (Submit vs Next)
        if submit_btn:
            if mode == "revisar":
                logger.info("[applicator] Botón de envío detectado. Modo 'revisar': detenido antes de enviar.")
                mark_job_status_applicator(job_url, "Lista para enviar")
                return "Lista para enviar"

            elif mode == "auto":
                if has_captcha:
                    logger.warning("[applicator] Modo 'auto': CAPTCHA detectado en la página -> 'Postular a mano'.")
                    mark_job_status_applicator(job_url, "Postular a mano")
                    return "Postular a mano"

                if has_needs_human:
                    logger.info("[applicator] Modo 'auto': campos obligatorios requieren respuesta humana -> 'Necesita respuesta'.")
                    mark_job_status_applicator(job_url, "Necesita respuesta")
                    return "Necesita respuesta"

                if all_required_from_bank and not has_llm:
                    logger.info("[applicator] Modo 'auto': enviando postulación automáticamente...")
                    _click_button(page, submit_btn)
                    try:
                        page.wait_for_timeout(3000)
                        page.wait_for_load_state("domcontentloaded")
                    except Exception:
                        pass

                    confirm_shot = os.path.join(job_shot_dir, "confirmacion.png")
                    try:
                        page.screenshot(path=confirm_shot, full_page=True)
                    except Exception:
                        pass

                    now_iso = datetime.datetime.now().isoformat()
                    mark_job_status_applicator(job_url, "Aplicada", applied_at=now_iso)
                    return "Aplicada"
                else:
                    logger.info("[applicator] Modo 'auto': contiene respuestas generadas por IA que requieren revisión -> 'Lista para enviar'.")
                    mark_job_status_applicator(job_url, "Lista para enviar")
                    return "Lista para enviar"

        elif next_btn:
            logger.info(f"[applicator] Avanzando al siguiente paso con: {next_btn}")
            clicked = _click_button(page, next_btn)
            if not clicked:
                logger.warning("[applicator] No se pudo hacer clic en el botón siguiente.")
                break
            try:
                page.wait_for_timeout(2000)
                page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            continue
        else:
            # Sin botones adicionales
            if mode == "revisar":
                mark_job_status_applicator(job_url, "Lista para enviar")
                return "Lista para enviar"
            break

    # Estado por defecto al completar formulario
    if mode == "revisar":
        mark_job_status_applicator(job_url, "Lista para enviar")
        return "Lista para enviar"

    mark_job_status_applicator(job_url, "Error al aplicar")
    return "Error al aplicar"


def apply_to_job(
    job: Dict[str, Any],
    mode: str = "revisar",
    llm_classifier_fn: Optional[Callable] = None,
    llm_text_fn: Optional[Callable] = None,
) -> str:
    """Envuelve la sesión de Edge para ejecutar la postulación sobre un trabajo dado."""
    apply_url = job.get("apply_url") or job.get("url")
    if not apply_url:
        logger.error(f"[applicator] La vacante {job.get('id')} no tiene URL de postulación")
        return "Error al aplicar"

    # Resolver CV
    if job.get("cv_path"):
        cv = job["cv_path"]
        if not os.path.exists(cv):
            base = os.path.basename(cv)
            cand1 = profile_paths.resolve(os.path.join("CVs_Listos", base))
            cand2 = profile_paths.resolve(base)
            if os.path.exists(cand1):
                job["cv_path"] = cand1
            elif os.path.exists(cand2):
                job["cv_path"] = cand2
            elif not os.path.isabs(cv):
                job["cv_path"] = os.path.abspath(cv)
    else:
        cv_dir = profile_paths.resolve("CVs_Listos")
        if os.path.isdir(cv_dir):
            for f in os.listdir(cv_dir):
                if f.lower().endswith(".pdf"):
                    job["cv_path"] = os.path.join(cv_dir, f)
                    break

    result_status = "Error al aplicar"

    def _page_action(page):
        nonlocal result_status
        result_status = postular(
            page,
            job,
            mode=mode,
            llm_classifier_fn=llm_classifier_fn,
            llm_text_fn=llm_text_fn,
        )

    try:
        with DynamicSession(headless=True) as session:
            session.fetch(apply_url, page_action=_page_action, network_idle=True)
    except Exception as e:
        logger.error(f"[applicator] Error durante DynamicSession para {apply_url}: {e}")
        mark_job_status_applicator(job.get("url") or apply_url, "Error al aplicar")
        result_status = "Error al aplicar"

    return result_status


def run_service_loop(mode: str = "revisar", interval_seconds: Optional[int] = None):
    """Loop continuo del servicio aplicador según la Fase F de APPLICATOR_PLAN.md."""
    print("====================================================")
    print(" Agente 4: SERVICIO APLICADOR AUTÓNOMO (Loop) ")
    print(f" Modo: {mode} ")
    print("====================================================\n")

    while True:
        answers_path = profile_paths.resolve("answers.yaml")
        bank = {}
        if os.path.exists(answers_path):
            try:
                with open(answers_path, "r", encoding="utf-8") as f:
                    bank = yaml.safe_load(f) or {}
            except Exception:
                pass

        reglas = bank.get("reglas") or {}
        nunca_postular = set(normalize_label(c) for c in reglas.get("nunca_postular_a", []))
        min_match = int(os.environ.get("APPLY_MIN_MATCH") or reglas.get("match_minimo_para_postular", 80))
        max_daily = int(reglas.get("maximo_postulaciones_por_dia", 25))

        today_count = get_applications_count_today()
        if today_count >= max_daily:
            logger.info(f"[applicator] Tope diario alcanzado ({today_count}/{max_daily}). Pausando 1 hora...")
            time.sleep(3600)
            continue

        jobs = get_jobs_for_applicator(min_match=min_match, limit=max_daily - today_count)
        if not jobs:
            logger.info(f"[applicator] Sin vacantes listas ('CV Generado' >= {min_match}%). Esperando 10 min...")
            time.sleep(600)
            continue

        for job in jobs:
            company_norm = normalize_label(job.get("company") or "")
            if company_norm in nunca_postular:
                logger.info(f"[applicator] Omitiendo {job.get('company')} (en lista 'nunca_postular_a')")
                mark_job_status_applicator(job["url"], "Filtrado")
                continue

            logger.info(f"[applicator] Procesando {job.get('company')} - {job.get('title')} ({job.get('match_percentage')}%)")
            res = apply_to_job(job, mode=mode)
            logger.info(f"[applicator] Resultado: {res}")

            wait_s = interval_seconds or random.randint(300, 900)
            logger.info(f"[applicator] Espera aleatoria de {wait_s // 60}m {wait_s % 60}s antes de la siguiente...")
            time.sleep(wait_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente 4 - Llenador y Servicio Aplicador")
    parser.add_argument("--url", type=str, help="URL de la vacante a postular")
    parser.add_argument("--mode", type=str, default=os.environ.get("APPLY_MODE", "revisar"), choices=["revisar", "auto"],
                        help="Modo de postulación: revisar (default, detiene antes de submit) o auto")
    parser.add_argument("--loop", action="store_true", help="Ejecutar en modo servicio 24/7 continuo")
    parser.add_argument("--limit", type=int, default=25, help="Límite de postulaciones")
    parser.add_argument("--interval", type=int, help="Segundos entre postulaciones para el loop")
    args = parser.parse_args()

    database.init_db()

    if args.loop:
        run_service_loop(mode=args.mode, interval_seconds=args.interval)
    elif args.url:
        job = get_job_by_url(args.url)
        if not job:
            # Buscar por apply_url
            conn = sqlite3.connect(database.get_db_path())
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE apply_url = ?", (args.url,)).fetchone()
            conn.close()
            if row:
                job = dict(row)
            else:
                database.save_job(
                    url=args.url,
                    title="Vacante Manual",
                    company="Empresa",
                    status="CV Generado",
                    apply_url=args.url,
                )
                job = get_job_by_url(args.url)

        res = apply_to_job(job, mode=args.mode)
        print(f"\n[Resultado] Postulación finalizada con estado: {res}")
    else:
        parser.print_help()
