from pydantic import BaseModel
import uuid
from datetime import date, datetime
from typing import Optional


class PayrollEntryOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    month: date
    planned_hours: float | None
    actual_hours: float | None
    carryover_hours: float
    paid_hours: float | None
    early_hours: float
    late_hours: float
    night_hours: float
    weekend_hours: float
    sunday_hours: float
    holiday_hours: float
    base_wage: float | None
    early_surcharge: float
    late_surcharge: float
    night_surcharge: float
    weekend_surcharge: float
    sunday_surcharge: float
    holiday_surcharge: float
    total_gross: float | None
    ytd_gross: float | None
    annual_limit_remaining: float | None
    status: str
    notes: str | None
    pdf_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PayrollCalculateRequest(BaseModel):
    employee_id: uuid.UUID
    month: date  # first day of month (e.g. 2025-03-01)


class PayrollUpdate(BaseModel):
    status: Optional[str] = None   # approved | paid
    notes: Optional[str] = None
