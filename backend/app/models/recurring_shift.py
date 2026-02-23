import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, Time, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RecurringShift(Base):
    __tablename__ = "recurring_shifts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    weekday: Mapped[int] = mapped_column(Integer, nullable=False)   # 0=Mo, 6=So
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)

    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shift_templates.id", ondelete="SET NULL"), nullable=True
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)

    holiday_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("holiday_profiles.id", ondelete="SET NULL"), nullable=True
    )
    skip_public_holidays: Mapped[bool] = mapped_column(Boolean, default=True)

    label: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Freitext-Bezeichnung

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    employee: Mapped["Employee | None"] = relationship()  # type: ignore[name-defined]
    template: Mapped["ShiftTemplate | None"] = relationship()  # type: ignore[name-defined]
    holiday_profile: Mapped["HolidayProfile | None"] = relationship(  # type: ignore[name-defined]
        back_populates="recurring_shifts"
    )
    generated_shifts: Mapped[list["Shift"]] = relationship(  # type: ignore[name-defined]
        back_populates="recurring_shift",
        foreign_keys="Shift.recurring_shift_id",
    )
