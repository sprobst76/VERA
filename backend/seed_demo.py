"""
Demo-Seed für VERA – Schuljahr 2025/26 BW + Beispieldienste.

SQLite:     DATABASE_URL=sqlite+aiosqlite:///./vera.db  .venv/bin/python seed_demo.py
PostgreSQL: DATABASE_URL=postgresql+asyncpg://vera:secret@localhost:5432/vera  .venv/bin/python seed_demo.py

Beim ersten Start auf PostgreSQL zuerst Tabellen anlegen:
  alembic upgrade head     (wenn Migrations vorhanden)
  oder einfach seed.py laufen lassen – create_tables() erledigt das.
"""
import asyncio
import secrets
from datetime import date, time, timedelta
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import AsyncSessionLocal, create_tables
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.models.employee import Employee
from app.models.shift import Shift, ShiftTemplate
from app.models.audit import AuditLog

# ── BW Schulferien 2025/26 ────────────────────────────────────────────────────
SCHOOL_HOLIDAYS = [
    (date(2025,  9, 15), date(2025,  9, 15)),  # Schuljahresbeginn (kein Ferientag)
    (date(2025, 10, 27), date(2025, 10, 30)),  # Herbstferien
    (date(2025, 12, 22), date(2026,  1,  5)),  # Weihnachten
    (date(2026,  3, 30), date(2026,  4, 11)),  # Ostern
    (date(2026,  5, 26), date(2026,  6,  5)),  # Pfingsten
    (date(2026,  7, 30), date(2026,  9, 12)),  # Sommer
]
SCHOOL_YEAR_START = date(2025,  9, 15)
SCHOOL_YEAR_END   = date(2026,  7, 24)

# Gesetzliche Feiertage BW (vereinfacht)
BW_HOLIDAYS_2025_26 = {
    date(2025, 10,  3), date(2025, 11,  1),
    date(2025, 12, 25), date(2025, 12, 26),
    date(2026,  1,  1), date(2026,  1,  6),
    date(2026,  4,  3), date(2026,  4,  6),
    date(2026,  5,  1), date(2026,  5, 14),
    date(2026,  5, 25), date(2026,  6,  4),
    date(2026, 10,  3),
}

def is_school_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if d in BW_HOLIDAYS_2025_26:
        return False
    for start, end in SCHOOL_HOLIDAYS:
        if start <= d <= end:
            return False
    return SCHOOL_YEAR_START <= d <= SCHOOL_YEAR_END

# ── Farben je Diensttyp ───────────────────────────────────────────────────────
COLORS = {
    "schule_vormittag":     "#2563eb",   # Blau
    "schule_ganztag":       "#7c3aed",   # Violett
    "assistenz_nachmittag": "#16a34a",   # Grün
    "assistenz_wochenende": "#d97706",   # Orange
    "foerderung":           "#0891b2",   # Cyan
}

DEMO_USERS = [
    {"email": "stefan@vera.demo",  "password": "demo1234", "role": "admin",    "name": "Stefan Probst"},
    {"email": "lea@vera.demo",     "password": "demo1234", "role": "manager",  "name": "Lea Hoffmann"},
    {"email": "anna@vera.demo",    "password": "demo1234", "role": "employee", "name": "Anna Müller"},
    {"email": "tobias@vera.demo",  "password": "demo1234", "role": "employee", "name": "Tobias Weber"},
    {"email": "marie@vera.demo",   "password": "demo1234", "role": "employee", "name": "Marie Schmidt"},
    {"email": "felix@vera.demo",   "password": "demo1234", "role": "employee", "name": "Felix Braun"},
    {"email": "lena@vera.demo",    "password": "demo1234", "role": "employee", "name": "Lena Fischer"},
    {"email": "noah@vera.demo",    "password": "demo1234", "role": "employee", "name": "Noah Wagner"},
    {"email": "sophie@vera.demo",  "password": "demo1234", "role": "employee", "name": "Sophie Becker"},
]

