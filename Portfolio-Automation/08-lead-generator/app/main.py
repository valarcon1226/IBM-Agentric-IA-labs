from fastapi import Depends, FastAPI, HTTPException

from app.database import check_dependencies
from app.routers.jobs import router as jobs_router
from app.routers.leads import router as leads_router
from app.security import verify_api_key


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="B2B Lead Generator")

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        try:
            await check_dependencies()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
        return {"status": "healthy"}

    fastapi_app.include_router(jobs_router, dependencies=[Depends(verify_api_key)])
    fastapi_app.include_router(leads_router, dependencies=[Depends(verify_api_key)])

    return fastapi_app


app = create_app()
