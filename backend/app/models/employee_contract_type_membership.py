import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmployeeContractTypeMembership(Base):
    """
    Verlauf der Gruppenmitgliedschaft eines Mitarbeiters (welchem ContractType zugeordnet).
    SCD Type 2: valid_to=NULL = aktuell aktiv.
    """
    __tablename__ = "employee_contract_type_memberships"
    __table_args__ = (
        Index("ix_employee_contract_type_memberships_employee_id", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    contract_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contract_types.id", ondelete="SET NULL"), nullable=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
