import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContractType(Base):
    """
    Vertragstyp (Vorlage) für Gruppen von Mitarbeitern.
    z.B. "Minijob Standard" mit Stundenlohn 13,50 €, Limit 38 h/Monat.
    Bei Änderung des Typs → neue ContractHistory-Einträge für alle verknüpften Mitarbeiter.
    """
    __tablename__ = "contract_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vertragsparameter
    contract_category: Mapped[str] = mapped_column(String(50), nullable=False)  # minijob | part_time | full_time
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    monthly_hours_limit: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    annual_salary_limit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    annual_hours_target: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    weekly_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Employees linked to this type
    employees: Mapped[list["Employee"]] = relationship(  # type: ignore[name-defined]
        back_populates="contract_type_obj",
        foreign_keys="Employee.contract_type_id",
    )
