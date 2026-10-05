"""jobHunter para cualquier persona: py main.py "Nombre Apellido"

1. Usa la carpeta Profiles/<Nombre Apellido>/ (ahí va el CV en PDF y ahí queda todo lo de esa persona).
2. Pide (solo la primera vez) las llaves gratis de IA de la persona y las guarda en su .env.
3. Perfil: si no existe, lee el CV y hace la entrevista; si existe, pregunta si hay cambios.
4. Preferencias de búsqueda (país, roles, años, contractor): se preguntan una vez y quedan guardadas.
5. Busca vacantes 9-5, genera CVs a la medida para las de 70%+ y abre un reporte HTML.

Opciones:  --reporte  solo regenera y abre el reporte (sin buscar ni generar CVs)
"""
import asyncio
import datetime
import glob
import html
import json
import os
import sqlite3
import sys
import urllib.request
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LLM_KEYS = [
    ("GEMINI_API_KEY", "Gemini (Google)", "https://aistudio.google.com/apikey"),
    ("GROQ_API_KEY", "Groq", "https://console.groq.com/keys"),
    ("OPENROUTER_API_KEY", "OpenRouter (opcional)", "https://openrouter.ai/keys"),
]


def ask(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    answer = input(f"{question}{hint}: ").strip()
    return answer or default


def yes(question: str, default: bool = False) -> bool:
    return ask(question + " (s/n)", "s" if default else "n").lower().startswith(("s", "y"))


# ---------------------------------------------------------------- llaves de IA y modelo local
def read_env(path: str) -> dict:
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


def detect_ollama() -> str:
    """Modelo local de Ollama a usar, o '' si no hay Ollama en este PC (entonces todo va con las llaves)."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            models = [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:
        return ""
    wanted = os.environ.get("OLLAMA_MODEL") or "qwen3:4b"
    return wanted if wanted in models else (models[0] if models else "")


def setup_keys(profile_dir: str, has_local_model: bool):
    env_path = os.path.join(profile_dir, ".env")
    env = read_env(env_path)
    if not any(env.get(k) for k, _, _ in LLM_KEYS):
        print("\n=== Llaves de IA (gratis, solo la primera vez) ===")
        print("jobHunter usa modelos de IA para leer vacantes y escribir tus CVs. Necesita TUS llaves (son gratis,")
        print("sin tarjeta). Saca al menos una; con dos rinde más el cupo diario:")
        for key, name, url in LLM_KEYS:
            print(f"  - {name}: {url}")
        if has_local_model:
            print("  (Tienes Ollama instalado: lo pesado corre en tu PC y las llaves se usan para lo demás.)")
        for key, name, _ in LLM_KEYS:
            value = input(f"Pega tu llave de {name} (Enter para saltar): ").strip()
            if value:
                env[key] = value
        if not any(env.get(k) for k, _, _ in LLM_KEYS):
            sys.exit("Sin al menos una llave no se puede continuar. Vuelve a correr cuando la tengas.")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# Llaves de IA de esta persona (no compartir este archivo)\n")
            f.writelines(f"{k}={v}\n" for k, v in env.items())
        print(f"Guardadas en {env_path}")
    os.environ.update(env)  # las de la persona mandan sobre cualquier otra
    # las que no dio quedan vacías a propósito, aunque existan en el sistema (p. ej. GEMINI_API_KEY de Gemini CLI)
    # o en el .env de la raíz (load_dotenv no pisa variables ya definidas): solo se usan las de esta persona
    for key in [k for k, _, _ in LLM_KEYS] + ["GOOGLE_API_KEY", "CEREBRAS_API_KEY"]:
        if not env.get(key):
            os.environ[key] = ""


# ---------------------------------------------------------------- perfil
def cv_files(profile_dir: str) -> list:
    return [f for f in glob.glob(os.path.join(profile_dir, "*.pdf")) if "CVs_Listos" not in f] + \
        glob.glob(os.path.join(profile_dir, "cv.txt"))


def profile_step(profile_dir: str) -> bool:
    """Crea o actualiza el perfil maestro. Devuelve True si hubo cambios (para repreguntar preferencias)."""
    import interviewer_agent
    import profile_paths
    master = profile_paths.resolve("master_profile.json")
    if os.path.exists(master):
        p = json.load(open(master, encoding="utf-8"))
        name = (p.get("personal_info") or {}).get("full_name", "")
        print(f"\n=== Perfil encontrado: {name} — {p.get('target_roles', '')} ({len(p.get('experience', []))} experiencias) ===")
        if not yes("¿Hay cambios en tu CV o en lo que buscas?"):
            return False
        print("Si tienes un CV nuevo, ponlo en PDF dentro de la carpeta (reemplaza el anterior) antes de seguir.")
        input("Enter para empezar la entrevista...")
    else:
        if not cv_files(profile_dir):
            sys.exit(f"\nNo encontré tu CV. Pon tu hoja de vida en PDF dentro de:\n  {profile_dir}\ny vuelve a correr.")
        print("\n=== Primera vez: voy a leer tu CV y hacerte unas preguntas para armar tu perfil ===")
    interviewer_agent.run_interview()
    if not os.path.exists(master):
        sys.exit("No se pudo crear el perfil (revisa tus llaves de IA o el CV) y vuelve a correr.")
    return True


def settings_step(changed: bool):
    import user_settings
    import profile_paths
    if os.path.exists(user_settings.path()) and not changed:
        return
    p = json.load(open(profile_paths.resolve("master_profile.json"), encoding="utf-8"))
    location = (p.get("personal_info") or {}).get("location", "")
    print("\n=== Preferencias de búsqueda (se guardan; se vuelven a preguntar solo si cambias el perfil) ===")
    country = ask("¿En qué país vives y trabajas?", location.split(",")[-1].strip() or "Colombia")
    families = list(user_settings.ROLE_FAMILY_LABELS)
    for i, fam in enumerate(families, 1):
        print(f"  {i}. {user_settings.ROLE_FAMILY_LABELS[fam]}")
    picked = ""
    while not picked:
        picked = ask("¿Qué tipos de rol buscas? (números separados por coma, p. ej. 10,11)")
    role_families = [families[int(x) - 1] for x in picked.replace(" ", "").split(",") if x.isdigit() and 0 < int(x) <= len(families)]
    years = ask("¿Cuántos años de experiencia real tienes en esos roles?", "2")
    remote_only = yes("¿Buscas SOLO trabajo remoto? (n = también híbrido o presencial en tu ciudad)", True)
    city = "" if remote_only else ask("¿En qué ciudad?", location.split(",")[0].strip())
    contractor = remote_only and yes("¿Aceptas trabajar remoto como contractor para empresas de otros países (sin visa ni permiso de trabajo)?", True)
    langs = ask("Idiomas de las vacantes que aceptas (en=inglés, es=español)", "en,es")
    latam = {"colombia", "mexico", "méxico", "argentina", "chile", "peru", "perú", "ecuador", "uruguay", "paraguay",
             "bolivia", "venezuela", "costa rica", "panama", "panamá", "guatemala", "el salvador", "honduras",
             "nicaragua", "republica dominicana", "república dominicana", "brazil", "brasil"}
    if remote_only:
        locations = [country] + (["Latin America"] if country.lower() in latam else []) + (["United States"] if contractor else [])
    else:
        locations = [f"{city}, {country}"]  # presencial, híbrido y remoto en su ciudad
    user_settings.save({
        "home_country": country.lower(), "search_locations": locations, "accept_international_contractor": contractor,
        "role_families": role_families,
        "years_by_family": {"default": int(years) if years.isdigit() else 2}, "allowed_langs": langs, "remote_only": remote_only,
        "cv_language": "auto",  # CV en el idioma de cada vacante
    })
    print(f"Guardado. Voy a buscar en: {', '.join(locations)}")


# ---------------------------------------------------------------- reporte
def report_step(profile_dir: str) -> str:
    import profile_paths
    db = sqlite3.connect(profile_paths.resolve("jobs.db"))
    cols = {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
    loc = "location" if "location" in cols else "'' AS location"
    rows = db.execute(f"SELECT id, title, company, {loc}, match_percentage, status, url, gap_analysis, cv_path, created_at "
                      "FROM jobs WHERE status IN ('CV Generado', 'Aprobado', 'Match Insuficiente') "
                      "ORDER BY match_percentage DESC").fetchall()
    guides = {os.path.basename(g).rsplit("_", 1)[-1][:-4]: g for g in glob.glob(os.path.join(profile_paths.resolve("study_guides"), "*.txt"))}
    e = html.escape

    def link(path):
        return os.path.relpath(path, profile_dir).replace("\\", "/") if path and os.path.exists(path) else ""

    cards = []
    for jid, title, company, location, match, status, url, gaps, cv_path, created in rows:
        cv = link(os.path.join(profile_paths.resolve("CVs_Listos"), os.path.basename((cv_path or "").replace("\\", "/")))) if cv_path else ""
        guide = link(guides.get(str(jid)))
        badge = "CV listo" if cv else ("CV en cola" if (match or 0) >= 70 else "Sin CV (match bajo)")
        cards.append(f"""<article class="{'top' if (match or 0) >= 70 else 'mid'}">
  <div class="pct">{match}%</div>
  <div><h3>{e(title)}</h3><p class="sub">{e(company)}{' · ' + e(location) if location else ''} · {e((created or '')[:10])}</p>
  {f'<p class="gaps"><b>Te falta:</b> {e(gaps)}</p>' if gaps else ''}
  <p class="links"><a href="{e(url)}" target="_blank">Ver oferta</a>{f' · <a href="{e(cv)}">Abrir CV</a>' if cv else ''}{f' · <a href="{e(guide)}">Plan de estudio</a>' if guide else ''}
  <span class="badge">{badge}</span></p></div>
</article>""")
    name = os.path.basename(profile_dir)
    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vacantes de {e(name)}</title><style>
:root{{--bg:#f5f6f8;--card:#fff;--ink:#17202b;--soft:#5b6673;--line:#dde2e8;--top:#177245;--top-bg:#ddf1e6;--mid:#9a6508;--mid-bg:#fbefd7;--accent:#1c6b86}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f151b;--card:#161f28;--ink:#e4ebf1;--soft:#9aa7b4;--line:#2a3541;--top:#6fd39c;--top-bg:#123424;--mid:#f0bf5e;--mid-bg:#382a0f;--accent:#6bb8d2}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px 16px}}
main{{max-width:900px;margin:0 auto}} h1{{margin:0 0 4px}} .meta{{color:var(--soft);margin:0 0 20px}}
article{{display:grid;grid-template-columns:64px 1fr;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px}}
.pct{{font-weight:700;font-size:17px;text-align:center;border-radius:8px;padding:8px 0;height:fit-content}}
.top .pct{{background:var(--top-bg);color:var(--top)}} .mid .pct{{background:var(--mid-bg);color:var(--mid)}}
h3{{margin:0;font-size:16px}} .sub{{margin:2px 0 6px;color:var(--soft);font-size:13.5px}} .gaps{{margin:4px 0;font-size:13.5px}}
.links{{margin:6px 0 0;font-size:14px}} a{{color:var(--accent);font-weight:600}}
.badge{{margin-left:8px;font-size:12px;color:var(--soft);border:1px solid var(--line);border-radius:6px;padding:1px 7px}}
</style></head><body><main>
<h1>Vacantes de {e(name)}</h1>
<p class="meta">{len(rows)} vacantes · {sum(1 for r in rows if (r[4] or 0) >= 70)} con 70%+ · generado el {datetime.datetime.now():%Y-%m-%d %H:%M}</p>
{''.join(cards) or '<p>Todavía no hay vacantes. Corre de nuevo main.py para buscar.</p>'}
</main></body></html>"""
    out = os.path.join(profile_dir, "reporte_vacantes.html")
    open(out, "w", encoding="utf-8").write(page)
    return out


# ---------------------------------------------------------------- flujo
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit('Uso: py main.py "Nombre Apellido"   (la carpeta Profiles/Nombre Apellido/ con tu CV en PDF)')
    name = " ".join(args).strip()
    os.chdir(HERE)  # las plantillas (CV_TEMPLATE/) se leen con rutas relativas
    os.environ["JOBHUNTER_PROFILE"] = name
    import profile_paths
    profile_dir = profile_paths.profile_dir()
    print(f"===== jobHunter · {name} =====\nCarpeta: {profile_dir}")

    local_model = detect_ollama()
    os.environ["OLLAMA_MODEL"] = local_model  # vacío = sin Ollama: todo con las llaves de la persona
    setup_keys(profile_dir, bool(local_model))

    import database
    database.init_db()
    if "--reporte" not in sys.argv:
        changed = profile_step(profile_dir)
        settings_step(changed)

        os.environ.setdefault("SCOUT_MAX_RUNTIME_HOURS", "0.5")
        os.environ.setdefault("SCOUT_NEW_JOBS_GOAL", "15")
        os.environ.setdefault("TAILOR_MAX_JOBS", "10")
        print("\n=== Buscando vacantes (máx. 30 min) ===")
        import scout_agent
        scout_agent.run_scout_agent()
        print("\n=== Generando CVs a la medida para las de 70%+ ===")
        import tailor_agent
        try:
            asyncio.run(tailor_agent.run_tailor_agent())
        except Exception as e:
            print(f"[-] No se pudieron generar los CVs ({e}). ¿Corriste 'py -m playwright install chromium'?")

    out = report_step(profile_dir)
    print(f"\n=== Listo. Reporte: {out} ===")
    webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
