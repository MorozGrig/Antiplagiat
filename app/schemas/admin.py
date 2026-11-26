"""Pydantic schemas for copyright disputes and admin operations."""
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from app.models.enums import DisputeStatus, MaterialStatus, UserStatus



class DisputeCreate(BaseModel):
    material_id: UUID
    original_material_id: UUID | None = None
    reason: str = Field(min_length=20, max_length=10000)
    evidence_url: HttpUrl | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url_length(cls, value):
        if value is not None and len(str(value)) > 512:
            raise ValueError("Ссылка на доказательство не должна превышать 512 символов")
        return value


class DisputeResolve(BaseModel):
    status: DisputeStatus = DisputeStatus.resolved
    resolution: str | None = Field(default=None, min_length=5, max_length=10000)
    moderator_comment: str | None = Field(default=None, max_length=5000)

    @field_validator("resolution", "moderator_comment", mode="before")
    @classmethod
    def clean_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_resolution(self):
        if self.status in (DisputeStatus.resolved, DisputeStatus.rejected):
            if not self.resolution:
                raise ValueError(
                    "Для разрешения или отклонения жалобы необходимо указать решение"
                )
        return self



class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    material_id: UUID
    original_material_id: UUID | None
    complainant_id: UUID
    reason: str
    evidence_url: str | None
    status: DisputeStatus
    resolution: str | None
    resolved_by: UUID | None
    moderator_comment: str | None
    created_at: datetime
    resolved_at: datetime | None


class AdminMaterialUpdate(BaseModel):
    status: MaterialStatus | None = None
    is_public: bool | None = None


class AdminUserUpdate(BaseModel):
    status: UserStatus | None = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class AdminMaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registration_number: str
    author_id: UUID
    title: str
    category: str
    status: MaterialStatus
    is_public: bool
    processing_status: str
    uniqueness_score: float | None
    sha256_hash: str
    created_at: datetime
