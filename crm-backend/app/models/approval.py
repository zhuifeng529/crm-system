from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import BusinessMixin, TimestampMixin


class ApprovalFlow(Base, BusinessMixin):
    __tablename__ = "approval_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ApprovalNode(Base, TimestampMixin):
    __tablename__ = "approval_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    flow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_flow.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="or")  # or / and
    approver_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ApprovalInstance(Base, BusinessMixin):
    __tablename__ = "approval_instance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_flow.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ApprovalTask(Base, TimestampMixin):
    __tablename__ = "approval_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_instance.id"), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("approval_node.id"), nullable=False)
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
