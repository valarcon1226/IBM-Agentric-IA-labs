import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_engine
from app.jobs_pipeline import run_job

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


class JobRequest(BaseModel):
    keyword: str
    location: str


class JobResponse(BaseModel):
    id: UUID
    status: str
    keyword: str
    location: str
    total_found: int
    started_at: datetime
    completed_at: datetime | None = None


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(req: JobRequest, background_tasks: BackgroundTasks):
    session_id = uuid.uuid4()

    async with AsyncSession(get_engine()) as db:
        stmt = text("""
            INSERT INTO scraping_sessions (id, keyword, location, status)
            VALUES (:id, :keyword, :location, 'RUNNING')
            RETURNING id, keyword, location, status, total_found, started_at, completed_at
        """)
        res = await db.execute(
            stmt, {"id": str(session_id), "keyword": req.keyword, "location": req.location}
        )
        row = res.fetchone()
        await db.commit()

    background_tasks.add_task(run_job, session_id, req.keyword, req.location)

    if not row:
        raise HTTPException(status_code=500, detail="Failed to create job")
    row_map = row._mapping
    return {
        "id": row_map["id"],
        "keyword": row_map["keyword"],
        "location": row_map["location"],
        "status": row_map["status"],
        "total_found": row_map["total_found"],
        "started_at": row_map["started_at"],
        "completed_at": row_map["completed_at"],
    }


@router.get("/{id}", response_model=JobResponse)
async def get_job(id: UUID):
    async with AsyncSession(get_engine()) as db:
        stmt = text("""
            SELECT id, keyword, location, status, total_found, started_at, completed_at
            FROM scraping_sessions
            WHERE id = :id
        """)
        res = await db.execute(stmt, {"id": str(id)})
        row = res.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        row_map = row._mapping
        return {
            "id": row_map["id"],
            "keyword": row_map["keyword"],
            "location": row_map["location"],
            "status": row_map["status"],
            "total_found": row_map["total_found"],
            "started_at": row_map["started_at"],
            "completed_at": row_map["completed_at"],
        }
