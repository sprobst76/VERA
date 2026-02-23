import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, ManagerOrAdmin
from app.models.holiday_profile import HolidayProfile, VacationPeriod, CustomHoliday
from app.schemas.holiday_profile import (
    HolidayProfileCreate, HolidayProfileUpdate, HolidayProfileOut, HolidayProfileListOut,
    VacationPeriodCreate, VacationPeriodUpdate, VacationPeriodOut,
    CustomHolidayCreate, CustomHolidayOut,
)
from app.utils.german_holidays import BW_SCHOOL_HOLIDAYS_2025_26

router = APIRouter(prefix="/holiday-profiles", tags=["holiday-profiles"])


# ── Holiday Profiles ─────────────────────────────────────────────────────────

@router.get("", response_model=list[HolidayProfileListOut])
async def list_profiles(current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(HolidayProfile)
        .where(HolidayProfile.tenant_id == current_user.tenant_id)
        .order_by(HolidayProfile.created_at.desc())
    )
    profiles = result.scalars().all()

    # Load period + holiday counts
    out = []
    for p in profiles:
        # Load related data
        vp_result = await db.execute(
            select(VacationPeriod).where(VacationPeriod.profile_id == p.id)
        )
        ch_result = await db.execute(
            select(CustomHoliday).where(CustomHoliday.profile_id == p.id)
        )
        vp_count = len(vp_result.scalars().all())
        ch_count = len(ch_result.scalars().all())

        out.append(HolidayProfileListOut(
            id=p.id,
            name=p.name,
            state=p.state,
            is_active=p.is_active,
            created_at=p.created_at,
            vacation_period_count=vp_count,
            custom_holiday_count=ch_count,
        ))
    return out


