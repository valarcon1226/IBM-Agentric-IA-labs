import argparse
import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_engine
from app.export.excel import write_leads_excel
from app.jobs_pipeline import run_job
from app.schemas import Lead, SourceStat


async def main():
    parser = argparse.ArgumentParser(description="B2B Lead Generator CLI")
    parser.add_argument("keyword", help="Keyword to search for")
    parser.add_argument("location", help="Location to search in")
    parser.add_argument("--out", required=True, help="Output file path (e.g. leads.xlsx)")

    args = parser.parse_args()

    session_id = uuid.uuid4()

    async with AsyncSession(get_engine()) as db:
        stmt = text("""
            INSERT INTO scraping_sessions (id, keyword, location, status)
            VALUES (:id, :keyword, :location, 'RUNNING')
        """)
        await db.execute(
            stmt, {"id": str(session_id), "keyword": args.keyword, "location": args.location}
        )
        await db.commit()

    print(f"Running job {session_id}...")
    await run_job(session_id, args.keyword, args.location)
    print("Job completed. Exporting results...")

    async with AsyncSession(get_engine()) as db:
        stmt_leads = text("""
            SELECT company_name, normalized_name, category, website, email, is_email_valid,
                   phone_raw, phone_e164, address_raw, city, lat, lng, rating, source_url,
                   lead_score
            FROM leads
            WHERE session_id = :session_id
            ORDER BY lead_score DESC
        """)
        res_leads = await db.execute(stmt_leads, {"session_id": str(session_id)})
        leads = []
        for row in res_leads.fetchall():
            row_dict = dict(row._mapping)
            row_dict["source_name"] = (
                "demo-directory" if row_dict.get("source_url") else "google-places"
            )
            leads.append(Lead(**row_dict))

        stmt_stats = text("""
            SELECT
                CASE WHEN source_url IS NOT NULL THEN 'demo-directory' ELSE 'google-places' END as source_name, 
                COUNT(*) as leads_found,
                (SELECT COUNT(*) FROM dedup_log WHERE session_id = :session_id) as duplicates_merged
            FROM leads
            WHERE session_id = :session_id
            GROUP BY source_name
        """)
        stats_res = await db.execute(stmt_stats, {"session_id": str(session_id)})
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

    write_leads_excel(leads, sources, args.out)
    print(f"Exported to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
