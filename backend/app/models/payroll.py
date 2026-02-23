import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HoursCarryover(Base):
    __tablename__ = "hours_carryover"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)

    from_month: Mapped[date] = mapped_column(Date, nullable=False)
    to_month: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PayrollEntry(Base):
    __tablename__ = "payroll_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)  # First day of month

    # Hours
    planned_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    carryover_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    paid_hours: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Surcharge hours
    early_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    late_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    night_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    weekend_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    sunday_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    holiday_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    # Wages
    base_wage: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    early_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    late_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    night_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    weekend_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    sunday_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    holiday_surcharge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_gross: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Minijob tracking
    ytd_gross: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    annual_limit_remaining: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft | approved | paid
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="payroll_entries")
