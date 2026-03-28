"""
audit_log.py — Pydantic v2 schemas for the audit log API.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    """Single audit log entry returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    old_values: dict | None
    new_values: dict | None
    created_at: datetime


class AuditLogPageOut(BaseModel):
    """Paginated list of audit log entries."""

    items: list[AuditLogOut]
    total: int
