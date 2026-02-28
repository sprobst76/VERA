import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContractHistory(Base):
    __tablename__ = "contract_history"
    __table_args__ = (
        Index("ix_contract_history_employee_id", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = aktuell gültig

    # Vertragsfelder (Snapshot)
    contract_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    weekly_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    full_time_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    monthly_hours_limit: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    annual_salary_limit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
