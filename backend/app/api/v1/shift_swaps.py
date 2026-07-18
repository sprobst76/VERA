"""
Dienst-Abgabe ("Schichttausch" MVP): ein Mitarbeiter stellt einen bereits
zugewiesenen Dienst zur Übernahme durch einen beliebigen Kollegen frei.

Zustandsmaschine: open -> completed | pending_approval -> completed | denied
                        -> withdrawn | expired | cancelled_system

Hybrid-Genehmigung: Dienste im Status "planned" werden bei Annahme sofort
wirksam (wie der bestehende Pool-Claim, inkl. Compliance-Vorabprüfung).
Dienste im Status "confirmed" brauchen eine Admin/Manager-Genehmigung
(konsistent mit der bestehenden Regel, dass bestätigte Dienste nur
Admin/Manager ändern dürfen).
"""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, update, or_

from app.api.deps import DB, CurrentUser, ManagerOrAdmin
from app.api.deps import get_own_employee_id as _own_employee_id
from app.models.employee import Employee
from app.models.shift import Shift
from app.models.shift_swap import ShiftSwapOffer
from app.schemas.shift_swap import ShiftSwapOfferCreate, ShiftSwapOfferOut, ShiftSwapReview
from app.services import audit_service
from app.services.compliance_service import ComplianceService
from app.services.notification_service import (
    notify_swap_offer_open, notify_swap_offer_created, notify_swap_accepted,
    notify_swap_pending_approval, notify_swap_approved, notify_swap_denied,
    notify_swap_cancelled,
)

router = APIRouter(prefix="/shift-swaps", tags=["shift-swaps"])

_BERLIN = ZoneInfo("Europe/Berlin")

# Verstöße, die eine Annahme/Genehmigung blockieren — dieselbe Philosophie wie
# beim bestehenden Claim-Vorab-Check: nur was die Annahme SELBST auslöst.
_BLOCKING_KEYWORDS = ("Ruhezeit", "Minijob-Jahresgrenze")


def _blocking_violations(cr) -> list[str]:
    return [v for v in cr.violations if any(k in v for k in _BLOCKING_KEYWORDS)]


async def cancel_active_offers_for_shifts(shift_ids: list[uuid.UUID], db, reason: str) -> None:
    """System-Hook: storniert offene/genehmigungspflichtige Angebote für Dienste,
    die anderweitig verändert wurden (storniert, gelöscht, Abwesenheit genehmigt)."""
    if not shift_ids:
        return
    result = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.shift_id.in_(shift_ids),
            ShiftSwapOffer.status.in_(("open", "pending_approval")),
        )
    )
    offers = result.scalars().all()
    for offer in offers:
        offer.status = "cancelled_system"
        offer.resolution_reason = reason
    if offers:
        await db.flush()
        for offer in offers:
            await notify_swap_cancelled(offer, reason, db)


