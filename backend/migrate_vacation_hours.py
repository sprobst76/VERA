"""
Migration: vacation_days → vacation_hours, days_count → hours_count

Formel Urlaubsstunden:
  vacation_hours = ROUND((monthly_hours_limit * 12 / 52) * 4, 1)
  (4 Urlaubswochen gem. BUrlG-Minimum)

Ausführen: .venv/bin/python migrate_vacation_hours.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "vera.db")

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("🔄 Migration: vacation_hours + hours_count ...\n")

# ── employees: add vacation_hours ─────────────────────────────────────────────
cols = [row[1] for row in cur.execute("PRAGMA table_info(employees)")]

if "vacation_hours" not in cols:
    cur.execute("ALTER TABLE employees ADD COLUMN vacation_hours REAL")
    print("  ✓ Spalte vacation_hours hinzugefügt")

    # Berechne aus monthly_hours_limit wenn vorhanden
    cur.execute("""
        UPDATE employees
        SET vacation_hours = ROUND((CAST(monthly_hours_limit AS REAL) * 12.0 / 52.0) * 4.0, 1)
        WHERE monthly_hours_limit IS NOT NULL AND monthly_hours_limit > 0
    """)
    # Fallback: vacation_days × 4h (grobe Näherung)
    cur.execute("""
        UPDATE employees
        SET vacation_hours = CAST(vacation_days AS REAL) * 4.0
        WHERE vacation_hours IS NULL OR vacation_hours = 0
    """)

    # Zeige Ergebnis
    rows = cur.execute("""
        SELECT first_name, last_name, contract_type,
               monthly_hours_limit, vacation_days, vacation_hours
        FROM employees ORDER BY last_name
    """).fetchall()
    print("\n  Mitarbeiter-Übersicht:")
    print(f"  {'Name':<20} {'Typ':<12} {'h/Mo':>6}  {'Tage':>5}  {'h Urlaub':>9}")
    print("  " + "─" * 58)
    for r in rows:
        name = f"{r['first_name']} {r['last_name']}"
        print(f"  {name:<20} {r['contract_type']:<12} {r['monthly_hours_limit'] or '–':>6}  "
              f"{r['vacation_days'] or '–':>5}  {r['vacation_hours'] or '–':>9}")
else:
    print("  ℹ️  vacation_hours existiert bereits")

# ── employee_absences: add hours_count ────────────────────────────────────────
abs_cols = [row[1] for row in cur.execute("PRAGMA table_info(employee_absences)")]

if "hours_count" not in abs_cols:
    cur.execute("ALTER TABLE employee_absences ADD COLUMN hours_count REAL")
    print("\n  ✓ Spalte hours_count hinzugefügt")
    # Migriere vorhandene days_count-Werte (×4h Näherung)
    cur.execute("""
        UPDATE employee_absences
        SET hours_count = ROUND(days_count * 4.0, 1)
        WHERE days_count IS NOT NULL
    """)
    migrated = cur.execute("SELECT COUNT(*) FROM employee_absences WHERE hours_count IS NOT NULL").fetchone()[0]
    print(f"  ✓ {migrated} Abwesenheiten migriert (days × 4h)")
else:
    print("  ℹ️  hours_count existiert bereits")

con.commit()
con.close()

print("\n✅ Migration abgeschlossen!")
