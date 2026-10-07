import re
import sqlite3
import os
import profile_paths

def init_db():
    """Inicializa la base de datos SQLite y crea la tabla si no existe."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            company TEXT,
            status TEXT,
            cover_letter TEXT,
            scraped_content TEXT,
            match_percentage INTEGER,
            gap_analysis TEXT,
            cv_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migración: agrega tailored_json si la tabla ya existía de antes (guarda el professional_summary +
    # experience que generó el LLM para cada job, para poder re-renderizar el PDF con una plantilla
    # nueva sin tener que volver a gastar cuota de Groq llamando al generador otra vez).
    cursor.execute("PRAGMA table_info(jobs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "tailored_json" not in existing_cols:
        cursor.execute("ALTER TABLE jobs ADD COLUMN tailored_json TEXT")
    if "location" not in existing_cols:  # ubicación de la oferta según LinkedIn (para el filtro de país)
        cursor.execute("ALTER TABLE jobs ADD COLUMN location TEXT")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS freelance_gigs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            platform TEXT,
            title TEXT,
            description TEXT,
            status TEXT,
            match_percentage INTEGER,
            reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    if "category" not in {r[1] for r in cursor.execute("PRAGMA table_info(freelance_gigs)")}:
        # tipo de proyecto (website, automation_integration, ai_agent...) para filtrar en el dashboard
        cursor.execute("ALTER TABLE freelance_gigs ADD COLUMN category TEXT")
    gig_cols = {r[1] for r in cursor.execute("PRAGMA table_info(freelance_gigs)")}
    for col in ("posted_at", "closes_at"):  # fechas de publicación y de cierre de propuestas (dashboard)
        if col not in gig_cols:
            cursor.execute(f"ALTER TABLE freelance_gigs ADD COLUMN {col} TEXT")
    if "missing_skills" not in {r[1] for r in cursor.execute("PRAGMA table_info(freelance_gigs)")}:
        cursor.execute("ALTER TABLE freelance_gigs ADD COLUMN missing_skills TEXT")  # skills que le faltan (plan de aprendizaje)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_name TEXT,
            demand_mentions INTEGER,
            estimated_automation_score TEXT,
            agent_idea TEXT,
            gigs_analyzed INTEGER,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Qué problema/tarea pide cada vacante o gig (lo extrae el modelo local, una sola vez por URL).
    # Es la materia prima del Trend Spotter: se agrupa por (domain, task) para ver qué nichos se repiten.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demand_signals (
            source_url TEXT PRIMARY KEY,
            source TEXT,
            domain TEXT,
            task TEXT,
            deliverable TEXT,
            automatable TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    if "hustle" not in {r[1] for r in cursor.execute("PRAGMA table_info(demand_signals)")}:
        cursor.execute("ALTER TABLE demand_signals ADD COLUMN hustle TEXT")  # side hustle del video (trend spotter)
    if "competition" not in {r[1] for r in cursor.execute("PRAGMA table_info(demand_signals)")}:
        cursor.execute("ALTER TABLE demand_signals ADD COLUMN competition INTEGER")  # propuestas que tenía el gig
    # URLs de gigs ya evaluados y borrados (purge_discarded_gigs): solo para no volver a evaluarlos
    cursor.execute("CREATE TABLE IF NOT EXISTS seen_gig_urls (url TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def get_signal_urls() -> set:
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    urls = {r[0] for r in conn.execute('SELECT source_url FROM demand_signals')}
    conn.close()
    return urls

def save_signal(source_url: str, source: str, domain: str, task: str, deliverable: str, automatable: str,
                hustle: str = None, competition: int = None):
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    conn.execute('INSERT OR IGNORE INTO demand_signals (source_url, source, domain, task, deliverable, automatable, hustle, competition) '
                 'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (source_url, source, domain, task, deliverable, automatable, hustle, competition))
    conn.commit()
    conn.close()

def get_signals(days: int) -> list:
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM demand_signals WHERE extracted_at > datetime('now', ?)", (f'-{days} days',)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_market_items() -> list:
    """Vacantes y gigs guardados como {url, source, title, description} — la demanda ya vista."""
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    rows = conn.execute("SELECT url, 'job', title, scraped_content FROM jobs WHERE url IS NOT NULL "
                        "UNION ALL SELECT url, 'gig', title, description FROM freelance_gigs WHERE url IS NOT NULL").fetchall()
    conn.close()
    return [{"url": r[0], "source": r[1], "title": r[2] or "", "description": r[3] or ""} for r in rows]

def hours_since_last_trend() -> float:
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    row = conn.execute("SELECT (julianday('now') - julianday(MAX(detected_at))) * 24 FROM market_trends").fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else float("inf")

def save_trend(trend_name: str, demand_mentions: int, estimated_automation_score: str, agent_idea: str, gigs_analyzed: int):
    """Guarda una tendencia detectada. No hace dedup (cada corrida es una observación con su propia fecha)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO market_trends (trend_name, demand_mentions, estimated_automation_score, agent_idea, gigs_analyzed)
        VALUES (?, ?, ?, ?, ?)
    ''', (trend_name, demand_mentions, estimated_automation_score, agent_idea, gigs_analyzed))
    conn.commit()
    conn.close()

def get_recent_trends(limit: int = 50) -> list:
    """Recupera las tendencias detectadas más recientes."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM market_trends ORDER BY detected_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_gig(url: str, platform: str, title: str, description: str, status: str, match_percentage: int = 0, reasoning: str = "",
             category: str = None, missing_skills: str = None, posted_at: str = None, closes_at: str = None) -> bool:
    """Guarda o actualiza un gig freelance. Devuelve True si era nuevo (INSERT), False si ya existia (UPDATE)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    is_new = True
    try:
        cursor.execute('''
            INSERT INTO freelance_gigs (url, platform, title, description, status, match_percentage, reasoning, category, missing_skills,
                                        posted_at, closes_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (url, platform, title, description, status, match_percentage, reasoning, category, missing_skills, posted_at, closes_at))
        conn.commit()
    except sqlite3.IntegrityError:
        is_new = False
        cursor.execute('''
            UPDATE freelance_gigs
            SET status = ?, match_percentage = ?, reasoning = ?, category = COALESCE(?, category),
                missing_skills = COALESCE(?, missing_skills), posted_at = COALESCE(?, posted_at), closes_at = COALESCE(?, closes_at)
            WHERE url = ?
        ''', (status, match_percentage, reasoning, category, missing_skills, posted_at, closes_at, url))
        conn.commit()
    finally:
        conn.close()
    return is_new

