"""
Filtros baratos (sin LLM) que el scout aplica ANTES de evaluar una vacante, para no gastar cupo
en cosas que igual se van a descartar:
  - duplicados: misma empresa + mismo título ya guardados (aunque la URL sea distinta)
  - pasantías / trainee
  - vacantes escritas en un idioma que no está en SCOUT_ALLOWED_LANGS (default "en,es")
Cada filtro devuelve un motivo (str) si hay que descartar, o None si la vacante pasa.
"""
import os
import re
import sqlite3
import unicodedata

import profile_paths

INTERN_PATTERN = re.compile(
    r"\b(intern|internship|interns|trainee|pasant[ií]a|pr[aá]cticas|becari[oa]|est[aá]gio|"
    r"estagi[aá]ri[oa]|stagiaire|praktikant|werkstudent|apprentice|alternance)\b",
    re.IGNORECASE,
)

# Palabras funcionales muy frecuentes y casi exclusivas de cada idioma. Contar cuántas aparecen
# alcanza para distinguir el idioma de una JD entera sin sumar una dependencia nueva.
_STOPWORDS = {
    "en": {"the", "and", "with", "you", "for", "our", "will", "are", "your", "have", "of", "to"},
    "es": {"el", "los", "las", "con", "para", "una", "del", "que", "por", "como", "tu", "nuestro"},
    "pt": {"não", "você", "com", "uma", "dos", "das", "em", "voce", "nao", "nossa", "são", "também"},
    "fr": {"le", "les", "des", "avec", "pour", "une", "vous", "nous", "est", "dans", "sur", "et"},
    "de": {"der", "die", "und", "mit", "für", "wir", "sie", "ist", "ein", "eine", "auf", "zu"},
    "nl": {"het", "een", "van", "naar", "bij", "met", "voor", "wij", "jij", "ons", "zijn", "je"},
    "da": {"og", "af", "til", "med", "som", "vi", "du", "er", "på", "det", "har", "en"},
    "sv": {"och", "att", "för", "med", "som", "vi", "du", "är", "på", "det", "har", "av"},
    "no": {"og", "av", "til", "med", "som", "vi", "du", "er", "på", "det", "har", "ikke"},
    "it": {"il", "gli", "per", "nella", "questo", "della", "che", "sono", "nostro", "e", "di", "un"},
}


# Señales en el TÍTULO (sirven aunque la descripción sea corta): marcas de género legales y la
# palabra "desarrollador/ingeniero" en cada idioma.
_TITLE_HINTS = {
    "pt": re.compile(r"desenvolvedor|engenheir|intelig[eê]ncia|\bvaga\b", re.I),
    "fr": re.compile(r"d[ée]veloppeur|ing[ée]nieur|\((f/h|h/f)\)", re.I),
    "de": re.compile(r"entwickler|\(m/w/d\)|\(w/m/d\)|ingenieur\b", re.I),
    "da": re.compile(r"udvikler|l[øo]sninger|\btil\b", re.I),
    "no": re.compile(r"utvikler", re.I),
    "nl": re.compile(r"ontwikkelaar", re.I),
    "it": re.compile(r"sviluppatore|ingegnere", re.I),
}

MIN_DESCRIPTION_CHARS = 200


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def allowed_langs() -> set:
    return {l.strip() for l in os.environ.get("SCOUT_ALLOWED_LANGS", "en,es").split(",") if l.strip()}


def detect_language(text: str) -> str:
    """Idioma más probable del texto ('en', 'es', ...) o '' si no hay suficiente texto."""
    words = re.findall(r"[^\W\d_]+", (text or "").lower())[:1500]
    if len(words) < 30:
        return ""
    scores = {lang: sum(1 for w in words if w in sw) for lang, sw in _STOPWORDS.items()}
    lang, best = max(scores.items(), key=lambda kv: kv[1])
    return lang if best >= 5 else ""


def is_duplicate(title: str, company: str, url: str) -> bool:
    """True si la URL ya fue evaluada antes, o si ya hay otra con misma empresa + título."""
    conn = sqlite3.connect(profile_paths.resolve("jobs.db"))
    try:
        if conn.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone():
            return True
        rows = conn.execute("SELECT title, company FROM jobs").fetchall()
    finally:
        conn.close()
    key = (_norm(title), _norm(company))
    return any((_norm(t), _norm(c)) == key for t, c in rows)


def rejection_reason(job: dict, clean_desc: str) -> str | None:
    title, company = job.get("title", ""), job.get("company", "")
    if os.environ.get("SCOUT_EXCLUDE_INTERNS", "1") == "1" and INTERN_PATTERN.search(title):
        return "pasantía/trainee"
    allowed = allowed_langs()
    for lang, pattern in _TITLE_HINTS.items():
        if lang not in allowed and pattern.search(title):
            return f"idioma de la vacante: {lang} (título)"
    lang = detect_language(f"{title}\n{clean_desc}")
    if lang and lang not in allowed:
        return f"idioma de la vacante: {lang}"
    desc = (clean_desc or "").strip()
    if desc.lower() in ("", "nan", "none") or len(desc) < MIN_DESCRIPTION_CHARS:
        return "sin descripción (no se puede evaluar solo por el título)"
    if is_duplicate(title, company, job.get("url", "")):
        return "duplicada (URL ya evaluada, o misma empresa + título)"
    return None
