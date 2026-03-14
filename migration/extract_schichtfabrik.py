#!/usr/bin/env python3
"""
Schichtfabrik → VERA Migration
================================
1. Extrahiert Mitarbeiter, Schichten und Abwesenheiten aus Schichtfabrik
2. Legt Mitarbeiter direkt in VERA an (interaktiv oder mit Defaults)

Verwendung:
  pip install requests
  python extract_schichtfabrik.py

Konfiguration via Umgebungsvariablen (oder direkte Anpassung unten):
  SF_BASE_URL, SF_EMAIL, SF_PASSWORD
  SF_DATE_FROM, SF_DATE_TO
  VERA_URL, VERA_EMAIL, VERA_PASSWORD
"""

import json
import os
import sys
import base64
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Bitte 'requests' installieren: pip install requests")
    sys.exit(1)

# ─── Konfiguration ────────────────────────────────────────────────────────────

SF_BASE_URL = os.getenv("SF_BASE_URL", "https://DEINE-FIRMA.shiftjuggler.com")
SF_EMAIL    = os.getenv("SF_EMAIL",    "deine@email.de")
SF_PASSWORD = os.getenv("SF_PASSWORD", "deinpasswort")

DATE_FROM = os.getenv("SF_DATE_FROM", "2024-01-01")
DATE_TO   = os.getenv("SF_DATE_TO",   date.today().isoformat())

VERA_URL      = os.getenv("VERA_URL",      "https://vera.lab.halbewahrheit21.de")
VERA_EMAIL    = os.getenv("VERA_EMAIL",    "stefan@vera.demo")
VERA_PASSWORD = os.getenv("VERA_PASSWORD", "")

OUTPUT_DIR = Path(__file__).parent / "output"

# ─── Schichtfabrik-Client ─────────────────────────────────────────────────────

class SchichtfabrikClient:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{email}:{password}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        self.session.verify = False

    def _post(self, action: str, params: dict = None) -> dict:
        url = f"{self.base_url}/api/{action}"
        data = params or {"_": "1"}
        try:
            resp = self.session.post(url, data=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            print(f"  HTTP-Fehler bei {action}: {e} → {resp.text[:300]}")
            return {}
        except Exception as e:
            print(f"  Fehler bei {action}: {e}")
            return {}

    def get_employees(self) -> list:
        print("Lade Mitarbeiter aus Schichtfabrik...")
        result = self._post("employee.getList", {
            "withPermissions":   0,
            "withCustomFields":  0,
            "withWorkplaceIdList": 0,
        })
        employees = _extract_list(result, ["employees", "data"])
        print(f"  → {len(employees)} Mitarbeiter gefunden, lade Detaildaten...")

        # hourlyRate, leaveEntitlements etc. nur in getCompleteData
        enriched = []
        for emp in employees:
            emp_id = emp.get("id") or emp.get("userId")
            detail = self._post("employee.getCompleteData", {"id": emp_id})
            if detail and "employee" in detail:
                merged = {**emp, **detail["employee"]}
                # Urlaubstage aus leaveEntitlements (aktuelles Jahr)
                leave = detail["employee"].get("leaveEntitlements", {})
                current_year = str(date.today().year)
                if current_year in leave:
                    merged["_vacation_days"] = leave[current_year].get("days", 30)
                enriched.append(merged)
            else:
                enriched.append(emp)

        print(f"  → {len(enriched)} Mitarbeiter mit Detaildaten")
        return enriched

    def get_shifts(self, date_from: str, date_to: str) -> list:
        print(f"Lade Schichten ({date_from} – {date_to})...")
        all_shifts = []
        start = datetime.strptime(date_from, "%Y-%m-%d").date()
        end   = datetime.strptime(date_to,   "%Y-%m-%d").date()
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=90), end)
            result = self._post("shift.getList", {
                "periodStart":      current.isoformat(),
                "periodEnd":        chunk_end.isoformat(),
                "withEmployeeData": 1,
                "withWorkplaceData":1,
            })
            chunk = _extract_list(result, ["shifts", "data"])
            print(f"  {current} – {chunk_end}: {len(chunk)} Schichten")
            all_shifts.extend(chunk)
            current = chunk_end + timedelta(days=1)
        print(f"  → {len(all_shifts)} Schichten gesamt")
        return all_shifts

    def get_absences(self, date_from: str, date_to: str) -> list:
        print(f"Lade Abwesenheiten ({date_from} – {date_to})...")
        result = self._post("absence.getList", {
            "startDateBegin":       date_from,
            "startDateEnd":         date_to,
            "withEmployeeData":     1,
            "withoutStatusFilter":  0,
            "withRejectedVacations":0,
            "withCanceledAbsences": 0,
        })
        absences = _extract_list(result, ["absences", "data"])
        print(f"  → {len(absences)} Abwesenheiten")
        return absences

    def get_absence_types(self) -> list:
        print("Lade Abwesenheitstypen...")
        result = self._post("absenceType.getList")
        types = _extract_list(result, ["absenceTypes", "data"])
        print(f"  → {len(types)} Typen")
        return types


