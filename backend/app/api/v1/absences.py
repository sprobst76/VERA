import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.deps import DB, AdminUser, ManagerOrAdmin, CurrentUser
from app.models.absence import EmployeeAbsence, CareRecipientAbsence
from app.models.employee import Employee
from app.models.shift import Shift
from app.schemas.absence import (
    EmployeeAbsenceCreate, EmployeeAbsenceUpdate, EmployeeAbsenceOut,
    CareAbsenceCreate, CareAbsenceOut,
)
from app.services.notification_service import notify_absence_decision

router = APIRouter(tags=["absences"])

# ── Employee Absences ─────────────────────────────────────────────────────────

employee_absences_router = APIRouter(prefix="/absences")


@employee_absences_router.get("", response_model=list[EmployeeAbsenceOut])
async def list_absences(
    current_user: CurrentUser, db: DB,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
):
    query = select(EmployeeAbsence).where(EmployeeAbsence.tenant_id == current_user.tenant_id)

    if current_user.role != "admin":
        # Non-admin: only own absences
        emp_result = await db.execute(
            select(Employee.id).where(Employee.user_id == current_user.id)
        )
        own_id = emp_result.scalar_one_or_none()
        if own_id is None:
            return []
        query = query.where(EmployeeAbsence.employee_id == own_id)
    elif employee_id:
        query = query.where(EmployeeAbsence.employee_id == employee_id)

    if status:
        query = query.where(EmployeeAbsence.status == status)

    result = await db.execute(query.order_by(EmployeeAbsence.start_date.desc()))
    return result.scalars().all()


@employee_absences_router.post("", response_model=EmployeeAbsenceOut, status_code=status.HTTP_201_CREATED)
async def create_absence(payload: EmployeeAbsenceCreate, current_user: CurrentUser, db: DB):
    # Non-admin: can only create for themselves
    if current_user.role != "admin":
        emp_result = await db.execute(
            select(Employee.id).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        own_id = emp_result.scalar_one_or_none()
        if own_id is None:
            raise HTTPException(status_code=403, detail="Kein Mitarbeiterprofil verknüpft")
        if payload.employee_id != own_id:
            raise HTTPException(status_code=403, detail="Nur eigene Abwesenheiten erlaubt")

    # Verify employee belongs to tenant
    emp_check = await db.execute(
        select(Employee.id).where(
            Employee.id == payload.employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    if emp_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    absence = EmployeeAbsence(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(absence)
    await db.commit()
    await db.refresh(absence)
    return absence


@employee_absences_router.put("/{absence_id}", response_model=EmployeeAbsenceOut)
async def update_absence(absence_id: uuid.UUID, payload: EmployeeAbsenceUpdate, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(EmployeeAbsence).where(
            EmployeeAbsence.id == absence_id,
            EmployeeAbsence.tenant_id == current_user.tenant_id,
        )
    )
    absence = result.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(absence, field, value)

    if payload.status in ("approved", "rejected"):
        absence.approved_by = current_user.id
        absence.approved_at = datetime.now(timezone.utc)

    # When approved: cancel all shifts in the absence period
    if payload.status == "approved":
        shifts_result = await db.execute(
            select(Shift).where(
                and_(
                    Shift.employee_id == absence.employee_id,
                    Shift.tenant_id == current_user.tenant_id,
                    Shift.date >= absence.start_date,
                    Shift.date <= absence.end_date,
                    Shift.status.not_in(["cancelled", "cancelled_absence"]),
                )
            )
        )
        for shift in shifts_result.scalars().all():
            shift.status = "cancelled_absence"

    # When rejected: re-open previously cancelled_absence shifts
    if payload.status == "rejected":
        shifts_result = await db.execute(
            select(Shift).where(
                and_(
                    Shift.employee_id == absence.employee_id,
                    Shift.tenant_id == current_user.tenant_id,
                    Shift.date >= absence.start_date,
                    Shift.date <= absence.end_date,
                    Shift.status == "cancelled_absence",
                )
            )
        )
        for shift in shifts_result.scalars().all():
            shift.status = "planned"

    await db.commit()
    await db.refresh(absence)

    # Mitarbeiter benachrichtigen wenn Antrag entschieden wurde
    if payload.status in ("approved", "rejected"):
        emp_result = await db.execute(
            select(Employee)
            .options(selectinload(Employee.user))
            .where(Employee.id == absence.employee_id)
        )
        emp = emp_result.scalar_one_or_none()
        if emp:
            await notify_absence_decision(absence, emp, payload.status, db)

    return absence


# ── Care Recipient Absences ───────────────────────────────────────────────────

care_absences_router = APIRouter(prefix="/care-absences")


@care_absences_router.get("", response_model=list[CareAbsenceOut])
async def list_care_absences(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(CareRecipientAbsence)
        .where(CareRecipientAbsence.tenant_id == current_user.tenant_id)
        .order_by(CareRecipientAbsence.start_date.desc())
    )
    return result.scalars().all()


@care_absences_router.post("", response_model=CareAbsenceOut, status_code=status.HTTP_201_CREATED)
async def create_care_absence(payload: CareAbsenceCreate, current_user: AdminUser, db: DB):
    absence = CareRecipientAbsence(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(absence)
    await db.commit()
    await db.refresh(absence)
    return absence
