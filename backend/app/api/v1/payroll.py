"""
Payroll API – Lohnabrechnung
"""
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select, and_

from app.api.deps import DB, ManagerOrAdmin, CurrentUser
from app.models.employee import Employee
from app.models.payroll import PayrollEntry
from app.models.tenant import Tenant
from app.schemas.payroll import PayrollEntryOut, PayrollCalculateRequest, PayrollUpdate
from app.services.payroll_service import PayrollService
from app.services.pdf_service import generate_payslip_pdf

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.get("", response_model=list[PayrollEntryOut])
async def list_payroll_entries(
    current_user: ManagerOrAdmin,
    db: DB,
    month: date | None = None,
    employee_id: uuid.UUID | None = None,
):
    """List payroll entries, optionally filtered by month and/or employee."""
    query = select(PayrollEntry).where(PayrollEntry.tenant_id == current_user.tenant_id)

    if month:
        # Match the first day of the given month
        query = query.where(PayrollEntry.month == month)
    if employee_id:
        query = query.where(PayrollEntry.employee_id == employee_id)

    result = await db.execute(query.order_by(PayrollEntry.month.desc(), PayrollEntry.employee_id))
    return result.scalars().all()


@router.post("/calculate", response_model=PayrollEntryOut, status_code=status.HTTP_200_OK)
async def calculate_payroll(
    payload: PayrollCalculateRequest,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """
    Calculate (or recalculate) the payroll for one employee and month.
    Creates a new draft entry or updates an existing draft.
    Approved/paid entries cannot be recalculated.
    """
    # Verify employee belongs to tenant
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == payload.employee_id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    if emp_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    # Check for existing locked entry
    existing_result = await db.execute(
        select(PayrollEntry).where(
            and_(
                PayrollEntry.employee_id == payload.employee_id,
                PayrollEntry.month == payload.month,
                PayrollEntry.tenant_id == current_user.tenant_id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing and existing.status in ("approved", "paid"):
        raise HTTPException(
            status_code=400,
            detail=f"Abrechnung ist bereits gesperrt (Status: {existing.status}). Bitte erst zurücksetzen.",
        )

    # Delete existing draft so service creates a fresh one
    if existing:
        await db.delete(existing)
        await db.flush()

    # Run PayrollService
    service = PayrollService(db)
    entry, _ = await service.calculate_monthly_payroll(payload.employee_id, payload.month)
    db.add(entry)

    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/calculate-all", response_model=list[PayrollEntryOut])
async def calculate_all_payroll(
    current_user: ManagerOrAdmin,
    db: DB,
    month: date | None = None,
):
    """
    Calculate payroll for ALL active employees for the given month.
    Skips employees whose entry is already approved/paid.
    """
    if month is None:
        from datetime import date as d
        today = d.today()
        month = today.replace(day=1)

    emp_result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == current_user.tenant_id,
            Employee.is_active == True,
        )
    )
    employees = emp_result.scalars().all()

    service = PayrollService(db)
    entries = []

    for emp in employees:
        # Check for locked entry
        existing_result = await db.execute(
            select(PayrollEntry).where(
                and_(
                    PayrollEntry.employee_id == emp.id,
                    PayrollEntry.month == month,
                    PayrollEntry.tenant_id == current_user.tenant_id,
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing and existing.status in ("approved", "paid"):
            entries.append(existing)
            continue

        if existing:
            await db.delete(existing)
            await db.flush()

        entry, _ = await service.calculate_monthly_payroll(emp.id, month)
        db.add(entry)
        entries.append(entry)

    await db.commit()
    for e in entries:
        await db.refresh(e)

    return entries


@router.get("/{entry_id}", response_model=PayrollEntryOut)
async def get_payroll_entry(entry_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(PayrollEntry).where(
            PayrollEntry.id == entry_id,
            PayrollEntry.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Abrechnungseintrag nicht gefunden")
    return entry


@router.put("/{entry_id}", response_model=PayrollEntryOut)
async def update_payroll_entry(
    entry_id: uuid.UUID,
    payload: PayrollUpdate,
    current_user: ManagerOrAdmin,
    db: DB,
):
    """Update status (draft→approved→paid) or notes."""
    result = await db.execute(
        select(PayrollEntry).where(
            PayrollEntry.id == entry_id,
            PayrollEntry.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Abrechnungseintrag nicht gefunden")

    VALID_TRANSITIONS = {
        "draft":    ["approved"],
        "approved": ["paid", "draft"],  # allow reverting
        "paid":     [],
    }
    if payload.status and payload.status not in VALID_TRANSITIONS.get(entry.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Statuswechsel: {entry.status} → {payload.status}",
        )

    if payload.status:
        entry.status = payload.status
    if payload.notes is not None:
        entry.notes = payload.notes

    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/{entry_id}/pdf")
async def download_payroll_pdf(entry_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    """Generiert den Lohnzettel als PDF und gibt ihn zum Download zurück."""
    result = await db.execute(
        select(PayrollEntry).where(
            PayrollEntry.id == entry_id,
            PayrollEntry.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Abrechnungseintrag nicht gefunden")

    emp_result = await db.execute(select(Employee).where(Employee.id == entry.employee_id))
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Mitarbeiter nicht gefunden")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    tenant_name = tenant.name if tenant else "VERA"

    pdf_bytes = generate_payslip_pdf(entry, employee, tenant_name)

    month_str = entry.month.strftime("%Y-%m")
    filename = f"vera-abrechnung-{employee.last_name.lower()}-{month_str}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
