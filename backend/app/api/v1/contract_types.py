"""
CRUD für Vertragstypen (ContractType) – Gruppenverträge für Mitarbeiter.

GET    /contract-types            – Liste aller Typen (Admin/Manager)
POST   /contract-types            – Neuen Typ anlegen (Admin)
PUT    /contract-types/{id}       – Typ aktualisieren + neue ContractHistory für alle MA (Admin)
DELETE /contract-types/{id}       – Soft-delete (Admin, nur wenn keine aktiven MA)
GET    /contract-types/{id}/employees – Alle Mitarbeiter des Typs
POST   /employees/{id}/assign-contract-type – MA einem Typ zuweisen (Admin)
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, ManagerOrAdmin, AdminUser
from app.models.contract_type import ContractType
from app.models.employee import Employee
from app.models.contract_history import ContractHistory

router = APIRouter(prefix="/contract-types", tags=["contract-types"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ContractTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    contract_category: str  # minijob | part_time | full_time
    hourly_rate: float
    monthly_hours_limit: Optional[float] = None
    annual_salary_limit: Optional[float] = None
    annual_hours_target: Optional[float] = None
    weekly_hours: Optional[float] = None


class ContractTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contract_category: Optional[str] = None
    hourly_rate: Optional[float] = None
    monthly_hours_limit: Optional[float] = None
    annual_salary_limit: Optional[float] = None
    annual_hours_target: Optional[float] = None
    weekly_hours: Optional[float] = None
    is_active: Optional[bool] = None
    # When provided, create new ContractHistory entries for all linked employees
    apply_from: Optional[date] = None  # defaults to today
    note: Optional[str] = None  # note for the generated ContractHistory entries


class ContractTypeOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    contract_category: str
    hourly_rate: float
    monthly_hours_limit: Optional[float]
    annual_salary_limit: Optional[float]
    annual_hours_target: Optional[float]
    weekly_hours: Optional[float]
    is_active: bool
    employee_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignContractTypePayload(BaseModel):
    contract_type_id: Optional[uuid.UUID] = None  # None = remove assignment


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _count_employees(db, contract_type_id: uuid.UUID) -> int:
    result = await db.execute(
        select(Employee).where(
            Employee.contract_type_id == contract_type_id,
            Employee.is_active == True,
        )
    )
    return len(result.scalars().all())


def _ct_to_out(ct: ContractType, employee_count: int = 0) -> dict:
    return {
        "id": ct.id,
        "tenant_id": ct.tenant_id,
        "name": ct.name,
        "description": ct.description,
        "contract_category": ct.contract_category,
        "hourly_rate": float(ct.hourly_rate),
        "monthly_hours_limit": float(ct.monthly_hours_limit) if ct.monthly_hours_limit else None,
        "annual_salary_limit": float(ct.annual_salary_limit) if ct.annual_salary_limit else None,
        "annual_hours_target": float(ct.annual_hours_target) if ct.annual_hours_target else None,
        "weekly_hours": float(ct.weekly_hours) if ct.weekly_hours else None,
        "is_active": ct.is_active,
        "employee_count": employee_count,
        "created_at": ct.created_at,
        "updated_at": ct.updated_at,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_contract_types(db: DB, current_user: ManagerOrAdmin):
    """Liste alle Vertragstypen des Tenants."""
    result = await db.execute(
        select(ContractType)
        .where(ContractType.tenant_id == current_user.tenant_id)
        .order_by(ContractType.name)
    )
    types = result.scalars().all()

    output = []
    for ct in types:
        count = await _count_employees(db, ct.id)
        output.append(_ct_to_out(ct, count))
    return output


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_contract_type(payload: ContractTypeCreate, db: DB, current_user: ManagerOrAdmin):
    """Neuen Vertragstyp anlegen."""
    ct = ContractType(
        tenant_id=current_user.tenant_id,
        **payload.model_dump(),
    )
    db.add(ct)
    await db.commit()
    await db.refresh(ct)
    return _ct_to_out(ct, 0)


@router.get("/{contract_type_id}")
async def get_contract_type(contract_type_id: uuid.UUID, db: DB, current_user: ManagerOrAdmin):
    result = await db.execute(
        select(ContractType).where(
            ContractType.id == contract_type_id,
            ContractType.tenant_id == current_user.tenant_id,
        )
    )
    ct = result.scalar_one_or_none()
    if not ct:
        raise HTTPException(status_code=404, detail="Vertragstyp nicht gefunden")
    count = await _count_employees(db, ct.id)
    return _ct_to_out(ct, count)


@router.put("/{contract_type_id}")
async def update_contract_type(
    contract_type_id: uuid.UUID,
    payload: ContractTypeUpdate,
    db: DB,
    current_user: ManagerOrAdmin,
):
    """
    Vertragstyp aktualisieren.
    Wenn Lohnparameter geändert werden UND apply_from gesetzt ist (oder Standardwert heute),
    werden neue ContractHistory-Einträge für alle Mitarbeiter des Typs angelegt.
    """
    result = await db.execute(
        select(ContractType).where(
            ContractType.id == contract_type_id,
            ContractType.tenant_id == current_user.tenant_id,
        )
    )
    ct = result.scalar_one_or_none()
    if not ct:
        raise HTTPException(status_code=404, detail="Vertragstyp nicht gefunden")

    # Track which wage fields changed
    wage_fields = {"hourly_rate", "monthly_hours_limit", "annual_salary_limit",
                   "annual_hours_target", "weekly_hours", "contract_category"}
    payload_data = payload.model_dump(exclude_unset=True)
    apply_from = payload_data.pop("apply_from", None)
    note = payload_data.pop("note", None)

    wage_changed = bool(set(payload_data.keys()) & wage_fields)

    for field, value in payload_data.items():
        setattr(ct, field, value)

    await db.commit()
    await db.refresh(ct)

    bulk_count = 0
    # Create new ContractHistory for all linked employees if wage parameters changed
    if wage_changed and apply_from is not False:
        effective_from = apply_from or date.today()

        # Find all active employees with this contract type
        emp_result = await db.execute(
            select(Employee).where(
                Employee.contract_type_id == contract_type_id,
                Employee.tenant_id == current_user.tenant_id,
                Employee.is_active == True,
            )
        )
        employees = emp_result.scalars().all()

        for emp in employees:
            # Close current open contract history entry
            open_result = await db.execute(
                select(ContractHistory).where(
                    ContractHistory.employee_id == emp.id,
                    ContractHistory.valid_to.is_(None),
                ).order_by(ContractHistory.valid_from.desc()).limit(1)
            )
            current_entry = open_result.scalar_one_or_none()
            if current_entry:
                current_entry.valid_to = effective_from

            # New ContractHistory entry from updated type
            new_entry = ContractHistory(
                tenant_id=current_user.tenant_id,
                employee_id=emp.id,
                valid_from=effective_from,
                valid_to=None,
                contract_type=ct.contract_category,
                hourly_rate=Decimal(str(ct.hourly_rate)),
                monthly_hours_limit=Decimal(str(ct.monthly_hours_limit)) if ct.monthly_hours_limit else None,
                annual_salary_limit=Decimal(str(ct.annual_salary_limit)) if ct.annual_salary_limit else None,
                annual_hours_target=Decimal(str(ct.annual_hours_target)) if ct.annual_hours_target else None,
                weekly_hours=Decimal(str(ct.weekly_hours)) if ct.weekly_hours else None,
                contract_type_id=contract_type_id,
                note=note or f"Gruppenvertrag '{ct.name}' aktualisiert",
                created_by_user_id=current_user.id,
            )
            db.add(new_entry)

            # Mirror to employee record
            emp.contract_type = ct.contract_category
            emp.hourly_rate = float(ct.hourly_rate)
            if ct.monthly_hours_limit:
                emp.monthly_hours_limit = float(ct.monthly_hours_limit)
            if ct.annual_salary_limit:
                emp.annual_salary_limit = float(ct.annual_salary_limit)
            if ct.annual_hours_target:
                emp.annual_hours_target = float(ct.annual_hours_target)
            if ct.weekly_hours:
                emp.weekly_hours = float(ct.weekly_hours)

            bulk_count += 1

        await db.commit()

    count = await _count_employees(db, ct.id)
    result_out = _ct_to_out(ct, count)
    result_out["updated_employees"] = bulk_count
    return result_out


@router.delete("/{contract_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract_type(
    contract_type_id: uuid.UUID,
    db: DB,
    current_user: ManagerOrAdmin,
):
    """Vertragstyp soft-löschen. Nur möglich wenn keine aktiven Mitarbeiter zugewiesen."""
    result = await db.execute(
        select(ContractType).where(
            ContractType.id == contract_type_id,
            ContractType.tenant_id == current_user.tenant_id,
        )
    )
    ct = result.scalar_one_or_none()
    if not ct:
        raise HTTPException(status_code=404, detail="Vertragstyp nicht gefunden")

    count = await _count_employees(db, ct.id)
    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Vertragstyp kann nicht gelöscht werden – {count} Mitarbeiter zugewiesen",
        )

    ct.is_active = False
    await db.commit()


@router.get("/{contract_type_id}/employees")
async def list_contract_type_employees(
    contract_type_id: uuid.UUID,
    db: DB,
    current_user: ManagerOrAdmin,
):
    """Alle Mitarbeiter die diesem Vertragstyp zugewiesen sind."""
    result = await db.execute(
        select(ContractType).where(
            ContractType.id == contract_type_id,
            ContractType.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vertragstyp nicht gefunden")

    emp_result = await db.execute(
        select(Employee).where(
            Employee.contract_type_id == contract_type_id,
            Employee.tenant_id == current_user.tenant_id,
        ).order_by(Employee.last_name, Employee.first_name)
    )
    employees = emp_result.scalars().all()
    return [{"id": str(e.id), "name": f"{e.first_name} {e.last_name}", "is_active": e.is_active}
            for e in employees]
