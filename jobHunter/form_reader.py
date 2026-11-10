"""Lector universal de formularios para el Agente Aplicador (Fase C de APPLICATOR_PLAN.md).

Scrapling lee y parsea los campos de cualquier ATS o formulario web sin inyectar IDs ni
modificar el DOM. Retorna una lista pura de dataclass Field.
"""
from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional

from scrapling.parser import Selector

logger = logging.getLogger("form_reader")


@dataclass
class Field:
    key: str
    kind: str
    label: str
    options: Optional[List[str]] = None
    required: bool = False
    locator: str = ""
    frame_index: int = 0


# ---------------------------------------------------------------------------
# Helpers para visibilidad y extracción limpia de texto
# ---------------------------------------------------------------------------

def is_node_hidden(node) -> bool:
    """Verifica si un nodo tiene estilos o atributos que lo oculten."""
    attrib = getattr(node, "attrib", {})
    if "hidden" in attrib:
        return True
    if attrib.get("aria-hidden") == "true":
        return True
    style = attrib.get("style", "").lower().replace(" ", "")
    if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
        return True
    tag = getattr(node, "tag", "")
    if isinstance(tag, str) and tag.lower() in ("script", "style", "noscript"):
        return True
    return False


def is_element_or_ancestor_hidden(el) -> bool:
    """Verifica si el elemento o cualquiera de sus ancestros está oculto."""
    curr = getattr(el, "_root", el)
    while curr is not None:
        if is_node_hidden(curr):
            return True
        curr = curr.getparent()
    return False


def get_visible_text(node, exclude_tags=("input", "select", "textarea", "button")) -> str:
    """Extrae el texto visible de un elemento, descartando ramas ocultas y tags excluidos."""
    raw = getattr(node, "_root", node)
    parts: List[str] = []

    def _walk(el):
        tag = el.tag if isinstance(el.tag, str) else ""
        t_low = tag.lower()
        if t_low in ("script", "style", "noscript"):
            return
        if el is not raw and t_low in exclude_tags:
            return
        if is_node_hidden(el):
            return

        if el.text:
            t = el.text.strip()
            if t:
                parts.append(t)
        for child in el:
            _walk(child)
            if child.tail:
                tail = child.tail.strip()
                if tail:
                    parts.append(tail)

    _walk(raw)
    joined = " ".join(parts).strip()
    return re.sub(r"\s+", " ", joined)


def clean_label_text(raw: str) -> tuple[str, bool]:
    """Limpia el texto de la etiqueta y detecta si contenía indicador de obligatorio (*, ✱, etc.)."""
    star_chars = ("*", "✱", "✻", "★", "\u2731", "\u2217", "\ufe61", "\uff0a")
    has_star = any(ch in raw for ch in star_chars)

    # Eliminar asteriscos, estrellas, dos puntos y espacios al inicio o fin
    cleaned = re.sub(r"^[\s\*:\u2731\u2217\ufe61\uff0a✱✻★]+|[\s\*:\u2731\u2217\ufe61\uff0a✱✻★]+$", "", raw).strip()
    # Si al limpiar quedó vacío pero raw tenía algo, preservar lo que quede
    if not cleaned and raw:
        for ch in star_chars:
            raw = raw.replace(ch, "")
        cleaned = raw.strip()
    return cleaned, has_star


def make_key(raw: str) -> str:
    """Genera un key normalizado tipo snake_case."""
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.strip().lower()).strip("_")
    return s or "field"


def determine_locator(el, kind: str = "") -> str:
    """Genera el locator Playwright más limpio según APPLICATOR_PLAN.md:

    #id -> [name=...] (+ [value=...] en radios) -> CSS selector de Scrapling.
    """
    elem_id = el.attrib.get("id", "").strip()
    if elem_id and not elem_id.startswith("agy_injected_"):
        if re.match(r"^[a-zA-Z0-9_\-]+$", elem_id):
            return f"#{elem_id}"
        return f'[id="{elem_id}"]'

    name = el.attrib.get("name", "").strip()
    if name:
        if kind == "radio":
            val = el.attrib.get("value", "").strip()
            if val:
                return f'input[name="{name}"][value="{val}"]'
            return f'input[name="{name}"]'
        tag = getattr(el, "tag", "input")
        return f'{tag}[name="{name}"]'

    # Fallback al generador de selectores CSS de Scrapling
    try:
        css = el.generate_css_selector
        if isinstance(css, str) and css:
            return css
    except Exception:
        pass

    tag = getattr(el, "tag", "input")
    return tag


