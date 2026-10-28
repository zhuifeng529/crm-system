import csv
import io
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.core.pagination import normalize_page
from app.core.timeutil import utc_now
from app.database import begin_immediate, get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import (
    Account,
    ClaimQuota,
    Contact,
    ImportJob,
    Lead,
    LeadMergeLog,
    PoolClaimLog,
)
from app.schemas.common import dumps_json
from app.services.audit import write_audit
from app.services.scope import apply_owner_scope

router = APIRouter()


class LeadIn(BaseModel):
    name: str
    contactName: str | None = None
    mobile: str | None = None
    email: str | None = None
    source: str | None = None
    channel: str | None = None
    industry: str | None = None
    companySize: str | None = None
    score: int | None = None
    ownerUserId: int | None = None
    tags: list[str] | None = None
    customFields: dict[str, Any] | None = None


class LeadPatch(BaseModel):
    name: str | None = None
    contactName: str | None = None
    mobile: str | None = None
    email: str | None = None
    source: str | None = None
    channel: str | None = None
    industry: str | None = None
    companySize: str | None = None
    score: int | None = None
    status: str | None = None
    tags: list[str] | None = None
    customFields: dict[str, Any] | None = None


class AssignIn(BaseModel):
    ids: list[int]
    userId: int


class ConvertIn(BaseModel):
    accountName: str | None = None
    createContact: bool = True


class InvalidateIn(BaseModel):
    reason: str


class MergeIn(BaseModel):
    primaryId: int
    mergeIds: list[int]


def _lead_out(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "name": lead.name,
        "contactName": lead.contact_name,
        "mobile": lead.mobile,
        "email": lead.email,
        "source": lead.source,
        "channel": lead.channel,
        "industry": lead.industry,
        "companySize": lead.company_size,
        "score": lead.score,
        "status": lead.status,
        "ownerUserId": lead.owner_user_id,
        "poolStatus": lead.pool_status,
        "pooledAt": lead.pooled_at,
        "lastFollowedAt": lead.last_followed_at,
        "convertedAccountId": lead.converted_account_id,
        "invalidReason": lead.invalid_reason,
        "tags": json.loads(lead.tags) if lead.tags else [],
        "customFields": json.loads(lead.custom_fields) if lead.custom_fields else {},
        "createdAt": lead.created_at,
        "updatedAt": lead.updated_at,
    }


@router.get("/leads")
def list_leads(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    status: str | None = None,
    source: str | None = None,
    owner: int | None = None,
    pool: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Lead).where(Lead.tenant_id == user.tenant_id, Lead.deleted_at.is_(None))
    stmt = apply_owner_scope(stmt, Lead, db, user)
    if status:
        stmt = stmt.where(Lead.status == status)
    if source:
        stmt = stmt.where(Lead.source == source)
    if owner is not None:
        stmt = stmt.where(Lead.owner_user_id == owner)
    if pool:
        stmt = stmt.where(Lead.pool_status == pool)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Lead.name.like(like), Lead.mobile.like(like), Lead.contact_name.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Lead.id.desc()).offset(offset).limit(size)).all()
    return {"items": [_lead_out(r) for r in rows], "page": page, "pageSize": size, "total": total}


