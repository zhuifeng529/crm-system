import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.core.pagination import normalize_page
from app.core.timeutil import utc_now
from app.database import get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import (
    Account,
    Activity,
    Attachment,
    AuditLog,
    Comment,
    Lead,
    Opportunity,
    OpportunityCollaborator,
    OpportunityLine,
    OpportunityStageHistory,
    Pipeline,
    PipelineStage,
)
from app.schemas.common import CollaboratorIn, dumps_json
from app.services.audit import write_audit
from app.services.scope import apply_owner_scope

router = APIRouter()


class ActivityIn(BaseModel):
    objectType: str
    objectId: int
    type: str
    subject: str | None = None
    content: str | None = None
    happenedAt: datetime | None = None
    nextFollowAt: datetime | None = None


class CommentIn(BaseModel):
    body: str
    mentions: list[int] | None = None


class OpportunityIn(BaseModel):
    accountId: int
    name: str
    amount: Decimal | None = None
    currency: str = "CNY"
    probability: int | None = None
    expectedCloseDate: str | None = None
    stageId: int
    ownerUserId: int | None = None
    competitor: str | None = None


class OpportunityPatch(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    probability: int | None = None
    expectedCloseDate: str | None = None
    competitor: str | None = None


class StageChangeIn(BaseModel):
    stageId: int
    remark: str | None = None


class CloseIn(BaseModel):
    result: str = Field(pattern="^(won|lost)$")
    lostReason: str | None = None


class LineIn(BaseModel):
    productName: str
    sku: str | None = None
    qty: Decimal = Decimal("1")
    unitPrice: Decimal = Decimal("0")


class LinesPut(BaseModel):
    items: list[LineIn]


class StagesPut(BaseModel):
    items: list[dict[str, Any]]


class CollaboratorsPut(BaseModel):
    items: list[CollaboratorIn]


def _touch_follow(db: Session, object_type: str, object_id: int) -> None:
    now = utc_now()
    if object_type == "lead":
        obj = db.get(Lead, object_id)
        if obj:
            obj.last_followed_at = now
            if obj.status in ("new", "assigned"):
                obj.status = "following"
    elif object_type == "account":
        obj = db.get(Account, object_id)
        if obj:
            obj.last_followed_at = now


@router.get("/activities")
def list_activities(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    objectType: str | None = None,
    objectId: int | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Activity).where(Activity.tenant_id == user.tenant_id, Activity.deleted_at.is_(None))
    if objectType:
        stmt = stmt.where(Activity.object_type == objectType)
    if objectId is not None:
        stmt = stmt.where(Activity.object_id == objectId)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Activity.happened_at.desc()).offset(offset).limit(size)).all()
    items = [
        {
            "id": a.id,
            "objectType": a.object_type,
            "objectId": a.object_id,
            "type": a.type,
            "subject": a.subject,
            "content": a.content,
            "happenedAt": a.happened_at,
            "ownerUserId": a.owner_user_id,
            "nextFollowAt": a.next_follow_at,
        }
        for a in rows
    ]
    return {"items": items, "page": page, "pageSize": size, "total": total}