# ---------------------------------------------------------------------------
# Reglas de Fase C: Orden de etiquetas
# ---------------------------------------------------------------------------

def resolve_field_label(el, selector: Selector) -> tuple[str, bool]:
    """Resuelve la etiqueta siguiendo estrictamente el orden de la Fase C:

    1. label[for=id]
    2. <label> que envuelve
    3. aria-labelledby
    4. aria-label
    5. fieldset > legend (grupos)
    6. texto del contenedor padre más cercano (parent.get_all_text(strip=True))
    7. placeholder
    8. name
    Devuelve (label_limpia, tiene_asterisco).
    """
    # una casilla suelta ("Custom" dentro de Pronouns) se llama como su propio <label>, no como el bloque
    ats = None if el.attrib.get("type", "").lower() in ("checkbox", "radio") else _ats_block_label(el)
    if ats:
        return ats
    raw_label = ""
    elem_id = el.attrib.get("id", "").strip()

    # 1. label[for=id]
    if elem_id:
        try:
            labels = selector.css(f'label[for="{elem_id}"]')
            for lbl in labels:
                if not is_element_or_ancestor_hidden(lbl):
                    txt = get_visible_text(lbl)
                    if txt:
                        raw_label = txt
                        break
        except Exception:
            pass

    # 2. <label> que envuelve
    if not raw_label:
        curr = getattr(el, "_root", el).getparent()
        while curr is not None and curr.tag not in ("form", "body", "html"):
            if curr.tag.lower() == "label" and not is_element_or_ancestor_hidden(curr):
                # Si el label contiene un sub-elemento dedicado de título (ej. Lever: div.application-label)
                title_els = curr.css(".application-label, .field-label, .label-text") if hasattr(curr, "css") else []
                if title_els:
                    txt = get_visible_text(title_els[0])
                    if txt:
                        raw_label = txt
                        break
                # Texto del label excluyendo inputs, selects, textareas y botones
                txt = get_visible_text(curr, exclude_tags=("input", "select", "textarea", "button", "a"))
                if txt:
                    raw_label = txt
                    break
            curr = curr.getparent()

    # 3. aria-labelledby
    if not raw_label and el.attrib.get("aria-labelledby"):
        ids = el.attrib["aria-labelledby"].split()
        collected: List[str] = []
        for ref_id in ids:
            try:
                targets = selector.css(f'#{ref_id}, [id="{ref_id}"]')
                for t in targets:
                    if not is_element_or_ancestor_hidden(t):
                        txt = get_visible_text(t)
                        if txt:
                            collected.append(txt)
            except Exception:
                pass
        if collected:
            raw_label = " ".join(collected)

    # 4. aria-label
    if not raw_label and el.attrib.get("aria-label"):
        raw_label = el.attrib["aria-label"].strip()

    # 5. fieldset > legend
    if not raw_label:
        curr = getattr(el, "_root", el).getparent()
        while curr is not None and curr.tag not in ("form", "body", "html"):
            if curr.tag.lower() == "fieldset":
                for child in curr:
                    if child.tag.lower() == "legend" and not is_element_or_ancestor_hidden(child):
                        txt = get_visible_text(child)
                        if txt:
                            raw_label = txt
                            break
                if raw_label:
                    break
            curr = curr.getparent()

    # 6. Texto del contenedor padre más cercano
    if not raw_label:
        curr = getattr(el, "_root", el).getparent()
        steps = 0
        while curr is not None and curr.tag not in ("form", "body", "html") and steps < 4:
            if not is_element_or_ancestor_hidden(curr):
                txt = get_visible_text(curr, exclude_tags=("input", "select", "textarea", "button", "a"))
                if txt and len(txt) < 300:
                    raw_label = txt
                    break
            curr = curr.getparent()
            steps += 1

    # 7. placeholder
    if not raw_label and el.attrib.get("placeholder"):
        raw_label = el.attrib["placeholder"].strip()

    # 8. name
    if not raw_label and el.attrib.get("name"):
        raw_label = el.attrib["name"].strip()

    return clean_label_text(raw_label)


