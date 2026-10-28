from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import BusinessMixin, TimestampMixin


class PoolRule(Base, BusinessMixin):
    __tablename__ = "pool_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idle_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    condition_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ClaimQuota(Base, BusinessMixin):
    __tablename__ = "claim_quota"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=True)
    dept_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("department.id"), nullable=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    max_count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)


class PoolClaimLog(Base, TimestampMixin):
    __tablename__ = "pool_claim_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PoolRecycleLog(Base, TimestampMixin):
    __tablename__ = "pool_recycle_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pool_rule.id"), nullable=True)
    recycled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