@router.post("/activities", status_code=201)
def create_activity(
    body: ActivityIn,
    user: Annotated[CurrentUser, Depends(require_permissions("activity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    activity = Activity(
        tenant_id=user.tenant_id,
        object_type=body.objectType,
        object_id=body.objectId,
        type=body.type,
        subject=body.subject,
        content=body.content,
        happened_at=body.happenedAt or utc_now(),
        owner_user_id=user.id,
        next_follow_at=body.nextFollowAt,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(activity)
    _touch_follow(db, body.objectType, body.objectId)
    db.commit()
    db.refresh(activity)
    return {"id": activity.id}


@router.get("/objects/{object_type}/{object_id}/timeline")
def timeline(
    object_type: str,
    object_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    activities = db.scalars(
        select(Activity).where(
            Activity.tenant_id == user.tenant_id,
            Activity.object_type == object_type,
            Activity.object_id == object_id,
            Activity.deleted_at.is_(None),
        )
    ).all()
    comments = db.scalars(
        select(Comment).where(
            Comment.tenant_id == user.tenant_id,
            Comment.object_type == object_type,
            Comment.object_id == object_id,
            Comment.deleted_at.is_(None),
        )
    ).all()
    audits = db.scalars(
        select(AuditLog).where(
            AuditLog.tenant_id == user.tenant_id,
            AuditLog.object_type == object_type,
            AuditLog.object_id == object_id,
        )
    ).all()
    items: list[dict[str, Any]] = []
    for a in activities:
        items.append({"kind": "activity", "id": a.id, "at": a.happened_at, "data": {"type": a.type, "subject": a.subject, "content": a.content}})
    for c in comments:
        items.append({"kind": "comment", "id": c.id, "at": c.created_at, "data": {"body": c.body, "authorId": c.author_id}})
    for au in audits:
        items.append({"kind": "audit", "id": au.id, "at": au.created_at, "data": {"action": au.action, "actorId": au.actor_id}})
    items.sort(key=lambda x: x["at"] or utc_now(), reverse=True)
    return {"items": items}


@router.post("/attachments")
async def upload_attachment(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    objectType: str = Form(...),
    objectId: int = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    key = f"{user.tenant_id}/{objectType}/{objectId}/{uuid4().hex}_{file.filename}"
    path = settings.upload_dir / key.replace("/", "_")
    path.write_bytes(content)
    att = Attachment(
        tenant_id=user.tenant_id,
        object_type=objectType,
        object_id=objectId,
        file_name=file.filename or "file",
        mime=file.content_type,
        size=len(content),
        storage_key=str(path),
        uploaded_by=user.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "fileName": att.file_name, "size": att.size}


@router.get("/attachments/{attachment_id}")
def get_attachment(
    attachment_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    att = db.get(Attachment, attachment_id)
    if not att or att.tenant_id != user.tenant_id or att.deleted_at:
        raise AppError("NOT_FOUND", "Attachment not found", 404)
    return {"id": att.id, "fileName": att.file_name, "mime": att.mime, "size": att.size, "storageKey": att.storage_key}


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    att = db.get(Attachment, attachment_id)
    if not att or att.tenant_id != user.tenant_id or att.deleted_at:
        raise AppError("NOT_FOUND", "Attachment not found", 404)
    att.deleted_at = utc_now()
    db.commit()
    return {"message": "ok"}


@router.get("/objects/{object_type}/{object_id}/comments")
def list_comments(
    object_type: str,
    object_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(Comment).where(
            Comment.tenant_id == user.tenant_id,
            Comment.object_type == object_type,
            Comment.object_id == object_id,
            Comment.deleted_at.is_(None),
        )
    ).all()
    return {
        "items": [
            {
                "id": c.id,
                "body": c.body,
                "mentions": json.loads(c.mentions) if c.mentions else [],
                "authorId": c.author_id,
                "createdAt": c.created_at,
            }
            for c in rows
        ]
    }


@router.post("/objects/{object_type}/{object_id}/comments", status_code=201)
def create_comment(
    object_type: str,
    object_id: int,
    body: CommentIn,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    comment = Comment(
        tenant_id=user.tenant_id,
        object_type=object_type,
        object_id=object_id,
        body=body.body,
        mentions=dumps_json(body.mentions),
        author_id=user.id,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}


# --- Opportunities / Pipelines ---


def _opp_out(o: Opportunity) -> dict[str, Any]:
    return {
        "id": o.id,
        "accountId": o.account_id,
        "name": o.name,
        "amount": float(o.amount) if o.amount is not None else None,
        "currency": o.currency,
        "probability": o.probability,
        "expectedCloseDate": o.expected_close_date.isoformat() if o.expected_close_date else None,
        "stageId": o.stage_id,
        "status": o.status,
        "lostReason": o.lost_reason,
        "ownerUserId": o.owner_user_id,
        "competitor": o.competitor,
        "wonAt": o.won_at,
        "lostAt": o.lost_at,
    }


@router.get("/pipelines")
def list_pipelines(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    pipes = db.scalars(
        select(Pipeline).where(Pipeline.tenant_id == user.tenant_id, Pipeline.deleted_at.is_(None))
    ).all()
    items = []
    for p in pipes:
        stages = db.scalars(
            select(PipelineStage).where(PipelineStage.pipeline_id == p.id).order_by(PipelineStage.sort_order)
        ).all()
        items.append(
            {
                "id": p.id,
                "name": p.name,
                "isDefault": bool(p.is_default),
                "stages": [
                    {
                        "id": s.id,
                        "code": s.code,
                        "name": s.name,
                        "sortOrder": s.sort_order,
                        "winProbability": s.win_probability,
                        "enterRequiredFields": json.loads(s.enter_required_fields) if s.enter_required_fields else [],
                        "needApproval": bool(s.need_approval),
                    }
                    for s in stages
                ],
            }
        )
    return {"items": items}


@router.put("/pipelines/{pipeline_id}/stages")
def put_stages(
    pipeline_id: int,
    body: StagesPut,
    user: Annotated[CurrentUser, Depends(require_permissions("pipeline:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    pipe = db.get(Pipeline, pipeline_id)
    if not pipe or pipe.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Pipeline not found", 404)
    existing = db.scalars(select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id)).all()
    by_code = {s.code: s for s in existing}
    kept_codes = set()
    for idx, item in enumerate(body.items):
        code = item["code"]
        kept_codes.add(code)
        if code in by_code:
            s = by_code[code]
            s.name = item.get("name", s.name)
            s.sort_order = item.get("sortOrder", idx)
            s.win_probability = item.get("winProbability", s.win_probability)
            s.enter_required_fields = dumps_json(item.get("enterRequiredFields"))
            s.need_approval = 1 if item.get("needApproval") else 0
        else:
            db.add(
                PipelineStage(
                    tenant_id=user.tenant_id,
                    pipeline_id=pipeline_id,
                    code=code,
                    name=item.get("name", code),
                    sort_order=item.get("sortOrder", idx),
                    win_probability=item.get("winProbability", 0),
                    enter_required_fields=dumps_json(item.get("enterRequiredFields")),
                    need_approval=1 if item.get("needApproval") else 0,
                )
            )
    db.commit()
    return {"message": "ok"}


@router.get("/opportunities")
def list_opportunities(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str | None = None,
    accountId: int | None = None,
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Opportunity).where(Opportunity.tenant_id == user.tenant_id, Opportunity.deleted_at.is_(None))
    stmt = apply_owner_scope(stmt, Opportunity, db, user)
    if status:
        stmt = stmt.where(Opportunity.status == status)
    if accountId is not None:
        stmt = stmt.where(Opportunity.account_id == accountId)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Opportunity.id.desc()).offset(offset).limit(size)).all()
    return {"items": [_opp_out(r) for r in rows], "page": page, "pageSize": size, "total": total}


@router.post("/opportunities", status_code=201)
def create_opportunity(
    body: OpportunityIn,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, body.accountId)
    if not account or account.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Account not found", 404)
    stage = db.get(PipelineStage, body.stageId)
    if not stage or stage.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Stage not found", 404)
    from datetime import date

    close_date = date.fromisoformat(body.expectedCloseDate) if body.expectedCloseDate else None
    opp = Opportunity(
        tenant_id=user.tenant_id,
        account_id=body.accountId,
        name=body.name,
        amount=body.amount,
        currency=body.currency,
        probability=body.probability if body.probability is not None else stage.win_probability,
        expected_close_date=close_date,
        stage_id=body.stageId,
        status="open",
        owner_user_id=body.ownerUserId or user.id,
        competitor=body.competitor,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(opp)
    db.flush()
    db.add(
        OpportunityStageHistory(
            tenant_id=user.tenant_id,
            opportunity_id=opp.id,
            from_stage_id=None,
            to_stage_id=body.stageId,
            actor_id=user.id,
            entered_at=utc_now(),
        )
    )
    db.commit()
    db.refresh(opp)
    return _opp_out(opp)


@router.get("/opportunities/{opp_id}")
def get_opportunity(
    opp_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id or opp.deleted_at:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    return _opp_out(opp)


@router.patch("/opportunities/{opp_id}")
def patch_opportunity(
    opp_id: int,
    body: OpportunityPatch,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id or opp.deleted_at:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    if opp.status != "open":
        raise AppError("CONFLICT", "Closed opportunity cannot be edited", 409)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        opp.name = data["name"]
    if "amount" in data:
        opp.amount = data["amount"]
    if "currency" in data:
        opp.currency = data["currency"]
    if "probability" in data:
        opp.probability = data["probability"]
    if "expectedCloseDate" in data:
        from datetime import date

        opp.expected_close_date = date.fromisoformat(data["expectedCloseDate"]) if data["expectedCloseDate"] else None
    if "competitor" in data:
        opp.competitor = data["competitor"]
    opp.updated_by = user.id
    db.commit()
    return _opp_out(opp)


@router.post("/opportunities/{opp_id}/stage")
def change_stage(
    opp_id: int,
    body: StageChangeIn,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id or opp.deleted_at:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    if opp.status != "open":
        raise AppError("CONFLICT", "Closed opportunity", 409)
    stage = db.get(PipelineStage, body.stageId)
    if not stage or stage.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Stage not found", 404)
    required = json.loads(stage.enter_required_fields) if stage.enter_required_fields else []
    missing = []
    for field in required:
        if field == "amount" and opp.amount is None:
            missing.append(field)
        if field == "expectedCloseDate" and opp.expected_close_date is None:
            missing.append(field)
    if missing:
        raise AppError("VALIDATION_ERROR", "Missing required fields for stage", 400, {"missing": missing})

    now = utc_now()
    hist = db.scalars(
        select(OpportunityStageHistory)
        .where(OpportunityStageHistory.opportunity_id == opp.id, OpportunityStageHistory.exited_at.is_(None))
        .order_by(OpportunityStageHistory.id.desc())
    ).first()
    if hist:
        hist.exited_at = now
    from_stage = opp.stage_id
    opp.stage_id = body.stageId
    opp.probability = stage.win_probability
    db.add(
        OpportunityStageHistory(
            tenant_id=user.tenant_id,
            opportunity_id=opp.id,
            from_stage_id=from_stage,
            to_stage_id=body.stageId,
            actor_id=user.id,
            remark=body.remark,
            entered_at=now,
        )
    )
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="stage_change",
        object_type="opportunity",
        object_id=opp.id,
        before={"stageId": from_stage},
        after={"stageId": body.stageId},
    )
    db.commit()
    return _opp_out(opp)


@router.post("/opportunities/{opp_id}/close")
def close_opportunity(
    opp_id: int,
    body: CloseIn,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id or opp.deleted_at:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    if opp.status != "open":
        raise AppError("CONFLICT", "Already closed", 409)
    if body.result == "lost" and not body.lostReason:
        raise AppError("VALIDATION_ERROR", "lostReason required", 400)
    now = utc_now()
    opp.status = body.result
    if body.result == "won":
        opp.won_at = now
        opp.probability = 100
    else:
        opp.lost_at = now
        opp.lost_reason = body.lostReason
        opp.probability = 0
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="close",
        object_type="opportunity",
        object_id=opp.id,
        after={"result": body.result, "lostReason": body.lostReason},
    )
    db.commit()
    return _opp_out(opp)


@router.get("/opportunities/{opp_id}/lines")
def get_lines(
    opp_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(select(OpportunityLine).where(OpportunityLine.opportunity_id == opp_id)).all()
    return {
        "items": [
            {
                "id": r.id,
                "productName": r.product_name,
                "sku": r.sku,
                "qty": float(r.qty),
                "unitPrice": float(r.unit_price),
                "amount": float(r.amount),
            }
            for r in rows
        ]
    }


@router.put("/opportunities/{opp_id}/lines")
def put_lines(
    opp_id: int,
    body: LinesPut,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    db.query(OpportunityLine).filter(OpportunityLine.opportunity_id == opp_id).delete()
    total = Decimal("0")
    for item in body.items:
        amount = (item.qty * item.unitPrice).quantize(Decimal("0.01"))
        total += amount
        db.add(
            OpportunityLine(
                tenant_id=user.tenant_id,
                opportunity_id=opp_id,
                product_name=item.productName,
                sku=item.sku,
                qty=item.qty,
                unit_price=item.unitPrice,
                amount=amount,
            )
        )
    opp.amount = total
    db.commit()
    return {"amount": float(total)}


@router.put("/opportunities/{opp_id}/collaborators")
def put_opp_collaborators(
    opp_id: int,
    body: CollaboratorsPut,
    user: Annotated[CurrentUser, Depends(require_permissions("opportunity:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    opp = db.get(Opportunity, opp_id)
    if not opp or opp.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Opportunity not found", 404)
    db.query(OpportunityCollaborator).filter(OpportunityCollaborator.opportunity_id == opp_id).delete()
    for item in body.items:
        db.add(OpportunityCollaborator(opportunity_id=opp_id, user_id=item.userId, role=item.role))
    db.commit()
    return {"message": "ok"}
