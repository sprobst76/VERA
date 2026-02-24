import uuid
from datetime import date, timedelta, datetime, timezone

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, and_

from app.api.deps import DB, AdminUser, CurrentUser, ManagerOrAdmin
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.shift import Shift, ShiftTemplate
from app.services.compliance_service import ComplianceService
from app.schemas.shift import (
    ShiftCreate, ShiftUpdate, ShiftOut, ShiftActualTime, ShiftConfirm,
    ShiftTemplateCreate, ShiftTemplateOut, BulkShiftCreate,
)

router = APIRouter(tags=["shifts"])

PRIVILEGED_ROLES = ("admin", "manager")


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
    except Exception:
        pass  # Compliance-Fehler nie die eigentliche Operation blockieren


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
        # Non-privileged: only own shifts — ignore any employee_id filter from client
        own_id = await _own_employee_id(current_user, db)
        if own_id is None:
            return []  # User has no linked employee record
        conditions.append(Shift.employee_id == own_id)
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


def _set_weekend_flags(shift: Shift) -> None:
    weekday = shift.date.weekday()
    shift.is_weekend = weekday >= 5
    shift.is_sunday = weekday == 6
