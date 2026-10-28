import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.pagination import normalize_page
from app.core.timeutil import utc_now
from app.database import begin_immediate, get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import Account, AccountCollaborator, ClaimQuota, Contact, PoolClaimLog
from app.schemas.common import CollaboratorIn, dumps_json
from app.services.audit import write_audit
from app.services.scope import apply_owner_scope

router = APIRouter()


class AccountIn(BaseModel):
    name: str
    industry: str | None = None
    region: str | None = None
    level: str | None = None
    lifecycleStatus: str | None = "prospect"
    ownerUserId: int | None = None
    parentAccountId: int | None = None
    customFields: dict[str, Any] | None = None


class AccountPatch(BaseModel):
    name: str | None = None
    industry: str | None = None
    region: str | None = None
    level: str | None = None
    lifecycleStatus: str | None = None
    customFields: dict[str, Any] | None = None


class TransferIn(BaseModel):
    ownerUserId: int


class LockIn(BaseModel):
    locked: bool


class ContactIn(BaseModel):
    name: str
    title: str | None = None
    mobile: str | None = None
    email: str | None = None
    decisionRole: str | None = None
    isPrimary: bool = False


class MergeIn(BaseModel):
    primaryId: int
    mergeIds: list[int]


class CollaboratorsPut(BaseModel):
    items: list[CollaboratorIn]


def _account_out(a: Account) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "industry": a.industry,
        "region": a.region,
        "level": a.level,
        "lifecycleStatus": a.lifecycle_status,
        "ownerUserId": a.owner_user_id,
        "parentAccountId": a.parent_account_id,
        "poolStatus": a.pool_status,
        "locked": bool(a.locked),
        "lastFollowedAt": a.last_followed_at,
        "customFields": json.loads(a.custom_fields) if a.custom_fields else {},
        "createdAt": a.created_at,
        "updatedAt": a.updated_at,
    }


def _contact_out(c: Contact) -> dict[str, Any]:
    return {
        "id": c.id,
        "accountId": c.account_id,
        "name": c.name,
        "title": c.title,
        "mobile": c.mobile,
        "email": c.email,
        "decisionRole": c.decision_role,
        "isPrimary": bool(c.is_primary),
    }


@router.get("/accounts")
def list_accounts(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    pool: str | None = None,
    owner: int | None = None,
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Account).where(Account.tenant_id == user.tenant_id, Account.deleted_at.is_(None))
    stmt = apply_owner_scope(stmt, Account, db, user)
    if keyword:
        stmt = stmt.where(Account.name.like(f"%{keyword}%"))
    if pool:
        stmt = stmt.where(Account.pool_status == pool)
    if owner is not None:
        stmt = stmt.where(Account.owner_user_id == owner)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Account.id.desc()).offset(offset).limit(size)).all()
    return {"items": [_account_out(r) for r in rows], "page": page, "pageSize": size, "total": total}