@router.post("", response_model=HolidayProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(data: HolidayProfileCreate, current_user: ManagerOrAdmin, db: DB):
    # If setting active, deactivate others
    if data.is_active:
        existing = await db.execute(
            select(HolidayProfile).where(
                HolidayProfile.tenant_id == current_user.tenant_id,
                HolidayProfile.is_active == True,
            )
        )
        for p in existing.scalars().all():
            p.is_active = False

    profile = HolidayProfile(
        tenant_id=current_user.tenant_id,
        name=data.name,
        state=data.state,
        is_active=data.is_active,
        created_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    await db.flush()  # get profile.id

    # BW preset
    if data.preset_bw and data.state == "BW":
        for start, end, name in BW_SCHOOL_HOLIDAYS_2025_26:
            vp = VacationPeriod(
                profile_id=profile.id,
                tenant_id=current_user.tenant_id,
                name=name,
                start_date=start,
                end_date=end,
            )
            db.add(vp)

    await db.commit()

    # Reload with relationships eagerly
    result = await db.execute(
        select(HolidayProfile)
        .options(
            selectinload(HolidayProfile.vacation_periods),
            selectinload(HolidayProfile.custom_holidays),
        )
        .where(HolidayProfile.id == profile.id)
    )
    return result.scalar_one()


@router.get("/{profile_id}", response_model=HolidayProfileOut)
async def get_profile(profile_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(HolidayProfile).where(
            HolidayProfile.id == profile_id,
            HolidayProfile.tenant_id == current_user.tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden")

    # Reload with eager relationships
    result2 = await db.execute(
        select(HolidayProfile)
        .options(
            selectinload(HolidayProfile.vacation_periods),
            selectinload(HolidayProfile.custom_holidays),
        )
        .where(HolidayProfile.id == profile_id)
    )
    return result2.scalar_one()


@router.put("/{profile_id}", response_model=HolidayProfileOut)
async def update_profile(profile_id: uuid.UUID, data: HolidayProfileUpdate, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(HolidayProfile).where(
            HolidayProfile.id == profile_id,
            HolidayProfile.tenant_id == current_user.tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden")

    # If activating this profile, deactivate others
    if data.is_active is True and not profile.is_active:
        existing = await db.execute(
            select(HolidayProfile).where(
                HolidayProfile.tenant_id == current_user.tenant_id,
                HolidayProfile.is_active == True,
                HolidayProfile.id != profile_id,
            )
        )
        for p in existing.scalars().all():
            p.is_active = False

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)

    await db.commit()

    # Reload with eager relationships
    result2 = await db.execute(
        select(HolidayProfile)
        .options(
            selectinload(HolidayProfile.vacation_periods),
            selectinload(HolidayProfile.custom_holidays),
        )
        .where(HolidayProfile.id == profile_id)
    )
    return result2.scalar_one()


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: uuid.UUID, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(HolidayProfile).where(
            HolidayProfile.id == profile_id,
            HolidayProfile.tenant_id == current_user.tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden")

    # Check if any recurring_shifts reference this profile
    from app.models.recurring_shift import RecurringShift
    rs_result = await db.execute(
        select(RecurringShift).where(
            RecurringShift.holiday_profile_id == profile_id,
            RecurringShift.is_active == True,
        )
    )
    if rs_result.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Profil wird von aktiven Regelterminen verwendet und kann nicht gelöscht werden."
        )

    await db.delete(profile)
    await db.commit()


# ── Vacation Periods ─────────────────────────────────────────────────────────

@router.post("/{profile_id}/periods", response_model=VacationPeriodOut, status_code=status.HTTP_201_CREATED)
async def add_period(profile_id: uuid.UUID, data: VacationPeriodCreate, current_user: ManagerOrAdmin, db: DB):
    profile = await _get_profile_or_404(profile_id, current_user.tenant_id, db)
    vp = VacationPeriod(
        profile_id=profile.id,
        tenant_id=current_user.tenant_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        color=data.color,
    )
    db.add(vp)
    await db.commit()
    await db.refresh(vp)
    return vp


@router.put("/{profile_id}/periods/{period_id}", response_model=VacationPeriodOut)
async def update_period(
    profile_id: uuid.UUID, period_id: uuid.UUID,
    data: VacationPeriodUpdate, current_user: ManagerOrAdmin, db: DB
):
    await _get_profile_or_404(profile_id, current_user.tenant_id, db)
    result = await db.execute(
        select(VacationPeriod).where(
            VacationPeriod.id == period_id,
            VacationPeriod.profile_id == profile_id,
        )
    )
    vp = result.scalar_one_or_none()
    if not vp:
        raise HTTPException(status_code=404, detail="Ferienperiode nicht gefunden")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(vp, field, value)
    await db.commit()
    await db.refresh(vp)
    return vp


@router.delete("/{profile_id}/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_period(
    profile_id: uuid.UUID, period_id: uuid.UUID,
    current_user: ManagerOrAdmin, db: DB
):
    await _get_profile_or_404(profile_id, current_user.tenant_id, db)
    result = await db.execute(
        select(VacationPeriod).where(
            VacationPeriod.id == period_id,
            VacationPeriod.profile_id == profile_id,
        )
    )
    vp = result.scalar_one_or_none()
    if not vp:
        raise HTTPException(status_code=404, detail="Ferienperiode nicht gefunden")
    await db.delete(vp)
    await db.commit()


# ── Custom Holidays ──────────────────────────────────────────────────────────

@router.post("/{profile_id}/custom-days", response_model=CustomHolidayOut, status_code=status.HTTP_201_CREATED)
async def add_custom_day(profile_id: uuid.UUID, data: CustomHolidayCreate, current_user: ManagerOrAdmin, db: DB):
    await _get_profile_or_404(profile_id, current_user.tenant_id, db)
    ch = CustomHoliday(
        profile_id=profile_id,
        tenant_id=current_user.tenant_id,
        date=data.date,
        name=data.name,
        color=data.color,
    )
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return ch


@router.delete("/{profile_id}/custom-days/{day_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_day(
    profile_id: uuid.UUID, day_id: uuid.UUID,
    current_user: ManagerOrAdmin, db: DB
):
    await _get_profile_or_404(profile_id, current_user.tenant_id, db)
    result = await db.execute(
        select(CustomHoliday).where(
            CustomHoliday.id == day_id,
            CustomHoliday.profile_id == profile_id,
        )
    )
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    await db.delete(ch)
    await db.commit()


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_profile_or_404(profile_id: uuid.UUID, tenant_id, db) -> HolidayProfile:
    result = await db.execute(
        select(HolidayProfile).where(
            HolidayProfile.id == profile_id,
            HolidayProfile.tenant_id == tenant_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil nicht gefunden")
    return profile
