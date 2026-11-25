"""Copyright dispute submission and moderation API."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.dependencies import get_current_user, require_moderator
from app.db.database import get_db
from app.models.enums import DisputeStatus
from app.models.models import CopyrightDispute, Material, User
from app.schemas.admin import DisputeCreate, DisputeResolve, DisputeResponse

router = APIRouter(prefix="/disputes", tags=["Copyright disputes"])


@router.post(
    "",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Подать спор о нарушении авторских прав",
)
async def create_dispute(
    payload: DisputeCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DisputeResponse:
    material = await session.get(Material, payload.material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if payload.original_material_id == payload.material_id:
        raise HTTPException(status_code=422, detail="Нельзя указать один материал как оригинал и спорный")
    if payload.original_material_id is not None:
        original = await session.get(Material, payload.original_material_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Предполагаемый оригинал не найден")

    dispute = CopyrightDispute(
        material_id=payload.material_id,
        original_material_id=payload.original_material_id,
        complainant_id=current_user.id,
        reason=payload.reason,
        evidence_url=str(payload.evidence_url) if payload.evidence_url else None,
        status=DisputeStatus.pending,
    )
    session.add(dispute)
    await session.flush()
    await session.refresh(dispute)
    return DisputeResponse.model_validate(dispute)


@router.get(
    "/mine",
    response_model=list[DisputeResponse],
    summary="Мои споры",
)
async def list_my_disputes(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DisputeResponse]:
    result = await session.scalars(
        select(CopyrightDispute)
        .where(CopyrightDispute.complainant_id == current_user.id)
        .order_by(CopyrightDispute.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [DisputeResponse.model_validate(row) for row in result.all()]


@router.get(
    "",
    response_model=list[DisputeResponse],
    summary="Очередь споров для модерации",
)
async def list_disputes(
    dispute_status: DisputeStatus | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
    _moderator: User = Depends(require_moderator),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DisputeResponse]:
    query = select(CopyrightDispute).order_by(CopyrightDispute.created_at.asc())
    if dispute_status is not None:
        query = query.where(CopyrightDispute.status == dispute_status)
    result = await session.scalars(query.limit(limit).offset(offset))
    return [DisputeResponse.model_validate(row) for row in result.all()]


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Получить спор",
)
async def get_dispute(
    dispute_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DisputeResponse:
    dispute = await session.get(CopyrightDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Спор не найден")
    if dispute.complainant_id != current_user.id and current_user.role.value not in ("expert", "admin"):
        raise HTTPException(status_code=403, detail="Недостаточно прав для просмотра спора")
    return DisputeResponse.model_validate(dispute)


@router.patch(
    "/{dispute_id}/status",
    response_model=DisputeResponse,
    summary="Изменить статус спора или вынести решение",
)
async def resolve_dispute(
    dispute_id: UUID,
    payload: DisputeResolve,
    session: AsyncSession = Depends(get_db),
    moderator: User = Depends(require_moderator),
) -> DisputeResponse:
    dispute = await session.scalar(
        select(CopyrightDispute)
        .where(CopyrightDispute.id == dispute_id)
        .with_for_update()
    )
    if dispute is None:
        raise HTTPException(status_code=404, detail="Спор не найден")
    if dispute.status in (DisputeStatus.resolved, DisputeStatus.rejected):
        raise HTTPException(status_code=409, detail="Спор уже закрыт")

    if payload.status not in (DisputeStatus.under_review, DisputeStatus.resolved, DisputeStatus.rejected):
        raise HTTPException(status_code=422, detail="Недопустимый статус для модератора")

    dispute.status = payload.status
    dispute.resolution = payload.resolution
    dispute.moderator_comment = payload.moderator_comment
    if payload.status in (DisputeStatus.resolved, DisputeStatus.rejected):
        dispute.resolved_by = moderator.id
        dispute.resolved_at = datetime.now(timezone.utc)
    else:
        dispute.resolved_by = None
        dispute.resolved_at = None

    await session.flush()
    await session.refresh(dispute)
    return DisputeResponse.model_validate(dispute)
