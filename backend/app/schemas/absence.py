from pydantic import BaseModel
import uuid
from datetime import date, datetime


class EmployeeAbsenceCreate(BaseModel):
    employee_id: uuid.UUID
    type: str  # vacation | sick | school_holiday | other
    start_date: date
    end_date: date
    days_count: float | None = None
    notes: str | None = None


class EmployeeAbsenceUpdate(BaseModel):
    status: str | None = None  # pending | approved | rejected
    notes: str | None = None
    days_count: float | None = None


class EmployeeAbsenceOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    type: str
    start_date: date
    end_date: date
    days_count: float | None
    status: str
    notes: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CareAbsenceCreate(BaseModel):
    type: str  # vacation | rehab | hospital | sick | other
    start_date: date
    end_date: date
    description: str | None = None
    notes: str | None = None
    shift_handling: str = "cancelled_unpaid"  # cancelled_unpaid | carry_over | paid_anyway
    notify_employees: bool = True


class CareAbsenceOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    type: str
    start_date: date
    end_date: date
    description: str | None
    notes: str | None
    shift_handling: str
    notify_employees: bool
    created_at: datetime

    model_config = {"from_attributes": True}
