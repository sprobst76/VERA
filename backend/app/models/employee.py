import uuid
from datetime import datetime, time, timezone

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, Integer, Time, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    contract_type: Mapped[str] = mapped_column(String(50), nullable=False)  # minijob | part_time | full_time
    hourly_rate: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    monthly_hours_limit: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    annual_salary_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=6672.0)
    vacation_days: Mapped[int] = mapped_column(Integer, default=30)

    qualifications: Mapped[list] = mapped_column(JSON, default=list)
    notification_prefs: Mapped[dict] = mapped_column(JSON, default=dict)

    ical_token: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matrix_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quiet_hours_start: Mapped[time] = mapped_column(Time, default=time(21, 0))
    quiet_hours_end: Mapped[time] = mapped_column(Time, default=time(7, 0))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="employees")
    user: Mapped["User | None"] = relationship(back_populates="employee")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="employee")
    absences: Mapped[list["EmployeeAbsence"]] = relationship(back_populates="employee")
    payroll_entries: Mapped[list["PayrollEntry"]] = relationship(back_populates="employee")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
