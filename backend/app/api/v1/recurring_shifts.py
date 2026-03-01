import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.api.deps import DB, ManagerOrAdmin
from app.models.holiday_profile import HolidayProfile, VacationPeriod, CustomHoliday
from app.models.recurring_shift import RecurringShift
from app.models.shift import Shift
from app.schemas.recurring_shift import (
    RecurringShiftCreate, RecurringShiftUpdate, RecurringShiftUpdateFrom,
    RecurringShiftPreview, RecurringShiftOut, RecurringShiftCreateResponse, PreviewResponse,
)
from app.services.recurring_shift_service import (
    generate_shifts, delete_future_planned_shifts, preview_generate,
)

router = APIRouter(prefix="/recurring-shifts", tags=["recurring-shifts"])


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RecurringShiftOut])
async def list_recurring_shifts(current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(RecurringShift).where(
            RecurringShift.tenant_id == current_user.tenant_id,
            RecurringShift.is_active == True,
        ).order_by(RecurringShift.weekday, RecurringShift.start_time)
    )
    shifts = result.scalars().all()
    return [RecurringShiftOut.from_orm_with_weekday(s) for s in shifts]


# ── Preview ──────────────────────────────────────────────────────────────────

@router.post("/preview", response_model=PreviewResponse)
async def preview(data: RecurringShiftPreview, current_user: ManagerOrAdmin, db: DB):
    profile = await _load_profile(data.holiday_profile_id, current_user.tenant_id, db)
    result = await preview_generate(
        weekday=data.weekday,
        from_date=data.valid_from,
        until_date=data.valid_until,
        profile=profile,
        skip_public_holidays=data.skip_public_holidays,
    )
    return result


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RecurringShiftCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_recurring_shift(data: RecurringShiftCreate, current_user: ManagerOrAdmin, db: DB):
    profile = await _load_profile(data.holiday_profile_id, current_user.tenant_id, db)

    rs = RecurringShift(
        tenant_id=current_user.tenant_id,
        weekday=data.weekday,
        start_time=data.start_time,
        end_time=data.end_time,
        break_minutes=data.break_minutes,
        employee_id=data.employee_id,
        template_id=data.template_id,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        holiday_profile_id=data.holiday_profile_id,
        skip_public_holidays=data.skip_public_holidays,
        label=data.label,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rs)
    await db.flush()  # get rs.id

    new_shifts, skipped = await generate_shifts(
        rs=rs,
        from_date=data.valid_from,
        until_date=data.valid_until,
        profile=profile,
        db=db,
    )
    for s in new_shifts:
        db.add(s)

    await db.commit()
    await db.refresh(rs)

    return RecurringShiftCreateResponse(
        recurring_shift=RecurringShiftOut.from_orm_with_weekday(rs),
        generated_count=len(new_shifts),
        skipped_count=skipped,
    )


# ── Update (meta only) ────────────────────────────────────────────────────────

@router.put("/{rs_id}", response_model=RecurringShiftOut)
async def update_recurring_shift(rs_id: uuid.UUID, data: RecurringShiftUpdate, current_user: ManagerOrAdmin, db: DB):
    rs = await _get_rs_or_404(rs_id, current_user.tenant_id, db)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(rs, field, value)

    await db.commit()
    await db.refresh(rs)
    return RecurringShiftOut.from_orm_with_weekday(rs)


# ── Update from Date ──────────────────────────────────────────────────────────

@router.post("/{rs_id}/update-from", response_model=RecurringShiftCreateResponse)
async def update_from(rs_id: uuid.UUID, data: RecurringShiftUpdateFrom, current_user: ManagerOrAdmin, db: DB):
    rs = await _get_rs_or_404(rs_id, current_user.tenant_id, db)

    # Apply new meta fields (inkl. optional valid_until-Verlängerung)
    for field in ("start_time", "end_time", "break_minutes", "employee_id", "template_id",
                  "holiday_profile_id", "skip_public_holidays", "label", "valid_until"):
        val = getattr(data, field)
        if val is not None:
            setattr(rs, field, val)

    # Delete future planned (non-confirmed, non-override) shifts
    await delete_future_planned_shifts(rs.id, data.from_date, current_user.tenant_id, db)

    # Load profile
    profile = await _load_profile(rs.holiday_profile_id, current_user.tenant_id, db)

    # Regenerate from from_date to valid_until
    new_shifts, skipped = await generate_shifts(
        rs=rs,
        from_date=data.from_date,
        until_date=rs.valid_until,
        profile=profile,
        db=db,
    )
    for s in new_shifts:
        db.add(s)

    await db.commit()
    await db.refresh(rs)

    return RecurringShiftCreateResponse(
        recurring_shift=RecurringShiftOut.from_orm_with_weekday(rs),
        generated_count=len(new_shifts),
        skipped_count=skipped,
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{rs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_shift(rs_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    rs = await _get_rs_or_404(rs_id, current_user.tenant_id, db)

    # Soft-delete
    rs.is_active = False

    # Delete ALL planned (non-confirmed) shifts for this recurring shift
    from datetime import date
    await delete_future_planned_shifts(rs.id, date.min, current_user.tenant_id, db)

    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_rs_or_404(rs_id: uuid.UUID, tenant_id, db) -> RecurringShift:
    result = await db.execute(
        select(RecurringShift).where(
            RecurringShift.id == rs_id,
            RecurringShift.tenant_id == tenant_id,
        )
    )
    rs = result.scalar_one_or_none()
    if not rs:
        raise HTTPException(status_code=404, detail="Regeltermin nicht gefunden")
    return rs


async def _load_profile(
    profile_id: uuid.UUID | None,
    tenant_id,
    db,
) -> HolidayProfile | None:
    if profile_id is None:
        # Try to use tenant's active profile
        result = await db.execute(
            select(HolidayProfile).where(
                HolidayProfile.tenant_id == tenant_id,
                HolidayProfile.is_active == True,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return None
    else:
        result = await db.execute(
            select(HolidayProfile).where(
                HolidayProfile.id == profile_id,
                HolidayProfile.tenant_id == tenant_id,
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Ferienprofil nicht gefunden")

    # Load relationships eagerly
    result2 = await db.execute(
        select(HolidayProfile)
        .options(
            selectinload(HolidayProfile.vacation_periods),
            selectinload(HolidayProfile.custom_holidays),
        )
        .where(HolidayProfile.id == profile.id)
    )
    return result2.scalar_one()
