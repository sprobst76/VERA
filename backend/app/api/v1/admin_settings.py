"""
Admin Settings API – SMTP-Konfiguration pro Tenant.

Gespeichert in Tenant.settings["smtp"] (vorhandene JSON-Spalte, keine Migration nötig).
Das Passwort wird nie im GET zurückgegeben – nur has_password: bool.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, AdminUser
from app.models.tenant import Tenant

router = APIRouter(prefix="/admin", tags=["admin-settings"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SmtpConfigUpdate(BaseModel):
    host: str
    port: int = 587
    user: str
    password: str          # leer lassen = altes Passwort beibehalten
    from_email: str


class SmtpConfigOut(BaseModel):
    host: str
    port: int
    user: str
    from_email: str
    has_password: bool     # Passwort nie im Klartext zurückgeben
    configured: bool       # True wenn host+user+password alle gesetzt


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/settings/smtp", response_model=SmtpConfigOut)
async def get_smtp_config(current_user: AdminUser, db: DB):
    """SMTP-Konfiguration des Tenants lesen (Passwort wird nie zurückgegeben)."""
    tenant = await _get_tenant(db, current_user.tenant_id)
    cfg = (tenant.settings or {}).get("smtp", {})
    return SmtpConfigOut(
        host=cfg.get("host", ""),
        port=cfg.get("port", 587),
        user=cfg.get("user", ""),
        from_email=cfg.get("from_email", ""),
        has_password=bool(cfg.get("password")),
        configured=bool(cfg.get("host") and cfg.get("user") and cfg.get("password")),
    )


@router.put("/settings/smtp", response_model=SmtpConfigOut)
async def update_smtp_config(payload: SmtpConfigUpdate, current_user: AdminUser, db: DB):
    """SMTP-Konfiguration speichern. Leeres password-Feld behält altes Passwort."""
    tenant = await _get_tenant(db, current_user.tenant_id)

    existing = dict((tenant.settings or {}).get("smtp", {}))
    existing["host"]       = payload.host
    existing["port"]       = payload.port
    existing["user"]       = payload.user
    existing["from_email"] = payload.from_email
    if payload.password:    # nur überschreiben wenn neues Passwort angegeben
        existing["password"] = payload.password

    tenant.settings = {**(tenant.settings or {}), "smtp": existing}
    await db.commit()

    return SmtpConfigOut(
        host=existing.get("host", ""),
        port=existing.get("port", 587),
        user=existing.get("user", ""),
        from_email=existing.get("from_email", ""),
        has_password=bool(existing.get("password")),
        configured=bool(existing.get("host") and existing.get("user") and existing.get("password")),
    )


@router.post("/settings/smtp/test", status_code=200)
async def test_smtp_config(current_user: AdminUser, db: DB):
    """Test-E-Mail an den eingeloggten Admin senden."""
    tenant = await _get_tenant(db, current_user.tenant_id)
    cfg = (tenant.settings or {}).get("smtp", {})

    if not cfg.get("host") or not cfg.get("user") or not cfg.get("password"):
        raise HTTPException(status_code=400, detail="SMTP nicht konfiguriert")

    to_addr = current_user.email
    if not to_addr:
        raise HTTPException(status_code=400, detail="Admin hat keine E-Mail-Adresse")

    import asyncio, smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    def _send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "VERA – SMTP Test erfolgreich"
        msg["From"]    = cfg.get("from_email") or cfg["user"]
        msg["To"]      = to_addr
        msg.attach(MIMEText(
            "Hallo,\n\nDer SMTP-Versand ist korrekt konfiguriert.\n\nVERA System",
            "plain", "utf-8",
        ))
        with smtplib.SMTP(cfg["host"], int(cfg.get("port", 587))) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            smtp.sendmail(msg["From"], [to_addr], msg.as_string())

    try:
        await asyncio.to_thread(_send)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP-Fehler: {str(e)[:200]}")

    return {"detail": f"Test-Mail an {to_addr} gesendet"}


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_tenant(db: DB, tenant_id) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant nicht gefunden")
    return tenant