# Contenedores que no son del formulario: banner de cookies (OneTrust y similares) y el desplegable de países del
# teléfono (intl-tel-input: "Search" / "List of countries"); el país del teléfono se elige con el campo Country.
_WIDGET_CHROME = re.compile(r"onetrust|cookie|consent|\biti__dropdown|\biti__country-container", re.I)


def _in_widget_chrome(el) -> bool:
    curr = getattr(el, "_root", el)
    while curr is not None and curr.tag not in ("form", "body", "html"):
        if _WIDGET_CHROME.search(f'{curr.attrib.get("id", "")} {curr.attrib.get("class", "")}'):
            return True
        curr = curr.getparent()
    return False


def _ats_block_label(el) -> Optional[tuple[str, bool]]:
    """Lever: cada pregunta va en li.application-question con su texto en .application-label. Tomar el <label> entero
    o el contenedor arrastraba textos del widget ("Couldn't auto-read resume. Analyzing resume... Success!") y en los
    grupos de casillas devolvía la primera opción ("He/him", "Yes") en vez de la pregunta."""
    curr = getattr(el, "_root", el).getparent()
    for _ in range(10):
        if curr is None or curr.tag in ("form", "body", "html"):
            return None
        if "application-question" in (curr.attrib.get("class") or "").split():
            lab = curr.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " application-label ")]')
            if lab:
                main = lab[0].xpath('./*[contains(concat(" ", normalize-space(@class), " "), " text ")]') or lab
                raw = " ".join(" ".join(main[0].itertext()).split())
                star = bool(lab[0].xpath('.//*[contains(@class, "required")]'))
                txt, has_star = clean_label_text(raw)
                return (txt, has_star or star) if txt else None
            return None
        curr = curr.getparent()
    return None


def resolve_group_question(elements: List[Any], selector: Selector) -> tuple[str, bool]:
    """Resuelve la etiqueta de la pregunta principal de un grupo (radios o checkboxes)."""
    ats = _ats_block_label(elements[0])
    if ats:
        return ats
    # 1. Buscar en ancestro fieldset o [role="radiogroup" / "group"]
    for el in elements:
        curr = getattr(el, "_root", el).getparent()
        while curr is not None and curr.tag not in ("form", "body", "html"):
            tag_low = curr.tag.lower()
            role_low = curr.attrib.get("role", "").lower()

            if tag_low == "fieldset" or role_low in ("radiogroup", "group"):
                # aria-labelledby en el grupo (ej. Workable, Greenhouse, Ashby)
                if curr.attrib.get("aria-labelledby"):
                    ref_ids = curr.attrib["aria-labelledby"].split()
                    texts = []
                    for ref_id in ref_ids:
                        target = selector.css(f'#{ref_id}, [id="{ref_id}"]')
                        for t in target:
                            if not is_element_or_ancestor_hidden(t):
                                txt = get_visible_text(t)
                                if txt:
                                    texts.append(txt)
                    if texts:
                        return clean_label_text(" ".join(texts))

                # aria-label en el grupo
                if curr.attrib.get("aria-label"):
                    return clean_label_text(curr.attrib["aria-label"])

                # legend dentro de fieldset
                if tag_low == "fieldset":
                    for child in curr:
                        if child.tag.lower() == "legend" and not is_element_or_ancestor_hidden(child):
                            txt = get_visible_text(child)
                            if txt:
                                return clean_label_text(txt)

            curr = curr.getparent()

    # 2. Contenedor padre común con texto previo a los inputs (excluyendo los labels de las opciones)
    for el in elements:
        curr = getattr(el, "_root", el).getparent()
        steps = 0
        while curr is not None and curr.tag not in ("form", "body", "html") and steps < 4:
            if not is_element_or_ancestor_hidden(curr):
                txt = get_visible_text(curr, exclude_tags=("input", "select", "textarea", "button", "label"))
                if txt and len(txt) < 300:
                    return clean_label_text(txt)
            curr = curr.getparent()
            steps += 1

    first_el = elements[0]
    name = first_el.attrib.get("name", "")
    return clean_label_text(name or "question")


