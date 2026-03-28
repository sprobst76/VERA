"""
audit_service.py — shared helper for writing AuditLog rows.

Usage:
    await audit_service.write(db, tenant_id=..., user_id=...,
                              entity_type="shift", entity_id=...,
                              action="create", new_values={...})
    # caller owns the transaction — do NOT commit here
    await db.commit()

The function stages an AuditLog row in the current session without
committing. If the caller's transaction is rolled back the audit row
disappears with it, keeping audit log consistent with the data change.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    """Stage an AuditLog row without committing.

    The caller is responsible for calling ``await db.commit()`` afterwards.
    If the enclosing transaction is rolled back the audit row is discarded
    automatically, so audit and data stay in sync.
    """
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(log)