# ─── VERA-Client ──────────────────────────────────────────────────────────────

class VeraClient:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.token = None
        self._login(email, password)

    def _login(self, email: str, password: str):
        resp = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"VERA Login fehlgeschlagen: {resp.status_code} {resp.text[:200]}")
            sys.exit(1)
        self.token = resp.json()["access_token"]
        print(f"  VERA Login erfolgreich ({email})")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get_existing_employees(self) -> list:
        resp = requests.get(
            f"{self.base_url}/employees",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def create_employee(self, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/employees",
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _extract_list(result: dict, keys: list) -> list:
    for k in keys:
        val = result.get(k)
        if val is not None:
            return list(val.values()) if isinstance(val, dict) else val
    return []


def save_json(data, filename: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Gespeichert: {path} ({path.stat().st_size/1024:.1f} KB)")


def parse_employee_name(e: dict) -> tuple[str, str]:
    first = e.get("firstName") or e.get("firstname") or ""
    last  = e.get("lastName")  or e.get("lastname")  or ""
    if not first and not last:
        parts = (e.get("name") or "").split(" ", 1)
        first = parts[0]
        last  = parts[1] if len(parts) > 1 else ""
    return first.strip(), last.strip()


def derive_contract(emp: dict) -> dict:
    """Leitet Vertragsdaten aus Schichtfabrik-Feldern ab."""
    hourly_rate = float(emp.get("hourlyRate") or 0.0)

    # Vertragstyp aus SF-Flags ableiten
    if emp.get("isFreelancer"):
        contract_type = "minijob"       # Freiberufler → Minijob als Näherung
    elif emp.get("isTemporaryEmployee"):
        contract_type = "part_time"
    elif hourly_rate > 0:
        # Grobe Heuristik: Minijob-Grenze 2025 = 556€/Monat
        # Bei >30h/Woche → full_time, sonst part_time
        contract_type = "part_time"     # konservativ; kann in VERA angepasst werden
    else:
        contract_type = "minijob"

    vacation_days = emp.get("_vacation_days", 30)

    return {
        "contract_type": contract_type,
        "hourly_rate":   hourly_rate,
        "weekly_hours":  None,          # SF speichert keine Wochenstunden
        "vacation_days": int(vacation_days) if vacation_days else 30,
    }


# ─── Import-Logik ─────────────────────────────────────────────────────────────

def import_employees_to_vera(sf_employees: list, vera: VeraClient) -> tuple[dict, list]:
    """
    Legt Mitarbeiter in VERA an. Vertragsdaten direkt aus Schichtfabrik.
    Gibt (sf_id → vera_id Mapping, Liste angelegter Mitarbeiter) zurück.
    """
    print("\nLade bestehende VERA-Mitarbeiter...")
    existing = vera.get_existing_employees()
    existing_emails = {(e.get("email") or "").lower() for e in existing}
    print(f"  {len(existing)} Mitarbeiter bereits in VERA")

    sf_id_to_vera_id = {}
    created = []
    skipped = []

    print(f"\n{'─'*50}")
    print(f"Importiere {len(sf_employees)} Mitarbeiter in VERA...")

    for emp in sf_employees:
        sf_id = str(emp.get("id") or emp.get("userId") or "")
        first_name, last_name = parse_employee_name(emp)
        email = (emp.get("email") or "").strip().lower()
        phone = emp.get("phone") or emp.get("mobilePhone") or ""
        full_name = f"{first_name} {last_name}".strip()

        if email and email in existing_emails:
            print(f"  ⏭  {full_name} ({email}) – bereits in VERA")
            skipped.append(full_name)
            continue

        if not first_name or not last_name:
            print(f"  ⚠  Unvollständiger Name '{full_name}' – übersprungen")
            skipped.append(full_name)
            continue

        contract = derive_contract(emp)

        payload = {
            "first_name":    first_name,
            "last_name":     last_name,
            "email":         email or None,
            "phone":         phone or None,
            "contract_type": contract["contract_type"],
            "hourly_rate":   contract["hourly_rate"],
            "weekly_hours":  contract["weekly_hours"],
            "vacation_days": contract["vacation_days"],
            "qualifications": [],
        }

        try:
            result = vera.create_employee(payload)
            vera_id = result.get("id")
            sf_id_to_vera_id[sf_id] = vera_id
            created.append({"name": full_name, "vera_id": vera_id, "sf_id": sf_id,
                            "hourly_rate": contract["hourly_rate"],
                            "contract_type": contract["contract_type"]})
            print(f"  ✓  {full_name} – {contract['contract_type']}, "
                  f"{contract['hourly_rate']:.2f}€/h → VERA-ID {vera_id}")
        except RuntimeError as e:
            print(f"  ✗  {full_name} – Fehler: {e}")
            skipped.append(full_name)

    print(f"\n  Erstellt: {len(created)} | Übersprungen: {len(skipped)}")
    return sf_id_to_vera_id, created


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if "DEINE-FIRMA" in SF_BASE_URL:
        print("FEHLER: Bitte Konfiguration anpassen (SF_BASE_URL, SF_EMAIL, SF_PASSWORD)")
        print()
        print("Umgebungsvariablen setzen:")
        print("  export SF_BASE_URL='https://meine-firma.shiftjuggler.com'")
        print("  export SF_EMAIL='admin@firma.de'")
        print("  export SF_PASSWORD='passwort'")
        print("  export SF_DATE_FROM='2024-01-01'")
        print()
        print("Für VERA-Import zusätzlich:")
        print("  export VERA_URL='https://vera.lab.halbewahrheit21.de'")
        print("  export VERA_EMAIL='stefan@clarasteam.de'")
        print("  export VERA_PASSWORD='...'")
        sys.exit(1)

    print("=" * 60)
    print("Schichtfabrik → VERA Migration")
    print(f"  Schichtfabrik: {SF_BASE_URL}")
    print(f"  VERA:          {VERA_URL}")
    print(f"  Zeitraum:      {DATE_FROM} – {DATE_TO}")
    print("=" * 60)

    # ── 1. Schichtfabrik: Daten laden ─────────────────────────────────────────
    sf = SchichtfabrikClient(SF_BASE_URL, SF_EMAIL, SF_PASSWORD)

    employees     = sf.get_employees()
    shifts        = sf.get_shifts(DATE_FROM, DATE_TO)
    absences      = sf.get_absences(DATE_FROM, DATE_TO)
    absence_types = sf.get_absence_types()

    # Nur aktive Mitarbeiter importieren (inaktive als Hinweis speichern)
    active_employees   = [e for e in employees if e.get("isActive", True)]
    inactive_employees = [e for e in employees if not e.get("isActive", True)]
    print(f"\n  {len(active_employees)} aktive, {len(inactive_employees)} inaktive Mitarbeiter")

    # Rohdaten sichern
    print("\nSpeichere Rohdaten...")
    save_json(employees,     "raw_employees.json")
    save_json(shifts,        "raw_shifts.json")
    save_json(absences,      "raw_absences.json")
    save_json(absence_types, "raw_absence_types.json")

    # ── 2. VERA: Mitarbeiter anlegen ──────────────────────────────────────────
    if not VERA_PASSWORD:
        print("\nVERA_PASSWORD nicht gesetzt – überspringe VERA-Import.")
        print("Setze VERA_PASSWORD und starte erneut für den automatischen Import.")
        return

    print(f"\n{'─'*50}")
    print("Verbinde mit VERA...")
    vera = VeraClient(VERA_URL, VERA_EMAIL, VERA_PASSWORD)

    id_mapping, created = import_employees_to_vera(active_employees, vera)

    # Mapping speichern (wird für Schichten-Import benötigt)
    save_json(id_mapping, "sf_to_vera_id_mapping.json")
    save_json(created,    "created_employees.json")

    # ── 3. Zusammenfassung ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("FERTIG")
    print(f"  Mitarbeiter angelegt:  {len(created)}")
    print(f"  Schichten extrahiert:  {len(shifts)}")
    print(f"  Abwesenheiten:         {len(absences)}")
    print()
    print("Gespeicherte Dateien:")
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")
    print()
    if inactive_employees:
        print(f"Hinweis: {len(inactive_employees)} inaktive Mitarbeiter wurden NICHT importiert.")
        print("  → raw_employees.json enthält alle (inkl. inaktive) zur Referenz.")
    print("=" * 60)


if __name__ == "__main__":
    main()
