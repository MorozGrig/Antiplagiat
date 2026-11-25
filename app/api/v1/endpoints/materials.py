"""Material registration and lookup API routes."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, DuplicateMaterialError
from app.db.database import get_db
from app.models.models import Material
from app.schemas.materials import (
    DuplicateMaterialResponse,
    MaterialDetailResponse,
    MaterialRegistrationResponse,
)
from app.services.material_service import register_material
from app.services.storage_service import StorageService, get_storage_service
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
    author_id: UUID = Form(..., description="UUID автора"),
    title: str = Form(..., min_length=1, max_length=255),
    category: str = Form(..., min_length=1, max_length=100),
    description: str | None = Form(None, max_length=10000),
    tags: list[str] | None = Form(None),
    session: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> MaterialRegistrationResponse:
    """Register file, reject exact SHA-256 duplicates, then enqueue processing.

    Authentication is not wired in the current project snapshot. Until an
    auth dependency is implemented, author_id is supplied explicitly as form
    data; the database FK remains the final check that this user exists.
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
            author_id=author_id,
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
        file_s3_path=result.file_s3_path,
        file_type=result.file_type,
        file_size_bytes=result.file_size_bytes,
        title=result.title,
        status=result.status,
        processing_status=result.processing_status,
        created_at=result.created_at,
        task_id=task_id,
    )


@router.get(
    "/{material_id}",
    response_model=MaterialDetailResponse,
    summary="Получить сведения о материале",
)
async def get_material(
    material_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> MaterialDetailResponse:
    material = await session.get(Material, material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Материал не найден",
        )
    return MaterialDetailResponse.model_validate(material)
