import logging
import uuid
from datetime import date, timedelta, datetime, timezone

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

from app.api.deps import DB, AdminUser, CurrentUser, ManagerOrAdmin
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.shift import Shift, ShiftTemplate
from app.services.compliance_service import ComplianceService
from app.services.notification_service import (
    notify_shift_assigned, notify_shift_changed,
    notify_pool_shift_open, notify_shift_claimed,
)
from app.api.v1.webhooks import dispatch_event
from app.schemas.shift import (
    ShiftCreate, ShiftUpdate, ShiftOut, ShiftActualTime, ShiftConfirm,
    ShiftTemplateCreate, ShiftTemplateOut, BulkShiftCreate,
    TimeCorrectionCreate, TimeCorrectionReview,
)

router = APIRouter(tags=["shifts"])

PRIVILEGED_ROLES = ("admin", "manager", "parent_viewer")


# ── Helper: resolve employee_id for current (non-admin) user ─────────────────

async def _own_employee_id(current_user, db) -> uuid.UUID | None:
    """Return the Employee.id linked to this User, or None if not found."""
    result = await db.execute(
        select(Employee.id).where(Employee.user_id == current_user.id)
    )
    return result.scalar_one_or_none()


async def _write_audit(db, *, tenant_id, user_id, entity_id, action: str,
                        old_values: dict | None = None, new_values: dict | None = None):
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="shift",
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(log)


# ── Shift Templates ──────────────────────────────────────────────────────────

templates_router = APIRouter(prefix="/shift-templates")


@templates_router.get("", response_model=list[ShiftTemplateOut])
async def list_templates(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(ShiftTemplate).where(
            ShiftTemplate.tenant_id == current_user.tenant_id,
            ShiftTemplate.is_active == True,
        ).order_by(ShiftTemplate.name)
    )
    return result.scalars().all()


