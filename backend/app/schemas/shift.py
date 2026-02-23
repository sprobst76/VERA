from pydantic import BaseModel
import uuid
from datetime import date as Date, datetime as DateTime, time as Time
from typing import Optional


class ShiftTemplateCreate(BaseModel):
    name: str
    weekdays: list[int]  # 0=Mo ... 6=So
    start_time: Time
    end_time: Time
    break_minutes: int = 0
    location: Optional[str] = None
    notes: Optional[str] = None
    required_skills: list[str] = []
    color: str = "#1E3A5F"
    valid_from: Optional[Date] = None
    valid_until: Optional[Date] = None


class ShiftTemplateOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    weekdays: list[int]
    start_time: Time
    end_time: Time
    break_minutes: int
    location: Optional[str]
    notes: Optional[str]
    required_skills: list[str]
    color: str
    is_active: bool
    valid_from: Optional[Date]
    valid_until: Optional[Date]
    created_at: DateTime

    model_config = {"from_attributes": True}


class ShiftCreate(BaseModel):
    employee_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    date: Date
    start_time: Time
    end_time: Time
    break_minutes: int = 0
    location: Optional[str] = None
    notes: Optional[str] = None


class ShiftUpdate(BaseModel):
    employee_id: Optional[uuid.UUID] = None
    date: Optional[Date] = None
    start_time: Optional[Time] = None
    end_time: Optional[Time] = None
    break_minutes: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    cancellation_reason: Optional[str] = None
    actual_start: Optional[Time] = None
    actual_end: Optional[Time] = None


class ShiftActualTime(BaseModel):
    """Self-service: employee reports actual start/end times."""
    actual_start: Optional[Time] = None
    actual_end: Optional[Time] = None
    notes: Optional[str] = None


class ShiftConfirm(BaseModel):
    """Admin/Manager confirms a shift (planned → confirmed)."""
    actual_start: Optional[Time] = None
    actual_end: Optional[Time] = None
    confirmation_note: Optional[str] = None


class ShiftOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: Optional[uuid.UUID]
    template_id: Optional[uuid.UUID]
    date: Date
    start_time: Time
    end_time: Time
    break_minutes: int
    location: Optional[str]
    notes: Optional[str]
    status: str
    cancellation_reason: Optional[str]
    actual_start: Optional[Time]
    actual_end: Optional[Time]
    confirmed_by: Optional[uuid.UUID]
    confirmed_at: Optional[DateTime]
    confirmation_note: Optional[str]
    is_holiday: bool
    is_weekend: bool
    is_sunday: bool
    rest_period_ok: bool
    break_ok: bool
    minijob_limit_ok: bool
    hours_carried_over: float
    created_at: DateTime
    updated_at: DateTime

    model_config = {"from_attributes": True}


class BulkShiftCreate(BaseModel):
    template_id: uuid.UUID
    from_date: Date
    to_date: Date
    employee_id: Optional[uuid.UUID] = None
    start_time_override: Optional[Time] = None
    end_time_override: Optional[Time] = None
