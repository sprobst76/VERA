"""
Demo-Seed für VERA – Schuljahr 2025/26 BW + Beispieldienste.

SQLite:     DATABASE_URL=sqlite+aiosqlite:///./vera.db  python3 seed_demo.py
PostgreSQL: DATABASE_URL=postgresql+asyncpg://vera:secret@localhost:5432/vera  python3 seed_demo.py
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
from app.models.contract_history import ContractHistory
from app.models.holiday_profile import HolidayProfile, VacationPeriod, CustomHoliday

# ── BW Schulferien 2025/26 ────────────────────────────────────────────────────
SCHOOL_HOLIDAYS = [
    (date(2025, 10, 27), date(2025, 10, 30), "Herbstferien"),
    (date(2025, 12, 22), date(2026,  1,  5), "Weihnachten"),
    (date(2026,  3, 30), date(2026,  4, 11), "Ostern"),
    (date(2026,  5, 26), date(2026,  6,  5), "Pfingsten"),
    (date(2026,  7, 30), date(2026,  9, 12), "Sommer"),
]
SCHOOL_YEAR_START = date(2025,  9, 15)
SCHOOL_YEAR_END   = date(2026,  7, 24)

# Gesetzliche Feiertage BW 2025/26
BW_HOLIDAYS_2025_26 = {
    date(2025, 10,  3), date(2025, 11,  1),
    date(2025, 12, 25), date(2025, 12, 26),
    date(2026,  1,  1), date(2026,  1,  6),
    date(2026,  4,  3), date(2026,  4,  6),
    date(2026,  5,  1), date(2026,  5, 14),
    date(2026,  5, 25), date(2026,  6,  4),
    date(2026, 10,  3),
}

# Vollständiges Skip-Set (Ferien + Feiertage)
def _build_skip_set() -> set[date]:
    skip: set[date] = set(BW_HOLIDAYS_2025_26)
    for start, end, _ in SCHOOL_HOLIDAYS:
        d = start
        while d <= end:
            skip.add(d)
            d += timedelta(days=1)
    return skip

SKIP_DATES = _build_skip_set()


def is_school_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in SKIP_DATES and SCHOOL_YEAR_START <= d <= SCHOOL_YEAR_END


def is_working_day(d: date) -> bool:
    """True wenn d im Schuljahr liegt und kein Ferien-/Feiertagsdatum ist."""
    return d not in SKIP_DATES and SCHOOL_YEAR_START <= d <= SCHOOL_YEAR_END


# ── Farben je Diensttyp ───────────────────────────────────────────────────────
COLORS = {
    "schule_vormittag":     "#2563eb",
    "schule_ganztag":       "#7c3aed",
    "assistenz_nachmittag": "#16a34a",
    "assistenz_wochenende": "#d97706",
    "foerderung":           "#0891b2",
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
    {
        "email": "anna@vera.demo", "first_name": "Anna", "last_name": "Müller",
        "contract_type": "part_time", "hourly_rate": 15.50, "weekly_hours": 20.0,
        "monthly_hours_limit": 80.0, "annual_hours_target": 960.0,
        "vacation_days": 30, "vacation_carryover": 5,
        "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0151-11223344",
        "emergency_contact": {"name": "Peter Müller", "phone": "0151-99887766", "relation": "Ehemann"},
        "history": [
            {"valid_from": date(2024, 9, 1), "valid_to": date(2025, 8, 31),
             "contract_type": "part_time", "hourly_rate": 14.50, "weekly_hours": 20.0,
             "annual_hours_target": 960.0, "note": "Vertrag 2024/25"},
        ],
    },
    {
        "email": "tobias@vera.demo", "first_name": "Tobias", "last_name": "Weber",
        "contract_type": "part_time", "hourly_rate": 16.00, "weekly_hours": 15.0,
        "monthly_hours_limit": 60.0, "annual_hours_target": 720.0,
        "vacation_days": 30, "vacation_carryover": 0,
        "qualifications": ["Schulbegleitung", "Pflege"], "phone": "0152-22334455",
        "emergency_contact": {"name": "Sandra Weber", "phone": "0152-88776655", "relation": "Schwester"},
        "history": [],
    },
    {
        "email": "marie@vera.demo", "first_name": "Marie", "last_name": "Schmidt",
        "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
        "annual_salary_limit": 6672.0, "vacation_days": 30, "vacation_carryover": 2,
        "qualifications": ["Schulbegleitung"], "phone": "0153-33445566",
        "emergency_contact": None,
        "history": [],
    },
    {
        "email": "felix@vera.demo", "first_name": "Felix", "last_name": "Braun",
        "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
        "annual_salary_limit": 6672.0, "vacation_days": 30, "vacation_carryover": 0,
        "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0154-44556677",
        "emergency_contact": None,
        "history": [],
    },
    {
        "email": "lena@vera.demo", "first_name": "Lena", "last_name": "Fischer",
        "contract_type": "minijob", "hourly_rate": 13.50, "monthly_hours_limit": 27.0,
        "annual_salary_limit": 6672.0, "vacation_days": 30, "vacation_carryover": 0,
        "qualifications": ["Schulbegleitung"], "phone": "0155-55667788",
        "emergency_contact": None,
        "history": [],
    },
    {
        "email": "noah@vera.demo", "first_name": "Noah", "last_name": "Wagner",
        "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
        "annual_salary_limit": 6672.0, "vacation_days": 30, "vacation_carryover": 0,
        "qualifications": ["Pflege"], "phone": "0156-66778899",
        "emergency_contact": None,
        "history": [],
    },
    {
        "email": "sophie@vera.demo", "first_name": "Sophie", "last_name": "Becker",
        "contract_type": "minijob", "hourly_rate": 13.00, "monthly_hours_limit": 27.0,
        "annual_salary_limit": 6672.0, "vacation_days": 30, "vacation_carryover": 0,
        "qualifications": ["Schulbegleitung", "Erste Hilfe"], "phone": "0157-77889900",
        "emergency_contact": None,
        "history": [],
    },
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
            await db.execute(delete(AuditLog).where(AuditLog.tenant_id == old_tenant.id))
            await db.execute(delete(Tenant).where(Tenant.id == old_tenant.id))
            await db.commit()
            print("  ♻️  Alter Demo-Tenant gelöscht\n")

        # Verwaiste Demo-User bereinigen
        demo_emails = [u["email"] for u in DEMO_USERS]
        orphan_result = await db.execute(select(User.id).where(User.email.in_(demo_emails)))
        orphan_ids = [row[0] for row in orphan_result.all()]
        if orphan_ids:
            await db.execute(delete(AuditLog).where(AuditLog.user_id.in_(orphan_ids)))
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

        # ── Ferienprofil ──────────────────────────────────────────────────────
        profile = HolidayProfile(
            tenant_id=tenant.id,
            name="BW Schuljahr 2025/26",
            state="BW",
            is_active=True,
        )
        db.add(profile)
        await db.flush()

        vacation_colors = {
            "Herbstferien": "#f59e0b",
            "Weihnachten":  "#3b82f6",
            "Ostern":       "#10b981",
            "Pfingsten":    "#8b5cf6",
            "Sommer":       "#ef4444",
        }
        for start, end, name in SCHOOL_HOLIDAYS:
            db.add(VacationPeriod(
                profile_id=profile.id,
                tenant_id=tenant.id,
                name=name,
                start_date=start,
                end_date=end,
                color=vacation_colors.get(name, "#6b7280"),
            ))

        # Bewegliche Feiertage als CustomHolidays (für Demo)
        for hol_date, hol_name in [
            (date(2026, 4, 3),  "Karfreitag"),
            (date(2026, 4, 6),  "Ostermontag"),
            (date(2026, 5, 14), "Christi Himmelfahrt"),
            (date(2026, 6, 4),  "Fronleichnam"),
        ]:
            db.add(CustomHoliday(
                profile_id=profile.id,
                tenant_id=tenant.id,
                date=hol_date,
                name=hol_name,
            ))

        await db.flush()
        print(f"\n  ✓ Ferienprofil 'BW Schuljahr 2025/26' mit {len(SCHOOL_HOLIDAYS)} Ferienperioden")

        # ── Employees + ContractHistory ───────────────────────────────────────
        employees: list[Employee] = []
        for d in EMPLOYEES_DATA:
            emp = Employee(
                tenant_id=tenant.id,
                user_id=users_map[d["email"]].id,
                first_name=d["first_name"], last_name=d["last_name"],
                email=d["email"], phone=d.get("phone"),
                contract_type=d["contract_type"],
                hourly_rate=d["hourly_rate"],
                weekly_hours=d.get("weekly_hours"),
                monthly_hours_limit=d.get("monthly_hours_limit"),
                annual_salary_limit=d.get("annual_salary_limit"),
                annual_hours_target=d.get("annual_hours_target"),
                vacation_days=d["vacation_days"],
                vacation_carryover=d.get("vacation_carryover", 0),
                qualifications=d.get("qualifications", []),
                emergency_contact=d.get("emergency_contact"),
                notification_prefs={
                    "channels": {"email": True, "telegram": False},
                    "events": {
                        "shift_assigned": True, "shift_changed": True,
                        "shift_reminder": True, "absence_approved": True,
                        "absence_rejected": True, "pool_shift_open": True,
                        "minijob_limit_80": True, "minijob_limit_95": True,
                    },
                },
                ical_token=secrets.token_urlsafe(32),
            )
            db.add(emp)
            employees.append(emp)
        await db.flush()

        # ContractHistory: aktueller Vertrag + ggf. Vorgänger
        for idx, d in enumerate(EMPLOYEES_DATA):
            emp = employees[idx]
            # Vorgänger-Einträge
            for h in d.get("history", []):
                db.add(ContractHistory(
                    employee_id=emp.id,
                    tenant_id=tenant.id,
                    valid_from=h["valid_from"],
                    valid_to=h["valid_to"],
                    contract_type=h["contract_type"],
                    hourly_rate=h["hourly_rate"],
                    weekly_hours=h.get("weekly_hours"),
                    annual_hours_target=h.get("annual_hours_target"),
                    note=h.get("note"),
                ))
            # Aktueller Vertrag (valid_to=None = offen)
            db.add(ContractHistory(
                employee_id=emp.id,
                tenant_id=tenant.id,
                valid_from=SCHOOL_YEAR_START,
                valid_to=None,
                contract_type=d["contract_type"],
                hourly_rate=d["hourly_rate"],
                weekly_hours=d.get("weekly_hours"),
                monthly_hours_limit=d.get("monthly_hours_limit"),
                annual_salary_limit=d.get("annual_salary_limit"),
                annual_hours_target=d.get("annual_hours_target"),
                note=f"Vertrag Schuljahr 2025/26",
            ))

        await db.flush()
        print(f"  ✓ {len(employees)} Mitarbeiter (mit Vertragsverlauf, Notfallkontakten)")

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
        print(f"  ✓ {len(tpl)} Schicht-Vorlagen")

        # ── Dienste generieren ────────────────────────────────────────────────
        today     = date.today()
        gen_start = max(SCHOOL_YEAR_START, today - timedelta(weeks=8))

        # Modifikations-Kandidaten (jeder 15. Schultag = abweichende Zeit)
        modified_dates: set[date] = set()
        d = gen_start
        count = 0
        while d <= SCHOOL_YEAR_END:
            if is_school_day(d):
                count += 1
                if count % 15 == 0:
                    modified_dates.add(d)
            d += timedelta(days=1)

        shifts: list[Shift] = []
        pt_idx   = 0
        mini_idx = 0

        current = gen_start
        while current <= SCHOOL_YEAR_END:
            wd      = current.weekday()
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

                # Di + Do: Ganztag-Dienst zusätzlich
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

                # 1× pro Woche offener Dienst (Mittwoch, zukünftig)
                if wd == 2 and not is_past:
                    shifts.append(Shift(
                        tenant_id=tenant.id, template_id=tpl["schule_ganztag"].id,
                        employee_id=None, date=current,
                        start_time=time(7, 45), end_time=time(15, 30),
                        break_minutes=30, location="Grundschule Musterstadt",
                        status="planned", is_weekend=False, is_sunday=False,
                        notes="Vertretung gesucht",
                    ))

            # Wochenende: NUR wenn kein Ferien-/Feiertagsdatum
            elif wd == 5 and SCHOOL_YEAR_START <= current and current not in SKIP_DATES:
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

            elif wd == 6 and SCHOOL_YEAR_START <= current and current not in SKIP_DATES:
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

        db.add_all(shifts)
        await db.commit()

        school_days = sum(1 for s in shifts if s.template_id == tpl["schule_vormittag"].id)
        open_shifts  = sum(1 for s in shifts if s.employee_id is None)
        print(f"  ✓ {len(shifts)} Dienste ({school_days} Schulbegleitung, {open_shifts} offen)")
        print(f"  ✓ {len(modified_dates)} modifizierte Dienste, 0 Dienste in Ferien/Feiertagen")

        print("\n" + "═" * 55)
        print("  VERA Demo bereit! → http://192.168.0.144:31368")
        print("═" * 55)
        print("\n  Alle Accounts – Passwort: demo1234\n")
        print("  ADMIN:      stefan@vera.demo")
        print("  VERWALTER:  lea@vera.demo")
        print("  TEILZEIT:   anna@vera.demo    |  tobias@vera.demo")
        print("  MINIJOB:    marie / felix / lena / noah / sophie @vera.demo")
        print("═" * 55 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
