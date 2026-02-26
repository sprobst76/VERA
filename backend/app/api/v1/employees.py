import secrets
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, AdminUser, CurrentUser
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeePublicOut


class EmployeeSelfUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None

router = APIRouter(prefix="/employees", tags=["employees"])


# ── Eigenes Profil (jeder Mitarbeiter) ───────────────────────────────────────

@router.get("/me", response_model=EmployeeOut)
async def get_own_employee(current_user: CurrentUser, db: DB):
    """Gibt das vollständige eigene Mitarbeiterprofil zurück (Gehalt, Kontakt etc.)."""
    result = await db.execute(
        select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Kein Mitarbeiterprofil mit diesem Account verknüpft")
    return employee


@router.put("/me", response_model=EmployeeOut)
async def update_own_employee(payload: EmployeeSelfUpdate, current_user: CurrentUser, db: DB):
    """Mitarbeiter bearbeitet eigenes Profil (nur phone und email)."""
    result = await db.execute(
        select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Kein Mitarbeiterprofil mit diesem Account verknüpft")
    if payload.phone is not None:
        employee.phone = payload.phone or None
    if payload.email is not None:
        employee.email = payload.email or None
    await db.commit()
    await db.refresh(employee)
    return employee


# ── Mitarbeiterliste ─────────────────────────────────────────────────────────

@router.get("", response_model=list[Any])
async def list_employees(current_user: CurrentUser, db: DB, active_only: bool = True):
    """
    Admin:       Vollständige Daten aller Mitarbeiter (EmployeeOut).
    Mitarbeiter: Öffentliche Namen-/Qualifikationsinfos aller Kollegen (EmployeePublicOut).
                 Eigene Daten bitte über GET /employees/me abrufen.
    """
    query = select(Employee).where(Employee.tenant_id == current_user.tenant_id)
    if active_only:
        query = query.where(Employee.is_active == True)
    result = await db.execute(query.order_by(Employee.last_name))
    employees = result.scalars().all()

    if current_user.role == "admin":
        return [EmployeeOut.model_validate(e).model_dump(mode="json") for e in employees]
    else:
        # Nur Name, Qualifikationen, Vertragstyp – kein Gehalt, kein Kontakt
        return [EmployeePublicOut.model_validate(e).model_dump(mode="json") for e in employees]


# ── Einzelnes Mitarbeiterprofil ───────────────────────────────────────────────

@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: uuid.UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    # Nicht-Admin darf nur sein eigenes vollständiges Profil sehen
    if current_user.role != "admin" and employee.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Zugriff verweigert – private Mitarbeiterdaten",
        )
    return employee


# ── Admin: Mitarbeiter anlegen / bearbeiten / deaktivieren ───────────────────

@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, current_user: AdminUser, db: DB):
    employee = Employee(
        tenant_id=current_user.tenant_id,
        ical_token=secrets.token_urlsafe(32),
        **payload.model_dump(),
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(employee_id: uuid.UUID, payload: EmployeeUpdate, current_user: AdminUser, db: DB):
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    updates = payload.model_dump(exclude_unset=True)

    # Validate user_id link if provided
    if "user_id" in updates and updates["user_id"] is not None:
        from app.models.user import User as UserModel
        user_result = await db.execute(
            select(UserModel).where(
                UserModel.id == updates["user_id"],
                UserModel.tenant_id == current_user.tenant_id,
            )
        )
        if not user_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
        # Check not already linked to another employee
        existing_link = await db.execute(
            select(Employee).where(
                Employee.user_id == updates["user_id"],
                Employee.tenant_id == current_user.tenant_id,
                Employee.id != employee_id,
            )
        )
        if existing_link.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Dieser Login-Account ist bereits mit einem anderen Mitarbeiter verknüpft",
            )

    for field, value in updates.items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_employee(employee_id: uuid.UUID, current_user: AdminUser, db: DB):
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    employee.is_active = False
    await db.commit()
