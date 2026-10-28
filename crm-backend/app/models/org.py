from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)


class Department(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("department.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, default="/")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UserAccount(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    dept_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("department.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    roles = relationship("Role", secondary="user_role", lazy="selectin")


class Role(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_role_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    data_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="self")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    permissions = relationship("Permission", secondary="role_permission", lazy="selectin")


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("code", name="uq_permission_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("role.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permission.id"), nullable=False)


class UserRole(Base):
    __tablename__ = "user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("role.id"), nullable=False)


class FieldPermission(Base):
    __tablename__ = "field_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "object_type", "field_name", name="uq_field_permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("role.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    access: Mapped[str] = mapped_column(String(32), nullable=False, default="read")
    allow_export: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class UserDataScopeOverride(Base):
    __tablename__ = "user_data_scope_override"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_data_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    data_scope: Mapped[str] = mapped_column(String(32), nullable=False)
