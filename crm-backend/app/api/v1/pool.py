from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.pagination import normalize_page
from app.core.timeutil import utc_now
from app.database import get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import Account, ClaimQuota, Lead, PoolRule
from app.schemas.common import dumps_json
from app.services.audit import write_audit

router = APIRouter()


class PoolRuleIn(BaseModel):
    objectType: str
    idleDays: int = 30
    conditionJson: dict[str, Any] | None = None
    enabled: bool = True


class ClaimQuotaIn(BaseModel):
    userId: int | None = None
    deptId: int | None = None
    objectType: str
    period: str = "day"
    maxCount: int = 10


class ForceAssignIn(BaseModel):
    objectType: str
    objectId: int
    userId: int


@router.get("/pool-rules")
def list_pool_rules(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(PoolRule).where(PoolRule.tenant_id == user.tenant_id, PoolRule.deleted_at.is_(None))
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "objectType": r.object_type,
                "idleDays": r.idle_days,
                "conditionJson": r.condition_json,
                "enabled": bool(r.enabled),
            }
            for r in rows
        ]
    }


@router.post("/pool-rules", status_code=201)
def create_pool_rule(
    body: PoolRuleIn,
    user: Annotated[CurrentUser, Depends(require_permissions("pool:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rule = PoolRule(
        tenant_id=user.tenant_id,
        object_type=body.objectType,
        idle_days=body.idleDays,
        condition_json=dumps_json(body.conditionJson),
        enabled=1 if body.enabled else 0,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id}


@router.patch("/pool-rules/{rule_id}")
def patch_pool_rule(
    rule_id: int,
    body: PoolRuleIn,
    user: Annotated[CurrentUser, Depends(require_permissions("pool:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rule = db.get(PoolRule, rule_id)
    if not rule or rule.tenant_id != user.tenant_id or rule.deleted_at:
        raise AppError("NOT_FOUND", "Pool rule not found", 404)
    rule.object_type = body.objectType
    rule.idle_days = body.idleDays
    rule.condition_json = dumps_json(body.conditionJson)
    rule.enabled = 1 if body.enabled else 0
    rule.updated_by = user.id
    db.commit()
    return {"id": rule.id}


@router.get("/pool/leads")
def pool_leads(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Lead).where(
        Lead.tenant_id == user.tenant_id,
        Lead.deleted_at.is_(None),
        Lead.pool_status == "pooled",
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Lead.pooled_at.desc()).offset(offset).limit(size)).all()
    return {
        "items": [{"id": r.id, "name": r.name, "source": r.source, "pooledAt": r.pooled_at} for r in rows],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.get("/pool/accounts")
def pool_accounts(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Account).where(
        Account.tenant_id == user.tenant_id,
        Account.deleted_at.is_(None),
        Account.pool_status == "pooled",
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Account.id.desc()).offset(offset).limit(size)).all()
    return {
        "items": [{"id": r.id, "name": r.name, "level": r.level} for r in rows],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.get("/claim-quotas")
def list_claim_quotas(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(ClaimQuota).where(ClaimQuota.tenant_id == user.tenant_id, ClaimQuota.deleted_at.is_(None))
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "userId": r.user_id,
                "deptId": r.dept_id,
                "objectType": r.object_type,
                "period": r.period,
                "maxCount": r.max_count,
            }
            for r in rows
        ]
    }


@router.put("/claim-quotas")
def put_claim_quotas(
    body: list[ClaimQuotaIn],
    user: Annotated[CurrentUser, Depends(require_permissions("pool:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    existing = db.scalars(
        select(ClaimQuota).where(ClaimQuota.tenant_id == user.tenant_id, ClaimQuota.deleted_at.is_(None))
    ).all()
    for row in existing:
        row.deleted_at = utc_now()
    for item in body:
        db.add(
            ClaimQuota(
                tenant_id=user.tenant_id,
                user_id=item.userId,
                dept_id=item.deptId,
                object_type=item.objectType,
                period=item.period,
                max_count=item.maxCount,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    db.commit()
    return {"message": "ok"}


@router.get("/claim-quotas/me")
def my_claim_quota(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    objectType: str = Query("lead"),
) -> dict[str, Any]:
    from datetime import datetime, timedelta

    from app.models import PoolClaimLog

    quota = db.scalar(
        select(ClaimQuota).where(
            ClaimQuota.tenant_id == user.tenant_id,
            ClaimQuota.object_type == objectType,
            ClaimQuota.deleted_at.is_(None),
            (ClaimQuota.user_id == user.id) | (ClaimQuota.user_id.is_(None)),
        )
    )
    max_count = quota.max_count if quota else None
    period = quota.period if quota else "day"
    now = utc_now()
    start = now - timedelta(days=now.weekday()) if period == "week" else datetime(now.year, now.month, now.day)
    used = db.scalar(
        select(func.count())
        .select_from(PoolClaimLog)
        .where(
            PoolClaimLog.tenant_id == user.tenant_id,
            PoolClaimLog.object_type == objectType,
            PoolClaimLog.user_id == user.id,
            PoolClaimLog.claimed_at >= start,
        )
    ) or 0
    remaining = None if max_count is None else max(max_count - used, 0)
    return {"objectType": objectType, "period": period, "maxCount": max_count, "used": used, "remaining": remaining}


@router.post("/pool/force-assign")
def force_assign(
    body: ForceAssignIn,
    user: Annotated[CurrentUser, Depends(require_permissions("pool:force_assign"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    if body.objectType == "lead":
        obj = db.get(Lead, body.objectId)
        if not obj or obj.tenant_id != user.tenant_id:
            raise AppError("NOT_FOUND", "Lead not found", 404)
        obj.owner_user_id = body.userId
        obj.pool_status = "private"
        obj.status = "assigned"
    elif body.objectType == "account":
        obj = db.get(Account, body.objectId)
        if not obj or obj.tenant_id != user.tenant_id:
            raise AppError("NOT_FOUND", "Account not found", 404)
        obj.owner_user_id = body.userId
        obj.pool_status = "private"
    else:
        raise AppError("VALIDATION_ERROR", "Unsupported objectType", 400)
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="force_assign",
        object_type=body.objectType,
        object_id=body.objectId,
        after={"userId": body.userId},
    )
    db.commit()
    return {"message": "ok"}
