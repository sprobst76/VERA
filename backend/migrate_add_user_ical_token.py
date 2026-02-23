"""
Migration: ical_token auf users-Tabelle hinzufügen.
Ausführen: .venv/bin/python migrate_add_user_ical_token.py
"""
import sqlite3, secrets, os

DB_PATH = os.path.join(os.path.dirname(__file__), "vera.db")
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cols = [row[1] for row in cur.execute("PRAGMA table_info(users)")]
if "ical_token" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN ical_token TEXT")
    # Generate unique token for each existing user
    users = cur.execute("SELECT id FROM users").fetchall()
    for (uid,) in users:
        cur.execute("UPDATE users SET ical_token = ? WHERE id = ?",
                    (secrets.token_urlsafe(32), uid))
    con.commit()
    print(f"✓ ical_token hinzugefügt und für {len(users)} User befüllt")
else:
    print("ℹ️  ical_token existiert bereits")

con.close()
