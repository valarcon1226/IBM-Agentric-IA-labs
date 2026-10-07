import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = os.environ.get("JOBS_DB_PATH", "./data/jobs.db")
# Default: sibling jobHunter/CVs_Listos next to this project's own folder.
CVS_DIR = Path(os.environ.get(
    "CVS_DIR",
    str(Path(__file__).resolve().parent.parent / "jobHunter" / "CVs_Listos"),
)).resolve()
# Planes de estudio del tailor: jobHunter/study_guides/STUDY_GUIDE_<empresa>_<id>.txt
STUDY_DIR = CVS_DIR.parent / "study_guides"
# Mismo clasificador de rol que usa jobHunter: su código (no la carpeta del perfil, donde están los datos)
import sys
sys.path.insert(0, os.environ.get("JOBHUNTER_CODE_DIR", str(CVS_DIR.parent)))
from archetypes import ARCHETYPE_LABELS, classify_archetype  # noqa: E402
STUDY_MIN_MATCH, STUDY_MAX_MATCH = 50, 90  # plan solo de 50 a 89%; de 90 para arriba basta con los gaps


def study_guides_by_id() -> dict:
    if not STUDY_DIR.is_dir():
        return {}
    return {p.stem.rsplit("_", 1)[-1]: p for p in STUDY_DIR.glob("STUDY_GUIDE_*.txt")}

app = FastAPI(title="Hustles Dashboard API")


class AppliedPayload(BaseModel):
    applied: bool


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_available() -> bool:
    return Path(DB_PATH).is_file()


def ensure_applied_column(conn, table: str):
    """Migración idempotente: agrega applied_at si la tabla ya existía sin ella.
    Mismo patrón que la migración de tailored_json en jobHunter/database.py."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "applied_at" not in existing_cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN applied_at TEXT")
        conn.commit()


@app.on_event("startup")
def migrate_on_startup():
    if not db_available():
        return
    conn = get_conn()
    try:
        ensure_applied_column(conn, "jobs")
        ensure_applied_column(conn, "freelance_gigs")
    finally:
        conn.close()


def set_applied(table: str, item_id: int, applied: bool):
    """Marca/desmarca applied_at para una fila. Devuelve (encontrada, applied_at)."""
    conn = get_conn()
    try:
        ensure_applied_column(conn, table)
        applied_at = datetime.now(timezone.utc).isoformat() if applied else None
        cur = conn.cursor()
        cur.execute(f"UPDATE {table} SET applied_at = ? WHERE id = ?", (applied_at, item_id))
        conn.commit()
        return cur.rowcount > 0, applied_at
    finally:
        conn.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "db_path": DB_PATH, "db_available": db_available(), "cvs_dir": str(CVS_DIR)}


@app.get("/api/jobs")
def get_jobs():
    if not db_available():
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, title, company, status, match_percentage, url, scraped_content,
                  cv_path, created_at, gap_analysis, applied_at, location, cv_link
           FROM jobs
           WHERE id >= 3 AND status != 'No Elegible'
           ORDER BY match_percentage DESC, id DESC"""
    )
    rows = cur.fetchall()
    conn.close()

    guides = study_guides_by_id()
    jobs = []
    for r in rows:
        gaps = [g.strip() for g in (r["gap_analysis"] or "").split(",") if g.strip()]
        jobs.append({
            "id": r["id"],
            "title": r["title"] or "",
            "company": r["company"] or "",
            "status": r["status"] or "",
            "match_percentage": r["match_percentage"] or 0,
            "url": r["url"] or "",
            "scraped_content": r["scraped_content"] or "",
            "cv_path": r["cv_path"] or "",
            "created_at": r["created_at"] or "",
            "gaps": gaps,
            "applied_at": r["applied_at"],
            "location": r["location"] or "",
            "cv_link": r["cv_link"] or "",
            "role": classify_archetype(r["title"]),
            "role_label": ARCHETYPE_LABELS[classify_archetype(r["title"])],
            "has_study": str(r["id"]) in guides and STUDY_MIN_MATCH <= (r["match_percentage"] or 0) < STUDY_MAX_MATCH,
        })
    return jobs


