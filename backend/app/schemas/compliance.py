"""
Schemas für Compliance-Endpunkte.
"""
import uuid
from datetime import date, time

from pydantic import BaseModel


class ComplianceViolationOut(BaseModel):
    shift_id: uuid.UUID
    shift_date: date
    start_time: time
    end_time: time
    employee_id: uuid.UUID | None
    employee_name: str          # "Vorname Nachname" oder "–"
    rest_period_ok: bool
    break_ok: bool
    minijob_limit_ok: bool
    status: str

    model_config = {"from_attributes": True}
