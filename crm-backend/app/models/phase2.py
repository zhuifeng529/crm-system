from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import BusinessMixin, TimestampMixin


class Contract(Base, BusinessMixin):
    __tablename__ = "contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False)
    opportunity_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("opportunity.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ContractPaymentPlan(Base, BusinessMixin):
    __tablename__ = "contract_payment_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contract.id"), nullable=False, index=True)
    due_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")


class PaymentRecord(Base, BusinessMixin):
    __tablename__ = "payment_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("contract_payment_plan.id"), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)


class InvoiceRequest(Base, BusinessMixin):
    __tablename__ = "invoice_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contract.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Campaign(Base, BusinessMixin):
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class CampaignMember(Base, TimestampMixin):
    __tablename__ = "campaign_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=False, index=True)
    lead_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lead.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("account.id"), nullable=True)


class Ticket(Base, BusinessMixin):
    __tablename__ = "ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=True)
    requester_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_account.id"), nullable=True)


class TicketEvent(Base, TimestampMixin):
    __tablename__ = "ticket_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("ticket.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountHealthScore(Base, TimestampMixin):
    __tablename__ = "account_health_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
