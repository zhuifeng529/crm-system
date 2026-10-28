from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.pagination import normalize_page
from app.core.security import hash_password
from app.database import get_db
from app.deps import CurrentUser, get_current_user, require_permissions
from app.models import Department, FieldPermission, Permission, Role, RolePermission, UserAccount, UserRole
from app.services.audit import write_audit

router = APIRouter()


class DepartmentIn(BaseModel):
    name: str
    parentId: int | None = None
    sortOrder: int = 0


class UserIn(BaseModel):
    username: str
    displayName: str
    password: str = Field(min_length=6)
    deptId: int | None = None
    email: str | None = None
    mobile: str | None = None
    roleIds: list[int] = []


class UserPatch(BaseModel):
    displayName: str | None = None
    deptId: int | None = None
    email: str | None = None
    mobile: str | None = None
    status: str | None = None
    roleIds: list[int] | None = None


class RoleIn(BaseModel):
    code: str
    name: str
    dataScope: str = "self"


class PermissionsPut(BaseModel):
    permissionIds: list[int]


class FieldPermissionsPut(BaseModel):
    items: list[dict[str, Any]]


@router.get("/departments")
def list_departments(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(Department)
        .where(Department.tenant_id == user.tenant_id, Department.deleted_at.is_(None))
        .order_by(Department.sort_order, Department.id)
    ).all()
    items = [
        {
            "id": d.id,
            "name": d.name,
            "parentId": d.parent_id,
            "path": d.path,
            "sortOrder": d.sort_order,
        }
        for d in rows
    ]
    return {"items": items}


@router.post("/departments", status_code=201)
def create_department(
    body: DepartmentIn,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    parent_path = "/"
    if body.parentId:
        parent = db.get(Department, body.parentId)
        if not parent or parent.tenant_id != user.tenant_id:
            raise AppError("NOT_FOUND", "Parent department not found", 404)
        parent_path = parent.path
    dept = Department(
        tenant_id=user.tenant_id,
        parent_id=body.parentId,
        name=body.name,
        path=parent_path,
        sort_order=body.sortOrder,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(dept)
    db.flush()
    dept.path = f"{parent_path}{dept.id}/"
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="create", object_type="department", object_id=dept.id, after={"name": dept.name})
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "path": dept.path}


@router.patch("/departments/{dept_id}")
def patch_department(
    dept_id: int,
    body: DepartmentIn,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    dept = db.get(Department, dept_id)
    if not dept or dept.tenant_id != user.tenant_id or dept.deleted_at:
        raise AppError("NOT_FOUND", "Department not found", 404)
    dept.name = body.name
    dept.sort_order = body.sortOrder
    dept.updated_by = user.id
    db.commit()
    return {"id": dept.id}


@router.delete("/departments/{dept_id}")
def delete_department(
    dept_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    from app.core.timeutil import utc_now

    dept = db.get(Department, dept_id)
    if not dept or dept.tenant_id != user.tenant_id or dept.deleted_at:
        raise AppError("NOT_FOUND", "Department not found", 404)
    dept.deleted_at = utc_now()
    db.commit()
    return {"message": "ok"}


@router.get("/users")
def list_users(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(UserAccount).where(UserAccount.tenant_id == user.tenant_id, UserAccount.deleted_at.is_(None))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((UserAccount.username.like(like)) | (UserAccount.display_name.like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(UserAccount.id).offset(offset).limit(size)).all()
    items = [
        {
            "id": u.id,
            "username": u.username,
            "displayName": u.display_name,
            "deptId": u.dept_id,
            "email": u.email,
            "mobile": u.mobile,
            "status": u.status,
            "roleIds": [r.id for r in u.roles],
        }
        for u in rows
    ]
    return {"items": items, "page": page, "pageSize": size, "total": total}


@router.post("/users", status_code=201)
def create_user(
    body: UserIn,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    exists = db.scalar(
        select(UserAccount).where(
            UserAccount.tenant_id == user.tenant_id,
            UserAccount.username == body.username,
            UserAccount.deleted_at.is_(None),
        )
    )
    if exists:
        raise AppError("CONFLICT", "Username already exists", 409)
    account = UserAccount(
        tenant_id=user.tenant_id,
        dept_id=body.deptId,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.displayName,
        email=body.email,
        mobile=body.mobile,
        status="active",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(account)
    db.flush()
    for rid in body.roleIds:
        db.add(UserRole(user_id=account.id, role_id=rid))
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="create", object_type="user", object_id=account.id)
    db.commit()
    return {"id": account.id}


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    body: UserPatch,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    account = db.get(UserAccount, user_id)
    if not account or account.tenant_id != user.tenant_id or account.deleted_at:
        raise AppError("NOT_FOUND", "User not found", 404)
    if body.displayName is not None:
        account.display_name = body.displayName
    if body.deptId is not None:
        account.dept_id = body.deptId
    if body.email is not None:
        account.email = body.email
    if body.mobile is not None:
        account.mobile = body.mobile
    if body.status is not None:
        account.status = body.status
    if body.roleIds is not None:
        db.query(UserRole).filter(UserRole.user_id == account.id).delete()
        for rid in body.roleIds:
            db.add(UserRole(user_id=account.id, role_id=rid))
    account.updated_by = user.id
    db.commit()
    return {"id": account.id}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
    newPassword: str = Query("ChangeMe123"),
) -> dict[str, str]:
    account = db.get(UserAccount, user_id)
    if not account or account.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "User not found", 404)
    account.password_hash = hash_password(newPassword)
    account.failed_login_count = 0
    if account.status == "locked":
        account.status = "active"
    write_audit(db, tenant_id=user.tenant_id, actor_id=user.id, action="reset_password", object_type="user", object_id=user_id)
    db.commit()
    return {"message": "ok"}


@router.get("/roles")
def list_roles(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(select(Role).where(Role.tenant_id == user.tenant_id, Role.deleted_at.is_(None))).all()
    return {
        "items": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "dataScope": r.data_scope,
                "permissionIds": [p.id for p in r.permissions],
            }
            for r in rows
        ]
    }


@router.post("/roles", status_code=201)
def create_role(
    body: RoleIn,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    role = Role(
        tenant_id=user.tenant_id,
        code=body.code,
        name=body.name,
        data_scope=body.dataScope,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"id": role.id}


@router.put("/roles/{role_id}/permissions")
def put_role_permissions(
    role_id: int,
    body: PermissionsPut,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    role = db.get(Role, role_id)
    if not role or role.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Role not found", 404)
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for pid in body.permissionIds:
        db.add(RolePermission(role_id=role_id, permission_id=pid))
    db.commit()
    return {"message": "ok"}


@router.put("/roles/{role_id}/field-permissions")
def put_field_permissions(
    role_id: int,
    body: FieldPermissionsPut,
    user: Annotated[CurrentUser, Depends(require_permissions("org:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    role = db.get(Role, role_id)
    if not role or role.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Role not found", 404)
    db.query(FieldPermission).filter(FieldPermission.role_id == role_id).delete()
    for item in body.items:
        db.add(
            FieldPermission(
                role_id=role_id,
                object_type=item["objectType"],
                field_name=item["fieldName"],
                access=item.get("access", "read"),
                allow_export=1 if item.get("allowExport", True) else 0,
            )
        )
    db.commit()
    return {"message": "ok"}


@router.get("/permissions")
def list_permissions(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(select(Permission).order_by(Permission.code)).all()
    return {
        "items": [
            {"id": p.id, "code": p.code, "resource": p.resource, "action": p.action, "name": p.name}
            for p in rows
        ]
    }
