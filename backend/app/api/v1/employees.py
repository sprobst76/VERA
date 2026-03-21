import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update, func

from app.api.deps import DB, AdminUser, CurrentUser, ManagerOrAdmin
from app.models.employee import Employee
from app.models.contract_history import ContractHistory
from app.models.employee_contract_type_membership import EmployeeContractTypeMembership
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeOut, EmployeePublicOut


class EmployeeSelfUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None
    availability_prefs: dict | None = None


class ContractHistoryCreate(BaseModel):
    valid_from: date
    contract_type: str
    hourly_rate: float
    weekly_hours: float | None = None
    full_time_percentage: float | None = None
    monthly_hours_limit: float | None = None
    annual_salary_limit: float | None = None
    annual_hours_target: float | None = None
    monthly_salary: float | None = None
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
    annual_hours_target: Decimal | None
    monthly_salary: Decimal | None
    contract_type_id: uuid.UUID | None = None
    note: str | None
    created_at: Any

    model_config = {"from_attributes": True}


class MembershipOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    contract_type_id: Optional[uuid.UUID]
    contract_type_name: Optional[str] = None
    valid_from: date
    valid_to: Optional[date]
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/employees", tags=["employees"])


def _sync_employee_mirror(employee: "Employee", contract: "ContractHistory") -> None:
    """Spiegelt alle ContractHistory-Felder auf die denormalisierten Employee-Mirror-Felder."""
    employee.contract_type = contract.contract_type
    employee.hourly_rate = float(contract.hourly_rate)
    employee.weekly_hours = float(contract.weekly_hours) if contract.weekly_hours is not None else None
    employee.full_time_percentage = float(contract.full_time_percentage) if contract.full_time_percentage is not None else None
    employee.monthly_hours_limit = float(contract.monthly_hours_limit) if contract.monthly_hours_limit is not None else None
    employee.annual_salary_limit = float(contract.annual_salary_limit) if contract.annual_salary_limit is not None else None
    employee.annual_hours_target = float(contract.annual_hours_target) if contract.annual_hours_target is not None else None
    employee.monthly_salary = float(contract.monthly_salary) if contract.monthly_salary is not None else None


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
    if payload.availability_prefs is not None:
        employee.availability_prefs = payload.availability_prefs
    await db.commit()
    await db.refresh(employee)
    return employee


# ── Urlaubskonto (muss VOR /{employee_id} stehen, sonst matcht FastAPI falsch) ─

