from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.core.timeutil import utc_now
from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import LoginLog, TokenBlacklist, UserAccount
from app.services.audit import write_audit

router = APIRouter(prefix="/auth")


class LoginIn(BaseModel):
    username: str
    password: str
    tenantId: int | None = None


class PasswordChangeIn(BaseModel):
    oldPassword: str
    newPassword: str = Field(min_length=6)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    stmt = select(UserAccount).where(UserAccount.username == body.username, UserAccount.deleted_at.is_(None))
    if body.tenantId is not None:
        stmt = stmt.where(UserAccount.tenant_id == body.tenantId)
    user = db.scalars(stmt).first()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    def _log(success: bool, tenant_id: int | None = None, user_id: int | None = None) -> None:
        db.add(
            LoginLog(
                tenant_id=tenant_id,
                user_id=user_id,
                username=body.username,
                success=1 if success else 0,
                ip=ip,
                ua=ua,
                created_at=utc_now(),
            )
        )

    if not user or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.status = "locked"
        _log(False, user.tenant_id if user else body.tenantId, user.id if user else None)
        db.commit()
        raise AppError("UNAUTHORIZED", "Invalid username or password", 401)

    if user.status == "locked":
        _log(False, user.tenant_id, user.id)
        db.commit()
        raise AppError("FORBIDDEN", "Account locked", 403)
    if user.status != "active":
        _log(False, user.tenant_id, user.id)
        db.commit()
        raise AppError("FORBIDDEN", "Account disabled", 403)

    token, jti, expire = create_access_token(
        {"sub": str(user.id), "tenant_id": user.tenant_id, "username": user.username}
    )
    user.failed_login_count = 0
    user.last_login_at = utc_now()
    _log(True, user.tenant_id, user.id)
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="login", object_type="user", object_id=user.id, ip=ip)
    db.commit()

    roles = [{"code": r.code, "name": r.name, "dataScope": r.data_scope} for r in user.roles]
    permissions = sorted({p.code for r in user.roles for p in r.permissions})
    return {
        "token": token,
        "tokenType": "Bearer",
        "expiresAt": expire.isoformat() + "Z",
        "user": {
            "id": user.id,
            "tenantId": user.tenant_id,
            "username": user.username,
            "displayName": user.display_name,
            "deptId": user.dept_id,
            "roles": roles,
            "permissions": permissions,
        },
    }


@router.post("/logout")
def logout(user: Annotated[CurrentUser, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    if user.jti:
        exp = utc_now()
        if user.token_exp and user.token_exp.isdigit():
            exp = datetime.utcfromtimestamp(int(user.token_exp))
        db.add(TokenBlacklist(jti=user.jti, expires_at=exp, created_at=utc_now()))
        db.commit()
    return {"message": "ok"}


@router.get("/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict[str, Any]:
    return {
        "id": user.id,
        "tenantId": user.tenant_id,
        "username": user.username,
        "displayName": user.display_name,
        "deptId": user.dept_id,
        "roles": user.roles,
        "permissions": sorted(user.permissions),
        "dataScope": user.data_scope,
    }


@router.post("/password/change")
def change_password(
    body: PasswordChangeIn,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    account = db.get(UserAccount, user.id)
    if not account or not verify_password(body.oldPassword, account.password_hash):
        raise AppError("VALIDATION_ERROR", "Old password incorrect", 400)
    account.password_hash = hash_password(body.newPassword)
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="password_change", object_type="user", object_id=user.id)
    db.commit()
    return {"message": "ok"}
