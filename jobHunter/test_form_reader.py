"""Pruebas del lector universal de formularios (Fase C de APPLICATOR_PLAN.md).

Se corre con: py test_form_reader.py
Imprime 'ok' si todas las aserciones pasan.
"""
import http.server
import os
import sys
import threading
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from form_reader import (
    Field,
    check_html_captcha,
    find_step_buttons,
    parse_html,
    read_form,
)
from edge_fetchers import DynamicSession

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "forms"


def load_fixture(name: str) -> str:
    path = FIXTURES_DIR / name
    assert path.is_file(), f"No existe el fixture: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Fixture Hecho a Mano (custom_form.html)
# Radios en fieldset, combobox, campo obligatorio con *, y prompt injection
# ---------------------------------------------------------------------------
html_custom = load_fixture("custom_form.html")
fields_custom = parse_html(html_custom)

# Exactamente 6 campos
assert len(fields_custom) == 6, f"Esperaba 6 campos, obtuve {len(fields_custom)}"

field_map = {f.key: f for f in fields_custom}

# 1.1 Campo obligatorio con * en label (sin atributo required)
f_name = field_map["applicant_name"]
assert f_name.kind == "text", f_name
assert f_name.label == "Full Name", f_name.label
assert f_name.required is True, "Debe ser obligatorio por asterisco en label"
assert f_name.locator == "#applicant_name", f_name.locator

# 1.2 Campo obligatorio por atributo required
f_email = field_map["applicant_email"]
assert f_email.kind == "email", f_email
assert f_email.label == "Email Address", f_email.label
assert f_email.required is True, "Debe ser obligatorio por required"
assert f_email.locator == "#applicant_email", f_email.locator

# 1.3 Radios agrupados en fieldset
f_auth = field_map["authorized_us"]
assert f_auth.kind == "radio", f_auth
assert f_auth.label == "Are you legally authorized to work in the United States?", f_auth.label
assert f_auth.required is True
assert f_auth.options == ["Yes", "No"], f_auth.options
assert "authorized_us" in f_auth.locator, f_auth.locator

# 1.4 Combobox con role="combobox"
f_role = field_map["preferred_role"]
assert f_role.kind == "combobox", f_role
assert f_role.label == "Preferred Engineering Role", f_role.label
assert f_role.options is None, "Combobox debe tener options=None (regla Fase C)"

# 1.5 Select dropdown
f_seniority = field_map["seniority"]
assert f_seniority.kind == "select", f_seniority
assert f_seniority.label == "Seniority Level", f_seniority.label
assert len(f_seniority.options) == 5, f_seniority.options
assert "Senior" in f_seniority.options

# 1.6 Textarea
f_note = field_map["cover_note"]
assert f_note.kind == "textarea", f_note
assert f_note.label == "Why do you want to join us?", f_note.label
assert f_note.required is False

# 1.7 SEGURIDAD: Que "APPROVED" nunca aparezca en ninguna etiqueta, key u opción
for f in fields_custom:
    assert "APPROVED" not in f.label, f"Prompt injection en label: {f.label}"
    assert "APPROVED" not in f.key, f"Prompt injection en key: {f.key}"
    if f.options:
        for opt in f.options:
            assert "APPROVED" not in opt, f"Prompt injection en opción: {opt}"

# Botones en custom_form
from scrapling.parser import Selector
s_custom = Selector(html_custom)
next_btn, submit_btn = find_step_buttons(s_custom)
assert next_btn is not None, "Debe detectar next_button"
assert submit_btn is not None, "Debe detectar submit_button"
assert check_html_captcha(s_custom) is False


# ---------------------------------------------------------------------------
# 2. Fixture Greenhouse (greenhouse.html)
# Formulario ATS real de Canonical
# ---------------------------------------------------------------------------
html_gh = load_fixture("greenhouse.html")
fields_gh = parse_html(html_gh)
assert len(fields_gh) >= 30, f"Greenhouse debe tener >=30 campos, tiene {len(fields_gh)}"

gh_map = {f.key: f for f in fields_gh}
assert "first_name" in gh_map
assert gh_map["first_name"].kind == "text"
assert gh_map["first_name"].label == "First Name"
assert gh_map["first_name"].required is True

assert "last_name" in gh_map
assert gh_map["last_name"].label == "Last Name"
assert gh_map["last_name"].required is True

assert "email" in gh_map
assert gh_map["email"].label == "Email"
assert gh_map["email"].required is True

assert "phone" in gh_map
assert gh_map["phone"].kind == "tel"

assert "candidate_location" in gh_map
assert gh_map["candidate_location"].kind == "combobox"

# CAPTCHA en Greenhouse
assert check_html_captcha(Selector(html_gh)) is True

# Verificación de AP-2b: conteos actualizados y 0 campos con label 'Select...'
assert len(fields_gh) == 33, f"Greenhouse debe tener 33 campos reales (sin fantasmas, captcha ni el buscador de países del teléfono), tiene {len(fields_gh)}"
select_ghosts = [f for f in fields_gh if f.label.strip().rstrip(".").lower() == "select" or f.label.strip() == "Select..."]
assert len(select_ghosts) == 0, f"Greenhouse no debe tener campos con label 'Select...', tiene {len(select_ghosts)}"


# ---------------------------------------------------------------------------
# 3. Fixture Lever (lever.html)
# Formulario ATS real de Supermove
# ---------------------------------------------------------------------------
html_lever = load_fixture("lever.html")
fields_lever = parse_html(html_lever)
assert len(fields_lever) >= 10, f"Lever debe tener >=10 campos, tiene {len(fields_lever)}"