EMPLOYEES_DATA = [
    {"email": "anna@vera.demo",   "first_name": "Anna",   "last_name": "Müller",
     "contract_type": "part_time", "hourly_rate": 15.50, "monthly_hours_limit": 80.0,
     "vacation_days": 30, "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0151-11223344"},
    {"email": "tobias@vera.demo", "first_name": "Tobias", "last_name": "Weber",
     "contract_type": "part_time", "hourly_rate": 16.00, "monthly_hours_limit": 60.0,
     "vacation_days": 30, "qualifications": ["Schulbegleitung", "Pflege"], "phone": "0152-22334455"},
    {"email": "marie@vera.demo",  "first_name": "Marie",  "last_name": "Schmidt",
     "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
     "annual_salary_limit": 6672.0, "vacation_days": 30, "qualifications": ["Schulbegleitung"], "phone": "0153-33445566"},
    {"email": "felix@vera.demo",  "first_name": "Felix",  "last_name": "Braun",
     "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
     "annual_salary_limit": 6672.0, "vacation_days": 30, "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0154-44556677"},
    {"email": "lena@vera.demo",   "first_name": "Lena",   "last_name": "Fischer",
     "contract_type": "minijob", "hourly_rate": 13.50, "monthly_hours_limit": 27.0,
     "annual_salary_limit": 6672.0, "vacation_days": 30, "qualifications": ["Schulbegleitung"], "phone": "0155-55667788"},
    {"email": "noah@vera.demo",   "first_name": "Noah",   "last_name": "Wagner",
     "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
     "annual_salary_limit": 6672.0, "vacation_days": 30, "qualifications": ["Pflege"], "phone": "0156-66778899"},
    {"email": "sophie@vera.demo", "first_name": "Sophie", "last_name": "Becker",
     "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
     "annual_salary_limit": 6672.0, "vacation_days": 30, "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0157-77889900"},
]


