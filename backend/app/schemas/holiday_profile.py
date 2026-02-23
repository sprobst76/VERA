import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ── VacationPeriod ───────────────────────────────────────────────────────────

class VacationPeriodCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    color: str = "#a6e3a1"


class VacationPeriodUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    color: str | None = None


class VacationPeriodOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    color: str

    model_config = {"from_attributes": True}


# ── CustomHoliday ────────────────────────────────────────────────────────────

class CustomHolidayCreate(BaseModel):
    date: date
    name: str
    color: str = "#fab387"


class CustomHolidayOut(BaseModel):
    id: uuid.UUID
    date: date
    name: str
    color: str

    model_config = {"from_attributes": True}


# ── HolidayProfile ───────────────────────────────────────────────────────────

class HolidayProfileCreate(BaseModel):
    name: str
    state: str = "BW"
    is_active: bool = False
    preset_bw: bool = False   # Auto-fill BW_SCHOOL_HOLIDAYS_2025_26


class HolidayProfileUpdate(BaseModel):
    name: str | None = None
    state: str | None = None
    is_active: bool | None = None


class HolidayProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    state: str
    is_active: bool
    created_at: datetime
    vacation_periods: list[VacationPeriodOut] = []
    custom_holidays: list[CustomHolidayOut] = []

    model_config = {"from_attributes": True}


class HolidayProfileListOut(BaseModel):
    id: uuid.UUID
    name: str
    state: str
    is_active: bool
    created_at: datetime
    vacation_period_count: int = 0
    custom_holiday_count: int = 0

    model_config = {"from_attributes": True}