@router.get("/vacation-balances", response_model=list[dict])
async def get_vacation_balances(
    current_user: CurrentUser,
    db: DB,
    year: int = Query(default=None),
):
    """
    Gibt Urlaubskonto aller Mitarbeiter zurück (Admin) bzw. nur das eigene (Employee).
    year: Kalenderjahr (Standard: aktuelles Jahr)
    """
    from app.models.absence import EmployeeAbsence
    from datetime import date as date_

    target_year = year or date_.today().year
    year_start = date_(target_year, 1, 1)
    year_end   = date_(target_year, 12, 31)

    # Welche Mitarbeiter darf man sehen?
    if current_user.role == "admin":
        emp_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == current_user.tenant_id,
                Employee.is_active == True,
            ).order_by(Employee.last_name)
        )
        employees = emp_result.scalars().all()
    else:
        emp_result = await db.execute(
            select(Employee).where(
                Employee.user_id == current_user.id,
                Employee.tenant_id == current_user.tenant_id,
            )
        )
        emp = emp_result.scalar_one_or_none()
        employees = [emp] if emp else []

    if not employees:
        return []

    emp_ids = [e.id for e in employees]

    # Genommene Urlaubstage (approved vacation absences)
    taken_result = await db.execute(
        select(
            EmployeeAbsence.employee_id,
            func.sum(EmployeeAbsence.days_count).label("taken"),
        )
        .where(
            EmployeeAbsence.employee_id.in_(emp_ids),
            EmployeeAbsence.type == "vacation",
            EmployeeAbsence.status == "approved",
            EmployeeAbsence.start_date >= year_start,
            EmployeeAbsence.start_date <= year_end,
        )
        .group_by(EmployeeAbsence.employee_id)
    )
    taken_map: dict[uuid.UUID, float] = {
        row.employee_id: float(row.taken or 0) for row in taken_result.all()
    }

    return [
        {
            "employee_id":   str(e.id),
            "first_name":    e.first_name,
            "last_name":     e.last_name,
            "entitlement":   e.vacation_days,
            "carryover":     e.vacation_carryover,
            "total":         e.vacation_days + e.vacation_carryover,
            "taken":         taken_map.get(e.id, 0.0),
            "remaining":     e.vacation_days + e.vacation_carryover - taken_map.get(e.id, 0.0),
            "year":          target_year,
        }
        for e in employees
    ]


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

    # parent_viewer: nur öffentliche Daten (JSONResponse bypasses EmployeeOut validation)
    if current_user.role == "parent_viewer":
        return JSONResponse(content=EmployeePublicOut.model_validate(employee).model_dump(mode="json"))

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

    # Ersten Vertragseintrag anlegen – valid_from = Eintrittsdatum oder heute
    contract = ContractHistory(
        tenant_id=current_user.tenant_id,
        employee_id=employee.id,
        created_by_user_id=current_user.id,
        valid_from=payload.start_date or date.today(),
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
    """
    Neue Vertragsperiode anlegen – retroaktiv-sicher.

    Sucht den Eintrag, dessen Zeitraum das neue valid_from enthält, und splittet ihn:
      - Bestehender Eintrag: valid_to = payload.valid_from
      - Neuer Eintrag:       valid_from = payload.valid_from, valid_to = alter valid_to
    So bleibt die Kette lückenlos, auch bei Einfügungen in der Vergangenheit.
    """
    from sqlalchemy import or_
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    # Den Eintrag finden, der den neuen Zeitpunkt "enthält"
    containing_result = await db.execute(
        select(ContractHistory).where(
            ContractHistory.employee_id == employee_id,
            ContractHistory.valid_from <= payload.valid_from,
            or_(
                ContractHistory.valid_to > payload.valid_from,
                ContractHistory.valid_to.is_(None),
            ),
        ).order_by(ContractHistory.valid_from.desc()).limit(1)
    )
    containing = containing_result.scalar_one_or_none()

    if containing and containing.valid_from == payload.valid_from:
        raise HTTPException(
            status_code=422,
            detail=f"Es existiert bereits ein Eintrag mit valid_from={payload.valid_from}.",
        )

    # Bestehenden Eintrag schließen (valid_to übernehmen für neuen Eintrag)
    inherited_valid_to = None
    if containing:
        inherited_valid_to = containing.valid_to
        containing.valid_to = payload.valid_from

    # Neuen Eintrag einfügen
    entry = ContractHistory(
        tenant_id=current_user.tenant_id,
        employee_id=employee_id,
        created_by_user_id=current_user.id,
        valid_to=inherited_valid_to,
        **payload.model_dump(),
    )
    db.add(entry)

    # Mirror-Felder auf Employee nur aktualisieren wenn neuer Eintrag der aktuelle ist
    if inherited_valid_to is None:
        _sync_employee_mirror(employee, entry)

    await db.commit()
    await db.refresh(entry)
    return entry


class ContractHistoryUpdate(BaseModel):
    """Felder eines bestehenden ContractHistory-Eintrags bearbeiten."""
    contract_type: str | None = None
    hourly_rate: float | None = None
    weekly_hours: float | None = None
    full_time_percentage: float | None = None
    monthly_hours_limit: float | None = None
    annual_salary_limit: float | None = None
    annual_hours_target: float | None = None
    monthly_salary: float | None = None
    note: str | None = None


@router.put("/{employee_id}/contracts/{contract_id}", response_model=ContractHistoryOut)
async def update_contract(
    employee_id: uuid.UUID,
    contract_id: uuid.UUID,
    payload: ContractHistoryUpdate,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """Finanziellen Inhalt eines bestehenden Vertragseintrags bearbeiten (valid_from/to unverändert)."""
    result = await db.execute(
        select(ContractHistory).where(
            ContractHistory.id == contract_id,
            ContractHistory.employee_id == employee_id,
            ContractHistory.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Vertragseintrag nicht gefunden")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    # Mirror auf Employee wenn aktueller Eintrag
    if entry.valid_to is None:
        emp_result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        emp = emp_result.scalar_one_or_none()
        if emp:
            _sync_employee_mirror(emp, entry)

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{employee_id}/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    employee_id: uuid.UUID,
    contract_id: uuid.UUID,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """
    Vertragseintrag löschen und Kette reparieren:
    Der vorherige Eintrag (valid_to == gelöschter.valid_from) übernimmt gelöschter.valid_to.
    """
    result = await db.execute(
        select(ContractHistory).where(
            ContractHistory.id == contract_id,
            ContractHistory.employee_id == employee_id,
            ContractHistory.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Vertragseintrag nicht gefunden")

    # Prüfen ob es der einzige Eintrag ist
    count_result = await db.execute(
        select(ContractHistory).where(
            ContractHistory.employee_id == employee_id,
            ContractHistory.tenant_id == current_user.tenant_id,
        )
    )
    all_entries = count_result.scalars().all()
    if len(all_entries) <= 1:
        raise HTTPException(status_code=422, detail="Mindestens ein Vertragseintrag muss erhalten bleiben")

    # Vorherigen Eintrag suchen (valid_to == entry.valid_from)
    prev = None
    if entry.valid_from:
        prev_result = await db.execute(
            select(ContractHistory).where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_to == entry.valid_from,
            )
        )
        prev = prev_result.scalar_one_or_none()

    # Wenn gelöschter Eintrag der aktuelle war, Mirror auf Employee zurücksetzen
    # (MUSS vor prev.valid_to-Änderung passieren, damit prev noch findbar ist)
    if entry.valid_to is None and prev:
        emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
        emp = emp_result.scalar_one_or_none()
        if emp:
            _sync_employee_mirror(emp, prev)

    # Kette reparieren: Vorgänger übernimmt valid_to des gelöschten Eintrags
    if prev:
        prev.valid_to = entry.valid_to

    await db.delete(entry)
    await db.commit()


@router.get("/{employee_id}/memberships", response_model=list[MembershipOut])
async def list_memberships(employee_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    """Verlauf der Gruppenmitgliedschaften (ContractType-Zugehörigkeit) eines Mitarbeiters."""
    from app.models.contract_type import ContractType

    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    mem_result = await db.execute(
        select(EmployeeContractTypeMembership)
        .where(EmployeeContractTypeMembership.employee_id == employee_id)
        .order_by(EmployeeContractTypeMembership.valid_from.desc())
    )
    memberships = mem_result.scalars().all()

    # ContractType-Namen auflösen
    ct_ids = {m.contract_type_id for m in memberships if m.contract_type_id}
    ct_names: dict[uuid.UUID, str] = {}
    if ct_ids:
        ct_result = await db.execute(
            select(ContractType).where(ContractType.id.in_(ct_ids))
        )
        ct_names = {ct.id: ct.name for ct in ct_result.scalars().all()}

    return [
        MembershipOut(
            id=m.id,
            employee_id=m.employee_id,
            contract_type_id=m.contract_type_id,
            contract_type_name=ct_names.get(m.contract_type_id) if m.contract_type_id else None,
            valid_from=m.valid_from,
            valid_to=m.valid_to,
            note=m.note,
            created_at=m.created_at,
        )
        for m in memberships
    ]


@router.post("/{employee_id}/assign-contract-type", response_model=EmployeeOut)
async def assign_contract_type(
    employee_id: uuid.UUID,
    payload: dict,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """
    Vertragstyp einem Mitarbeiter zuweisen (oder entfernen wenn contract_type_id=null).
    Wenn valid_from angegeben wird (ISO-Datum), wird eine neue ContractHistory angelegt
    und der aktuell offene Eintrag geschlossen.
    """
    from app.models.contract_type import ContractType
    from decimal import Decimal as D

    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    ct_id = payload.get("contract_type_id")
    valid_from_raw = payload.get("valid_from")

    if ct_id:
        ct_id = uuid.UUID(str(ct_id))
        ct_result = await db.execute(
            select(ContractType).where(
                ContractType.id == ct_id,
                ContractType.tenant_id == current_user.tenant_id,
            )
        )
        ct = ct_result.scalar_one_or_none()
        if not ct:
            raise HTTPException(status_code=404, detail="Vertragstyp nicht gefunden")

        employee.contract_type_id = ct_id

        # Membership-History: offenen Eintrag schließen + neuen anlegen
        from datetime import date as _date_cls
        mem_from = _date_cls.fromisoformat(str(valid_from_raw)) if valid_from_raw else _date_cls.today()
        prev_mem_result = await db.execute(
            select(EmployeeContractTypeMembership).where(
                EmployeeContractTypeMembership.employee_id == employee_id,
                EmployeeContractTypeMembership.valid_to.is_(None),
            )
        )
        prev_mem = prev_mem_result.scalar_one_or_none()
        if prev_mem:
            prev_mem.valid_to = mem_from
        new_mem = EmployeeContractTypeMembership(
            tenant_id=current_user.tenant_id,
            employee_id=employee_id,
            contract_type_id=ct_id,
            valid_from=mem_from,
            note=f"Zugewiesen: {ct.name}",
            created_by_user_id=current_user.id,
        )
        db.add(new_mem)

        # ContractHistory anlegen (immer – auch ohne valid_from → date.today())
        effective_from = mem_from  # mem_from ist bereits date.today() wenn kein valid_from

        open_result = await db.execute(
            select(ContractHistory).where(
                ContractHistory.employee_id == employee_id,
                ContractHistory.valid_to.is_(None),
            ).order_by(ContractHistory.valid_from.desc()).limit(1)
        )
        current_entry = open_result.scalar_one_or_none()

        if current_entry and effective_from <= current_entry.valid_from:
            # Retroaktiv oder gleicher Tag: offenen Eintrag in-place aktualisieren
            # (kein neuer Eintrag – das würde valid_to == valid_from erzeugen)
            current_entry.valid_from = effective_from
            current_entry.contract_type = ct.contract_category
            current_entry.hourly_rate = D(str(ct.hourly_rate))
            current_entry.monthly_hours_limit = D(str(ct.monthly_hours_limit)) if ct.monthly_hours_limit is not None else None
            current_entry.annual_salary_limit = D(str(ct.annual_salary_limit)) if ct.annual_salary_limit is not None else None
            current_entry.annual_hours_target = D(str(ct.annual_hours_target)) if ct.annual_hours_target is not None else None
            current_entry.weekly_hours = D(str(ct.weekly_hours)) if ct.weekly_hours is not None else None
            current_entry.contract_type_id = ct_id
            current_entry.note = f"Vertragstyp '{ct.name}' zugewiesen"
            active_ch = current_entry
        else:
            # Normaler SCD-Fall: alten Eintrag schließen, neuen anlegen
            if current_entry:
                current_entry.valid_to = effective_from
            new_entry = ContractHistory(
                tenant_id=current_user.tenant_id,
                employee_id=employee_id,
                valid_from=effective_from,
                valid_to=None,
                contract_type=ct.contract_category,
                hourly_rate=D(str(ct.hourly_rate)),
                monthly_hours_limit=D(str(ct.monthly_hours_limit)) if ct.monthly_hours_limit is not None else None,
                annual_salary_limit=D(str(ct.annual_salary_limit)) if ct.annual_salary_limit is not None else None,
                annual_hours_target=D(str(ct.annual_hours_target)) if ct.annual_hours_target is not None else None,
                weekly_hours=D(str(ct.weekly_hours)) if ct.weekly_hours is not None else None,
                contract_type_id=ct_id,
                note=f"Vertragstyp '{ct.name}' zugewiesen",
                created_by_user_id=current_user.id,
            )
            db.add(new_entry)
            active_ch = new_entry

        # Employee-Spiegel aktualisieren
        _sync_employee_mirror(employee, active_ch)
    else:
        employee.contract_type_id = None
        # Offene Membership schließen
        from datetime import date as _date_cls
        prev_mem_result = await db.execute(
            select(EmployeeContractTypeMembership).where(
                EmployeeContractTypeMembership.employee_id == employee_id,
                EmployeeContractTypeMembership.valid_to.is_(None),
            )
        )
        prev_mem = prev_mem_result.scalar_one_or_none()
        if prev_mem:
            prev_mem.valid_to = _date_cls.today()

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
