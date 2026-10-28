import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import utc_now
from app.database import get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import ExportAudit, Opportunity, PipelineStage, SalesTarget

router = APIRouter()


class ExportIn(BaseModel):
    objectType: str
    filter: dict[str, Any] | None = None


@router.get("/dashboards/overview")
def overview(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    open_count = db.scalar(
        select(func.count()).where(
            Opportunity.tenant_id == user.tenant_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == "open",
        )
    ) or 0
    won_amount = db.scalar(
        select(func.coalesce(func.sum(Opportunity.amount), 0)).where(
            Opportunity.tenant_id == user.tenant_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == "won",
        )
    ) or 0
    targets = db.scalars(
        select(SalesTarget).where(SalesTarget.tenant_id == user.tenant_id, SalesTarget.deleted_at.is_(None))
    ).all()
    target_sum = sum(float(t.target_value) for t in targets) or 0
    achievement = (float(won_amount) / target_sum) if target_sum else None
    return {
        "openOpportunities": open_count,
        "wonAmount": float(won_amount),
        "targetAmount": target_sum,
        "achievementRate": achievement,
    }


@router.get("/dashboards/funnel")
def funnel(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    stages = db.scalars(
        select(PipelineStage).where(PipelineStage.tenant_id == user.tenant_id).order_by(PipelineStage.sort_order)
    ).all()
    items = []
    for stage in stages:
        count = db.scalar(
            select(func.count()).where(
                Opportunity.tenant_id == user.tenant_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.status == "open",
                Opportunity.stage_id == stage.id,
            )
        ) or 0
        amount = db.scalar(
            select(func.coalesce(func.sum(Opportunity.amount), 0)).where(
                Opportunity.tenant_id == user.tenant_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.status == "open",
                Opportunity.stage_id == stage.id,
            )
        ) or 0
        items.append({"stageId": stage.id, "stageCode": stage.code, "stageName": stage.name, "count": count, "amount": float(amount)})
    return {"items": items}


@router.get("/dashboards/performance")
def performance(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ownerUserId: int | None = None,
) -> dict[str, Any]:
    stmt = (
        select(Opportunity.owner_user_id, func.count(), func.coalesce(func.sum(Opportunity.amount), 0))
        .where(
            Opportunity.tenant_id == user.tenant_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == "won",
        )
        .group_by(Opportunity.owner_user_id)
    )
    if ownerUserId is not None:
        stmt = stmt.where(Opportunity.owner_user_id == ownerUserId)
    rows = db.execute(stmt).all()
    ranking = [{"ownerUserId": r[0], "wonCount": r[1], "wonAmount": float(r[2])} for r in rows]
    ranking.sort(key=lambda x: x["wonAmount"], reverse=True)

    opps = []
    if ownerUserId is not None:
        opp_rows = db.scalars(
            select(Opportunity).where(
                Opportunity.tenant_id == user.tenant_id,
                Opportunity.owner_user_id == ownerUserId,
                Opportunity.deleted_at.is_(None),
            )
        ).all()
        opps = [{"id": o.id, "name": o.name, "amount": float(o.amount or 0), "status": o.status} for o in opp_rows]
    return {"ranking": ranking, "opportunities": opps}


@router.post("/reports/export")
def export_report(
    body: ExportIn,
    user: Annotated[CurrentUser, Depends(require_permissions("report:export"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    db.add(
        ExportAudit(
            tenant_id=user.tenant_id,
            user_id=user.id,
            object_type=body.objectType,
            filter_json=json.dumps(body.filter or {}, ensure_ascii=False),
            row_count=0,
            created_at=utc_now(),
        )
    )
    db.commit()
    return {"jobId": None, "message": "export accepted", "status": "queued"}
