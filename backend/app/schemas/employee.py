from pydantic import BaseModel, EmailStr
from typing import Any
import uuid
from datetime import datetime, time


# ── Öffentliches Profil (für alle Mitarbeiter sichtbar) ──────────────────────

class EmployeePublicOut(BaseModel):
    """Nur Name und koordinationsrelevante Felder – kein Gehalt, kein Kontakt."""
    id: uuid.UUID
    first_name: str
    last_name: str
    contract_type: str          # minijob | part_time | full_time
    qualifications: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


# ── Privates Profil (nur Admin + eigene Person) ───────────────────────────────

class EmployeeOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    contract_type: str
    hourly_rate: float
    weekly_hours: float | None
    full_time_percentage: float | None
    monthly_hours_limit: float | None
    annual_salary_limit: float | None
    vacation_days: int
    qualifications: list[str]
    notification_prefs: dict[str, Any]
    ical_token: str | None
    telegram_chat_id: str | None
    matrix_user_id: str | None
    quiet_hours_start: time
    quiet_hours_end: time
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── CRUD-Schemas (nur Admin) ──────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr | None = None
    phone: str | None = None
    contract_type: str  # minijob | part_time | full_time
    hourly_rate: float
    weekly_hours: float | None = None
    full_time_percentage: float | None = None
    monthly_hours_limit: float | None = None
    annual_salary_limit: float | None = 6672.0
    vacation_days: int = 30
    qualifications: list[str] = []
    notification_prefs: dict[str, Any] = {}
    telegram_chat_id: str | None = None
    matrix_user_id: str | None = None
    quiet_hours_start: time = time(21, 0)
    quiet_hours_end: time = time(7, 0)


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    contract_type: str | None = None
    hourly_rate: float | None = None
    weekly_hours: float | None = None
    full_time_percentage: float | None = None
    monthly_hours_limit: float | None = None
    annual_salary_limit: float | None = None
    vacation_days: int | None = None
    qualifications: list[str] | None = None
    notification_prefs: dict[str, Any] | None = None
    telegram_chat_id: str | None = None
    matrix_user_id: str | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    is_active: bool | None = None
    user_id: uuid.UUID | None = None  # link/unlink login account
