import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DeploymentModel(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    deployed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="ci-bot")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )


class DeploymentBase(BaseModel):
    service_name: Annotated[str, Field(min_length=1, max_length=100)]
    environment: Annotated[str, Field(min_length=1, max_length=50)]
    version: Annotated[str, Field(min_length=1, max_length=50)]
    status: Annotated[str, Field(default="pending", min_length=1, max_length=30)]
    deployed_by: Annotated[str, Field(default="ci-bot", min_length=1, max_length=100)]
    description: Annotated[str, Field(default="", max_length=500)]


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentUpdate(BaseModel):
    service_name: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    environment: Annotated[str | None, Field(default=None, min_length=1, max_length=50)] = None
    version: Annotated[str | None, Field(default=None, min_length=1, max_length=50)] = None
    status: Annotated[str | None, Field(default=None, min_length=1, max_length=30)] = None
    deployed_by: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    description: Annotated[str | None, Field(default=None, max_length=500)] = None


class DeploymentResponse(DeploymentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
