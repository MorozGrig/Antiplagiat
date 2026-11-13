"""Модели SQLAlchemy (100% соответствие схеме PostgreSQL)."""

from app.models.enums import (
    CertificateStatus,
    CheckMethod,
    DisputeStatus,
    MaterialStatus,
    ProcessingStatus,
    UserRole,
    UserStatus,
)
from app.models.models import (
    ALL_MODELS,
    Base,
    Certificate,
    CopyrightDispute,
    Material,
    MaterialHash,
    MaterialTextContent,
    ProcessingLog,
    SimilarityCheck,
    User,
    registration_number_seq,
)

__all__ = [
    "Base",
    "User",
    "Material",
    "MaterialTextContent",
    "MaterialHash",
    "SimilarityCheck",
    "Certificate",
    "CopyrightDispute",
    "ProcessingLog",
    "registration_number_seq",
    "ALL_MODELS",
    "UserRole",
    "UserStatus",
    "MaterialStatus",
    "ProcessingStatus",
    "CertificateStatus",
    "CheckMethod",
    "DisputeStatus",
]
