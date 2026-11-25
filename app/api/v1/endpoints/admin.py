"""Administrator-only registry management API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.db.database import get_db
from app.models.enums import DisputeStatus, MaterialStatus
from app.models.models import CopyrightDispute, Material, ProcessingLog, User
from app.schemas.admin import (
    AdminMaterialResponse,
    AdminMaterialUpdate,
    AdminUserResponse,
    AdminUserUpdate,
)

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[AdminUserResponse], summary="Список пользователей")
async def list_users(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
) -> list[AdminUserResponse]:
    query = select(User).order_by(User.created_at.desc())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where((User.username.ilike(pattern)) | (User.email.ilike(pattern)))
    result = await session.scalars(query.limit(limit).offset(offset))
    return [AdminUserResponse.model_validate(user) for user in result.all()]


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Изменить статус пользователя",
)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminUserResponse:
    if payload.status is None:
        raise HTTPException(status_code=422, detail="Необходимо указать новый статус")
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Нельзя менять собственный статус через этот API")
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.status = payload.status
    await session.flush()
    await session.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.get(
    "/materials",
    response_model=list[AdminMaterialResponse],
    summary="Список материалов реестра",
)
async def list_materials(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    material_status: MaterialStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=1, max_length=255),
) -> list[AdminMaterialResponse]:
    query = select(Material).order_by(Material.created_at.desc())
    if material_status is not None:
        query = query.where(Material.status == material_status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            (Material.title.ilike(pattern))
            | (Material.registration_number.ilike(pattern))
            | (Material.sha256_hash == search.strip())
        )
    result = await session.scalars(query.limit(limit).offset(offset))
    return [AdminMaterialResponse.model_validate(material) for material in result.all()]


@router.patch(
    "/materials/{material_id}",
    response_model=AdminMaterialResponse,
    summary="Изменить статус и публичность материала",
)
async def update_material(
    material_id: UUID,
    payload: AdminMaterialUpdate,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminMaterialResponse:
    if payload.status is None and payload.is_public is None:
        raise HTTPException(status_code=422, detail="Необходимо передать status или is_public")
    material = await session.scalar(
        select(Material).where(Material.id == material_id).with_for_update()
    )
    if material is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if payload.status is not None:
        material.status = payload.status
    if payload.is_public is not None:
        material.is_public = payload.is_public
    await session.flush()
    await session.refresh(material)
    return AdminMaterialResponse.model_validate(material)


@router.get("/stats", summary="Сводная статистика реестра")
async def registry_stats(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    users_count = await session.scalar(select(func.count()).select_from(User))
    materials_count = await session.scalar(select(func.count()).select_from(Material))
    disputes_count = await session.scalar(
        select(func.count()).select_from(CopyrightDispute)
    )
    pending_disputes = await session.scalar(
        select(func.count())
        .select_from(CopyrightDispute)
        .where(CopyrightDispute.status == DisputeStatus.pending)
    )
    return {
        "users_total": int(users_count or 0),
        "materials_total": int(materials_count or 0),
        "disputes_total": int(disputes_count or 0),
        "disputes_pending": int(pending_disputes or 0),
    }


@router.get("/processing-log", summary="Журнал обработки материалов")
async def processing_log(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    material_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    query = select(ProcessingLog).order_by(ProcessingLog.started_at.desc())
    if material_id is not None:
        query = query.where(ProcessingLog.material_id == material_id)
    result = await session.scalars(query.limit(limit).offset(offset))
    return [
        {
            "id": row.id,
            "material_id": row.material_id,
            "step": row.step,
            "status": row.status,
            "details": row.details,
            "error_message": row.error_message,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }
        for row in result.all()
    ]