@router.post("/leads", status_code=201)
def create_lead(
    body: LeadIn,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    if body.mobile:
        dup = db.scalar(
            select(Lead).where(
                Lead.tenant_id == user.tenant_id,
                Lead.mobile == body.mobile,
                Lead.deleted_at.is_(None),
            )
        )
        if dup:
            raise AppError("CONFLICT", "Lead with same mobile exists", 409, {"existingId": dup.id})
    lead = Lead(
        tenant_id=user.tenant_id,
        name=body.name,
        contact_name=body.contactName,
        mobile=body.mobile,
        email=body.email,
        source=body.source,
        channel=body.channel,
        industry=body.industry,
        company_size=body.companySize,
        score=body.score,
        status="assigned" if (body.ownerUserId or user.id) else "new",
        owner_user_id=body.ownerUserId or user.id,
        pool_status="private",
        tags=dumps_json(body.tags),
        custom_fields=dumps_json(body.customFields),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(lead)
    db.flush()
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="create", object_type="lead", object_id=lead.id)
    db.commit()
    db.refresh(lead)
    return _lead_out(lead)


@router.get("/leads/{lead_id}")
def get_lead(
    lead_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    return _lead_out(lead)


@router.patch("/leads/{lead_id}")
def patch_lead(
    lead_id: int,
    body: LeadPatch,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    data = body.model_dump(exclude_unset=True)
    mapping = {
        "name": "name",
        "contactName": "contact_name",
        "mobile": "mobile",
        "email": "email",
        "source": "source",
        "channel": "channel",
        "industry": "industry",
        "companySize": "company_size",
        "score": "score",
        "status": "status",
    }
    for k, attr in mapping.items():
        if k in data:
            setattr(lead, attr, data[k])
    if "tags" in data:
        lead.tags = dumps_json(data["tags"])
    if "customFields" in data:
        lead.custom_fields = dumps_json(data["customFields"])
    lead.updated_by = user.id
    db.commit()
    db.refresh(lead)
    return _lead_out(lead)


@router.post("/leads/import")
async def import_leads(
    user: Annotated[CurrentUser, Depends(require_permissions("lead:import"))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    key = f"imports/{user.tenant_id}/{utc_now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    path = settings.upload_dir / key.replace("/", "_")
    path.write_bytes(content)
    job = ImportJob(
        tenant_id=user.tenant_id,
        type="lead",
        file_key=str(path),
        status="processing",
        created_by=user.id,
    )
    db.add(job)
    db.flush()

    # Process CSV synchronously for MVP (worker-ready via import_job status)
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    total = success = fail = 0
    for row in reader:
        total += 1
        name = (row.get("name") or row.get("公司") or "").strip()
        if not name:
            fail += 1
            continue
        lead = Lead(
            tenant_id=user.tenant_id,
            name=name,
            contact_name=(row.get("contactName") or row.get("联系人") or None),
            mobile=(row.get("mobile") or row.get("手机") or None),
            email=(row.get("email") or None),
            source=(row.get("source") or "import"),
            status="new",
            owner_user_id=None,
            pool_status="private",
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(lead)
        success += 1
    job.total = total
    job.success = success
    job.fail = fail
    job.status = "done"
    db.commit()
    return {"jobId": job.id}


@router.get("/import-jobs/{job_id}")
def get_import_job(
    job_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job or job.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Import job not found", 404)
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "total": job.total,
        "success": job.success,
        "fail": job.fail,
    }


@router.post("/leads/assign")
def assign_leads(
    body: AssignIn,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:assign"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    leads = db.scalars(
        select(Lead).where(Lead.tenant_id == user.tenant_id, Lead.id.in_(body.ids), Lead.deleted_at.is_(None))
    ).all()
    for lead in leads:
        lead.owner_user_id = body.userId
        lead.status = "assigned"
        lead.pool_status = "private"
        lead.updated_by = user.id
        write_audit(
            db,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="assign",
            object_type="lead",
            object_id=lead.id,
            after={"ownerUserId": body.userId},
        )
    db.commit()
    return {"updated": len(leads)}


@router.post("/leads/{lead_id}/claim")
def claim_lead(
    lead_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:claim"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    begin_immediate(db)
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    if lead.pool_status != "pooled":
        raise AppError("CONFLICT", "Lead is not in pool", 409)

    quota = db.scalar(
        select(ClaimQuota).where(
            ClaimQuota.tenant_id == user.tenant_id,
            ClaimQuota.object_type == "lead",
            ClaimQuota.deleted_at.is_(None),
            or_(ClaimQuota.user_id == user.id, ClaimQuota.user_id.is_(None)),
        )
    )
    if quota:
        from datetime import datetime, timedelta

        now = utc_now()
        if quota.period == "week":
            start = now - timedelta(days=now.weekday())
        else:
            start = datetime(now.year, now.month, now.day)
        claimed = db.scalar(
            select(func.count())
            .select_from(PoolClaimLog)
            .where(
                PoolClaimLog.tenant_id == user.tenant_id,
                PoolClaimLog.object_type == "lead",
                PoolClaimLog.user_id == user.id,
                PoolClaimLog.claimed_at >= start,
            )
        ) or 0
        if claimed >= quota.max_count:
            raise AppError("QUOTA_EXCEEDED", "Claim quota exceeded", 429)

    lead.owner_user_id = user.id
    lead.pool_status = "private"
    lead.status = "assigned"
    lead.pooled_at = None
    lead.updated_by = user.id
    db.add(
        PoolClaimLog(
            tenant_id=user.tenant_id,
            object_type="lead",
            object_id=lead.id,
            user_id=user.id,
            claimed_at=utc_now(),
        )
    )
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="claim", object_type="lead", object_id=lead.id)
    db.commit()
    return _lead_out(lead)


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: int,
    body: ConvertIn,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    if lead.status == "converted":
        raise AppError("CONFLICT", "Lead already converted", 409)

    account = Account(
        tenant_id=user.tenant_id,
        name=body.accountName or lead.name,
        industry=lead.industry,
        owner_user_id=lead.owner_user_id or user.id,
        lifecycle_status="prospect",
        pool_status="private",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(account)
    db.flush()
    contact_id = None
    if body.createContact and (lead.contact_name or lead.mobile or lead.email):
        contact = Contact(
            tenant_id=user.tenant_id,
            account_id=account.id,
            name=lead.contact_name or lead.name,
            mobile=lead.mobile,
            email=lead.email,
            is_primary=1,
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(contact)
        db.flush()
        contact_id = contact.id

    lead.status = "converted"
    lead.converted_account_id = account.id
    lead.updated_by = user.id
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="convert",
        object_type="lead",
        object_id=lead.id,
        after={"accountId": account.id, "contactId": contact_id},
    )
    db.commit()
    return {"accountId": account.id, "contactId": contact_id, "lead": _lead_out(lead)}


@router.post("/leads/{lead_id}/invalidate")
def invalidate_lead(
    lead_id: int,
    body: InvalidateIn,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    lead.status = "invalid"
    lead.invalid_reason = body.reason
    lead.updated_by = user.id
    db.commit()
    return _lead_out(lead)


@router.post("/leads/merge")
def merge_leads(
    body: MergeIn,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    primary = db.get(Lead, body.primaryId)
    if not primary or primary.tenant_id != user.tenant_id or primary.deleted_at:
        raise AppError("NOT_FOUND", "Primary lead not found", 404)
    for mid in body.mergeIds:
        other = db.get(Lead, mid)
        if other and other.tenant_id == user.tenant_id and not other.deleted_at:
            other.deleted_at = utc_now()
            other.status = "invalid"
            other.invalid_reason = f"merged_into_{primary.id}"
    db.add(
        LeadMergeLog(
            tenant_id=user.tenant_id,
            from_ids=json.dumps(body.mergeIds),
            to_id=primary.id,
            created_by=user.id,
        )
    )
    db.commit()
    return {"primaryId": primary.id, "merged": body.mergeIds}


@router.post("/leads/{lead_id}/return-to-pool")
def return_to_pool(
    lead_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("lead:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.deleted_at:
        raise AppError("NOT_FOUND", "Lead not found", 404)
    lead.pool_status = "pooled"
    lead.status = "pooled"
    lead.pooled_at = utc_now()
    lead.owner_user_id = None
    lead.updated_by = user.id
    db.commit()
    return _lead_out(lead)