def get_known_gig_urls() -> set:
    """Devuelve el set de URLs de gigs ya vistos (para no re-evaluar lo mismo en cada corrida)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM freelance_gigs UNION SELECT url FROM seen_gig_urls')
    urls = {row[0] for row in cursor.fetchall()}
    conn.close()
    return urls


def purge_discarded_gigs() -> int:
    """Borra los gigs descartados que ya no aportan nada: los que el Trend Spotter ya leyó (su señal queda en
    demand_signals) y los fuera de rubro / otro idioma. Antes guarda su URL (para no re-evaluarlos) y pasa la
    cantidad de propuestas a la señal (dato de competencia del Trend Spotter). Los aplicados nunca se borran."""
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(freelance_gigs)")}
    not_applied = "AND applied_at IS NULL" if "applied_at" in cols else ""
    where = (f"status = 'Descartado' {not_applied} AND (url IN (SELECT source_url FROM demand_signals) "
             "OR reasoning LIKE '[Filtro] fuera de rubro%' OR reasoning LIKE '[Filtro] idioma%')")
    bids = re.compile(r"(\d+) propuestas|demasiada competencia \((\d+)\)")
    for url, reasoning in conn.execute(f"SELECT url, reasoning FROM freelance_gigs WHERE {where}").fetchall():
        m = bids.search(reasoning or "")
        if m:
            conn.execute("UPDATE demand_signals SET competition = COALESCE(competition, ?) WHERE source_url = ?",
                         (int(m.group(1) or m.group(2)), url))
    conn.execute(f"INSERT OR IGNORE INTO seen_gig_urls (url) SELECT url FROM freelance_gigs WHERE {where}")
    n = conn.execute(f"DELETE FROM freelance_gigs WHERE {where}").rowcount
    conn.commit()
    if n:
        conn.execute("VACUUM")  # devuelve el espacio al disco
    conn.close()
    return n

def get_applicable_gigs() -> list:
    """Recupera los gigs freelance marcados como aplicables para ti."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freelance_gigs WHERE status = "Aplicable" ORDER BY match_percentage DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def set_job_location(url: str, location: str):
    if not location:
        return
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    conn.execute("UPDATE jobs SET location = ? WHERE url = ?", (location, url))
    conn.commit()
    conn.close()

