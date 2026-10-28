from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import BusinessMixin, TimestampMixin


class Lead(Base, BusinessMixin):
    __tablename__ = "lead"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", index=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=True, index=True)
    pool_status: Mapped[str] = mapped_column(String(32), nullable=False, default="private", index=True)
    pooled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_followed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    converted_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("account.id"), nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[str | None] = mapped_column(Text, nullable=True)


class LeadAssignmentRule(Base, BusinessMixin):
    __tablename__ = "lead_assignment_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    condition_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, default="round_robin")
    target_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class LeadMergeLog(Base, TimestampMixin):
    __tablename__ = "lead_merge_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    from_ids: Mapped[str] = mapped_column(Text, nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, ForeignKey("lead.id"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LeadCollaborator(Base):
    __tablename__ = "lead_collaborator"
    __table_args__ = (UniqueConstraint("lead_id", "user_id", name="uq_lead_collaborator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("lead.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="collaborator")


class Account(Base, BusinessMixin):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lifecycle_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    parent_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("account.id"), nullable=True)
    pool_status: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_followed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    custom_fields: Mapped[str | None] = mapped_column(Text, nullable=True)


class Contact(Base, BusinessMixin):
    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AccountCollaborator(Base):
    __tablename__ = "account_collaborator"
    __table_args__ = (UniqueConstraint("account_id", "user_id", name="uq_account_collaborator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="collaborator")


class Pipeline(Base, BusinessMixin):
    __tablename__ = "pipeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PipelineStage(Base, TimestampMixin):
    __tablename__ = "pipeline_stage"
    __table_args__ = (UniqueConstraint("pipeline_id", "code", name="uq_pipeline_stage_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    pipeline_id: Mapped[int] = mapped_column(Integer, ForeignKey("pipeline.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_probability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enter_required_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    need_approval: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Opportunity(Base, BusinessMixin):
    __tablename__ = "opportunity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="CNY")
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stage_id: Mapped[int] = mapped_column(Integer, ForeignKey("pipeline_stage.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False, index=True)
    competitor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    won_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OpportunityLine(Base, TimestampMixin):
    __tablename__ = "opportunity_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunity.id"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)


class OpportunityStageHistory(Base, TimestampMixin):
    __tablename__ = "opportunity_stage_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunity.id"), nullable=False, index=True)
    from_stage_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_stage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OpportunityCollaborator(Base):
    __tablename__ = "opportunity_collaborator"
    __table_args__ = (UniqueConstraint("opportunity_id", "user_id", name="uq_opp_collaborator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunity.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="collaborator")
