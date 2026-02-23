"""
Migration: Super-Admins-Tabelle und Tenant.is_active-Spalte hinzufügen.
Ausführen mit: python migrate_add_superadmin.py
"""
import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_PATH", "vera.db")
con = sqlite3.connect(DB_PATH)

try:
    con.execute("""
        CREATE TABLE IF NOT EXISTS super_admins (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL
        )
    """)
    print("✓ Tabelle super_admins erstellt (oder existiert bereits)")
except Exception as e:
    print(f"  super_admins: {e}")

try:
    con.execute("ALTER TABLE tenants ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    print("✓ tenants.is_active hinzugefügt")
except Exception as e:
    print(f"  tenants.is_active: {e}")

try:
    con.execute("ALTER TABLE super_admins ADD COLUMN totp_secret TEXT")
    print("✓ super_admins.totp_secret hinzugefügt")
except Exception as e:
    print(f"  super_admins.totp_secret: {e}")

try:
    con.execute("ALTER TABLE super_admins ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0")
    print("✓ super_admins.totp_enabled hinzugefügt")
except Exception as e:
    print(f"  super_admins.totp_enabled: {e}")

con.commit()
con.close()
print("Migration abgeschlossen.")
