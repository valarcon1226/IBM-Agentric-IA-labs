import csv
import io
import tempfile

from fastapi import APIRouter, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_engine
from app.export.excel import write_leads_excel
from app.schemas import Lead, SourceStat

router = APIRouter(prefix="/api/v1/leads", tags=["Leads"])


@router.get("")
async def get_leads(
    min_score: int = Query(0, ge=0, le=100), category: str | None = None, q: str | None = None
):
    async with AsyncSession(get_engine()) as db:
        conditions = ["lead_score >= :min_score"]
        from typing import Any

        params: dict[str, Any] = {"min_score": min_score}

        if category:
            conditions.append("category = :category")
            params["category"] = category

        if q:
            conditions.append(
                "to_tsvector ('english', company_name || ' ' || COALESCE(category, '')) @@ plainto_tsquery('english', :q)"
            )
            params["q"] = q

        where_clause = " AND ".join(conditions)
        stmt = text(f"""
            SELECT company_name, normalized_name, category, website, email, is_email_valid,
                   phone_raw, phone_e164, address_raw, city, lat, lng, rating, source_url,
                   lead_score
            FROM leads
            WHERE {where_clause}
            ORDER BY lead_score DESC, company_name ASC
        """)
        res = await db.execute(stmt, params)

        results = []
        for row in res.fetchall():
            row_dict = dict(row._mapping)
            row_dict["source_name"] = (
                "demo-directory" if row_dict.get("source_url") else "google-places"
            )
            results.append(row_dict)

        return results


@router.get("/export")
async def export_leads(format: str = Query("xlsx", pattern="^(xlsx|csv|json)$")):
    async with AsyncSession(get_engine()) as db:
        stmt = text("""
            SELECT company_name, normalized_name, category, website, email, is_email_valid,
                   phone_raw, phone_e164, address_raw, city, lat, lng, rating, source_url,
                   lead_score
            FROM leads
            ORDER BY lead_score DESC
        """)
        res = await db.execute(stmt)
        leads_data = []
        for row in res.fetchall():
            row_dict = dict(row._mapping)
            row_dict["source_name"] = (
                "demo-directory" if row_dict.get("source_url") else "google-places"
            )
            leads_data.append(Lead(**row_dict))

        if format == "json":
            return [lead.model_dump() for lead in leads_data]

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(Lead.model_fields.keys()))
            writer.writeheader()
            for lead in leads_data:
                writer.writerow(lead.model_dump())
            return Response(content=output.getvalue(), media_type="text/csv")

        if format == "xlsx":
            # For xlsx, calculate SourceStats
            stmt_stats = text("""
                SELECT
                    CASE WHEN source_url IS NOT NULL THEN 'demo-directory' ELSE 'google-places' END as source_name, 
                    COUNT(*) as leads_found,
                    (SELECT COUNT(*) FROM dedup_log) as duplicates_merged
                FROM leads
                GROUP BY source_name
            """)
            stats_res = await db.execute(stmt_stats)
            sources = []
            for row in stats_res.fetchall():
                sources.append(
                    SourceStat(
                        source_name=row.source_name,
                        leads_found=row.leads_found,
                        duplicates_merged=row.duplicates_merged,
                    )
                )

            if not sources:
                sources = [SourceStat(source_name="unknown", leads_found=0, duplicates_merged=0)]

            # Generate temp file
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            tmp.close()
            write_leads_excel(leads_data, sources, tmp.name)

            return FileResponse(
                tmp.name,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="leads.xlsx",
            )
