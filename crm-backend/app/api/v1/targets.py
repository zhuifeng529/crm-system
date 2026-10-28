from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.database import get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import SalesTarget

router = APIRouter()


class TargetIn(BaseModel):
    scopeType: str
    scopeId: int
    metric: str
    periodType: str
    periodKey: str
    targetValue: Decimal


class TargetPatch(BaseModel):
    targetValue: Decimal | None = None
    metric: str | None = None


@router.get("/sales-targets")
def list_targets(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(SalesTarget).where(SalesTarget.tenant_id == user.tenant_id, SalesTarget.deleted_at.is_(None))
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "scopeType": r.scope_type,
                "scopeId": r.scope_id,
                "metric": r.metric,
                "periodType": r.period_type,
                "periodKey": r.period_key,
                "targetValue": float(r.target_value),
            }
            for r in rows
        ]
    }


@router.post("/sales-targets", status_code=201)
def create_target(
    body: TargetIn,
    user: Annotated[CurrentUser, Depends(require_permissions("target:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    row = SalesTarget(
        tenant_id=user.tenant_id,
        scope_type=body.scopeType,
        scope_id=body.scopeId,
        metric=body.metric,
        period_type=body.periodType,
        period_key=body.periodKey,
        target_value=body.targetValue,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/sales-targets/{target_id}")
def patch_target(
    target_id: int,
    body: TargetPatch,
    user: Annotated[CurrentUser, Depends(require_permissions("target:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    row = db.get(SalesTarget, target_id)
    if not row or row.tenant_id != user.tenant_id or row.deleted_at:
        raise AppError("NOT_FOUND", "Target not found", 404)
    if body.targetValue is not None:
        row.target_value = body.targetValue
    if body.metric is not None:
        row.metric = body.metric
    row.updated_by = user.id
    db.commit()
    return {"id": row.id}
