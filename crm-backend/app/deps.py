from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_token
from app.database import get_db
from app.models import Department, TokenBlacklist, UserAccount, UserDataScopeOverride

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: int
    tenant_id: int
    dept_id: int | None
    username: str
    display_name: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    data_scope: str = "self"
    jti: str | None = None
    token_exp: str | None = None


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise AppError("UNAUTHORIZED", "Missing bearer token", 401)
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise AppError("UNAUTHORIZED", "Invalid or expired token", 401) from exc

    jti = payload.get("jti")
    if jti:
        blocked = db.scalar(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
        if blocked:
            raise AppError("UNAUTHORIZED", "Token revoked", 401)

    user_id = payload.get("sub")
    if user_id is None:
        raise AppError("UNAUTHORIZED", "Invalid token subject", 401)

    user = db.get(UserAccount, int(user_id))
    if not user or user.deleted_at is not None or user.status != "active":
        raise AppError("UNAUTHORIZED", "User inactive or not found", 401)

    role_codes = [r.code for r in user.roles]
    permissions: set[str] = set()
    data_scope = "self"
    for role in user.roles:
        data_scope = _prefer_scope(data_scope, role.data_scope)
        for perm in role.permissions:
            permissions.add(perm.code)

    override = db.scalar(select(UserDataScopeOverride).where(UserDataScopeOverride.user_id == user.id))
    if override:
        data_scope = override.data_scope

    request.state.current_user = user
    return CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        dept_id=user.dept_id,
        username=user.username,
        display_name=user.display_name,
        roles=role_codes,
        permissions=permissions,
        data_scope=data_scope,
        jti=jti,
        token_exp=str(payload.get("exp")) if payload.get("exp") else None,
    )


def require_permissions(*codes: str):
    def _checker(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if "admin:*" in user.permissions or "*:*" in user.permissions:
            return user
        missing = [c for c in codes if c not in user.permissions]
        if missing:
            raise AppError("FORBIDDEN", f"Missing permissions: {', '.join(missing)}", 403)
        return user

    return _checker


def _prefer_scope(current: str, candidate: str) -> str:
    order = ["self", "dept", "dept_and_below", "company"]
    return candidate if order.index(candidate) > order.index(current) else current


def visible_user_ids(db: Session, user: CurrentUser) -> list[int] | None:
    """Return None for company-wide; otherwise list of visible owner user ids."""
    if user.data_scope == "company":
        return None
    if user.data_scope == "self":
        return [user.id]
    if user.dept_id is None:
        return [user.id]

    dept = db.get(Department, user.dept_id)
    if not dept:
        return [user.id]

    if user.data_scope == "dept":
        rows = db.scalars(
            select(UserAccount.id).where(
                UserAccount.tenant_id == user.tenant_id,
                UserAccount.dept_id == user.dept_id,
                UserAccount.deleted_at.is_(None),
            )
        ).all()
        return list(rows) or [user.id]

    # dept_and_below
    path_prefix = dept.path
    dept_ids = db.scalars(
        select(Department.id).where(
            Department.tenant_id == user.tenant_id,
            Department.deleted_at.is_(None),
            Department.path.like(f"{path_prefix}%"),
        )
    ).all()
    rows = db.scalars(
        select(UserAccount.id).where(
            UserAccount.tenant_id == user.tenant_id,
            UserAccount.dept_id.in_(dept_ids),
            UserAccount.deleted_at.is_(None),
        )
    ).all()
    return list(rows) or [user.id]


def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key