async def seed():
    print("🌱 VERA Demo-Seed (Schuljahr 2025/26) ...\n")
    await create_tables()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, delete

        # ── Bestehenden Demo-Tenant bereinigen ────────────────────────────────
        existing = await db.execute(select(Tenant).where(Tenant.slug == "vera-demo"))
        old_tenant = existing.scalar_one_or_none()
        if old_tenant:
            # audit_log.tenant_id hat kein ON DELETE CASCADE → erst explizit löschen.
            # Alle anderen Tabellen haben ON DELETE CASCADE auf tenant_id → werden
            # automatisch mitgelöscht wenn der Tenant gelöscht wird.
            await db.execute(delete(AuditLog).where(AuditLog.tenant_id == old_tenant.id))
            await db.execute(delete(Tenant).where(Tenant.id == old_tenant.id))
            await db.commit()
            print("  ♻️  Alter Demo-Tenant gelöscht\n")

        # Verwaiste Demo-User ohne Tenant bereinigen (z. B. abgebrochener vorheriger Lauf).
        # AuditLog-Einträge dieser User zuerst nullen, da user_id ohne ON DELETE.
        demo_emails = [u["email"] for u in DEMO_USERS]
        orphan_result = await db.execute(
            select(User.id).where(User.email.in_(demo_emails))
        )
        orphan_ids = [row[0] for row in orphan_result.all()]
        if orphan_ids:
            await db.execute(
                delete(AuditLog).where(AuditLog.user_id.in_(orphan_ids))
            )
            await db.execute(delete(User).where(User.id.in_(orphan_ids)))
            await db.commit()

        # ── Tenant ────────────────────────────────────────────────────────────
        tenant = Tenant(
            name="VERA Demo", slug="vera-demo", plan="pro", state="BW",
            settings={"demo_mode": True},
        )
        db.add(tenant)
        await db.flush()
        print(f"  ✓ Tenant '{tenant.name}'")

        # ── Users ─────────────────────────────────────────────────────────────
        users_map: dict[str, User] = {}
        for u in DEMO_USERS:
            user = User(
                tenant_id=tenant.id, email=u["email"],
                hashed_password=hash_password(u["password"]), role=u["role"],
            )
            db.add(user)
            await db.flush()
            users_map[u["email"]] = user
            print(f"  ✓ [{u['role']:8}] {u['name']:20} {u['email']}")

        # ── Employees ─────────────────────────────────────────────────────────
        employees: list[Employee] = []
        for d in EMPLOYEES_DATA:
            emp = Employee(
                tenant_id=tenant.id, user_id=users_map[d["email"]].id,
                first_name=d["first_name"], last_name=d["last_name"],
                email=d["email"], phone=d.get("phone"),
                contract_type=d["contract_type"], hourly_rate=d["hourly_rate"],
                monthly_hours_limit=d.get("monthly_hours_limit"),
                annual_salary_limit=d.get("annual_salary_limit"),
                vacation_days=d["vacation_days"],
                qualifications=d.get("qualifications", []),
                notification_prefs={},
                ical_token=secrets.token_urlsafe(32),
            )
            db.add(emp)
            employees.append(emp)
        await db.flush()
        print(f"\n  ✓ {len(employees)} Mitarbeiter")

        parttimers  = [e for e in employees if e.contract_type == "part_time"]
        minijobbers = [e for e in employees if e.contract_type == "minijob"]

        # ── Schicht-Vorlagen ──────────────────────────────────────────────────
        tpl = {}
        templates_def = [
            ("schule_vormittag", ShiftTemplate(
                tenant_id=tenant.id, name="Schulbegleitung Vormittag",
                weekdays=[0,1,2,3,4], start_time=time(7,45), end_time=time(13,15),
                break_minutes=0, location="Grundschule Musterstadt",
                required_skills=["Schulbegleitung"], color=COLORS["schule_vormittag"],
                valid_from=SCHOOL_YEAR_START, valid_until=SCHOOL_YEAR_END,
            )),
            ("schule_ganztag", ShiftTemplate(
                tenant_id=tenant.id, name="Schulbegleitung Ganztag",
                weekdays=[0,1,2,3,4], start_time=time(7,45), end_time=time(15,30),
                break_minutes=30, location="Grundschule Musterstadt",
                required_skills=["Schulbegleitung"], color=COLORS["schule_ganztag"],
                valid_from=SCHOOL_YEAR_START, valid_until=SCHOOL_YEAR_END,
            )),
            ("assistenz_nachmittag", ShiftTemplate(
                tenant_id=tenant.id, name="Assistenz Nachmittag",
                weekdays=[0,1,2,3,4], start_time=time(14,0), end_time=time(18,0),
                break_minutes=0, location="Zuhause",
                required_skills=[], color=COLORS["assistenz_nachmittag"],
                valid_from=SCHOOL_YEAR_START, valid_until=SCHOOL_YEAR_END,
            )),
            ("assistenz_wochenende", ShiftTemplate(
                tenant_id=tenant.id, name="Assistenz Wochenende",
                weekdays=[5,6], start_time=time(10,0), end_time=time(14,0),
                break_minutes=0, location="Zuhause",
                required_skills=[], color=COLORS["assistenz_wochenende"],
            )),
            ("foerderung", ShiftTemplate(
                tenant_id=tenant.id, name="Förderung / Therapie-Begleitung",
                weekdays=[1,3], start_time=time(15,0), end_time=time(17,0),
                break_minutes=0, location="Therapiezentrum",
                required_skills=["Erste Hilfe"], color=COLORS["foerderung"],
                valid_from=SCHOOL_YEAR_START, valid_until=SCHOOL_YEAR_END,
            )),
        ]
        for key, t in templates_def:
            db.add(t)
            tpl[key] = t
        await db.flush()
        print(f"  ✓ {len(tpl)} Schicht-Vorlagen (mit Farben)")

        # ── Dienste generieren ────────────────────────────────────────────────
        # Für das gesamte Schuljahr Regeltermine anlegen.
        # Für Anzeige sinnvoll: 8 Wochen zurück bis Schuljahresende.
        today = date.today()
        gen_start = max(SCHOOL_YEAR_START, today - timedelta(weeks=8))

        # Modifikations-Kandidaten bestimmen (jeder 15. Schultag = abweichende Zeit)
        modified_dates: set[date] = set()
        d = gen_start
        count = 0
        while d <= SCHOOL_YEAR_END:
            if is_school_day(d):
                count += 1
                if count % 15 == 0:
                    modified_dates.add(d)
            d += timedelta(days=1)

        # Alle Shift-Objekte in einer Liste sammeln, dann bulk-flushen
        shifts: list[Shift] = []
        pt_idx   = 0
        mini_idx = 0

        current = gen_start
        while current <= SCHOOL_YEAR_END:
            wd = current.weekday()
            is_past = current < today

            if is_school_day(current):
                # Schulbegleitung Vormittag – Teilzeit abwechselnd
                pt_emp = parttimers[pt_idx % len(parttimers)]
                is_modified = current in modified_dates
                shifts.append(Shift(
                    tenant_id=tenant.id, template_id=tpl["schule_vormittag"].id,
                    employee_id=pt_emp.id, date=current,
                    start_time=time(8, 0)  if is_modified else time(7, 45),
                    end_time=time(13, 45)  if is_modified else time(13, 15),
                    break_minutes=0, location="Grundschule Musterstadt",
                    status="completed" if is_past else "planned",
                    is_weekend=False, is_sunday=False,
                    notes="⚠️ Abweichende Zeit (Elterngespräch)" if is_modified else None,
                ))
                pt_idx += 1

                # Di + Do: Ganztag-Dienst zusätzlich (anderer MA)
                if wd in (1, 3):
                    mini_emp = minijobbers[mini_idx % len(minijobbers)]
                    shifts.append(Shift(
                        tenant_id=tenant.id, template_id=tpl["schule_ganztag"].id,
                        employee_id=mini_emp.id, date=current,
                        start_time=time(7, 45), end_time=time(15, 30),
                        break_minutes=30, location="Grundschule Musterstadt",
                        status="completed" if is_past else "planned",
                        is_weekend=False, is_sunday=False,
                    ))
                    mini_idx += 1

                # Nachmittag: Minijobber reihum
                mini_emp = minijobbers[mini_idx % len(minijobbers)]
                shifts.append(Shift(
                    tenant_id=tenant.id, template_id=tpl["assistenz_nachmittag"].id,
                    employee_id=mini_emp.id, date=current,
                    start_time=time(14, 0), end_time=time(18, 0),
                    break_minutes=0, location="Zuhause",
                    status="completed" if is_past else "planned",
                    is_weekend=False, is_sunday=False,
                ))
                mini_idx += 1

                # Di + Do: Förderung
                if wd in (1, 3):
                    mini_emp2 = minijobbers[(mini_idx + 2) % len(minijobbers)]
                    shifts.append(Shift(
                        tenant_id=tenant.id, template_id=tpl["foerderung"].id,
                        employee_id=mini_emp2.id, date=current,
                        start_time=time(15, 0), end_time=time(17, 0),
                        break_minutes=0, location="Therapiezentrum",
                        status="completed" if is_past else "planned",
                        is_weekend=False, is_sunday=False,
                    ))

                # 1× pro Woche einen offenen Dienst (Mittwoch, in Zukunft)
                if wd == 2 and not is_past:
                    shifts.append(Shift(
                        tenant_id=tenant.id, template_id=tpl["schule_ganztag"].id,
                        employee_id=None, date=current,
                        start_time=time(7, 45), end_time=time(15, 30),
                        break_minutes=30, location="Grundschule Musterstadt",
                        status="planned", is_weekend=False, is_sunday=False,
                        notes="Vertretung gesucht",
                    ))

            elif wd == 5 and SCHOOL_YEAR_START <= current:
                # Samstag: Wochenend-Assistenz (jede Woche)
                mini_emp = minijobbers[mini_idx % len(minijobbers)]
                shifts.append(Shift(
                    tenant_id=tenant.id, template_id=tpl["assistenz_wochenende"].id,
                    employee_id=mini_emp.id, date=current,
                    start_time=time(10, 0), end_time=time(14, 0),
                    break_minutes=0, location="Zuhause",
                    status="completed" if is_past else "planned",
                    is_weekend=True, is_sunday=False,
                ))
                mini_idx += 1

            elif wd == 6 and SCHOOL_YEAR_START <= current:
                # Sonntag: jede 2. Woche
                week_num = (current - SCHOOL_YEAR_START).days // 7
                if week_num % 2 == 0:
                    mini_emp = minijobbers[mini_idx % len(minijobbers)]
                    shifts.append(Shift(
                        tenant_id=tenant.id, template_id=tpl["assistenz_wochenende"].id,
                        employee_id=mini_emp.id, date=current,
                        start_time=time(10, 0), end_time=time(14, 0),
                        break_minutes=0, location="Zuhause",
                        status="completed" if is_past else "planned",
                        is_weekend=True, is_sunday=True,
                    ))
                    mini_idx += 1

            current += timedelta(days=1)

        # Bulk-Insert: alle Shifts auf einmal hinzufügen (effizienter bei PostgreSQL)
        db.add_all(shifts)
        await db.commit()

        school_days = sum(1 for s in shifts if s.template_id == tpl["schule_vormittag"].id)
        print(f"  ✓ {len(shifts)} Dienste angelegt ({school_days} Schulbegleitung-Tage)")
        print(f"  ✓ {len(modified_dates)} modifizierte Dienste (abweichende Zeiten)")

        print("\n" + "═" * 55)
        print("  VERA Demo bereit! → http://192.168.0.144:31368")
        print("═" * 55)
        print("\n  Alle Accounts – Passwort: demo1234\n")
        print("  ADMIN:      stefan@vera.demo")
        print("  VERWALTER:  lea@vera.demo")
        print("  TEILZEIT:   anna@vera.demo    |  tobias@vera.demo")
        print("  MINIJOB:    marie / felix / lena / noah / sophie @vera.demo")
        print("\n  Diensttypen & Farben:")
        names = {
            "schule_vormittag":     "Schulbegleitung Vormittag",
            "schule_ganztag":       "Schulbegleitung Ganztag",
            "assistenz_nachmittag": "Assistenz Nachmittag",
            "assistenz_wochenende": "Assistenz Wochenende",
            "foerderung":           "Förderung / Therapie",
        }
        for key, color in COLORS.items():
            print(f"    {color}  {names[key]}")
        print("═" * 55 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
