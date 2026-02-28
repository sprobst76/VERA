import secrets
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update

from app.api.deps import DB, AdminUser, CurrentUser, ManagerOrAdmin
from app.models.employee import Employee
from app.models.contract_history import ContractHistory
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeePublicOut


class EmployeeSelfUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None


class ContractHistoryCreate(BaseModel):
    valid_from: date
    contract_type: str
    hourly_rate: float
    weekly_hours: float | None = None
    full_time_percentage: float | None = None
    monthly_hours_limit: float | None = None
    annual_salary_limit: float | None = None
    note: str | None = None


class ContractHistoryOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    valid_from: date
    valid_to: date | None
    contract_type: str
    hourly_rate: Decimal
    weekly_hours: Decimal | None
    full_time_percentage: Decimal | None
    monthly_hours_limit: Decimal | None
    annual_salary_limit: Decimal | None
    note: str | None
    created_at: Any

    model_config = {"from_attributes": True}


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
    await db.flush()  # ID generieren ohne commit

    # Ersten Vertragseintrag anlegen
    contract = ContractHistory(
        tenant_id=current_user.tenant_id,
        employee_id=employee.id,
        created_by_user_id=current_user.id,
        valid_from=date.today(),
        valid_to=None,
        contract_type=payload.contract_type,
        hourly_rate=payload.hourly_rate,
        weekly_hours=payload.weekly_hours,
        full_time_percentage=payload.full_time_percentage,
        monthly_hours_limit=payload.monthly_hours_limit,
        annual_salary_limit=payload.annual_salary_limit,
    )
    db.add(contract)
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


# ── Vertragsverlauf ──────────────────────────────────────────────────────────

@router.get("/{employee_id}/contracts", response_model=list[ContractHistoryOut])
async def list_contracts(employee_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    """Gibt alle Vertragsperioden eines Mitarbeiters zurück (neueste zuerst)."""
    # Mitarbeiter muss zum selben Tenant gehören
    emp = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    if not emp.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    result = await db.execute(
        select(ContractHistory)
        .where(
            ContractHistory.employee_id == employee_id,
            ContractHistory.tenant_id == current_user.tenant_id,
        )
        .order_by(ContractHistory.valid_from.desc())
    )
    return result.scalars().all()


@router.post("/{employee_id}/contracts", response_model=ContractHistoryOut, status_code=status.HTTP_201_CREATED)
async def add_contract(employee_id: uuid.UUID, payload: ContractHistoryCreate, current_user: ManagerOrAdmin, db: DB):
    """Neue Vertragsperiode anlegen. Schließt automatisch den aktuell offenen Eintrag."""
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    # Aktuell offenen Eintrag schließen
    await db.execute(
        update(ContractHistory)
        .where(
            ContractHistory.employee_id == employee_id,
            ContractHistory.valid_to.is_(None),
        )
        .values(valid_to=payload.valid_from)
    )

    # Neuen Eintrag anlegen
    entry = ContractHistory(
        tenant_id=current_user.tenant_id,
        employee_id=employee_id,
        created_by_user_id=current_user.id,
        valid_to=None,
        **payload.model_dump(),
    )
    db.add(entry)

    # Mirror-Felder auf Employee aktualisieren
    employee.contract_type = payload.contract_type
    employee.hourly_rate = payload.hourly_rate
    employee.weekly_hours = payload.weekly_hours
    employee.full_time_percentage = payload.full_time_percentage
    employee.monthly_hours_limit = payload.monthly_hours_limit
    employee.annual_salary_limit = payload.annual_salary_limit

    await db.commit()
    await db.refresh(entry)
    return entry


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
