"""
Bootstrap-Tool: Ersten SuperAdmin anlegen.

Verwendung:
  python create_superadmin.py <email> <passwort>

Beispiel:
  python create_superadmin.py admin@vera.de meinSicheresPasswort123
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.superadmin import SuperAdmin
import app.models  # noqa – alle Modelle laden


async def main(email: str, password: str) -> None:
    if len(password) < 8:
        print("Fehler: Passwort muss mindestens 8 Zeichen lang sein.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(SuperAdmin).where(SuperAdmin.email == email))
        if existing.scalar_one_or_none():
            print(f"SuperAdmin mit E-Mail '{email}' existiert bereits.")
            sys.exit(0)

        sa = SuperAdmin(
            email=email,
            hashed_password=hash_password(password),
        )
        db.add(sa)
        await db.commit()
        await db.refresh(sa)
        print(f"✓ SuperAdmin '{email}' wurde erstellt (ID: {sa.id})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python create_superadmin.py <email> <passwort>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1], sys.argv[2]))
