from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import check_db_health, get_db, init_db
from app.models import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentUpdate,
    HealthResponse,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.get("/", tags=["Root"])
def root_info() -> dict[str, str]:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    db_ok = check_db_health()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        database="connected" if db_ok else "disconnected",
    )


@app.post(
    "/api/v1/deployments",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Deployments"],
)
def create_deployment_endpoint(
    deployment_in: DeploymentCreate,
    db: Session = Depends(get_db),
) -> DeploymentResponse:
    obj = crud.create_deployment(db, deployment_in)
    return DeploymentResponse.model_validate(obj)


@app.get(
    "/api/v1/deployments",
    response_model=list[DeploymentResponse],
    tags=["Deployments"],
)
def list_deployments_endpoint(
    environment: str | None = Query(default=None, max_length=50),
    status: str | None = Query(default=None, max_length=30),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Sequence[DeploymentResponse]:
    items = crud.list_deployments(
        db,
        environment=environment,
        status=status,
        skip=skip,
        limit=limit,
    )
    return [DeploymentResponse.model_validate(i) for i in items]


@app.get(
    "/api/v1/deployments/{deployment_id}",
    response_model=DeploymentResponse,
    tags=["Deployments"],
)
def get_deployment_endpoint(
    deployment_id: int,
    db: Session = Depends(get_db),
) -> DeploymentResponse:
    obj = crud.get_deployment(db, deployment_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment with id {deployment_id} not found",
        )
    return DeploymentResponse.model_validate(obj)


@app.put(
    "/api/v1/deployments/{deployment_id}",
    response_model=DeploymentResponse,
    tags=["Deployments"],
)
def update_deployment_endpoint(
    deployment_id: int,
    update_in: DeploymentUpdate,
    db: Session = Depends(get_db),
) -> DeploymentResponse:
    obj = crud.get_deployment(db, deployment_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment with id {deployment_id} not found",
        )
    updated = crud.update_deployment(db, obj, update_in)
    return DeploymentResponse.model_validate(updated)


@app.delete(
    "/api/v1/deployments/{deployment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Deployments"],
)
def delete_deployment_endpoint(
    deployment_id: int,
    db: Session = Depends(get_db),
) -> None:
    obj = crud.get_deployment(db, deployment_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment with id {deployment_id} not found",
        )
    crud.delete_deployment(db, obj)
