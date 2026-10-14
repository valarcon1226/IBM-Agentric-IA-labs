from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeploymentCreate, DeploymentModel, DeploymentUpdate


def create_deployment(db: Session, deployment_in: DeploymentCreate) -> DeploymentModel:
    """Create a new deployment record in the database."""
    db_obj = DeploymentModel(
        service_name=deployment_in.service_name,
        environment=deployment_in.environment,
        version=deployment_in.version,
        status=deployment_in.status,
        deployed_by=deployment_in.deployed_by,
        description=deployment_in.description,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_deployment(db: Session, deployment_id: int) -> DeploymentModel | None:
    """Retrieve a single deployment record by ID."""
    return db.get(DeploymentModel, deployment_id)


def list_deployments(
    db: Session,
    environment: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[DeploymentModel]:
    """List deployments with optional filtering by environment and status."""
    stmt = select(DeploymentModel)
    if environment is not None:
        stmt = stmt.where(DeploymentModel.environment == environment)
    if status is not None:
        stmt = stmt.where(DeploymentModel.status == status)
    stmt = stmt.offset(skip).limit(limit).order_by(DeploymentModel.id.desc())
    return db.scalars(stmt).all()


def update_deployment(
    db: Session,
    deployment: DeploymentModel,
    update_in: DeploymentUpdate,
) -> DeploymentModel:
    """Update an existing deployment with provided fields."""
    update_data = update_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deployment, field, value)
    db.commit()
    db.refresh(deployment)
    return deployment


def delete_deployment(db: Session, deployment: DeploymentModel) -> None:
    """Delete a deployment record from the database."""
    db.delete(deployment)
    db.commit()
