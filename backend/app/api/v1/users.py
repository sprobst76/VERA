"""
Users API – Benutzerverwaltung (nur Admin)
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select

from app.api.deps import DB, AdminUser
from app.core.security import hash_password
from app.models.user import User
from app.models.employee import Employee

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = ("admin", "manager", "employee")


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    has_employee: bool  # convenience flag

    model_config = {"from_attributes": False}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "employee"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        return v


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("", response_model=list[UserOut])
async def list_users(current_user: AdminUser, db: DB):
    """List all users in the tenant."""
    users_result = await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.email)
    )
    users = users_result.scalars().all()

    # Fetch linked employee IDs in one query
    emp_result = await db.execute(
        select(Employee.user_id).where(
            Employee.tenant_id == current_user.tenant_id,
            Employee.user_id.isnot(None),
        )
    )
    linked_user_ids = {row[0] for row in emp_result.all()}

    return [
        UserOut(
            id=u.id,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            has_employee=u.id in linked_user_ids,
        )
        for u in users
    ]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, current_user: AdminUser, db: DB):
    """Admin creates a new login account (e.g. for an employee)."""
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Ungültige Rolle. Erlaubt: {VALID_ROLES}")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")

    user = User(
        tenant_id=current_user.tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        has_employee=False,
    )


@router.put("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, current_user: AdminUser, db: DB):
    """Update role, active status, or password."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # Prevent demoting self
    if user.id == current_user.id and payload.role and payload.role != current_user.role:
        raise HTTPException(status_code=400, detail="Eigene Rolle kann nicht geändert werden")

    if payload.role:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Ungültige Rolle")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    await db.commit()
    await db.refresh(user)

    emp_result = await db.execute(
        select(Employee.user_id).where(
            Employee.tenant_id == current_user.tenant_id,
            Employee.user_id == user.id,
        )
    )
    has_employee = emp_result.scalar_one_or_none() is not None

    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        has_employee=has_employee,
    )
