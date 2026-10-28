"""In-process scheduler for pool recycle (no Redis)."""

from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.timeutil import utc_now
from app.database import SessionLocal
from app.models import Account, Lead, PoolRecycleLog, PoolRule

_scheduler: BackgroundScheduler | None = None


def recycle_idle_objects() -> None:
    db = SessionLocal()
    try:
        rules = db.scalars(select(PoolRule).where(PoolRule.enabled == 1, PoolRule.deleted_at.is_(None))).all()
        now = utc_now()
        for rule in rules:
            threshold = now - timedelta(days=rule.idle_days)
            if rule.object_type == "lead":
                rows = db.scalars(
                    select(Lead).where(
                        Lead.tenant_id == rule.tenant_id,
                        Lead.deleted_at.is_(None),
                        Lead.pool_status == "private",
                        Lead.status.notin_(["converted", "invalid"]),
                        Lead.last_followed_at.is_not(None),
                        Lead.last_followed_at < threshold,
                    )
                ).all()
                for lead in rows:
                    from_owner = lead.owner_user_id
                    lead.pool_status = "pooled"
                    lead.status = "pooled"
                    lead.owner_user_id = None
                    lead.pooled_at = now
                    db.add(
                        PoolRecycleLog(
                            tenant_id=lead.tenant_id,
                            object_type="lead",
                            object_id=lead.id,
                            from_owner_id=from_owner,
                            rule_id=rule.id,
                            recycled_at=now,
                        )
                    )
            elif rule.object_type == "account":
                rows = db.scalars(
                    select(Account).where(
                        Account.tenant_id == rule.tenant_id,
                        Account.deleted_at.is_(None),
                        Account.pool_status == "private",
                        Account.locked == 0,
                        Account.last_followed_at.is_not(None),
                        Account.last_followed_at < threshold,
                    )
                ).all()
                for account in rows:
                    from_owner = account.owner_user_id
                    account.pool_status = "pooled"
                    account.owner_user_id = from_owner  # keep last owner ref via recycle log
                    # For pooled accounts, owner still required by schema — assign system-like keep then clear via log
                    db.add(
                        PoolRecycleLog(
                            tenant_id=account.tenant_id,
                            object_type="account",
                            object_id=account.id,
                            from_owner_id=from_owner,
                            rule_id=rule.id,
                            recycled_at=now,
                        )
                    )
        db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(recycle_idle_objects, "interval", hours=1, id="pool_recycle")
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
