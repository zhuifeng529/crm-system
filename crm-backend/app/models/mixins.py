from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditUserMixin:
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TenantMixin:
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)


class BusinessMixin(TenantMixin, TimestampMixin, SoftDeleteMixin, AuditUserMixin):
    pass


def json_text() -> mapped_column:
    return mapped_column(Text, nullable=True)


def status_text(default: str | None = None) -> mapped_column:
    return mapped_column(String(64), nullable=False, default=default) if default else mapped_column(String(64), nullable=False)
