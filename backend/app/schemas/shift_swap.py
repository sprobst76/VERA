import uuid
from datetime import datetime as DateTime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ShiftSwapOfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shift_id: uuid.UUID
    note: Optional[str] = None


class ShiftSwapReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool
    note: Optional[str] = None


class ShiftSwapOfferOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    shift_id: uuid.UUID
    offering_employee_id: uuid.UUID
    status: str
    note: Optional[str]
    expires_at: DateTime
    accepted_by_employee_id: Optional[uuid.UUID]
    accepted_at: Optional[DateTime]
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[DateTime]
    review_note: Optional[str]
    resolution_reason: Optional[str]
    created_at: DateTime
    updated_at: DateTime

    model_config = ConfigDict(from_attributes=True)
