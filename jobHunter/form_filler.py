"""Llenador de formularios con Playwright para el Agente Aplicador (Fase E de APPLICATOR_PLAN.md).

Llena campos por tipo (fill/press_sequentially, select_option, check/uncheck, set_input_files,
combobox = clic -> escribir -> role=option; respaldo de React solo si el normal falla)
y verifica lo escrito con input_value() o la opción seleccionada/marcada.
"""
import difflib
import logging
import os
import re
from typing import Any, Optional

from form_reader import Field
from answer_engine import Answer, normalize_label

logger = logging.getLogger("form_filler")


def _resolve_target(page: Any, frame_index: int = 0) -> Any:
    """Devuelve el frame correspondiente o la página principal."""
    if hasattr(page, "frames") and 0 <= frame_index < len(page.frames):
        return page.frames[frame_index]
    return page


def _find_element(target: Any, field: Field):
    """Busca el locator en el frame/página usando el locator original o selectores de respaldo."""
    # 1. Locator directo generado por form_reader
    if field.locator:
        try:
            loc = target.locator(field.locator)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass

    # 2. Respaldo por ID o Name
    if field.key:
        for sel in (f"#{field.key}", f'[name="{field.key}"]', f'input[name="{field.key}"]'):
            try:
                loc = target.locator(sel)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                continue

    # 3. Respaldo por get_by_label
    if field.label:
        try:
            loc = target.get_by_label(field.label)
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass

    return None


_OPTION_TEXT_JS = """el => {
    const l = el.closest('label');
    if (l) return l.innerText;
    if (el.id) {
        const lbl = document.querySelector(`label[for="${el.id}"]`);
        if (lbl) return lbl.innerText;
    }
    return '';
}"""


def _check_many(target: Any, field: Field, wanted: list) -> bool:
    """Grupo de casillas con varias respuestas: marca las elegidas (por texto o value) y verifica que quedaron."""
    want = {normalize_label(w) for w in wanted}
    boxes = target.locator(field.locator)
    done = set()
    for i in range(boxes.count()):
        box = boxes.nth(i)
        hit = want & {normalize_label(box.evaluate(_OPTION_TEXT_JS) or ""), normalize_label(box.get_attribute("value") or "")}
        if not hit:
            continue
        try:
            box.check(timeout=3000)
        except Exception:
            box.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }")
        if box.is_checked():
            done |= hit
    if done != want:
        logger.warning(f"[form_filler] Grupo '{field.label}': marcadas {sorted(done)} de {sorted(want)}")
        return not field.required
    logger.info(f"[form_filler] Grupo verificado '{field.label}': {sorted(done)}")
    return True


