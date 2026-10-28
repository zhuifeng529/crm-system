from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import BusinessMixin, TimestampMixin


class SalesTarget(Base, BusinessMixin):
    __tablename__ = "sales_target"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_key: Mapped[str] = mapped_column(String(32), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)


class SysDict(Base, TimestampMixin):
    __tablename__ = "sys_dict"
    __table_args__ = (UniqueConstraint("tenant_id", "dict_type", name="uq_sys_dict_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    dict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class SysDictItem(Base, TimestampMixin):
    __tablename__ = "sys_dict_item"
    __table_args__ = (UniqueConstraint("dict_id", "value", name="uq_sys_dict_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    dict_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_dict.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CustomFieldDef(Base, BusinessMixin):
    __tablename__ = "custom_field_def"
    __table_args__ = (UniqueConstraint("tenant_id", "object_type", "field_key", name="uq_custom_field"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LayoutDef(Base, BusinessMixin):
    __tablename__ = "layout_def"
    __table_args__ = (UniqueConstraint("tenant_id", "object_type", name="uq_layout_object"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    layout_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class Notification(Base, TimestampMixin):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="inbox")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class TodoTask(Base, BusinessMixin):
    __tablename__ = "todo_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ref_object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ref_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
