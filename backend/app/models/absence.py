import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmployeeAbsence(Base):
    __tablename__ = "employee_absences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)

    type: Mapped[str] = mapped_column(String(50), nullable=False)  # vacation | sick | school_holiday | other
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | approved | rejected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(back_populates="absences")


class CareRecipientAbsence(Base):
    __tablename__ = "care_recipient_absences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    type: Mapped[str] = mapped_column(String(50), nullable=False)  # vacation | rehab | hospital | sick | other
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    shift_handling: Mapped[str] = mapped_column(
        String(50), default="cancelled_unpaid"
    )  # cancelled_unpaid | carry_over | paid_anyway
    notify_employees: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
