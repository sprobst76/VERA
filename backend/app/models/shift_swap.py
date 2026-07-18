import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShiftSwapOffer(Base):
    """
    Dienst-Abgabe: ein Mitarbeiter stellt einen bereits zugewiesenen Dienst zur
    Übernahme durch einen beliebigen Kollegen frei. Der Dienst selbst bleibt bis
    zum Vollzug unverändert zugewiesen (Overlay, keine Mutation des Shifts).

    status: open | pending_approval | completed | withdrawn | expired |
            denied | cancelled_system
    """
    __tablename__ = "shift_swap_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    offering_employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="open")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    accepted_by_employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolution_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    shift: Mapped["Shift"] = relationship(foreign_keys=[shift_id])
    offering_employee: Mapped["Employee"] = relationship(foreign_keys=[offering_employee_id])
    accepted_by: Mapped["Employee | None"] = relationship(foreign_keys=[accepted_by_employee_id])