def resolve_option_label(el, selector: Selector) -> str:
    """Extrae el texto de una opción individual de radio/checkbox."""
    elem_id = el.attrib.get("id", "").strip()
    if elem_id:
        try:
            labels = selector.css(f'label[for="{elem_id}"]')
            for lbl in labels:
                if not is_element_or_ancestor_hidden(lbl):
                    txt = get_visible_text(lbl)
                    if txt:
                        clean_txt, _ = clean_label_text(txt)
                        return clean_txt
        except Exception:
            pass

    curr = getattr(el, "_root", el).getparent()
    while curr is not None and curr.tag not in ("fieldset", "form", "body", "html"):
        if curr.tag.lower() == "label" and not is_element_or_ancestor_hidden(curr):
            txt = get_visible_text(curr, exclude_tags=("input", "select", "textarea", "button"))
            if txt:
                clean_txt, _ = clean_label_text(txt)
                return clean_txt
        curr = curr.getparent()

    if el.attrib.get("aria-label"):
        clean_txt, _ = clean_label_text(el.attrib["aria-label"])
        return clean_txt

    return el.attrib.get("value", "").strip()


# ---------------------------------------------------------------------------
# Parser principal HTML puro
# ---------------------------------------------------------------------------

def parse_html(html: str, frame_index: int = 0) -> List[Field]:
    """Parsea el HTML de un frame o página y devuelve la lista de Field.

    Puro, basado en Scrapling Selector, sin navegador.
    """
    if not html or not html.strip():
        return []

    selector = Selector(html)
    fields: List[Field] = []
    seen_keys: Dict[str, int] = {}

    def _register_field(f: Field):
        base_key = f.key or "field"
        seen_keys[base_key] = seen_keys.get(base_key, 0) + 1
        if seen_keys[base_key] > 1:
            f.key = f"{base_key}_{seen_keys[base_key]}"
        fields.append(f)

    # 1. Agrupar radios por name
    radio_groups: Dict[str, List[Any]] = {}
    # 2. Agrupar checkboxes por name (si comparten name)
    checkbox_groups: Dict[str, List[Any]] = {}

    # Extraer todos los elementos interactivos
    css_query = (
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), '
        'textarea, select, [contenteditable="true"], [role="textbox"], [role="combobox"], [role="listbox"], [role="radiogroup"]'
    )
    # Un input de texto con aria-hidden = copia interna de un widget (el "requiredInput" de react-select en Greenhouse
    # y Workable), no una pregunta. Radios/checkbox/file con aria-hidden SÍ son campos: Workable y otros los ocultan
    # para dibujar los suyos. Los textarea de captcha (g-recaptcha-response) los resuelve el captcha, no nosotros.
    elements = [el for el in selector.css(css_query)
                if not (el.attrib.get("aria-hidden") == "true"
                        and el.attrib.get("type", "text").lower() not in ("radio", "checkbox", "file"))
                and not re.match(r"(g-recaptcha|h-captcha|cf-turnstile)", el.attrib.get("name") or el.attrib.get("id") or "")
                and not _in_widget_chrome(el)]

    # Primera pasada: identificar grupos de radio y checkbox
    for el in elements:
        tag = getattr(el, "tag", "").lower()
        t_type = el.attrib.get("type", "").lower()
        name = el.attrib.get("name", "").strip()

        if tag == "input" and t_type == "radio":
            grp_key = name or f"_radio_{id(el)}"
            radio_groups.setdefault(grp_key, []).append(el)
        elif tag == "input" and t_type == "checkbox" and name:
            checkbox_groups.setdefault(name, []).append(el)

    processed_radios = set()
    processed_checkboxes = set()

    # Procesar grupos de radios
    for grp_name, r_elements in radio_groups.items():
        question_label, q_has_star = resolve_group_question(r_elements, selector)

        options: List[str] = []
        is_required = q_has_star
        for r_el in r_elements:
            processed_radios.add(r_el)
            if "required" in r_el.attrib or r_el.attrib.get("aria-required") == "true":
                is_required = True

            opt_text = resolve_option_label(r_el, selector)
            if opt_text and opt_text not in options:
                options.append(opt_text)

        if not options:
            options = [r.attrib.get("value", f"option_{i}") for i, r in enumerate(r_elements)]

        first_el = r_elements[0]
        locator = f'input[type="radio"][name="{grp_name}"]' if not grp_name.startswith("_radio_") else determine_locator(first_el, kind="radio")
        f_key = make_key(grp_name if not grp_name.startswith("_radio_") else question_label)

        _register_field(Field(
            key=f_key,
            kind="radio",
            label=question_label,
            options=options,
            required=is_required,
            locator=locator,
            frame_index=frame_index,
        ))

    # Procesar grupos de checkboxes (solo si son 2 o más con el mismo name)
    for grp_name, cb_elements in checkbox_groups.items():
        if len(cb_elements) >= 2:
            question_label, q_has_star = resolve_group_question(cb_elements, selector)
            options = []
            is_required = q_has_star

            for cb_el in cb_elements:
                processed_checkboxes.add(cb_el)
                if "required" in cb_el.attrib or cb_el.attrib.get("aria-required") == "true":
                    is_required = True
                opt_text = resolve_option_label(cb_el, selector)
                if opt_text and opt_text not in options:
                    options.append(opt_text)

            locator = f'input[type="checkbox"][name="{grp_name}"]'
            _register_field(Field(
                key=make_key(grp_name),
                kind="checkbox",
                label=question_label,
                options=options,
                required=is_required,
                locator=locator,
                frame_index=frame_index,
            ))

    # Segunda pasada: campos restantes individuales
    for el in elements:
        if el in processed_radios or el in processed_checkboxes:
            continue

        tag = getattr(el, "tag", "").lower()
        role = el.attrib.get("role", "").lower()
        t_type = el.attrib.get("type", "text").lower()
        name = el.attrib.get("name", "").strip()
        elem_id = el.attrib.get("id", "").strip()

        # AP-2b: un <input> con aria-hidden="true" (o tabindex="-1" + aria-hidden) NO es un campo.
        if el.attrib.get("aria-hidden") == "true":
            continue

        label, has_star = resolve_field_label(el, selector)

        is_required = bool(
            "required" in el.attrib
            or el.attrib.get("aria-required") == "true"
            or has_star
        )

        kind = "text"
        options = None

        if role == "combobox":
            kind = "combobox"
            options = None  # Regla Fase C: Combobox de React: options=None
        elif role == "radiogroup":
            continue
        elif tag == "select" or role == "listbox":
            kind = "select"
            opt_elements = el.css("option")
            options = []
            for opt in opt_elements:
                txt = get_visible_text(opt)
                if txt:
                    clean_opt, _ = clean_label_text(txt)
                    options.append(clean_opt)
        elif tag == "textarea" or role == "textbox":
            kind = "textarea" if tag == "textarea" else "textbox"
        elif el.attrib.get("contenteditable") == "true":
            kind = "contenteditable"
        elif tag == "input":
            if t_type == "checkbox":
                kind = "checkbox"
                options = None
            elif t_type == "file":
                kind = "file"
            elif t_type in ("email", "tel", "number", "url", "date", "password", "text"):
                kind = t_type
            else:
                kind = "text"

        locator = determine_locator(el, kind=kind)
        field_key = make_key(name or elem_id or label)

        _register_field(Field(
            key=field_key,
            kind=kind,
            label=label,
            options=options,
            required=is_required,
            locator=locator,
            frame_index=frame_index,
        ))

    return fields


