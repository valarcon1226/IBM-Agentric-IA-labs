import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_engine
from app.dedup import dedup_leads
from app.email_validation import is_email_valid
from app.fetching import PoliteFetcher
from app.normalization import normalize_email, normalize_name, normalize_phone, normalize_website
from app.schemas import Lead, RawLead
from app.scoring import score_lead
from app.sources.demo_directory import DemoDirectoryAdapter
from app.sources.google_places import GooglePlacesAdapter

logger = logging.getLogger(__name__)


async def run_job(session_id: UUID, keyword: str, location: str) -> None:
    async with AsyncSession(get_engine()) as db:
        try:
            raw_leads: list[RawLead] = []

            def scrape() -> list[RawLead]:
                local_leads = []
                with httpx.Client() as client:
                    try:
                        fetcher = PoliteFetcher(
                            client=client,
                            user_agent=settings.SCRAPER_USER_AGENT,
                            min_interval=1.0 / settings.SCRAPER_RATE_LIMIT_PER_SECOND,
                        )
                        demo_adapter = DemoDirectoryAdapter(
                            base_url=settings.DEMO_DIRECTORY_BASE_URL, fetcher=fetcher
                        )
                        local_leads.extend(demo_adapter.search(keyword, location))
                    except Exception:
                        logger.exception("DemoDirectoryAdapter failed")

                    if settings.GOOGLE_PLACES_API_KEY:
                        try:
                            google_adapter = GooglePlacesAdapter(client=client)
                            local_leads.extend(google_adapter.search(keyword, location))
                        except Exception:
                            logger.exception("GooglePlacesAdapter failed")

                return local_leads

            raw_leads = await asyncio.to_thread(scrape)

            leads: list[Lead] = []
            for raw in raw_leads:
                lead = Lead.from_raw(raw)
                lead.normalized_name = normalize_name(lead.company_name)
                lead.phone_e164 = normalize_phone(lead.phone_raw)
                lead.email = normalize_email(lead.email)
                lead.website = normalize_website(lead.website)
                lead.is_email_valid = is_email_valid(
                    lead.email, timeout=settings.EMAIL_MX_TIMEOUT_SECONDS
                )
                leads.append(lead)

            kept_leads, log_entries = dedup_leads(leads, settings.FUZZY_MATCH_THRESHOLD)

            for lead in kept_leads:
                lead.lead_score = score_lead(lead)

            total_found = len(kept_leads)

            for lead in kept_leads:
                stmt = text("""
                    INSERT INTO leads (
                        session_id, company_name, normalized_name, category, website, email,
                        is_email_valid, phone_raw, phone_e164, address_raw, city, lat, lng,
                        rating, source_url, lead_score
                    ) VALUES (
                        :session_id, :company_name, :normalized_name, :category, :website, :email,
                        :is_email_valid, :phone_raw, :phone_e164, :address_raw, :city, :lat, :lng,
                        :rating, :source_url, :lead_score
                    )
                    ON CONFLICT (website, phone_e164) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        company_name = EXCLUDED.company_name,
                        normalized_name = EXCLUDED.normalized_name,
                        category = EXCLUDED.category,
                        email = EXCLUDED.email,
                        is_email_valid = EXCLUDED.is_email_valid,
                        address_raw = EXCLUDED.address_raw,
                        city = EXCLUDED.city,
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        rating = EXCLUDED.rating,
                        source_url = EXCLUDED.source_url,
                        lead_score = EXCLUDED.lead_score
                    RETURNING id
                """)
                params = {
                    "session_id": str(session_id),
                    "company_name": lead.company_name,
                    "normalized_name": lead.normalized_name,
                    "category": lead.category,
                    "website": lead.website,
                    "email": lead.email,
                    "is_email_valid": lead.is_email_valid,
                    "phone_raw": lead.phone_raw,
                    "phone_e164": lead.phone_e164,
                    "address_raw": lead.address_raw,
                    "city": lead.city,
                    "lat": lead.lat,
                    "lng": lead.lng,
                    "rating": lead.rating,
                    "source_url": lead.source_url,
                    "lead_score": lead.lead_score,
                }
                res = await db.execute(stmt, params)
                surviving_lead_id = res.scalar_one()
                # store the assigned db id on the object temporarily
                lead._db_id = surviving_lead_id  # type: ignore[attr-defined]

            for entry in log_entries:
                surviving_lead_id = getattr(entry.surviving_lead, "_db_id", None)
                if surviving_lead_id:
                    stmt = text("""
                        INSERT INTO dedup_log  (session_id, surviving_lead_id, merged_lead_data, similarity_score)
                        VALUES (:session_id , :surviving_lead_id, :merged_lead_data, :similarity_score)
                    """)
                    await db.execute(
                        stmt,
                        {
                            "session_id": str(session_id),
                            "surviving_lead_id": surviving_lead_id,
                            "merged_lead_data": json.dumps(entry.merged_lead_data),
                            "similarity_score": entry.similarity_score,
                        },
                    )

            stmt = text("""
                UPDATE scraping_sessions
                SET status = 'COMPLETED', completed_at = :completed_at, total_found = :total_found
                WHERE id = :session_id
            """)
            await db.execute(
                stmt,
                {
                    "completed_at": datetime.now(UTC),
                    "total_found": total_found,
                    "session_id": str(session_id),
                },
            )

            await db.commit()

        except Exception:
            logger.exception("Job pipeline failed")
            await db.rollback()
            stmt = text("""
                UPDATE scraping_sessions
                SET status = 'FAILED', completed_at = :completed_at
                WHERE id = :session_id
            """)
            await db.execute(
                stmt, {"completed_at": datetime.now(UTC), "session_id": str(session_id)}
            )
            await db.commit()
            raise
