import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import utc_now
from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    tenant_id: int,
    actor_id: int | None,
    action: str,
    object_type: str,
    object_id: int | None = None,
    before: Any = None,
    after: Any = None,
    ip: str | None = None,
    request_id: str | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_json=None if before is None else json.dumps(before, ensure_ascii=False, default=str),
            after_json=None if after is None else json.dumps(after, ensure_ascii=False, default=str),
            ip=ip,
            request_id=request_id,
            created_at=utc_now(),
        )
    )