@router.post("", response_model=ShiftSwapOfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(payload: ShiftSwapOfferCreate, current_user: CurrentUser, db: DB):
    """Eigenen Dienst zur Übernahme durch einen Kollegen freistellen."""
    if current_user.role in ("admin", "manager", "parent_viewer"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter können eigene Dienste anbieten")

    own_id = await _own_employee_id(current_user, db)
    if own_id is None:
        raise HTTPException(status_code=403, detail="Kein Mitarbeiterprofil verknüpft")

    result = await db.execute(
        select(Shift).where(Shift.id == payload.shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")
    if shift.employee_id != own_id:
        raise HTTPException(status_code=403, detail="Nur eigene Dienste können angeboten werden")
    if shift.status not in ("planned", "confirmed"):
        raise HTTPException(status_code=400, detail=f"Dienst im Status '{shift.status}' kann nicht angeboten werden")

    shift_start = datetime.combine(shift.date, shift.start_time, tzinfo=_BERLIN).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if shift_start - now < timedelta(hours=2):
        raise HTTPException(status_code=400, detail="Dienst beginnt zu bald, um noch angeboten zu werden")

    existing = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.shift_id == shift.id,
            ShiftSwapOffer.status.in_(("open", "pending_approval")),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Für diesen Dienst läuft bereits ein Angebot")

    expires_at = min(now + timedelta(hours=48), shift_start - timedelta(hours=2))

    offer = ShiftSwapOffer(
        tenant_id=current_user.tenant_id,
        shift_id=shift.id,
        offering_employee_id=own_id,
        status="open",
        note=payload.note,
        expires_at=expires_at,
    )
    db.add(offer)
    await db.flush()

    await audit_service.write(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                               entity_type="shift_swap_offer", entity_id=offer.id, action="create",
                               new_values={"shift_id": str(shift.id), "note": payload.note})
    await db.commit()
    await db.refresh(offer)

    offering_emp = await db.get(Employee, own_id)
    await notify_swap_offer_open(offer, shift, offering_emp, db)
    await notify_swap_offer_created(offer, shift, offering_emp, db)

    return offer


@router.get("", response_model=list[ShiftSwapOfferOut])
async def list_offers(
    current_user: CurrentUser,
    db: DB,
    status_filter: str | None = Query(None, alias="status"),
):
    if current_user.role == "parent_viewer":
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    query = select(ShiftSwapOffer).where(ShiftSwapOffer.tenant_id == current_user.tenant_id)

    if current_user.role not in ("admin", "manager"):
        own_id = await _own_employee_id(current_user, db)
        query = query.where(
            or_(ShiftSwapOffer.offering_employee_id == own_id, ShiftSwapOffer.status == "open")
        )

    if status_filter:
        query = query.where(ShiftSwapOffer.status == status_filter)

    result = await db.execute(query.order_by(ShiftSwapOffer.created_at.desc()))
    return result.scalars().all()


@router.get("/{offer_id}", response_model=ShiftSwapOfferOut)
async def get_offer(offer_id: uuid.UUID, current_user: CurrentUser, db: DB):
    if current_user.role == "parent_viewer":
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    result = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.id == offer_id, ShiftSwapOffer.tenant_id == current_user.tenant_id
        )
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden")

    if current_user.role not in ("admin", "manager"):
        own_id = await _own_employee_id(current_user, db)
        if offer.offering_employee_id != own_id and offer.status != "open":
            raise HTTPException(status_code=403, detail="Zugriff verweigert")

    return offer


@router.post("/{offer_id}/accept", response_model=ShiftSwapOfferOut)
async def accept_offer(offer_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Offenes Angebot annehmen. Bei 'planned'-Diensten sofort wirksam (nach
    Compliance-Vorabprüfung), bei 'confirmed'-Diensten geht es in Genehmigung."""
    if current_user.role in ("admin", "manager", "parent_viewer"):
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter können Angebote annehmen")

    own_id = await _own_employee_id(current_user, db)
    if own_id is None:
        raise HTTPException(status_code=403, detail="Kein Mitarbeiterprofil verknüpft")

    offer_result = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.id == offer_id, ShiftSwapOffer.tenant_id == current_user.tenant_id
        )
    )
    offer = offer_result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden")
    if offer.offering_employee_id == own_id:
        raise HTTPException(status_code=400, detail="Eigenes Angebot kann nicht selbst angenommen werden")

    shift_result = await db.execute(select(Shift).where(Shift.id == offer.shift_id))
    shift = shift_result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")

    target_status = "pending_approval" if shift.status == "confirmed" else "completed"

    # Atomarer bedingter Übergang: nur die Anfrage, die das Angebot noch im
    # Status 'open' antrifft, gewinnt. Auf Postgres hält das UPDATE den
    # Row-Lock bis zum Commit/Rollback, ein gleichzeitiger zweiter Accept
    # blockiert und bekommt danach rowcount==0.
    claim = await db.execute(
        update(ShiftSwapOffer)
        .where(ShiftSwapOffer.id == offer_id, ShiftSwapOffer.status == "open")
        .values(status=target_status, accepted_by_employee_id=own_id, accepted_at=datetime.now(timezone.utc))
    )
    if claim.rowcount == 0:
        raise HTTPException(status_code=409, detail="Angebot ist nicht mehr verfügbar")

    accepting_emp = await db.get(Employee, own_id)
    compliance = ComplianceService(db)
    cr = await compliance.check_shift(shift, accepting_emp)
    blocking = _blocking_violations(cr)
    if blocking:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Kann nicht übernommen werden: {'; '.join(blocking)}")

    offering_emp = await db.get(Employee, offer.offering_employee_id)

    if target_status == "completed":
        old_employee_id = shift.employee_id
        shift.employee_id = own_id
        shift.acknowledged_at = None
        await audit_service.write(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                                   entity_type="shift", entity_id=shift.id, action="swap_completed",
                                   old_values={"employee_id": str(old_employee_id)},
                                   new_values={"employee_id": str(own_id)})

    await db.commit()
    await db.refresh(offer)

    if target_status == "completed":
        await notify_swap_accepted(offer, shift, offering_emp, accepting_emp, db)
    else:
        await notify_swap_pending_approval(offer, shift, db)

    return offer


@router.post("/{offer_id}/withdraw", response_model=ShiftSwapOfferOut)
async def withdraw_offer(offer_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Anbieter (oder Admin/Manager) zieht ein noch nicht vollzogenes Angebot zurück."""
    result = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.id == offer_id, ShiftSwapOffer.tenant_id == current_user.tenant_id
        )
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden")

    if current_user.role not in ("admin", "manager"):
        own_id = await _own_employee_id(current_user, db)
        if own_id != offer.offering_employee_id:
            raise HTTPException(status_code=403, detail="Nur der Anbieter oder Admin/Manager können zurückziehen")

    if offer.status not in ("open", "pending_approval"):
        raise HTTPException(status_code=400, detail=f"Angebot im Status '{offer.status}' kann nicht zurückgezogen werden")

    offer.status = "withdrawn"
    await db.commit()
    await db.refresh(offer)
    return offer


@router.post("/{offer_id}/review", response_model=ShiftSwapOfferOut)
async def review_offer(offer_id: uuid.UUID, payload: ShiftSwapReview, current_user: ManagerOrAdmin, db: DB):
    """Admin/Manager genehmigt oder lehnt ein Angebot ab, das auf einem
    bereits bestätigten Dienst angenommen wurde (Status 'pending_approval')."""
    result = await db.execute(
        select(ShiftSwapOffer).where(
            ShiftSwapOffer.id == offer_id, ShiftSwapOffer.tenant_id == current_user.tenant_id
        )
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Angebot nicht gefunden")
    if offer.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Angebot ist nicht in Genehmigung (Status: {offer.status})")

    shift_result = await db.execute(select(Shift).where(Shift.id == offer.shift_id))
    shift = shift_result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")

    offer.reviewed_by = current_user.id
    offer.reviewed_at = datetime.now(timezone.utc)
    offer.review_note = payload.note

    offering_emp = await db.get(Employee, offer.offering_employee_id)
    accepting_emp = await db.get(Employee, offer.accepted_by_employee_id)

    if not payload.approved:
        offer.status = "denied"
        await db.commit()
        await db.refresh(offer)
        await notify_swap_denied(offer, shift, offering_emp, accepting_emp, db)
        return offer

    compliance = ComplianceService(db)
    cr = await compliance.check_shift(shift, accepting_emp)
    blocking = _blocking_violations(cr)
    if blocking:
        raise HTTPException(status_code=409, detail=f"Genehmigung nicht möglich: {'; '.join(blocking)}")

    old_employee_id = shift.employee_id
    shift.employee_id = offer.accepted_by_employee_id
    shift.acknowledged_at = None
    offer.status = "completed"

    await audit_service.write(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                               entity_type="shift", entity_id=shift.id, action="swap_completed",
                               old_values={"employee_id": str(old_employee_id)},
                               new_values={"employee_id": str(offer.accepted_by_employee_id)})

    await db.commit()
    await db.refresh(offer)
    await notify_swap_approved(offer, shift, offering_emp, accepting_emp, db)
    return offer
