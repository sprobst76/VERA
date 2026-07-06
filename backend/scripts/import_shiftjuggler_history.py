#!/usr/bin/env python3
"""
Shiftjuggler-Historie -> VERA: einmaliger Bulk-Import (Schichten + Abwesenheiten)

Bewusst KEIN Aufruf der Live-REST-API: POST /shifts und PUT /absences/{id}
(status=approved/rejected) loesen unbedingt Telegram/E-Mail/Push-Benachrichtigungen
und Webhook-Events aus. Bei ~1200 historischen Schichten und ~85 Abwesenheiten seit
2022 waere das massives Spam fuer echte Mitarbeiter. Dieses Skript schreibt direkt
ueber die ORM-Modelle im laufenden App-Kontext (compliance-Flags + Audit-Log werden
repliziert, notify_*/dispatch_event werden NICHT aufgerufen).

Laeuft INNERHALB des vera-api-Containers (braucht app-Package + DB-Zugriff):

    docker exec -e SJ_PASS=... -e VERA_TENANT_SLUG=clarasteam \\
        vera-vera-api-1 python3 /app/scripts/import_shiftjuggler_history.py --dry-run

Reihenfolge: erst --dry-run pruefen, dann ohne Flag fuer den echten Import.
Idempotent: bereits vorhandene Schichten/Abwesenheiten werden uebersprungen,
mehrfaches Ausfuehren ist sicher.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.shift import Shift  # noqa: E402
from app.models.absence import EmployeeAbsence  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import audit_service  # noqa: E402
from app.services.compliance_service import ComplianceService  # noqa: E402
from app.api.v1.shifts import _set_weekend_flags  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")

# ── Shiftjuggler-Konfiguration ─────────────────────────────────────────────────

_env_file = Path("/app/.env.shiftjuggler")
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

SJ_BASE = os.getenv("SJ_BASE", "")
SJ_USER = os.getenv("SJ_USER", "")
SJ_PASS = os.getenv("SJ_PASS", "")
TENANT_SLUG = os.getenv("VERA_TENANT_SLUG", "clarasteam")

ABSENCE_TYPE_MAP = {"vacation": "vacation", "illness": "sick"}
ABSENCE_STATUS_MAP = {"published": "approved", "rejected": "rejected"}
# "canceled" wird bewusst uebersprungen -- ist nie tatsaechlich passiert.


def sj_post(endpoint: str, body: dict) -> dict | list:
    r = httpx.post(f"{SJ_BASE}{endpoint}", auth=(SJ_USER, SJ_PASS), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _as_list(result, keys) -> list:
    if isinstance(result, list):
        return result
    for k in keys:
        v = result.get(k)
        if v is not None:
            return list(v.values()) if isinstance(v, dict) else v
    return []


def fetch_sj_employees() -> list[dict]:
    result = sj_post("/api/employee.getList", {
        "withPermissions": 0, "withCustomFields": 0, "withWorkplaceIdList": 0,
    })
    return _as_list(result, ["employees", "data"])


def fetch_sj_shifts(date_from: date, date_to: date) -> list[dict]:
    all_shifts = []
    current = date_from
    while current <= date_to:
        chunk_end = min(date(current.year, 12, 31), date_to)
        raw = sj_post("/api/shift.getList", {
            "periodStart": current.isoformat(), "periodEnd": chunk_end.isoformat(),
            "withEmployeeData": 1, "withWorkplaceData": 1,
        })
        all_shifts.extend(_as_list(raw, ["shifts", "data"]))
        current = date(chunk_end.year + 1, 1, 1)
    return all_shifts


def fetch_sj_absences(date_from: date, date_to: date) -> list[dict]:
    raw = sj_post("/api/absence.getList", {
        "startDateBegin": date_from.isoformat(), "startDateEnd": date_to.isoformat(),
        "withEmployeeData": 1, "withoutStatusFilter": 1,
        "withRejectedVacations": 0, "withCanceledAbsences": 0,
    })
    return _as_list(raw, ["absences", "data"])


# ── Mitarbeiter-Matching ────────────────────────────────────────────────────────

def build_employee_mapping(sj_employees: list[dict], vera_employees: list[Employee]) -> dict[str, Employee]:
    """sj_id (str) -> VERA Employee. Admin-Accounts ausgeschlossen, Duplikate
    (z.B. zwei 'Melanie Britsch'-Eintraege durch fruehere Vertragsumstellung ohne
    ContractHistory) werden auf den aktiven VERA-Eintrag aufgeloest."""
    by_name: dict[tuple[str, str], list[Employee]] = {}
    for e in vera_employees:
        key = (e.first_name.strip().lower(), e.last_name.strip().lower())
        by_name.setdefault(key, []).append(e)

    mapping: dict[str, Employee] = {}
    for emp in sj_employees:
        if emp.get("isAdmin"):
            continue  # Familien-/Admin-Accounts, keine echten Beschaeftigten
        sj_id = str(emp.get("id"))
        first = (emp.get("firstname") or emp.get("firstName") or "").strip().lower()
        last = (emp.get("lastname") or emp.get("lastName") or "").strip().lower()
        candidates = by_name.get((first, last), [])
        if not candidates:
            print(f"  [WARN] Kein VERA-Match fuer SJ-Mitarbeiter '{emp.get('firstname')} {emp.get('lastname')}' (id={sj_id})")
            continue
        active = [c for c in candidates if c.is_active]
        chosen = active[0] if active else candidates[0]
        if len(candidates) > 1:
            print(f"  [INFO] Mehrere VERA-Eintraege fuer '{emp.get('firstname')} {emp.get('lastname')}' "
                  f"-> nehme aktiven ({chosen.id})")
        mapping[sj_id] = chosen
    return mapping


# ── Schichten ────────────────────────────────────────────────────────────────────

async def import_shifts(db, tenant: Tenant, admin_user_id, emp_map: dict[str, Employee],
                         sj_shifts: list[dict], dry_run: bool) -> Counter:
    stats = Counter()

    existing_result = await db.execute(select(Shift.employee_id, Shift.date, Shift.start_time)
                                        .where(Shift.tenant_id == tenant.id))
    existing_keys = {(str(r[0]), r[1], r[2]) for r in existing_result.all()}

    today = date.today()

    for s in sj_shifts:
        assigned = s.get("assignedEmployees") or []
        if not assigned:
            stats["no_employee_assigned"] += 1
            continue
        sj_emp_id = str(assigned[0]["id"])
        emp = emp_map.get(sj_emp_id)
        if emp is None:
            stats["no_vera_match"] += 1
            continue

        start_ts, end_ts = s.get("startTimestamp"), s.get("endTimestamp")
        if not start_ts or not end_ts:
            stats["missing_timestamps"] += 1
            continue

        start_dt = datetime.fromtimestamp(start_ts, tz=TZ)
        end_dt = datetime.fromtimestamp(end_ts, tz=TZ)
        shift_date = start_dt.date()
        start_time = start_dt.time().replace(second=0, microsecond=0)
        end_time = end_dt.time().replace(second=0, microsecond=0)

        key = (str(emp.id), shift_date, start_time)
        if key in existing_keys:
            stats["duplicate_skipped"] += 1
            continue

        notes = (s.get("information") or "").strip()
        if not notes:
            notes = (s.get("workplace") or {}).get("name", "") or ""

        stats["would_create" if dry_run else "created"] += 1
        if dry_run:
            existing_keys.add(key)
            continue

        shift = Shift(
            tenant_id=tenant.id,
            employee_id=emp.id,
            date=shift_date,
            start_time=start_time,
            end_time=end_time,
            break_minutes=int(s.get("breakTime", 0) or 0),
            notes=notes or None,
            status="completed" if shift_date < today else "planned",
        )
        _set_weekend_flags(shift)
        db.add(shift)
        await db.flush()
        await audit_service.write(
            db, tenant_id=tenant.id, user_id=admin_user_id,
            entity_type="shift", entity_id=shift.id, action="create",
            new_values={"date": str(shift_date), "start_time": str(start_time),
                        "end_time": str(end_time), "employee_id": str(emp.id),
                        "source": "shiftjuggler_history_import"},
        )
        existing_keys.add(key)

        try:
            svc = ComplianceService(db)
            cr = await svc.check_shift(shift, emp)
            shift.rest_period_ok = not any("Ruhezeit" in v for v in cr.violations)
            shift.break_ok = not any("Pause" in v for v in cr.violations)
            shift.minijob_limit_ok = not any("Minijob" in v for v in cr.violations)
        except Exception as e:
            print(f"  [WARN] Compliance-Check fehlgeschlagen fuer Shift {shift.id}: {e}")

        if stats["created"] % 100 == 0:
            await db.commit()
            print(f"  ... {stats['created']} Schichten committed")

    if not dry_run:
        await db.commit()
    return stats


# ── Abwesenheiten ────────────────────────────────────────────────────────────────

async def import_absences(db, tenant: Tenant, admin_user_id, emp_map: dict[str, Employee],
                           sj_absences: list[dict], dry_run: bool) -> Counter:
    stats = Counter()

    existing_result = await db.execute(
        select(EmployeeAbsence.employee_id, EmployeeAbsence.type,
               EmployeeAbsence.start_date, EmployeeAbsence.end_date)
        .where(EmployeeAbsence.tenant_id == tenant.id)
    )
    existing_keys = {(str(r[0]), r[1], r[2], r[3]) for r in existing_result.all()}

    for a in sj_absences:
        sj_status = a.get("status")
        vera_status = ABSENCE_STATUS_MAP.get(sj_status)
        if vera_status is None:
            stats[f"skipped_status_{sj_status}"] += 1
            continue

        sj_emp_id = str(a.get("userID") or (a.get("employee") or {}).get("id") or "")
        emp = emp_map.get(sj_emp_id)
        if emp is None:
            stats["no_vera_match"] += 1
            continue

        sj_type = a.get("absenceTypeBase") or a.get("absenceType")
        vera_type = ABSENCE_TYPE_MAP.get(sj_type, "other")

        start_ts, end_ts = a.get("startTimestamp"), a.get("endTimestamp")
        if not start_ts or not end_ts:
            stats["missing_timestamps"] += 1
            continue
        start_date = datetime.fromtimestamp(start_ts, tz=TZ).date()
        end_date = (datetime.fromtimestamp(end_ts, tz=TZ) - timedelta(seconds=1)).date()

        key = (str(emp.id), vera_type, start_date, end_date)
        if key in existing_keys:
            stats["duplicate_skipped"] += 1
            continue

        counts_as = (a.get("countsAs") or {})
        days_count = round(sum(float(v) for v in counts_as.values()), 1) if counts_as else None

        stats["would_create" if dry_run else "created"] += 1
        if dry_run:
            existing_keys.add(key)
            continue

        absence = EmployeeAbsence(
            tenant_id=tenant.id,
            employee_id=emp.id,
            type=vera_type,
            start_date=start_date,
            end_date=end_date,
            days_count=days_count,
            status=vera_status,
            notes="Import aus Shiftjuggler-Historie",
            approved_by=admin_user_id if vera_status in ("approved", "rejected") else None,
        )
        db.add(absence)
        await db.flush()
        existing_keys.add(key)

        # Ueberlappende Schichten stornieren (repliziert update_absence-Logik,
        # ohne Benachrichtigungen/Webhooks)
        if vera_status == "approved":
            overlap_result = await db.execute(
                select(Shift).where(
                    Shift.employee_id == emp.id,
                    Shift.tenant_id == tenant.id,
                    Shift.date >= start_date,
                    Shift.date <= end_date,
                    Shift.status.not_in(["cancelled", "cancelled_absence"]),
                )
            )
            for shift in overlap_result.scalars().all():
                shift.status = "cancelled_absence"

        await audit_service.write(
            db, tenant_id=tenant.id, user_id=admin_user_id,
            entity_type="absence", entity_id=absence.id, action="create",
            new_values={"type": vera_type, "start_date": str(start_date),
                        "end_date": str(end_date), "status": vera_status,
                        "employee_id": str(emp.id),
                        "source": "shiftjuggler_history_import"},
        )

    if not dry_run:
        await db.commit()
    return stats


# ── Main ─────────────────────────────────────────────────────────────────────────

async def main(date_from: date, date_to: date, dry_run: bool) -> None:
    if not SJ_PASS:
        print("FEHLER: SJ_PASS nicht gesetzt.")
        sys.exit(1)

    print("=" * 70)
    print(f"{'[DRY RUN] ' if dry_run else ''}Shiftjuggler-Historie -> VERA")
    print(f"  Zeitraum: {date_from} .. {date_to}")
    print(f"  Tenant:   {TENANT_SLUG}")
    print("=" * 70)

    async with AsyncSessionLocal() as db:
        tenant_result = await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            print(f"FEHLER: Tenant '{TENANT_SLUG}' nicht gefunden.")
            sys.exit(1)

        admin_result = await db.execute(
            select(User).where(User.tenant_id == tenant.id, User.role == "admin")
            .order_by(User.created_at)
        )
        admin_user = admin_result.scalars().first()
        if admin_user is None:
            print("FEHLER: Kein Admin-User im Tenant gefunden.")
            sys.exit(1)
        print(f"  Audit-Attribution: {admin_user.email} ({admin_user.id})\n")

        vera_emp_result = await db.execute(select(Employee).where(Employee.tenant_id == tenant.id))
        vera_employees = list(vera_emp_result.scalars().all())

        print("Lade Shiftjuggler-Mitarbeiter...")
        sj_employees = fetch_sj_employees()
        emp_map = build_employee_mapping(sj_employees, vera_employees)
        print(f"  {len(emp_map)}/{len([e for e in sj_employees if not e.get('isAdmin')])} "
              f"nicht-Admin-Mitarbeiter gematcht\n")

        print(f"Lade Shiftjuggler-Schichten ({date_from} .. {date_to})...")
        sj_shifts = fetch_sj_shifts(date_from, date_to)
        print(f"  {len(sj_shifts)} Schichten geladen\n")

        print("Importiere Schichten...")
        shift_stats = await import_shifts(db, tenant, admin_user.id, emp_map, sj_shifts, dry_run)
        for k, v in shift_stats.items():
            print(f"  {k}: {v}")

        print(f"\nLade Shiftjuggler-Abwesenheiten ({date_from} .. {date_to})...")
        sj_absences = fetch_sj_absences(date_from, date_to)
        print(f"  {len(sj_absences)} Abwesenheiten geladen\n")

        print("Importiere Abwesenheiten...")
        absence_stats = await import_absences(db, tenant, admin_user.id, emp_map, sj_absences, dry_run)
        for k, v in absence_stats.items():
            print(f"  {k}: {v}")

    print("\n" + "=" * 70)
    print("FERTIG (DRY RUN, nichts geschrieben)" if dry_run else "FERTIG (geschrieben)")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shiftjuggler-Historie -> VERA Bulk-Import")
    parser.add_argument("--from", dest="from_date", default="2022-01-01", metavar="YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=date.today().isoformat(), metavar="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(main(
        date.fromisoformat(args.from_date),
        date.fromisoformat(args.to_date),
        args.dry_run,
    ))
