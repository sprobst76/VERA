"""
SuperAdmin API – globale Tenant-Verwaltung.

Alle Endpunkte unter /superadmin/... erfordern einen SuperAdmin-Token.
SuperAdmins haben keinen Tenant-Kontext – sie sehen und verwalten alle Tenants.
"""
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select, func

from app.api.deps import DB, SuperAdminUser
import pyotp
import qrcode
import qrcode.image.svg
import io

from app.core.security import (
    hash_password, verify_password,
    create_superadmin_token, create_superadmin_challenge_token,
    decode_token,
)
from app.models.employee import Employee
from app.models.superadmin import SuperAdmin
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SuperAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SuperAdminLoginResponse(BaseModel):
    """Entweder vollständiges Token ODER Challenge für 2FA."""
    access_token: str | None = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    challenge_token: str | None = None


class TwoFAVerifyRequest(BaseModel):
    challenge_token: str
    totp_code: str


class SuperAdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TwoFASetupResponse(BaseModel):
    secret: str          # base32 – für manuellen Eintrag in Authenticator
    totp_uri: str        # otpauth://totp/... – für QR-Code
    qr_svg: str          # fertig gerenderte SVG als String


class TwoFAConfirmRequest(BaseModel):
    totp_code: str       # 6-stelliger Code aus der App


class TwoFADisableRequest(BaseModel):
    password: str
    totp_code: str


class SuperAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class SuperAdminCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        return v


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    state: str
    is_active: bool
    created_at: datetime
    user_count: int
    employee_count: int


class TenantCreate(BaseModel):
    name: str
    slug: str
    state: str = "BW"
    plan: str = "free"
    # Erster Admin-Account für den Tenant
    admin_email: EmailStr
    admin_password: str

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug darf nur Kleinbuchstaben, Zahlen und Bindestriche enthalten")
        return v

    @field_validator("admin_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        return v


class TenantUpdate(BaseModel):
    name: str | None = None
    plan: str | None = None
    state: str | None = None
    is_active: bool | None = None


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=SuperAdminLoginResponse)
async def superadmin_login(payload: SuperAdminLoginRequest, db: DB):
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.email == payload.email))
    sa = result.scalar_one_or_none()

    if not sa or not verify_password(payload.password, sa.hashed_password):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    if not sa.is_active:
        raise HTTPException(status_code=403, detail="Account deaktiviert")

    if sa.totp_enabled:
        # Passwort OK, aber 2FA noch ausstehend → Challenge-Token zurückgeben
        challenge = create_superadmin_challenge_token(sa.id)
        return SuperAdminLoginResponse(requires_2fa=True, challenge_token=challenge)

    token = create_superadmin_token(sa.id)
    return SuperAdminLoginResponse(access_token=token)


@router.post("/login/verify-2fa", response_model=SuperAdminToken)
async def verify_2fa(payload: TwoFAVerifyRequest, db: DB):
    """Schritt 2 des Logins: Challenge-Token + TOTP-Code → vollständiges Access-Token."""
    try:
        data = decode_token(payload.challenge_token)
        if data.get("type") != "superadmin_challenge":
            raise ValueError
        sa_id = uuid.UUID(data["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Ungültiger oder abgelaufener Challenge-Token")

    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == sa_id))
    sa = result.scalar_one_or_none()
    if not sa or not sa.is_active or not sa.totp_enabled or not sa.totp_secret:
        raise HTTPException(status_code=401, detail="Ungültige Anfrage")

    totp = pyotp.TOTP(sa.totp_secret)
    if not totp.verify(payload.totp_code, valid_window=1):
        raise HTTPException(status_code=401, detail="Ungültiger Authenticator-Code")

    token = create_superadmin_token(sa.id)
    return SuperAdminToken(access_token=token)


@router.get("/me", response_model=SuperAdminOut)
async def superadmin_me(current_sa: SuperAdminUser):
    return current_sa


# ── 2FA-Verwaltung (authentifiziert) ─────────────────────────────────────────

