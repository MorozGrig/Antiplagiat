"""Pydantic response schemas for material registration endpoints."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaterialRegistrationResponse(BaseModel):
    material_id: UUID
    registration_number: str
    sha256_hash: str
    file_s3_path: str
    file_type: str
    file_size_bytes: int
    title: str
    status: str
    processing_status: str
    created_at: datetime
    task_id: str | None = None


class MaterialDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_number: str
    author_id: UUID
    title: str
    description: str | None = None
    category: str
    tags: list[str] | None = None
    sha256_hash: str
    file_type: str
    file_size_bytes: int
    status: str
    processing_status: str
    uniqueness_score: float | None = None
    created_at: datetime


class DuplicateMaterialResponse(BaseModel):
    error: str = "duplicate_material"
    message: str
    details: dict = Field(default_factory=dict)
