"""
audit_log.py — Admin-only endpoint for reading the audit trail.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Query

from sqlalchemy import select, func

from app.api.deps import AdminUser, DB
from app.models.audit import AuditLog
from app.schemas.audit_log import AuditLogPageOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=AuditLogPageOut)
async def list_audit_log(
    current_user: AdminUser,
    db: DB,
    entity_type: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Returns paginated audit log entries for the current tenant.
    Admin-only. Supports filtering by entity_type and date range.
    """
    conditions = [AuditLog.tenant_id == current_user.tenant_id]
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if from_date:
        conditions.append(AuditLog.created_at >= from_date)
    if to_date:
        conditions.append(AuditLog.created_at < to_date + timedelta(days=1))

    total_q = select(func.count()).select_from(AuditLog).where(*conditions)
    total = (await db.execute(total_q)).scalar() or 0

    items_q = (
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(items_q)
    items = result.scalars().all()

    return AuditLogPageOut(items=items, total=total)
