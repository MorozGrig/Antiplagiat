"""Public certificate verification endpoints (no authentication required)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.database import get_db
from app.models.enums import CertificateStatus, MaterialStatus, ProcessingStatus
from app.models.models import Certificate

router = APIRouter(prefix="/public/verification", tags=["Public verification"])


class PublicVerificationResponse(BaseModel):
    """Only information intended for public disclosure."""

    model_config = ConfigDict(from_attributes=True)

    verified: bool
    certificate_number: str
    registration_number: str
    material_title: str
    category: str
    author_name: str
    sha256_hash: str
    uniqueness_score: float
    issued_at: datetime
    certificate_status: str


@router.get(
    "/{certificate_number}",
    response_model=PublicVerificationResponse,
    summary="Публичная проверка подлинности свидетельства",
    responses={
        404: {"description": "Свидетельство не найдено или не является публичным"},
        410: {"description": "Свидетельство отозвано"},
    },
)
async def verify_certificate(
    certificate_number: str,
    session: AsyncSession = Depends(get_db),
) -> PublicVerificationResponse:
    """Verify a certificate by its public number.

    Private fields (author email/ID, S3 path, internal material ID, raw text)
    are deliberately not returned. Non-public or blocked materials are
    indistinguishable from unknown certificates.
    """
    certificate = await session.scalar(
        select(Certificate)
        .options(joinedload(Certificate.material).joinedload("author"))
        .where(Certificate.certificate_number == certificate_number)
    )
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Свидетельство не найдено",
        )

    material = certificate.material
    if (
        not material.is_public
        or material.status != MaterialStatus.active
        or material.processing_status != ProcessingStatus.completed
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Свидетельство не найдено",
        )

    if certificate.status != CertificateStatus.valid:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Свидетельство отозвано",
        )

    if material.uniqueness_score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сведения о свидетельстве недоступны",
        )

    return PublicVerificationResponse(
        verified=True,
        certificate_number=certificate.certificate_number,
        registration_number=material.registration_number,
        material_title=material.title,
        category=material.category,
        author_name=material.author.username,
        sha256_hash=material.sha256_hash,
        uniqueness_score=float(material.uniqueness_score),
        issued_at=certificate.issued_at,
        certificate_status=certificate.status.value,
    )


@router.get(
    "/registration/{registration_number}",
    response_model=PublicVerificationResponse,
    summary="Проверка свидетельства по регистрационному номеру материала",
    responses={
        404: {"description": "Публичная регистрация со свидетельством не найдена"},
        410: {"description": "Свидетельство отозвано"},
    },
)
async def verify_by_registration_number(
    registration_number: str,
    session: AsyncSession = Depends(get_db),
) -> PublicVerificationResponse:
    """Resolve the certificate number from a public material registration ID."""
    from app.models.models import Material

    certificate = await session.scalar(
        select(Certificate)
        .join(Material, Certificate.material_id == Material.id)
        .where(Material.registration_number == registration_number)
    )
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Публичная регистрация со свидетельством не найдена",
        )
    return await verify_certificate(certificate.certificate_number, session)