@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(current_sa: SuperAdminUser, db: DB):
    """Generiert ein neues TOTP-Secret und gibt QR-Code + URI zurück.
    2FA ist erst nach confirm aktiv."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_sa.email, issuer_name="VERA Admin")

    # QR-Code als SVG generieren
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(uri, image_factory=factory, box_size=10)
    stream = io.BytesIO()
    img.save(stream)
    svg = stream.getvalue().decode()

    # Secret temporär speichern (wird erst bei confirm aktiviert)
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == current_sa.id))
    sa = result.scalar_one()
    sa.totp_secret = secret  # noch nicht enabled – nur gespeichert
    await db.commit()

    return TwoFASetupResponse(secret=secret, totp_uri=uri, qr_svg=svg)


@router.post("/2fa/confirm")
async def confirm_2fa(payload: TwoFAConfirmRequest, current_sa: SuperAdminUser, db: DB):
    """Bestätigt den TOTP-Code und aktiviert 2FA dauerhaft."""
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == current_sa.id))
    sa = result.scalar_one()

    if not sa.totp_secret:
        raise HTTPException(status_code=400, detail="Zuerst /2fa/setup aufrufen")

    totp = pyotp.TOTP(sa.totp_secret)
    if not totp.verify(payload.totp_code, valid_window=1):
        raise HTTPException(status_code=400, detail="Ungültiger Code – bitte erneut versuchen")

    sa.totp_enabled = True
    await db.commit()
    return {"message": "2FA erfolgreich aktiviert"}


@router.delete("/2fa")
async def disable_2fa(payload: TwoFADisableRequest, current_sa: SuperAdminUser, db: DB):
    """Deaktiviert 2FA – erfordert Passwort + aktuellen TOTP-Code."""
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == current_sa.id))
    sa = result.scalar_one()

    if not verify_password(payload.password, sa.hashed_password):
        raise HTTPException(status_code=401, detail="Falsches Passwort")

    if sa.totp_enabled and sa.totp_secret:
        totp = pyotp.TOTP(sa.totp_secret)
        if not totp.verify(payload.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Ungültiger Authenticator-Code")

    sa.totp_enabled = False
    sa.totp_secret = None
    await db.commit()
    return {"message": "2FA deaktiviert"}


# ── Tenant-Verwaltung ─────────────────────────────────────────────────────────

@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(current_sa: SuperAdminUser, db: DB):
    tenants_result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    tenants = tenants_result.scalars().all()

    # User- und Mitarbeiterzahlen pro Tenant
    user_counts_result = await db.execute(
        select(User.tenant_id, func.count(User.id)).group_by(User.tenant_id)
    )
    user_counts = {row[0]: row[1] for row in user_counts_result.all()}

    emp_counts_result = await db.execute(
        select(Employee.tenant_id, func.count(Employee.id)).group_by(Employee.tenant_id)
    )
    emp_counts = {row[0]: row[1] for row in emp_counts_result.all()}

    return [
        TenantOut(
            id=t.id,
            name=t.name,
            slug=t.slug,
            plan=t.plan,
            state=t.state,
            is_active=t.is_active,
            created_at=t.created_at,
            user_count=user_counts.get(t.id, 0),
            employee_count=emp_counts.get(t.id, 0),
        )
        for t in tenants
    ]


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, current_sa: SuperAdminUser, db: DB):
    # Slug-Eindeutigkeit prüfen
    existing_slug = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    if existing_slug.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug bereits vergeben")

    # E-Mail-Eindeutigkeit prüfen
    existing_email = await db.execute(select(User).where(User.email == payload.admin_email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")

    # Tenant anlegen
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        state=payload.state,
        plan=payload.plan,
    )
    db.add(tenant)
    await db.flush()  # tenant.id wird befüllt

    # Ersten Admin-User anlegen
    admin_user = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        role="admin",
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(tenant)

    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        state=tenant.state,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        user_count=1,
        employee_count=0,
    )


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: uuid.UUID, payload: TenantUpdate, current_sa: SuperAdminUser, db: DB):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden")

    if payload.name is not None:
        tenant.name = payload.name
    if payload.plan is not None:
        tenant.plan = payload.plan
    if payload.state is not None:
        tenant.state = payload.state
    if payload.is_active is not None:
        tenant.is_active = payload.is_active
        # Alle User des Tenants ebenfalls (de)aktivieren
        users_result = await db.execute(select(User).where(User.tenant_id == tenant_id))
        for u in users_result.scalars().all():
            u.is_active = payload.is_active

    await db.commit()
    await db.refresh(tenant)

    user_count = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    emp_count = await db.execute(
        select(func.count(Employee.id)).where(Employee.tenant_id == tenant_id)
    )

    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        state=tenant.state,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        user_count=user_count.scalar(),
        employee_count=emp_count.scalar(),
    )


# ── SuperAdmin-Verwaltung ─────────────────────────────────────────────────────

@router.get("/admins", response_model=list[SuperAdminOut])
async def list_superadmins(current_sa: SuperAdminUser, db: DB):
    result = await db.execute(select(SuperAdmin).order_by(SuperAdmin.email))
    return result.scalars().all()


@router.post("/admins", response_model=SuperAdminOut, status_code=status.HTTP_201_CREATED)
async def create_superadmin(payload: SuperAdminCreate, current_sa: SuperAdminUser, db: DB):
    existing = await db.execute(select(SuperAdmin).where(SuperAdmin.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")

    sa = SuperAdmin(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(sa)
    await db.commit()
    await db.refresh(sa)
    return sa


@router.patch("/admins/{admin_id}", response_model=SuperAdminOut)
async def update_superadmin(
    admin_id: uuid.UUID,
    payload: dict,
    current_sa: SuperAdminUser,
    db: DB,
):
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == admin_id))
    sa = result.scalar_one_or_none()
    if not sa:
        raise HTTPException(status_code=404, detail="SuperAdmin nicht gefunden")

    # Selbst-Deaktivierung verhindern
    if sa.id == current_sa.id and payload.get("is_active") is False:
        raise HTTPException(status_code=400, detail="Eigenen Account nicht deaktivierbar")

    if "is_active" in payload:
        sa.is_active = payload["is_active"]
    if "password" in payload and payload["password"]:
        if len(payload["password"]) < 8:
            raise HTTPException(status_code=400, detail="Passwort mindestens 8 Zeichen")
        sa.hashed_password = hash_password(payload["password"])

    await db.commit()
    await db.refresh(sa)
    return sa