@app.get("/api/study/{job_id}")
def get_study(job_id: int):
    path = study_guides_by_id().get(str(job_id))
    if not path:
        raise HTTPException(status_code=404, detail="No study plan for this job")
    return FileResponse(path, media_type="text/plain; charset=utf-8")


@app.post("/api/jobs/{job_id}/applied")
def set_job_applied(job_id: int, payload: AppliedPayload):
    if not db_available():
        raise HTTPException(status_code=404, detail="DB not available")
    found, applied_at = set_applied("jobs", job_id, payload.applied)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "id": job_id, "applied_at": applied_at}


@app.get("/api/cv/{job_id}")
def get_cv(job_id: int):
    if not db_available():
        raise HTTPException(status_code=404, detail="DB not available")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cv_path FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row["cv_path"]:
        raise HTTPException(status_code=404, detail="No CV recorded for this job")

    # cv_path in the DB can be a stale absolute path (predates a project folder
    # rename), so resolve by filename against CVS_DIR instead of trusting it.
    # Split on both separators: rows written on Windows keep "C:\...\CV.pdf" paths,
    # which os.path.basename on Linux (homelab) would not split.
    filename = row["cv_path"].replace("\\", "/").rsplit("/", 1)[-1]
    candidate = (CVS_DIR / filename).resolve()
    if candidate.parent != CVS_DIR or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"CV file '{filename}' not found in {CVS_DIR}")
    return FileResponse(candidate, media_type="application/pdf", filename=filename)


@app.get("/api/freelance")
def get_freelance():
    if not db_available():
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, url, platform, title, description, status, match_percentage, category,
                  reasoning, created_at, applied_at, posted_at, closes_at
           FROM freelance_gigs
           ORDER BY match_percentage DESC, id DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/freelance/{gig_id}/applied")
def set_gig_applied(gig_id: int, payload: AppliedPayload):
    if not db_available():
        raise HTTPException(status_code=404, detail="DB not available")
    found, applied_at = set_applied("freelance_gigs", gig_id, payload.applied)
    if not found:
        raise HTTPException(status_code=404, detail="Gig not found")
    return {"ok": True, "id": gig_id, "applied_at": applied_at}


@app.get("/api/learning")
def get_learning():
    """Plan de aprendizaje que escribe jobHunter/learning_plan.py (gaps agrupados + horas al mínimo viable)."""
    path = CVS_DIR.parent / "learning_plan.json"
    if not path.is_file():
        return []
    import json
    skills = json.loads(path.read_text(encoding="utf-8")).get("skills", [])
    return [{"id": i, **s} for i, s in enumerate(skills)]


@app.get("/api/signals")
def get_signals():
    """Todo lo que pidió el mercado en 30 días (una fila por vacante/gig analizado), para explorar y filtrar."""
    if not db_available():
        return []
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(demand_signals)")}
    opt = {c: f"s.{c}" if c in cols else "NULL" for c in ("budget", "hustle", "title")}
    rows = conn.execute(
        f"""SELECT s.source_url, s.source, s.domain, s.task, s.deliverable, s.automatable, s.competition,
                   {opt['budget']} AS budget, {opt['hustle']} AS hustle, s.extracted_at,
                   COALESCE({opt['title']}, (SELECT title FROM freelance_gigs WHERE url = s.source_url LIMIT 1),
                            (SELECT title FROM jobs WHERE url = s.source_url LIMIT 1)) AS title
            FROM demand_signals s WHERE s.extracted_at > datetime('now', '-30 days')"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/trends")
def get_trends():
    if not db_available():
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, trend_name, demand_mentions, estimated_automation_score,
                  agent_idea, gigs_analyzed, detected_at
           FROM market_trends
           ORDER BY demand_mentions DESC, id DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Mounted last so it never shadows the /api/* routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
