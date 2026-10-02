from fastapi import FastAPI, HTTPException

from app.db import check_dependencies
from app.routes import router

app = FastAPI(title="Smart Data Intake")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        check_dependencies()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
    return {"status": "healthy"}
