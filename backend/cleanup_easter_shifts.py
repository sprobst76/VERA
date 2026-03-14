"""
Einmaliges Cleanup-Script: Löscht Demo-Schichten in den Osterferien 2026
(30.03. – 11.04.2026) aus der Produktions-Datenbank.

Ausführen auf dem VPS:
  cd /opt/vera/backend  (oder wo auch immer das Backend liegt)
  DATABASE_URL=postgresql://... python3 cleanup_easter_shifts.py

Oder lokal mit SSH-Tunnel:
  python3 cleanup_easter_shifts.py
"""
import asyncio
import os
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

EASTER_START = date(2026, 3, 30)
EASTER_END   = date(2026, 4, 11)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Fallback: lokale SQLite für Entwicklung
    "sqlite+aiosqlite:///./vera.db",
)


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # 1. Zeige betroffene Schichten
        result = await conn.execute(
            text("""
                SELECT id, date, start_time, end_time, status, employee_id
                FROM shifts
                WHERE date >= :start AND date <= :end
                ORDER BY date
            """),
            {"start": str(EASTER_START), "end": str(EASTER_END)},
        )
        rows = result.fetchall()

        if not rows:
            print("✅ Keine Schichten in den Osterferien gefunden – nichts zu tun.")
            return

        print(f"⚠️  {len(rows)} Schicht(en) gefunden in Osterferien ({EASTER_START} – {EASTER_END}):")
        for r in rows:
            print(f"   {r.date}  {str(r.start_time)[:5]}–{str(r.end_time)[:5]}  status={r.status}  id={r.id}")

        confirm = input("\nAlle diese Schichten löschen? [ja/nein]: ").strip().lower()
        if confirm != "ja":
            print("Abgebrochen.")
            return

        # 2. Löschen
        del_result = await conn.execute(
            text("""
                DELETE FROM shifts
                WHERE date >= :start AND date <= :end
            """),
            {"start": str(EASTER_START), "end": str(EASTER_END)},
        )
        print(f"✅ {del_result.rowcount} Schicht(en) gelöscht.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
