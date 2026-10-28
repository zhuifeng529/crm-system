import json
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
from app.models import (
    ApprovalFlow,
    ApprovalNode,
    AuditLog,
    CustomFieldDef,
    ExportAudit,
    LayoutDef,
    LoginLog,
    Notification,
    SysDict,
    SysDictItem,
    TodoTask,
)
from app.schemas.common import dumps_json

router = APIRouter()


class DictItemIn(BaseModel):
    label: str
    value: str
    sortOrder: int = 0
    enabled: bool = True


class CustomFieldIn(BaseModel):
    objectType: str
    fieldKey: str
    fieldType: str
    label: str
    options: list[Any] | None = None
    required: bool = False


class LayoutPut(BaseModel):
    layout: dict[str, Any]


class ApprovalFlowIn(BaseModel):
    objectType: str
    name: str
    nodes: list[dict[str, Any]] = []


class ReadNotificationsIn(BaseModel):
    ids: list[int] | None = None
    all: bool = False


@router.get("/dicts/{dict_type}/items")
def list_dict_items(
    dict_type: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    d = db.scalar(select(SysDict).where(SysDict.tenant_id == user.tenant_id, SysDict.dict_type == dict_type))
    if not d:
        return {"items": []}
    rows = db.scalars(
        select(SysDictItem).where(SysDictItem.dict_id == d.id).order_by(SysDictItem.sort_order)
    ).all()
    return {
        "items": [
            {"id": r.id, "label": r.label, "value": r.value, "sortOrder": r.sort_order, "enabled": bool(r.enabled)}
            for r in rows
        ]
    }


@router.post("/dicts/{dict_type}/items", status_code=201)
def create_dict_item(
    dict_type: str,
    body: DictItemIn,
    user: Annotated[CurrentUser, Depends(require_permissions("dict:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    d = db.scalar(select(SysDict).where(SysDict.tenant_id == user.tenant_id, SysDict.dict_type == dict_type))
    if not d:
        d = SysDict(tenant_id=user.tenant_id, dict_type=dict_type, name=dict_type)
        db.add(d)
        db.flush()
    item = SysDictItem(
        tenant_id=user.tenant_id,
        dict_id=d.id,
        label=body.label,
        value=body.value,
        sort_order=body.sortOrder,
        enabled=1 if body.enabled else 0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


@router.patch("/dicts/{dict_type}/items/{item_id}")
def patch_dict_item(
    dict_type: str,
    item_id: int,
    body: DictItemIn,
    user: Annotated[CurrentUser, Depends(require_permissions("dict:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    item = db.get(SysDictItem, item_id)
    if not item or item.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Dict item not found", 404)
    item.label = body.label
    item.value = body.value
    item.sort_order = body.sortOrder
    item.enabled = 1 if body.enabled else 0
    db.commit()
    return {"id": item.id}


@router.delete("/dicts/{dict_type}/items/{item_id}")
def delete_dict_item(
    dict_type: str,
    item_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("dict:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    item = db.get(SysDictItem, item_id)
    if not item or item.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Dict item not found", 404)
    db.delete(item)
    db.commit()
    return {"message": "ok"}


@router.get("/custom-fields")
def list_custom_fields(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    objectType: str | None = None,
) -> dict[str, Any]:
    stmt = select(CustomFieldDef).where(CustomFieldDef.tenant_id == user.tenant_id, CustomFieldDef.deleted_at.is_(None))
    if objectType:
        stmt = stmt.where(CustomFieldDef.object_type == objectType)
    rows = db.scalars(stmt).all()
    return {
        "items": [
            {
                "id": r.id,
                "objectType": r.object_type,
                "fieldKey": r.field_key,
                "fieldType": r.field_type,
                "label": r.label,
                "options": json.loads(r.options) if r.options else [],
                "required": bool(r.required),
            }
            for r in rows
        ]
    }


@router.post("/custom-fields", status_code=201)
def create_custom_field(
    body: CustomFieldIn,
    user: Annotated[CurrentUser, Depends(require_permissions("field:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    row = CustomFieldDef(
        tenant_id=user.tenant_id,
        object_type=body.objectType,
        field_key=body.fieldKey,
        field_type=body.fieldType,
        label=body.label,
        options=dumps_json(body.options),
        required=1 if body.required else 0,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.patch("/custom-fields/{field_id}")
def patch_custom_field(
    field_id: int,
    body: CustomFieldIn,
    user: Annotated[CurrentUser, Depends(require_permissions("field:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    row = db.get(CustomFieldDef, field_id)
    if not row or row.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Custom field not found", 404)
    row.label = body.label
    row.field_type = body.fieldType
    row.options = dumps_json(body.options)
    row.required = 1 if body.required else 0
    db.commit()
    return {"id": row.id}


@router.delete("/custom-fields/{field_id}")
def delete_custom_field(
    field_id: int,
    user: Annotated[CurrentUser, Depends(require_permissions("field:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    row = db.get(CustomFieldDef, field_id)
    if not row or row.tenant_id != user.tenant_id:
        raise AppError("NOT_FOUND", "Custom field not found", 404)
    row.deleted_at = utc_now()
    db.commit()
    return {"message": "ok"}


@router.get("/layouts/{object_type}")
def get_layout(
    object_type: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    row = db.scalar(
        select(LayoutDef).where(
            LayoutDef.tenant_id == user.tenant_id,
            LayoutDef.object_type == object_type,
            LayoutDef.deleted_at.is_(None),
        )
    )
    return {"objectType": object_type, "layout": json.loads(row.layout_json) if row else {}}


@router.put("/layouts/{object_type}")
def put_layout(
    object_type: str,
    body: LayoutPut,
    user: Annotated[CurrentUser, Depends(require_permissions("layout:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    row = db.scalar(
        select(LayoutDef).where(LayoutDef.tenant_id == user.tenant_id, LayoutDef.object_type == object_type)
    )
    if not row:
        row = LayoutDef(tenant_id=user.tenant_id, object_type=object_type, layout_json="{}", created_by=user.id)
        db.add(row)
    row.layout_json = json.dumps(body.layout, ensure_ascii=False)
    row.updated_by = user.id
    db.commit()
    return {"message": "ok"}


@router.get("/approval-flows")
def list_approval_flows(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(ApprovalFlow).where(ApprovalFlow.tenant_id == user.tenant_id, ApprovalFlow.deleted_at.is_(None))
    ).all()
    items = []
    for f in rows:
        nodes = db.scalars(select(ApprovalNode).where(ApprovalNode.flow_id == f.id).order_by(ApprovalNode.sort_order)).all()
        items.append(
            {
                "id": f.id,
                "objectType": f.object_type,
                "name": f.name,
                "enabled": bool(f.enabled),
                "nodes": [{"id": n.id, "name": n.name, "mode": n.mode, "sortOrder": n.sort_order} for n in nodes],
            }
        )
    return {"items": items}


@router.post("/approval-flows", status_code=201)
def create_approval_flow(
    body: ApprovalFlowIn,
    user: Annotated[CurrentUser, Depends(require_permissions("approval:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    flow = ApprovalFlow(
        tenant_id=user.tenant_id,
        object_type=body.objectType,
        name=body.name,
        enabled=1,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(flow)
    db.flush()
    for idx, node in enumerate(body.nodes):
        db.add(
            ApprovalNode(
                tenant_id=user.tenant_id,
                flow_id=flow.id,
                name=node.get("name", f"node-{idx}"),
                sort_order=node.get("sortOrder", idx),
                mode=node.get("mode", "or"),
                approver_json=dumps_json(node.get("approvers")),
            )
        )
    db.commit()
    return {"id": flow.id}


@router.get("/audit-logs")
def list_audit_logs(
    user: Annotated[CurrentUser, Depends(require_permissions("audit:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    actor: int | None = None,
    action: str | None = None,
    objectType: str | None = None,
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor_id == actor)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if objectType:
        stmt = stmt.where(AuditLog.object_type == objectType)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset(offset).limit(size)).all()
    return {
        "items": [
            {
                "id": r.id,
                "actorId": r.actor_id,
                "action": r.action,
                "objectType": r.object_type,
                "objectId": r.object_id,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.get("/login-logs")
def list_login_logs(
    user: Annotated[CurrentUser, Depends(require_permissions("audit:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(LoginLog).where(LoginLog.tenant_id == user.tenant_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(LoginLog.id.desc()).offset(offset).limit(size)).all()
    return {
        "items": [
            {
                "id": r.id,
                "userId": r.user_id,
                "username": r.username,
                "success": bool(r.success),
                "ip": r.ip,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.get("/export-audits")
def list_export_audits(
    user: Annotated[CurrentUser, Depends(require_permissions("audit:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(ExportAudit).where(ExportAudit.tenant_id == user.tenant_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ExportAudit.id.desc()).offset(offset).limit(size)).all()
    return {
        "items": [
            {
                "id": r.id,
                "userId": r.user_id,
                "objectType": r.object_type,
                "rowCount": r.row_count,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.get("/notifications")
def list_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    page, size, offset = normalize_page(page, pageSize)
    stmt = select(Notification).where(Notification.tenant_id == user.tenant_id, Notification.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Notification.id.desc()).offset(offset).limit(size)).all()
    return {
        "items": [
            {
                "id": r.id,
                "channel": r.channel,
                "title": r.title,
                "body": r.body,
                "readAt": r.read_at,
                "createdAt": r.created_at,
            }
            for r in rows
        ],
        "page": page,
        "pageSize": size,
        "total": total,
    }


@router.post("/notifications/read")
def read_notifications(
    body: ReadNotificationsIn,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    stmt = select(Notification).where(Notification.tenant_id == user.tenant_id, Notification.user_id == user.id)
    if not body.all and body.ids:
        stmt = stmt.where(Notification.id.in_(body.ids))
    rows = db.scalars(stmt).all()
    now = utc_now()
    for r in rows:
        if r.read_at is None:
            r.read_at = now
    db.commit()
    return {"message": "ok"}


@router.get("/todos")
def list_todos(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(TodoTask).where(
            TodoTask.tenant_id == user.tenant_id,
            TodoTask.user_id == user.id,
            TodoTask.deleted_at.is_(None),
        )
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "type": r.type,
                "title": r.title,
                "dueAt": r.due_at,
                "status": r.status,
                "refObjectType": r.ref_object_type,
                "refObjectId": r.ref_object_id,
            }
            for r in rows
        ]
    }


@router.patch("/todos/{todo_id}")
def patch_todo(
    todo_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status: str = Query("done"),
) -> dict[str, Any]:
    row = db.get(TodoTask, todo_id)
    if not row or row.tenant_id != user.tenant_id or row.user_id != user.id:
        raise AppError("NOT_FOUND", "Todo not found", 404)
    row.status = status
    db.commit()
    return {"id": row.id, "status": row.status}
