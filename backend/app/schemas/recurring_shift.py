import uuid
from datetime import date, datetime, time

from pydantic import BaseModel


WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class RecurringShiftCreate(BaseModel):
    weekday: int                           # 0=Mo … 6=So
    start_time: time
    end_time: time
    break_minutes: int = 0
    employee_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    valid_from: date
    valid_until: date
    holiday_profile_id: uuid.UUID | None = None
    skip_public_holidays: bool = True
    label: str | None = None


class RecurringShiftUpdate(BaseModel):
    weekday: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = None
    employee_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    holiday_profile_id: uuid.UUID | None = None
    skip_public_holidays: bool | None = None
    label: str | None = None
    is_active: bool | None = None


class RecurringShiftUpdateFrom(BaseModel):
    """Update a recurring shift 'ab Datum': regenerate from from_date forward."""
    from_date: date
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = None
    employee_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    holiday_profile_id: uuid.UUID | None = None
    skip_public_holidays: bool | None = None
    label: str | None = None


class RecurringShiftPreview(BaseModel):
    weekday: int
    valid_from: date
    valid_until: date
    holiday_profile_id: uuid.UUID | None = None
    skip_public_holidays: bool = True


class RecurringShiftOut(BaseModel):
    id: uuid.UUID
    weekday: int
    weekday_name: str
    start_time: time
    end_time: time
    break_minutes: int
    employee_id: uuid.UUID | None
    template_id: uuid.UUID | None
    valid_from: date
    valid_until: date
    holiday_profile_id: uuid.UUID | None
    skip_public_holidays: bool
    label: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_weekday(cls, obj):
        data = {
            "id": obj.id,
            "weekday": obj.weekday,
            "weekday_name": WEEKDAY_NAMES[obj.weekday] if 0 <= obj.weekday <= 6 else "?",
            "start_time": obj.start_time,
            "end_time": obj.end_time,
            "break_minutes": obj.break_minutes,
            "employee_id": obj.employee_id,
            "template_id": obj.template_id,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "holiday_profile_id": obj.holiday_profile_id,
            "skip_public_holidays": obj.skip_public_holidays,
            "label": obj.label,
            "is_active": obj.is_active,
            "created_at": obj.created_at,
        }
        return cls(**data)


class RecurringShiftCreateResponse(BaseModel):
    recurring_shift: RecurringShiftOut
    generated_count: int
    skipped_count: int


class PreviewResponse(BaseModel):
    generated_count: int
    skipped_count: int
    skipped_dates: list[str]