@templates_router.post("", response_model=ShiftTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(payload: ShiftTemplateCreate, current_user: ManagerOrAdmin, db: DB):
    template = ShiftTemplate(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@templates_router.put("/{template_id}", response_model=ShiftTemplateOut)
async def update_template(template_id: uuid.UUID, payload: ShiftTemplateCreate, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(ShiftTemplate).where(
            ShiftTemplate.id == template_id,
            ShiftTemplate.tenant_id == current_user.tenant_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return template


# ── Compliance helper ─────────────────────────────────────────────────────────

async def _run_compliance(shift: "Shift", db) -> None:
    """Compliance-Flags auf dem Shift aktualisieren (kein Fehler bei Problemen)."""
    if not shift.employee_id:
        return
    emp = await db.get(Employee, shift.employee_id)
    if not emp:
        return
    try:
        svc = ComplianceService(db)
        cr = await svc.check_shift(shift, emp)
        shift.rest_period_ok   = not any("Ruhezeit" in v for v in cr.violations)
        shift.break_ok         = not any("Pause"    in v for v in cr.violations)
        shift.minijob_limit_ok = not any("Minijob"  in v for v in cr.violations)
        await db.commit()
        await db.refresh(shift)
    except Exception as e:
        logger.warning("Compliance-Check fehlgeschlagen für Shift %s: %s", shift.id, e)


# ── Shifts ───────────────────────────────────────────────────────────────────

shifts_router = APIRouter(prefix="/shifts")


@shifts_router.get("", response_model=list[ShiftOut])
async def list_shifts(
    current_user: CurrentUser,
    db: DB,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    employee_id: uuid.UUID | None = Query(None),
):
    conditions = [Shift.tenant_id == current_user.tenant_id]

    if current_user.role not in PRIVILEGED_ROLES:
        # Non-privileged: own shifts + open (unassigned) shifts in same tenant → Pool
        own_id = await _own_employee_id(current_user, db)
        if own_id is None:
            return []  # User has no linked employee record
        from sqlalchemy import or_
        conditions.append(
            or_(Shift.employee_id == own_id, Shift.employee_id.is_(None))
        )
    else:
        # Admin/manager: optional employee filter
        if employee_id:
            conditions.append(Shift.employee_id == employee_id)

    if from_date:
        conditions.append(Shift.date >= from_date)
    if to_date:
        conditions.append(Shift.date <= to_date)

    result = await db.execute(
        select(Shift).where(and_(*conditions)).order_by(Shift.date, Shift.start_time)
    )
    return result.scalars().all()


@shifts_router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
async def create_shift(payload: ShiftCreate, current_user: ManagerOrAdmin, db: DB):
    shift = Shift(tenant_id=current_user.tenant_id, **payload.model_dump())
    _set_weekend_flags(shift)
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    await _run_compliance(shift, db)
    if shift.employee_id:
        emp = await db.get(Employee, shift.employee_id)
        if emp:
            await notify_shift_assigned(shift, emp, db)
    else:
        # Offener Dienst → alle Mitarbeiter benachrichtigen
        await notify_pool_shift_open(shift, db)
    await dispatch_event(db, current_user.tenant_id, "shift.created", {
        "shift_id": str(shift.id), "date": str(shift.date),
        "employee_id": str(shift.employee_id) if shift.employee_id else None,
    })
    return shift


@shifts_router.post("/bulk", response_model=list[ShiftOut], status_code=status.HTTP_201_CREATED)
async def create_bulk_shifts(payload: BulkShiftCreate, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(ShiftTemplate).where(
            ShiftTemplate.id == payload.template_id,
            ShiftTemplate.tenant_id == current_user.tenant_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    shifts = []
    current_date = payload.from_date
    while current_date <= payload.to_date:
        if current_date.weekday() in template.weekdays:
            shift = Shift(
                tenant_id=current_user.tenant_id,
                template_id=template.id,
                employee_id=payload.employee_id,
                date=current_date,
                start_time=payload.start_time_override or template.start_time,
                end_time=payload.end_time_override or template.end_time,
                break_minutes=template.break_minutes,
                location=template.location,
                notes=template.notes,
            )
            _set_weekend_flags(shift)
            db.add(shift)
            shifts.append(shift)
        current_date += timedelta(days=1)

    await db.commit()
    for s in shifts:
        await db.refresh(s)
    return shifts


@shifts_router.get("/{shift_id}", response_model=ShiftOut)
async def get_shift(shift_id: uuid.UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # Non-privileged may only access their own shifts
    if current_user.role not in PRIVILEGED_ROLES:
        own_id = await _own_employee_id(current_user, db)
        if own_id is None or shift.employee_id != own_id:
            raise HTTPException(status_code=404, detail="Shift not found")

    return shift


@shifts_router.put("/{shift_id}", response_model=ShiftOut)
async def update_shift(shift_id: uuid.UUID, payload: ShiftUpdate, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    is_privileged = current_user.role in PRIVILEGED_ROLES

    # ── Permission matrix ────────────────────────────────────────────────────
    if shift.status == "planned":
        if not is_privileged:
            # Employee: only own shift, only actual times + notes
            own_id = await _own_employee_id(current_user, db)
            if own_id is None or shift.employee_id != own_id:
                raise HTTPException(status_code=403, detail="Zugriff verweigert")
            allowed = {"actual_start", "actual_end", "notes"}
            payload_dict = payload.model_dump(exclude_unset=True)
            forbidden = set(payload_dict.keys()) - allowed
            if forbidden:
                raise HTTPException(
                    status_code=403,
                    detail=f"Mitarbeiter dürfen nur Ist-Zeiten und Notizen ändern (verboten: {forbidden})",
                )
    elif shift.status == "confirmed":
        if not is_privileged:
            raise HTTPException(status_code=403, detail="Bestätigte Dienste können nur von Admin/Verwalter geändert werden")
    else:
        # cancelled / completed / cancelled_absence
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Nur Admins können abgeschlossene/stornierte Dienste bearbeiten")

    # Capture old values for audit log
    old_values = {f: str(getattr(shift, f)) for f in payload.model_dump(exclude_unset=True)}

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shift, field, value)

    _set_weekend_flags(shift)

    new_values = {f: str(getattr(shift, f)) for f in payload.model_dump(exclude_unset=True)}
    await _write_audit(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                        entity_id=shift_id, action="update",
                        old_values=old_values, new_values=new_values)

    await db.commit()
    await db.refresh(shift)
    await _run_compliance(shift, db)
    # Notification: Zuweisung oder Zeitänderung
    if shift.employee_id:
        emp = await db.get(Employee, shift.employee_id)
        if emp:
            payload_keys = set(payload.model_dump(exclude_unset=True).keys())
            if "employee_id" in payload_keys and old_values.get("employee_id") in ("None", None):
                await notify_shift_assigned(shift, emp, db)
            else:
                changed = [f for f in ("start_time", "end_time", "location") if f in payload_keys]
                if changed:
                    await notify_shift_changed(shift, emp, changed, db)
    # Webhook: shift.updated or shift.cancelled
    event = "shift.cancelled" if shift.status in ("cancelled", "cancelled_absence") else "shift.updated"
    await dispatch_event(db, current_user.tenant_id, event, {
        "shift_id": str(shift.id), "date": str(shift.date),
        "status": shift.status,
        "employee_id": str(shift.employee_id) if shift.employee_id else None,
    })
    return shift


@shifts_router.post("/{shift_id}/confirm", response_model=ShiftOut)
async def confirm_shift(shift_id: uuid.UUID, payload: ShiftConfirm, current_user: ManagerOrAdmin, db: DB):
    """Admin/Manager confirms a shift (planned → confirmed). Logged to audit trail."""
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    if shift.status != "planned":
        raise HTTPException(
            status_code=400,
            detail=f"Dienst kann nicht bestätigt werden – aktueller Status: {shift.status}",
        )

    old_status = shift.status
    shift.status = "confirmed"
    shift.confirmed_by = current_user.id
    shift.confirmed_at = datetime.now(timezone.utc)
    if payload.confirmation_note is not None:
        shift.confirmation_note = payload.confirmation_note
    if payload.actual_start is not None:
        shift.actual_start = payload.actual_start
    if payload.actual_end is not None:
        shift.actual_end = payload.actual_end

    await _write_audit(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                        entity_id=shift_id, action="confirm",
                        old_values={"status": old_status},
                        new_values={
                            "status": "confirmed",
                            "confirmed_by": str(current_user.id),
                            "confirmed_at": shift.confirmed_at.isoformat(),
                            "confirmation_note": payload.confirmation_note,
                        })

    await db.commit()
    await db.refresh(shift)
    return shift


@shifts_router.post("/{shift_id}/claim", response_model=ShiftOut)
async def claim_shift(shift_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Employee claims an open shift (no employee_id assigned)."""
    if current_user.role in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Nur Mitarbeiter können offene Dienste annehmen")

    own_id = await _own_employee_id(current_user, db)
    if own_id is None:
        raise HTTPException(status_code=403, detail="Kein Mitarbeiterprofil verknüpft")

    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")

    if shift.employee_id is not None:
        raise HTTPException(status_code=409, detail="Dienst ist bereits vergeben")

    if shift.status != "planned":
        raise HTTPException(status_code=400, detail="Nur geplante Dienste können angenommen werden")

    shift.employee_id = own_id

    await _write_audit(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                        entity_id=shift_id, action="claim",
                        old_values={"employee_id": None},
                        new_values={"employee_id": str(own_id)})

    await db.commit()
    await db.refresh(shift)

    # Admin/Manager über Dienstannahme informieren
    claiming_emp = await db.get(Employee, own_id)
    if claiming_emp:
        await notify_shift_claimed(shift, claiming_emp, db)

    return shift


@shifts_router.post("/{shift_id}/time-correction", response_model=ShiftOut)
async def submit_time_correction(
    shift_id: uuid.UUID,
    payload: TimeCorrectionCreate,
    current_user: CurrentUser,
    db: DB,
):
    """
    Employee (own shift) or Admin/Manager submits actual worked times for review.
    Allowed when shift status is 'confirmed' or 'completed'.
    Sets time_correction_status = 'pending'.
    """
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")

    is_privileged = current_user.role in PRIVILEGED_ROLES

    if not is_privileged:
        own_id = await _own_employee_id(current_user, db)
        if own_id is None or shift.employee_id != own_id:
            raise HTTPException(status_code=403, detail="Zugriff verweigert")

    if shift.status not in ("confirmed", "completed"):
        raise HTTPException(
            status_code=400,
            detail="Zeitkorrektur nur für bestätigte oder abgeschlossene Dienste möglich",
        )

    if shift.time_correction_status == "pending":
        raise HTTPException(status_code=400, detail="Korrektur wartet bereits auf Bestätigung")

    old_actual_start = str(shift.actual_start)
    shift.actual_start = payload.actual_start
    shift.actual_end = payload.actual_end
    shift.actual_break_minutes = payload.actual_break_minutes
    shift.time_correction_note = payload.note
    shift.time_correction_status = "pending"
    # Clear previous confirmation
    shift.time_correction_confirmed_by = None
    shift.time_correction_confirmed_at = None

    await _write_audit(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                        entity_id=shift_id, action="time_correction_submit",
                        old_values={"actual_start": old_actual_start},
                        new_values={
                            "actual_start": str(payload.actual_start),
                            "actual_end": str(payload.actual_end),
                            "actual_break_minutes": str(payload.actual_break_minutes),
                            "note": payload.note,
                        })

    await db.commit()
    await db.refresh(shift)
    return shift


@shifts_router.put("/{shift_id}/time-correction", response_model=ShiftOut)
async def review_time_correction(
    shift_id: uuid.UUID,
    payload: TimeCorrectionReview,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """
    Admin/Manager approves or rejects a pending time correction.
    approved=True  → time_correction_status = 'confirmed' (payroll uses actual times)
    approved=False → time_correction_status = 'rejected'
    """
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")

    if shift.time_correction_status != "pending":
        raise HTTPException(status_code=400, detail="Keine ausstehende Korrektur für diesen Dienst")

    if payload.approved:
        shift.time_correction_status = "confirmed"
        shift.time_correction_confirmed_by = current_user.id
        shift.time_correction_confirmed_at = datetime.now(timezone.utc)
        if payload.note:
            shift.time_correction_note = payload.note
    else:
        shift.time_correction_status = "rejected"
        if payload.note:
            shift.time_correction_note = payload.note

    await _write_audit(db, tenant_id=current_user.tenant_id, user_id=current_user.id,
                        entity_id=shift_id, action="time_correction_review",
                        new_values={
                            "approved": str(payload.approved),
                            "status": shift.time_correction_status,
                            "note": payload.note,
                        })

    await db.commit()
    await db.refresh(shift)
    return shift


@shifts_router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(shift_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.tenant_id == current_user.tenant_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    await db.delete(shift)
    await db.commit()


@shifts_router.get("/{shift_id}/suggestions")
async def suggest_employees_for_shift(
    shift_id: uuid.UUID,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """
    Gibt sortierte Mitarbeiter-Vorschläge für einen offenen Dienst zurück.
    Scoring: Keine Konflikte (+30), Qualifikation (+25), Limit (+20), Ruhezeit (+15).
    """
    from app.services.matching_service import MatchingService
    svc = MatchingService(db)
    return await svc.suggest_employees(shift_id, current_user.tenant_id)


def _set_weekend_flags(shift: Shift) -> None:
    weekday = shift.date.weekday()
    shift.is_weekend = weekday >= 5
    shift.is_sunday = weekday == 6