@router.post("/accounts", status_code=201)
def create_account(
    body: AccountIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = Account(
        tenant_id=user.tenant_id,
        name=body.name,
        industry=body.industry,
        region=body.region,
        level=body.level,
        lifecycle_status=body.lifecycleStatus,
        owner_user_id=body.ownerUserId or user.id,
        parent_account_id=body.parentAccountId,
        pool_status="private",
        custom_fields=dumps_json(body.customFields),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(account)
    db.flush()
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="create", object_type="account", object_id=account.id)
    db.commit()
    db.refresh(account)
    return _account_out(account)


@router.get("/accounts/{account_id}")
def get_account(
    account_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "Account not found", 404)
    return _account_out(account)


@router.patch("/accounts/{account_id}")
def patch_account(
    account_id: int,
    body: AccountPatch,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "Account not found", 404)
    if account.locked:
        raise AppError("CONFLICT", "Account is locked", 409)
    data = body.model_dump(exclude_unset=True)
    mapping = {
        "name": "name",
        "industry": "industry",
        "region": "region",
        "level": "level",
        "lifecycleStatus": "lifecycle_status",
    }
    for k, attr in mapping.items():
        if k in data:
            setattr(account, attr, data[k])
    if "customFields" in data:
        account.custom_fields = dumps_json(data["customFields"])
    account.updated_by = user.id
    db.commit()
    db.refresh(account)
    return _account_out(account)


@router.post("/accounts/merge")
def merge_accounts(
    body: MergeIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    primary = db.get(Account, body.primaryId)
    if not primary or primary.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Primary account not found", 404)
    for mid in body.mergeIds:
        other = db.get(Account, mid)
        if other and other.tenant_id == user.tenant_id and not other.deleted_at:
            other.deleted_at = utc_now()
            db.execute(
                Contact.__table__.update().where(Contact.account_id == mid).values(account_id=primary.id)
            )
    db.commit()
    return {"primaryId": primary.id, "merged": body.mergeIds}


@router.post("/accounts/{account_id}/transfer")
def transfer_account(
    account_id: int,
    body: TransferIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "Account not found", 404)
    before = account.owner_user_id
    account.owner_user_id = body.ownerUserId
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="transfer",
        object_type="account",
        object_id=account.id,
        before={"ownerUserId": before},
        after={"ownerUserId": body.ownerUserId},
    )
    db.commit()
    return _account_out(account)


@router.post("/accounts/{account_id}/lock")
def lock_account(
    account_id: int,
    body: LockIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "Account not found", 404)
    account.locked = 1 if body.locked else 0
    db.commit()
    return _account_out(account)


@router.post("/accounts/{account_id}/claim")
def claim_account(
    account_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("account:claim"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    begin_immediate(db)
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "Account not found", 404)
    if account.pool_status != "pooled":
        raise AppError("CONFLICT", "Account is not in pool", 409)
    quota = db.scalar(
        select(ClaimQuota).where(
            ClaimQuota.tenant_id == user.tenant_id,
            ClaimQuota.object_type == "account",
            ClaimQuota.deleted_at.is_(None),
            or_(ClaimQuota.user_id == user.id, ClaimQuota.user_id.is_(None)),
        )
    )
    if quota:
        from datetime import datetime, timedelta

        now = utc_now()
        start = now - timedelta(days=now.weekday()) if quota.period == "week" else datetime(now.year, now.month, now.day)
        claimed = db.scalar(
            select(func.count())
            .select_from(PoolClaimLog)
            .where(
                PoolClaimLog.tenant_id == user.tenant_id,
                PoolClaimLog.object_type == "account",
                PoolClaimLog.user_id == user.id,
                PoolClaimLog.claimed_at >= start,
            )
        ) or 0
        if claimed >= quota.max_count:
            raise AppError("QUOTA_EXCEEDED", "Claim quota exceeded", 429)
    account.owner_user_id = user.id
    account.pool_status = "private"
    db.add(
        PoolClaimLog(
            tenant_id=user.tenant_id,
            object_type="account",
            object_id=account.id,
            user_id=user.id,
            claimed_at=utc_now(),
        )
    )
    db.commit()
    return _account_out(account)


@router.get("/accounts/{account_id}/contacts")
def list_contacts(
    account_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Account not found", 404)
    rows = db.scalars(
        select(Contact).where(
            Contact.account_id == account_id,
            Contact.tenant_id == user.tenant_id,
            Contact.deleted_at.is_(None),
        )
    ).all()
    return {"items": [_contact_out(c) for c in rows]}


@router.post("/accounts/{account_id}/contacts", status_code=201)
def create_contact(
    account_id: int,
    body: ContactIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Account not found", 404)
    contact = Contact(
        tenant_id=user.tenant_id,
        account_id=account_id,
        name=body.name,
        title=body.title,
        mobile=body.mobile,
        email=body.email,
        decision_role=body.decisionRole,
        is_primary=1 if body.isPrimary else 0,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _contact_out(contact)


@router.patch("/contacts/{contact_id}")
def patch_contact(
    contact_id: int,
    body: ContactIn,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    contact = db.get(Contact, contact_id)
    if not contact or contact.tenant_id != user.tenant_id or contact.deleted_at:
        raise AppError("NOT_FOUND", "Contact not found", 404)
    contact.name = body.name
    contact.title = body.title
    contact.mobile = body.mobile
    contact.email = body.email
    contact.decision_role = body.decisionRole
    contact.is_primary = 1 if body.isPrimary else 0
    contact.updated_by = user.id
    db.commit()
    return _contact_out(contact)


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    contact = db.get(Contact, contact_id)
    if not contact or contact.tenant_id != user.tenant_id or contact.deleted_at:
        raise AppError("NOT_FOUND", "Contact not found", 404)
    contact.deleted_at = utc_now()
    db.commit()
    return {"message": "ok"}


@router.put("/accounts/{account_id}/collaborators")
def put_collaborators(
    account_id: int,
    body: CollaboratorsPut,
    user: Annotated[CurrentUser, Depends(require_permissions("account:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    account = db.get(Account, account_id)
    if not account or account.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Account not found", 404)
    db.query(AccountCollaborator).filter(AccountCollaborator.account_id == account_id).delete()
    for item in body.items:
        db.add(AccountCollaborator(account_id=account_id, user_id=item.userId, role=item.role))
    db.commit()
    return {"message": "ok"}