lever_map = {f.key: f for f in fields_lever}
assert "name" in lever_map
assert lever_map["name"].label == "Full name"
assert lever_map["name"].required is True

assert "email" in lever_map
assert lever_map["email"].label == "Email"
assert lever_map["email"].required is True

assert "resume" in lever_map
assert lever_map["resume"].kind == "file"
assert lever_map["resume"].required is True

assert "urls_linkedin" in lever_map
assert lever_map["urls_linkedin"].label == "LinkedIn URL"

_, lever_submit = find_step_buttons(Selector(html_lever))
assert lever_submit is not None
assert check_html_captcha(Selector(html_lever)) is True


# ---------------------------------------------------------------------------
# 4. Fixture Ashby (ashby.html)
# Formulario ATS real de Linear
# ---------------------------------------------------------------------------
html_ashby = load_fixture("ashby.html")
fields_ashby = parse_html(html_ashby)
assert len(fields_ashby) >= 10, f"Ashby debe tener >=10 campos, tiene {len(fields_ashby)}"

ashby_labels = {f.label: f for f in fields_ashby}
assert "Name" in ashby_labels
assert ashby_labels["Name"].required is True
assert ashby_labels["Name"].kind == "text"

assert "Email" in ashby_labels
assert ashby_labels["Email"].required is True
assert ashby_labels["Email"].kind == "email"

assert "Resume" in ashby_labels
assert ashby_labels["Resume"].kind == "file"

assert "Location" in ashby_labels
assert ashby_labels["Location"].required is True

_, ashby_submit = find_step_buttons(Selector(html_ashby))
assert ashby_submit is not None


# ---------------------------------------------------------------------------
# 5. Fixture Workable (workable.html)
# Formulario ATS real de Devsu con múltiples preguntas en radio groups
# ---------------------------------------------------------------------------
html_workable = load_fixture("workable.html")
fields_workable = parse_html(html_workable)
assert len(fields_workable) >= 15, f"Workable debe tener >=15 campos, tiene {len(fields_workable)}"

# Verificar que los grupos radio extrajeron preguntas y opciones reales
radio_fields = [f for f in fields_workable if f.kind == "radio"]
assert len(radio_fields) >= 10, f"Debe tener >=10 radio groups, tiene {len(radio_fields)}"
for rf in radio_fields:
    assert len(rf.options) >= 2, f"Radio group {rf.key} debe tener >=2 opciones"
    assert len(rf.label) > 10, f"Radio group {rf.key} debe tener una pregunta descriptiva"

# Primera pregunta de honestidad en Workable
f_honesty = radio_fields[0]
assert "During this application process" in f_honesty.label
assert "Yes" in f_honesty.options and "No" in f_honesty.options

_, workable_submit = find_step_buttons(Selector(html_workable))
assert workable_submit is not None


# ---------------------------------------------------------------------------
# 6. Prueba con Navegador Real: DynamicSession (Edge, headless) + Iframe
# Servido con python http.server para comprobar que read_form(page) entra a iframes
# ---------------------------------------------------------------------------
class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)

    def log_message(self, format, *args):
        pass


httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
port = httpd.server_address[1]
srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
srv_thread.start()

iframe_url = f"http://127.0.0.1:{port}/fixtures/forms/company_iframe.html"
live_result = None


def _inspect_iframe_page(page):
    global live_result
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("iframe#grnhse_iframe")
    page.wait_for_timeout(1000)
    live_result = read_form(page)


try:
    with DynamicSession(headless=True) as session:
        session.fetch(iframe_url, page_action=_inspect_iframe_page, network_idle=True)
finally:
    httpd.shutdown()

assert live_result is not None, "read_form no devolvió resultado"
iframe_fields = [f for f in live_result["fields"] if f.frame_index > 0]
assert len(iframe_fields) >= 30, (
    f"read_form debe encontrar los campos dentro del iframe (frame_index > 0), encontró {len(iframe_fields)}"
)
# Verificar que el primer campo dentro del iframe es First Name
first_field = iframe_fields[0]
assert first_field.label == "First Name"
assert first_field.required is True
assert first_field.frame_index == 1

# Ningún fixture devuelve el textarea interno del captcha como pregunta; Workable conserva sus radios (aria-hidden)
for _fx in ("greenhouse.html", "lever.html", "ashby.html", "workable.html"):
    assert not [f for f in parse_html(load_fixture(_fx)) if "recaptcha" in f.key], _fx
assert sum(f.kind == "radio" for f in parse_html(load_fixture("workable.html"))) == 10

# Formularios reales (Lever, banners de cookies): la pregunta sale de .application-label, sin textos del widget
_lever = """<form><ul>
<li class="application-question resume"><label><div class="application-label">Resume/CV <span class="required">✱</span></div>
<div class="application-field"><input type="file" name="resume"><span>Couldn't auto-read resume.</span><span>Analyzing resume...</span></div></label></li>
<li class="application-question"><div class="application-label"><div class="text">Pronouns</div></div><ul>
<li><label><input type="checkbox" name="pronouns" value="He/him"><span>He/him</span></label></li>
<li><label><input type="checkbox" name="pronouns" value="She/her"><span>She/her</span></label></li></ul></li>
</ul></form>
<div id="onetrust-consent-sdk"><input type="checkbox" id="ot_group_id_c0002"><label for="ot_group_id_c0002">Performance Cookies</label></div>"""
_lf = parse_html(_lever)
assert sorted((f.label, f.required) for f in _lf) == [("Pronouns", False), ("Resume/CV", True)], [(f.label, f.required) for f in _lf]

print("ok")
