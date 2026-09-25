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
    conn.commit()
    conn.close()

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

def save_gig(url: str, platform: str, title: str, description: str, status: str, match_percentage: int = 0, reasoning: str = "") -> bool:
    """Guarda o actualiza un gig freelance. Devuelve True si era nuevo (INSERT), False si ya existia (UPDATE)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    is_new = True
    try:
        cursor.execute('''
            INSERT INTO freelance_gigs (url, platform, title, description, status, match_percentage, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (url, platform, title, description, status, match_percentage, reasoning))
        conn.commit()
    except sqlite3.IntegrityError:
        is_new = False
        cursor.execute('''
            UPDATE freelance_gigs
            SET status = ?, match_percentage = ?, reasoning = ?
            WHERE url = ?
        ''', (status, match_percentage, reasoning, url))
        conn.commit()
    finally:
        conn.close()
    return is_new

def get_known_gig_urls() -> set:
    """Devuelve el set de URLs de gigs ya vistos (para no re-evaluar lo mismo en cada corrida)."""
    db_path = profile_paths.resolve('jobs.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM freelance_gigs')
    urls = {row[0] for row in cursor.fetchall()}
    conn.close()
    return urls

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