def save_job(url: str, title: str, company: str, status: str = "Encontrado", cover_letter: str = None, scraped_content: str = None, match_percentage: int = 0, gap_analysis: str = "", cv_path: str = None) -> bool:
    """Guarda o actualiza una vacante en la base de datos. Devuelve True si era una vacante nueva (INSERT), False si ya existia (UPDATE)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    is_new = True
    try:
        cursor.execute('''
            INSERT INTO jobs (url, title, company, status, cover_letter, scraped_content, match_percentage, gap_analysis, cv_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (url, title, company, status, cover_letter, scraped_content, match_percentage, gap_analysis, cv_path))
        conn.commit()
    except sqlite3.IntegrityError:
        # Si la URL ya existe, la actualizamos — pero sin hacer retroceder el estado: si el scout
        # re-encuentra una vacante que ya tiene CV (o que el tailor marcó No Elegible), antes la
        # devolvía a 'Aprobado' y el tailor la regeneraba de cero gastando cupo.
        is_new = False
        cursor.execute('''
            UPDATE jobs
            SET status = CASE WHEN status IN ('CV Generado', 'No Elegible', 'Match Insuficiente', 'Filtrado')
                              THEN status ELSE ? END,
                cover_letter = COALESCE(?, cover_letter),
                title = COALESCE(?, title),
                company = COALESCE(?, company),
                scraped_content = COALESCE(?, scraped_content),
                match_percentage = COALESCE(?, match_percentage),
                gap_analysis = COALESCE(?, gap_analysis),
                cv_path = COALESCE(?, cv_path)
            WHERE url = ?
        ''', (status, cover_letter, title, company, scraped_content, match_percentage, gap_analysis, cv_path, url))
        conn.commit()
    finally:
        conn.close()
    return is_new

def get_approved_jobs() -> list:
    """Recupera todos los trabajos que están aprobados y listos para sastre."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs WHERE status = "Aprobado" ORDER BY match_percentage DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_low_match_jobs(min_match: int, max_match: int) -> list:
    """Vacantes visibles sin CV (Match Insuficiente) con match en [min_match, max_match)."""
    conn = sqlite3.connect(profile_paths.resolve('jobs.db'))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM jobs WHERE status = 'Match Insuficiente' AND match_percentage >= ? "
                        "AND match_percentage < ? ORDER BY match_percentage DESC", (min_match, max_match)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_job_status(url: str, new_status: str, cv_path: str = None, tailored_json: str = None):
    """Actualiza el estado, ruta del CV, y opcionalmente el JSON tailored (summary+experience) de un job."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if cv_path and tailored_json:
        cursor.execute('UPDATE jobs SET status = ?, cv_path = ?, tailored_json = ? WHERE url = ?', (new_status, cv_path, tailored_json, url))
    elif cv_path:
        cursor.execute('UPDATE jobs SET status = ?, cv_path = ? WHERE url = ?', (new_status, cv_path, url))
    else:
        cursor.execute('UPDATE jobs SET status = ? WHERE url = ?', (new_status, url))
    conn.commit()
    conn.close()

def get_job_by_url(url: str):
    """Recupera la informacion de una vacante por su URL."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs WHERE url = ?', (url,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None
