"""
CRUD für Diensttypen (ShiftType) – Farbe, Erinnerungseinstellungen etc.
"""
import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.database import DB
from app.core.security import CurrentUser, ManagerOrAdmin
from app.models.shift_type import ShiftType
from app.schemas.shift import ShiftTypeCreate, ShiftTypeOut, ShiftTypeUpdate

router = APIRouter(prefix="/shift-types", tags=["shift-types"])


@router.get("", response_model=list[ShiftTypeOut])
async def list_shift_types(db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(ShiftType)
        .where(ShiftType.tenant_id == current_user.tenant_id, ShiftType.is_active == True)
        .order_by(ShiftType.name)
    )
    return result.scalars().all()


@router.post("", response_model=ShiftTypeOut, status_code=status.HTTP_201_CREATED)
async def create_shift_type(payload: ShiftTypeCreate, db: DB, current_user: ManagerOrAdmin):
    st = ShiftType(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(st)
    await db.commit()
    await db.refresh(st)
    return st


@router.put("/{shift_type_id}", response_model=ShiftTypeOut)
async def update_shift_type(
    shift_type_id: uuid.UUID,
    payload: ShiftTypeUpdate,
    db: DB,
    current_user: ManagerOrAdmin,
):
    result = await db.execute(
        select(ShiftType).where(
            ShiftType.id == shift_type_id,
            ShiftType.tenant_id == current_user.tenant_id,
        )
    )
    st = result.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Diensttyp nicht gefunden")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(st, field, value)

    await db.commit()
    await db.refresh(st)
    return st


@router.delete("/{shift_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift_type(
    shift_type_id: uuid.UUID,
    db: DB,
    current_user: ManagerOrAdmin,
):
    result = await db.execute(
        select(ShiftType).where(
            ShiftType.id == shift_type_id,
            ShiftType.tenant_id == current_user.tenant_id,
        )
    )
    st = result.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Diensttyp nicht gefunden")

    # Soft-delete: deactivate so existing shifts keep the reference
    st.is_active = False
    await db.commit()
