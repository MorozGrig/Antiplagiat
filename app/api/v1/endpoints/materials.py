"""Material registration and lookup API routes."""
from __future__ import annotations
from sqlalchemy import func, select
from urllib.parse import urlparse

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import AppError, DuplicateMaterialError
from app.db.database import get_db
from app.models.enums import UserRole
from app.models.models import Certificate, Material, SimilarityCheck, User
from app.schemas.materials import (
    DuplicateMaterialResponse,
    MaterialDetailResponse,
    MaterialListPageResponse,
    MaterialRegistrationResponse,
)
from app.services.material_service import register_material
from app.services.storage_service import StorageService, get_storage_service
# Configure the Redis-backed default Celery app before resolving shared_task.
from app.workers.celery_app import celery_app  # noqa: F401
from app.workers.tasks_processing import process_material

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post(
    "",
    response_model=MaterialRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать авторский материал",
    responses={
        409: {"model": DuplicateMaterialResponse, "description": "Точный дубликат SHA-256"},
        422: {"description": "Некорректный файл или параметры"},
    },
)
async def create_material(
    file: UploadFile = File(..., description="Файл материала"),
    current_user: User = Depends(get_current_user),
    title: str = Form(..., min_length=1, max_length=255),
    category: str = Form(..., min_length=1, max_length=100),
    description: str | None = Form(None, max_length=10000),
    tags: list[str] | None = Form(None),
    session: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> MaterialRegistrationResponse:
    """Register file, reject exact SHA-256 duplicates, then enqueue processing.

    The author is always derived from the authenticated JWT subject.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Необходимо передать имя файла",
        )

    try:
        result = await register_material(
            session=session,
            storage=storage,
            upload=file,
            author_id=current_user.id,
            title=title.strip(),
            category=category.strip(),
            description=description,
            tags=tags,
        )
        # Ensure the material is committed before the worker can read it.
        await session.commit()
    except DuplicateMaterialError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.to_payload(),
        ) from exc
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_payload()) from exc
    except Exception:
        logger.exception("Material registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось зарегистрировать материал",
        )

    task_id: str | None = None
    try:
        async_result = process_material.delay(result.material_id)
        task_id = str(async_result.id)
    except Exception:
        # The database record is already committed. Do not pretend registration
        # failed; leave processing_status=pending for an operational retry.
        logger.exception(
            "Material %s registered but Celery task could not be queued",
            result.material_id,
        )

    return MaterialRegistrationResponse(
        material_id=result.material_id,
        registration_number=result.registration_number,
        sha256_hash=result.sha256_hash,
        file_type=result.file_type,
        file_size_bytes=result.file_size_bytes,
        title=result.title,
        status=result.status,
        processing_status=result.processing_status,
        created_at=result.created_at,
        task_id=task_id,
    )


@router.get(
    "",
    response_model=MaterialListPageResponse,
    summary="Получить список авторских материалов",
)
async def list_materials(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaterialListPageResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = select(Material)
    count_query = select(func.count(Material.id))

    if current_user.role != UserRole.admin:
        query = query.where(Material.author_id == current_user.id)
        count_query = count_query.where(Material.author_id == current_user.id)

    total = await session.scalar(count_query)

    result = await session.scalars(
        query.order_by(Material.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return MaterialListPageResponse(
        items=list(result.all()),
        total=total or 0,
        limit=limit,
        offset=offset,
    )

@router.get(
    "/{material_id}/certificate/download",
    summary="Скачать PDF-свидетельство о проверке уникальности",
)
async def download_material_certificate(
    material_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    material = await session.get(Material, material_id)

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Материал не найден",
        )

    if material.author_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав",
        )

    certificate = await session.scalar(
        select(Certificate).where(Certificate.material_id == material_id)
    )

    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сертификат ещё не создан",
        )

    if certificate.status.value != "valid":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Сертификат отозван",
        )

    parsed_path = urlparse(certificate.pdf_s3_path)
    if parsed_path.scheme != "s3" or not parsed_path.netloc or not parsed_path.path.lstrip("/"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Некорректный путь к файлу сертификата",
        )

    try:
        pdf_bytes = await run_in_threadpool(
            storage.download_bytes,
            key=parsed_path.path.lstrip("/"),
            bucket=parsed_path.netloc,
        )
    except Exception:
        logger.exception("Could not download certificate for material %s", material_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось получить файл сертификата из хранилища",
        )

    filename = f"certificate-{certificate.certificate_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
@router.get(
    "/{material_id}",
    response_model=MaterialDetailResponse,
    summary="Получить сведения о материале",
)
async def get_material(
    material_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaterialDetailResponse:
    material = await session.get(Material, material_id)

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Материал не найден",
        )

    if material.author_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав",
        )

    query = (
        select(SimilarityCheck, Material)
        .join(
            Material,
            SimilarityCheck.matched_material_id == Material.id,
        )
        .where(SimilarityCheck.target_material_id == material_id)
        .order_by(SimilarityCheck.similarity_percentage.desc())
    )

    result = await session.execute(query)
    matches = result.all()

    response = MaterialDetailResponse.model_validate(material)
    certificate = await session.scalar(
        select(Certificate).where(Certificate.material_id == material_id)
    )

    if certificate is not None:
        response.certificate_number = certificate.certificate_number
        response.certificate_issued_at = certificate.issued_at
        response.certificate_status = certificate.status.value

    response.similarity_matches = [
        {
            "matched_material_id": matched.id,
            "matched_registration_number": matched.registration_number,
            "matched_title": matched.title,
            "similarity_percentage": float(check.similarity_percentage),
            "check_method": check.check_method.value,
        }
        for check, matched in matches
    ]

    return response
