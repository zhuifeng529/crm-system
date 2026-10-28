from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.timeutil import utc_now
from app.database import get_db
from app.deps import CurrentUser, get_current_user
from app.models import ApprovalInstance, ApprovalTask
from app.services.audit import write_audit

router = APIRouter()


class DecideIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str | None = None


@router.get("/approvals/todo")
def approvals_todo(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = db.scalars(
        select(ApprovalTask).where(
            ApprovalTask.tenant_id == user.tenant_id,
            ApprovalTask.assignee_id == user.id,
            ApprovalTask.status == "pending",
        )
    ).all()
    items = []
    for t in rows:
        inst = db.get(ApprovalInstance, t.instance_id)
        items.append(
            {
                "taskId": t.id,
                "instanceId": t.instance_id,
                "objectType": inst.object_type if inst else None,
                "objectId": inst.object_id if inst else None,
                "status": t.status,
            }
        )
    return {"items": items}


@router.post("/approvals/{task_id}/decide")
def decide(
    task_id: int,
    body: DecideIn,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    task = db.get(ApprovalTask, task_id)
    if not task or task.tenant_id != user.tenant_id or task.assignee_id != user.id:
        raise AppError("NOT_FOUND", "Approval task not found", 404)
    if task.status != "pending":
        raise AppError("CONFLICT", "Task already decided", 409)
    task.status = "done"
    task.decision = body.decision
    task.comment = body.comment
    task.decided_at = utc_now()
    inst = db.get(ApprovalInstance, task.instance_id)
    if inst:
        inst.status = "approved" if body.decision == "approve" else "rejected"
    write_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action=body.decision,
        object_type="approval_task",
        object_id=task.id,
        after={"comment": body.comment},
    )
    db.commit()
    return {"taskId": task.id, "decision": body.decision}