# ---------------------------------------------------------------------------
# Botones y Captcha
# ---------------------------------------------------------------------------

NEXT_KEYWORDS = (
    "next", "continue", "review", "proceed", "step",
    "siguiente", "continuar", "revisar", "avanzar", "paso"
)
SUBMIT_KEYWORDS = (
    "submit application", "submit", "apply now", "apply", "send application", "send", "finish", "complete",
    "enviar postulación", "enviar postulacion", "enviar solicitud", "enviar", "postular", "postularse", "finalizar", "completar"
)


def find_step_buttons(selector: Selector) -> tuple[Optional[str], Optional[str]]:
    """Encuentra locators para next_button y submit_button en inglés o español."""
    next_btn: Optional[str] = None
    submit_btn: Optional[str] = None

    buttons = selector.css('button, input[type="submit"], input[type="button"], [role="button"], a.btn, a.button')
    for btn in buttons:
        if is_element_or_ancestor_hidden(btn):
            continue

        txt = get_visible_text(btn)
        if not txt:
            txt = btn.attrib.get("value", "") or btn.attrib.get("aria-label", "")
        txt_low = txt.strip().lower()

        is_submit_type = btn.attrib.get("type", "").lower() == "submit"

        if not submit_btn:
            if is_submit_type or any(k in txt_low for k in SUBMIT_KEYWORDS):
                submit_btn = determine_locator(btn)
                continue

        if not next_btn:
            if any(k in txt_low for k in NEXT_KEYWORDS):
                next_btn = determine_locator(btn)
                continue

    return next_btn, submit_btn


