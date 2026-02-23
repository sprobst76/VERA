import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HolidayProfile(Base):
    __tablename__ = "holiday_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)  # z.B. "BW 2025/26"
    state: Mapped[str] = mapped_column(String(10), default="BW")    # Bundesland-Kürzel
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    vacation_periods: Mapped[list["VacationPeriod"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="VacationPeriod.start_date"
    )
    custom_holidays: Mapped[list["CustomHoliday"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="CustomHoliday.date"
    )
    recurring_shifts: Mapped[list["RecurringShift"]] = relationship(  # type: ignore[name-defined]
        back_populates="holiday_profile"
    )


class VacationPeriod(Base):
    __tablename__ = "vacation_periods"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("holiday_profiles.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)   # z.B. "Herbstferien"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#a6e3a1")  # Catppuccin green

    profile: Mapped["HolidayProfile"] = relationship(back_populates="vacation_periods")


class CustomHoliday(Base):
    __tablename__ = "custom_holidays"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("holiday_profiles.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)    # z.B. "Konferenztag"
    color: Mapped[str] = mapped_column(String(20), default="#fab387")  # Catppuccin peach

    profile: Mapped["HolidayProfile"] = relationship(back_populates="custom_holidays")