def fill(page: Any, field: Field, answer: Any) -> bool:
    """Llena un campo del formulario en la página viva de Playwright y verifica lo escrito.

    Retorna True si el llenado y verificación fueron exitosos (o si se omitió deliberadamente),
    False si ocurrió un error en un campo obligatorio.
    """
    if isinstance(answer, Answer):
        val = answer.value
        source = answer.source
        needs_human = answer.needs_human
    else:
        val = answer
        source = "raw"
        needs_human = False

    # Regla: omisión deliberada (skip) o campo opcional sin valor
    if source == "skip":
        logger.info(f"[form_filler] Campo '{field.label}' omitido por regla (source='skip')")
        return True

    if val is None or (str(val).strip() == "" and field.kind != "checkbox"):
        if not field.required:
            logger.info(f"[form_filler] Campo opcional '{field.label}' sin respuesta -> se omite")
            return True
        else:
            logger.warning(f"[form_filler] Campo obligatorio '{field.label}' sin respuesta (needs_human={needs_human})")
            return False

    target = _resolve_target(page, field.frame_index)
    loc = _find_element(target, field)

    if loc is None:
        logger.warning(f"[form_filler] No se encontró el elemento para '{field.label}' (locator='{field.locator}')")
        return not field.required

    kind = (field.kind or "text").lower()

    # -----------------------------------------------------------------------
    # 1. Archivos (file: Resume / CV / Cover Letter)
    # -----------------------------------------------------------------------
    if kind == "file":
        file_path = str(val).strip()
        if not os.path.exists(file_path):
            import profile_paths
            base = os.path.basename(file_path)
            cand1 = profile_paths.resolve(os.path.join("CVs_Listos", base))
            cand2 = profile_paths.resolve(base)
            if os.path.exists(cand1):
                file_path = cand1
            elif os.path.exists(cand2):
                file_path = cand2
            elif not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            logger.warning(f"[form_filler] Archivo no existe para subir a '{field.label}': {file_path}")
            return not field.required
        try:
            loc.set_input_files(file_path, timeout=5000)
            logger.info(f"[form_filler] Archivo subido a '{field.label}': {os.path.basename(file_path)}")
            return True
        except Exception as e:
            logger.warning(f"[form_filler] Error al subir archivo a '{field.label}': {e}")
            return not field.required

    # -----------------------------------------------------------------------
    # 2. Casillas de verificación (checkbox)
    # -----------------------------------------------------------------------
    if kind == "checkbox" and isinstance(val, (list, tuple)):
        return _check_many(target, field, val)  # "marca todas las que apliquen": una casilla por opción elegida
    if kind == "checkbox":
        is_checked = str(val).strip().lower() in ("true", "yes", "1", "si", "sí", "on")
        if field.options and len(field.options) == 1:
            if str(val).strip().lower() == field.options[0].strip().lower():
                is_checked = True

        try:
            loc.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        try:
            if is_checked:
                loc.check(timeout=3000)
            else:
                loc.uncheck(timeout=3000)
        except Exception:
            # Fallback React / JS
            try:
                loc.evaluate("""(el, chk) => {
                    el.checked = chk;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""", is_checked)
            except Exception as e:
                logger.debug(f"[form_filler] Fallback JS checkbox falló: {e}")

        # Verificación
        try:
            actual = loc.is_checked()
            if actual == is_checked:
                logger.info(f"[form_filler] Checkbox verificado '{field.label}': {actual}")
                return True
        except Exception:
            pass
        return True

    # -----------------------------------------------------------------------
    # 3. Botones de opción (radio)
    # -----------------------------------------------------------------------
    if kind == "radio":
        val_str = str(val).strip()
        val_norm = normalize_label(val_str)
        checked_ok = False

        try:
            loc.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        # Buscar todos los radios asociados (por locator de grupo o por name)
        radios_locator = target.locator(field.locator)
        count = 0
        try:
            count = radios_locator.count()
        except Exception:
            pass

        if count == 0 and field.key:
            radios_locator = target.locator(f'input[type="radio"][name="{field.key}"]')
            try:
                count = radios_locator.count()
            except Exception:
                pass

        for i in range(count):
            r = radios_locator.nth(i)
            r_val = (r.get_attribute("value") or "").strip()
            r_val_norm = normalize_label(r_val)

            # Buscar texto de la etiqueta que envuelve o cercana
            r_lbl_text = ""
            try:
                r_lbl_text = r.evaluate("""el => {
                    const l = el.closest('label');
                    if (l) return l.innerText;
                    if (el.id) {
                        const lbl = document.querySelector(`label[for="${el.id}"]`);
                        if (lbl) return lbl.innerText;
                    }
                    return '';
                }""") or ""
            except Exception:
                pass
            lbl_norm = normalize_label(r_lbl_text)

            # Coincidencia con el valor o la etiqueta
            if (val_norm == r_val_norm or val_norm == lbl_norm
                    or (val_norm in ("yes", "si") and r_val_norm in ("yes", "si", "1", "true"))
                    or (val_norm in ("no",) and r_val_norm in ("no", "0", "false"))):
                try:
                    r.check(timeout=3000)
                    checked_ok = True
                    break
                except Exception:
                    # Fallback JS
                    try:
                        r.evaluate("""el => {
                            el.checked = true;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }""")
                        checked_ok = True
                        break
                    except Exception:
                        pass

        # Verificación
        if checked_ok:
            logger.info(f"[form_filler] Radio verificado '{field.label}': '{val_str}'")
            return True

        if not field.required:
            return True
        logger.warning(f"[form_filler] No se pudo seleccionar radio '{field.label}' con valor '{val_str}'")
        return False

    # -----------------------------------------------------------------------
    # 4. Desplegable nativo (select)
    # -----------------------------------------------------------------------
    if kind == "select":
        str_val = str(val).strip()
        success = False

        try:
            loc.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        # Estrategia 1: select_option por label
        try:
            loc.select_option(label=str_val, timeout=2500)
            success = True
        except Exception:
            pass

        # Estrategia 2: select_option por value
        if not success:
            try:
                loc.select_option(value=str_val, timeout=1000)
                success = True
            except Exception:
                pass

        # Estrategia 3: difflib con las opciones del DOM
        if not success:
            try:
                dom_options = loc.evaluate("el => Array.from(el.options).map(o => o.text.trim())")
                if dom_options:
                    matches = difflib.get_close_matches(str_val, dom_options, n=1, cutoff=0.5)
                    if matches:
                        loc.select_option(label=matches[0], timeout=2000)
                        success = True
            except Exception:
                pass

        # Fallback React / JS
        if not success:
            try:
                js_ok = loc.evaluate("""(el, targetVal) => {
                    const norm = targetVal.toLowerCase().trim();
                    for (let opt of el.options) {
                        if (opt.text.trim().toLowerCase() === norm || opt.value.trim().toLowerCase() === norm) {
                            el.value = opt.value;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            return true;
                        }
                    }
                    return false;
                }""", str_val)
                if js_ok:
                    success = True
            except Exception as e:
                logger.debug(f"[form_filler] Fallback JS select falló: {e}")

        # Verificación
        try:
            sel_text = loc.evaluate("el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text.trim() : ''")
            sel_val = loc.input_value()
            if sel_text or sel_val:
                logger.info(f"[form_filler] Select verificado '{field.label}': '{sel_text or sel_val}'")
                return True
        except Exception:
            pass
        return success or not field.required

    # -----------------------------------------------------------------------
    # 5. Combobox (React / ARIA / Custom)
    # "combobox = clic -> escribir -> role=option; respaldo de React solo si el normal falla"
    # -----------------------------------------------------------------------
    if kind == "combobox":
        str_val = str(val).strip()

        try:
            loc.scroll_into_view_if_needed(timeout=2000)
            loc.click(timeout=2000)
        except Exception:
            pass

        tag = ""
        try:
            tag = loc.evaluate("el => el.tagName.toLowerCase()")
        except Exception:
            pass

        if tag == "input":
            # Input de combobox (ej. react-select)
            try:
                loc.fill("")
                loc.press_sequentially(str_val, delay=15)
            except Exception:
                try:
                    loc.fill(str_val, force=True)
                except Exception:
                    pass

            # Pausa breve para desplegar las opciones
            try:
                page.wait_for_timeout(400)
            except Exception:
                pass

            # Buscar la opción con role="option"
            clicked_opt = False
            try:
                opts = target.locator('[role="option"], .select__option, [role="listbox"] > *')
                count = opts.count()
                for i in range(count):
                    item = opts.nth(i)
                    txt = item.inner_text().strip()
                    if txt.lower() == str_val.lower() or str_val.lower() in txt.lower():
                        item.click(timeout=2000)
                        clicked_opt = True
                        break
                if not clicked_opt and count > 0:
                    opts.first.click(timeout=2000)
                    clicked_opt = True
            except Exception:
                pass

            if not clicked_opt:
                try:
                    loc.press("Enter")
                    loc.press("Tab")
                except Exception:
                    pass

            # Fallback React si sigue vacío
            try:
                if not loc.input_value():
                    loc.evaluate("""(el, v) => {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
                        if (setter) setter.call(el, v);
                        else el.value = v;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", str_val)
            except Exception:
                pass

            # Verificación
            try:
                cur = loc.input_value()
                if cur and (str_val.lower() in cur.lower() or cur.lower() in str_val.lower()):
                    logger.info(f"[form_filler] Combobox verificado '{field.label}': '{cur}'")
                    return True
            except Exception:
                pass
            return True

        else:
            # Div o contenedor con role="combobox" (ej. custom_form.html)
            try:
                loc.press_sequentially(str_val, delay=15)
            except Exception:
                pass

            # Buscar si abrió opciones
            clicked_opt = False
            try:
                opts = target.locator('[role="option"]')
                count = opts.count()
                for i in range(count):
                    item = opts.nth(i)
                    if str_val.lower() in item.inner_text().strip().lower():
                        item.click(timeout=2000)
                        clicked_opt = True
                        break
            except Exception:
                pass

            if not clicked_opt:
                # Fallback JS: inyectar texto y atributos en el div
                try:
                    loc.evaluate("""(el, v) => {
                        el.innerText = v;
                        el.setAttribute('aria-expanded', 'true');
                        el.setAttribute('data-value', v);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", str_val)
                except Exception as e:
                    logger.debug(f"[form_filler] Fallback custom combobox error: {e}")

            # Verificación
            try:
                txt = loc.inner_text()
                if str_val.lower() in txt.lower():
                    logger.info(f"[form_filler] Combobox div verificado '{field.label}': '{txt.strip()}'")
                    return True
            except Exception:
                pass
            return True

    # -----------------------------------------------------------------------
    # 6. Texto enriquecido (contenteditable)
    # -----------------------------------------------------------------------
    if kind == "contenteditable":
        str_val = str(val).strip()
        try:
            loc.scroll_into_view_if_needed(timeout=2000)
            loc.click(timeout=2000)
            loc.evaluate("""(el, v) => {
                el.innerText = v;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", str_val)
            actual = loc.inner_text().strip()
            if str_val in actual:
                logger.info(f"[form_filler] Contenteditable verificado '{field.label}'")
                return True
        except Exception as e:
            logger.warning(f"[form_filler] Error en contenteditable '{field.label}': {e}")
        return not field.required

    # -----------------------------------------------------------------------
    # 7. Cajas de texto estándar (text, email, tel, number, url, date, password, textarea, textbox)
    # -----------------------------------------------------------------------
    str_val = str(val).strip()
    typed = False

    try:
        loc.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    try:
        loc.click(timeout=2000)
        loc.fill("", timeout=2000)
        loc.press_sequentially(str_val, delay=10)
        loc.press("Tab")
        typed = True
    except Exception:
        try:
            loc.fill(str_val, force=True, timeout=2000)
            typed = True
        except Exception:
            pass

    # Verificación preliminar
    current_val = ""
    try:
        current_val = loc.input_value()
    except Exception:
        pass

    # Respaldo React si está vacío tras escribir
    if not current_val:
        try:
            loc.evaluate("""(el, v) => {
                const isTextarea = el.tagName === 'TEXTAREA';
                const proto = isTextarea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
                if (setter) {
                    setter.call(el, v);
                } else {
                    el.value = v;
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", str_val)
        except Exception as e:
            logger.debug(f"[form_filler] Fallback React input falló: {e}")

    # Verificación final
    try:
        final_val = loc.input_value()
        if final_val.strip() == str_val or str_val in final_val or final_val in str_val:
            logger.info(f"[form_filler] Texto verificado '{field.label}': '{final_val[:30]}...'")
            return True
    except Exception:
        try:
            final_text = loc.inner_text()
            if str_val in final_text or final_text.strip() == str_val:
                return True
        except Exception:
            pass

    if typed:
        return True

    if not field.required:
        return True

    logger.warning(f"[form_filler] No se pudo verificar texto en '{field.label}'")
    return False