def check_html_captcha(selector: Selector) -> bool:
    """Detecta iframes o marcas de CAPTCHA en el HTML."""
    iframes = selector.css('iframe')
    for iframe in iframes:
        src = iframe.attrib.get("src", "").lower()
        if any(k in src for k in ("recaptcha", "hcaptcha", "challenges.cloudflare.com", "turnstile", "cf-chl")):
            return True

    captcha_markers = selector.css('.g-recaptcha, .h-captcha, .cf-turnstile, #recaptcha, #hcaptcha')
    return len(captcha_markers) > 0


# ---------------------------------------------------------------------------
# Función con navegador vivo (Playwright Page)
# ---------------------------------------------------------------------------

def read_form(page: Any) -> Dict[str, Any]:
    """Recorre todos los frames de page, extrae los campos con Scrapling,

    detecta botones next/submit y presencia de CAPTCHA.
    Tiene respaldo de Playwright si Scrapling detecta 0 campos por Shadow DOM.
    """
    all_fields: List[Field] = []
    has_captcha = False
    next_button: Optional[str] = None
    submit_button: Optional[str] = None

    frames = page.frames
    for idx, frame in enumerate(frames):
        url = (frame.url or "").lower()
        if any(k in url for k in ("recaptcha", "hcaptcha", "challenges.cloudflare.com", "turnstile", "cf-chl")):
            has_captcha = True

        try:
            content = frame.content()
            frame_selector = Selector(content)
            if not has_captcha and check_html_captcha(frame_selector):
                has_captcha = True

            frame_fields = parse_html(content, frame_index=idx)
            all_fields.extend(frame_fields)

            if not next_button or not submit_button:
                f_next, f_submit = find_step_buttons(frame_selector)
                if not next_button and f_next:
                    next_button = f_next
                if not submit_button and f_submit:
                    submit_button = f_submit
        except Exception as e:
            logger.warning(f"[form_reader] Error al leer frame {idx}: {e}")

    # Respaldo Shadow DOM
    if len(all_fields) == 0:
        try:
            pw_candidates = page.locator(
                'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), '
                'textarea, select'
            )
            count = pw_candidates.count()
            if count > 0:
                logger.warning(
                    f"[form_reader] Scrapling encontró 0 campos pero Playwright detectó {count} "
                    f"campos (posible Shadow DOM). Usando respaldo de Playwright..."
                )
                for i in range(count):
                    el = pw_candidates.nth(i)
                    aria_hidden = el.evaluate("e => e.getAttribute('aria-hidden')")
                    if aria_hidden == "true":
                        continue
                    tag = el.evaluate("e => e.tagName.toLowerCase()")
                    t_type = el.evaluate("e => e.getAttribute('type') || ''").lower()
                    name = el.evaluate("e => e.getAttribute('name') || ''")
                    el_id = el.evaluate("e => e.id || ''")
                    label = el.evaluate('''e => {
                        if (e.id) {
                            const l = document.querySelector(`label[for="${e.id}"]`);
                            if (l) return l.innerText;
                        }
                        const parentLabel = e.closest('label');
                        if (parentLabel) return parentLabel.innerText;
                        return e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.name || '';
                    }''')
                    clean_lbl, has_star = clean_label_text(label)
                    if clean_lbl.strip().rstrip(".").lower() == "select" or clean_lbl.strip() == "Select...":
                        continue
                    is_req = el.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'") or has_star

                    kind = t_type or tag
                    options = None
                    if tag == "select":
                        kind = "select"
                        options = el.evaluate("e => Array.from(e.options).map(o => o.text.trim()).filter(Boolean)")

                    locator = f"#{el_id}" if el_id else (f'{tag}[name="{name}"]' if name else f"{tag}:nth-of-type({i+1})")
                    all_fields.append(Field(
                        key=make_key(name or el_id or clean_lbl),
                        kind=kind,
                        label=clean_lbl,
                        options=options,
                        required=bool(is_req),
                        locator=locator,
                        frame_index=0,
                    ))
        except Exception as e:
            logger.warning(f"[form_reader] Falló respaldo de Playwright: {e}")

    return {
        "fields": all_fields,
        "next_button": next_button,
        "submit_button": submit_button,
        "captcha": has_captcha,
    }
