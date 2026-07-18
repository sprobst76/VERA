"""
Feedback API – Änderungswünsche/Bug-Meldungen von Mitarbeitern (Rückkanal
aus dem /help-Bereich). Jeder eingeloggte Tenant-User (nicht parent_viewer)
kann melden; Admin/Manager triagieren Status + Notiz.
"""
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, ManagerOrAdmin
from app.models.employee import Employee
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackOut
from app.services.notification_service import notify_feedback_submitted

router = APIRouter(prefix="/feedback", tags=["feedback"])

VALID_CATEGORIES = ("bug", "wish", "question")
VALID_STATUSES = ("open", "in_progress", "resolved", "declined")


@router.post("", response_model=FeedbackOut, status_code=201)
async def create_feedback(payload: FeedbackCreate, current_user: CurrentUser, db: DB):
    if current_user.role == "parent_viewer":
        raise HTTPException(status_code=403, detail="Zugriff verweigert")
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Ungültige Kategorie: {payload.category}")

    emp_result = await db.execute(
        select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.tenant_id == current_user.tenant_id,
        )
    )
    emp = emp_result.scalar_one_or_none()
    reporter_name = f"{emp.first_name} {emp.last_name}" if emp else current_user.email

    fb = Feedback(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        reporter_name=reporter_name,
        category=payload.category,
        title=payload.title,
        description=payload.description,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    await notify_feedback_submitted(fb, db)

    return fb


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(current_user: CurrentUser, db: DB, status_filter: str | None = None):
    if current_user.role == "parent_viewer":
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    query = select(Feedback).where(Feedback.tenant_id == current_user.tenant_id)
    if current_user.role not in ("admin", "manager"):
        query = query.where(Feedback.created_by_user_id == current_user.id)
    if status_filter:
        query = query.where(Feedback.status == status_filter)

    result = await db.execute(query.order_by(Feedback.created_at.desc()))
    return result.scalars().all()


@router.patch("/{feedback_id}", response_model=FeedbackOut)
async def update_feedback(feedback_id: uuid.UUID, payload: FeedbackUpdate, current_user: ManagerOrAdmin, db: DB):
    result = await db.execute(
        select(Feedback).where(Feedback.id == feedback_id, Feedback.tenant_id == current_user.tenant_id)
    )
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="Rückmeldung nicht gefunden")

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Ungültiger Status: {payload.status}")
        fb.status = payload.status
    if payload.admin_note is not None:
        fb.admin_note = payload.admin_note

    await db.commit()
    await db.refresh(fb)
    return fb
