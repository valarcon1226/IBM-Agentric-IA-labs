"""API: create a report with either engine, poll it until it is done."""

import json
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app import config
from app.crews import autogen_team, crewai_crew

ENGINES = {"crewai": crewai_crew.run, "autogen": autogen_team.run}

if config.DATABASE_URL.startswith("sqlite:///"):
    Path(config.DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(config.DATABASE_URL)


class Base(DeclarativeBase):
    pass


class ReportRow(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(300))
    engine: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | completed | failed
    result: Mapped[str | None] = mapped_column(Text, default=None)  # Report JSON, or the error message


Base.metadata.create_all(engine)
app = FastAPI(title="Multi-agent research crews")


class ReportRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    engine: Literal["crewai", "autogen"]


def _generate(report_id: int) -> None:
    # Own session: the request's session is closed by the time a background task runs.
    with Session(engine) as db:
        row = db.get(ReportRow, report_id)
        try:
            row.result = ENGINES[row.engine](row.topic).model_dump_json()
            row.status = "completed"
        except Exception as e:  # the API reports the failure instead of leaving the job pending
            row.result, row.status = f"{type(e).__name__}: {e}", "failed"
        db.commit()


def _out(row: ReportRow) -> dict:
    done = row.status == "completed"
    return {
        "id": row.id,
        "topic": row.topic,
        "engine": row.engine,
        "status": row.status,
        "report": json.loads(row.result) if done else None,
        "error": row.result if row.status == "failed" else None,
    }


@app.post("/reports", status_code=202)
def create_report(req: ReportRequest, background: BackgroundTasks) -> dict:
    with Session(engine) as db:
        row = ReportRow(topic=req.topic.strip(), engine=req.engine)
        db.add(row)
        db.commit()
        db.refresh(row)
        background.add_task(_generate, row.id)
        return _out(row)


@app.get("/reports/{report_id}")
def get_report(report_id: int) -> dict:
    with Session(engine) as db:
        row = db.get(ReportRow, report_id)
        if row is None:
            raise HTTPException(404, "Report not found")
        return _out(row)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
