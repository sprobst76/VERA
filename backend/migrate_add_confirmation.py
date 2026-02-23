"""
Migration: Add shift confirmation fields to shifts table.
Run once: python migrate_add_confirmation.py
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "vera.db")
con = sqlite3.connect(db_path)

columns = {
    "confirmed_by":       "TEXT",
    "confirmed_at":       "TEXT",
    "confirmation_note":  "TEXT",
}

existing = {row[1] for row in con.execute("PRAGMA table_info(shifts)")}

for col, col_type in columns.items():
    if col not in existing:
        con.execute(f"ALTER TABLE shifts ADD COLUMN {col} {col_type}")
        print(f"Added column: {col}")
    else:
        print(f"Column already exists: {col}")

con.commit()
con.close()
print("Migration done.")
