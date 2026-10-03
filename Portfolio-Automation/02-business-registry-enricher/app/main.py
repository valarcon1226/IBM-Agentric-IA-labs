import asyncio

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import ValidationError

from app.database import check_dependencies
from app.enrichment import CacheError, NotFoundError, UpstreamError, enrich
from app.models import (
    CompanyRequest,
    CompanyResult,
    EnrichBatchRequest,
    EnrichBatchResponse,
    SingleEnrichResponse,
)
from app.security import verify_api_key

app = FastAPI(title="Business Registry Enricher")


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await check_dependencies()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
    return {"status": "healthy"}


async def _enrich_for_batch(company: CompanyRequest) -> CompanyResult:
    # A failing item never aborts the batch (DECISIONES-02 E8): it just becomes a
    # not_found/error result with a short, internals-free message.
    try:
        result = await enrich(company.country, company.identifier)
    except NotFoundError:
        return CompanyResult(
            country=company.country,
            identifier=company.identifier,
            status="not_found",
            error="Company not found",
        )
    except UpstreamError:
        return CompanyResult(
            country=company.country,
            identifier=company.identifier,
            status="error",
            error="Registry temporarily unavailable",
        )
    except CacheError:
        return CompanyResult(
            country=company.country,
            identifier=company.identifier,
            status="error",
            error="Cache temporarily unavailable",
        )
    return CompanyResult(
        country=company.country,
        identifier=company.identifier,
        company_name=result["company_name"],
        status=result["status"],
        cached=result["cached"],
    )


@app.post("/api/v1/enrich", dependencies=[Depends(verify_api_key)])
async def enrich_batch(request: EnrichBatchRequest) -> EnrichBatchResponse:
    # Concurrent: per-registry limiters still cap the upstream rate; gather keeps input order.
    results = await asyncio.gather(*(_enrich_for_batch(c) for c in request.companies))
    return EnrichBatchResponse(results=list(results))


@app.get("/api/v1/enrich/{country}/{identifier}", dependencies=[Depends(verify_api_key)])
async def enrich_single(
    country: str, identifier: str, force_refresh: bool = Query(False)
) -> SingleEnrichResponse:
    try:
        company = CompanyRequest(country=country, identifier=identifier)
    except ValidationError as exc:
        # exc.errors() includes a non-serializable "ctx" (the raw ValueError instance);
        # keep only the JSON-safe fields FastAPI itself would otherwise render.
        errors = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from exc

    try:
        result = await enrich(company.country, company.identifier, force_refresh=force_refresh)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail="Registry temporarily unavailable") from exc
    except CacheError as exc:
        raise HTTPException(status_code=503, detail="Cache temporarily unavailable") from exc

    return SingleEnrichResponse(
        country=company.country,
        identifier=company.identifier,
        company_name=result["company_name"],
        status=result["status"],
        incorporation_date=result["incorporation_date"],
        raw_data=result["raw_data"],
        cached=result["cached"],
    )
