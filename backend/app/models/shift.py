import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, Integer, Time, Date, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weekdays: Mapped[list] = mapped_column(JSON, nullable=False)  # [0,1,2] = Mo,Di,Mi
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)

    color: Mapped[str] = mapped_column(String(20), default="#1E3A5F")  # Hex-Farbe

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    shifts: Mapped[list["Shift"]] = relationship(back_populates="template")


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shift_templates.id"), nullable=True)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50), default="planned"
    )  # planned | confirmed | completed | cancelled | cancelled_absence
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    actual_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    actual_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Confirmation tracking
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Compliance flags (auto-computed)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sunday: Mapped[bool] = mapped_column(Boolean, default=False)
    rest_period_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    break_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    minijob_limit_ok: Mapped[bool] = mapped_column(Boolean, default=True)

    hours_carried_over: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Recurring shift link
    recurring_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recurring_shifts.id", ondelete="SET NULL"), nullable=True
    )
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    employee: Mapped["Employee | None"] = relationship(back_populates="shifts")
    template: Mapped["ShiftTemplate | None"] = relationship(back_populates="shifts")
    recurring_shift: Mapped["RecurringShift | None"] = relationship(  # type: ignore[name-defined]
        back_populates="generated_shifts",
        foreign_keys=[recurring_shift_id],
    )

    @property
    def duration_hours(self) -> float:
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        if end < start:
            from datetime import timedelta
            end += timedelta(days=1)
        net_minutes = (end - start).total_seconds() / 60 - self.break_minutes
        return max(0, net_minutes / 60)
