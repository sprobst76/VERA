# VERA – Systemarchitektur

Stand: 2026-03-14

---

## Überblick

VERA ist ein mandantenfähiges Schichtplanungs- und Abrechnungssystem für den
Arbeitgebermodell-Bereich (PAB – Persönliches Budget). Es verbindet eine FastAPI-Backend-
API mit einem Next.js-Frontend und bietet vollständige Arbeitsrechtsprüfungen (ArbZG),
Lohnberechnung mit gesetzlichen Zuschlägen (§3b EStG) und Benachrichtigungen über
mehrere Kanäle.

```
┌─────────────────────────────────────────────────────────────────┐
│                          Internet                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS (Cloudflare DNS)
                  ┌────────▼────────┐
                  │    Traefik      │  TLS-Termination, Rate-Limiting
                  └──┬──────────┬──┘
                     │          │
          ┌──────────▼──┐  ┌────▼──────────┐
          │  Next.js 14 │  │  FastAPI      │
          │  (Frontend) │  │  (Backend)    │
          │  Port 3000  │  │  Port 8000    │
          └─────────────┘  └──────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
     ┌────────▼───────┐  ┌────────▼──────┐  ┌────────▼───────┐
     │  PostgreSQL 16  │  │   Redis 7     │  │  Celery Worker │
     │  (Primärdaten)  │  │  (Cache/MQ)  │  │  + Beat        │
     └────────────────┘  └───────────────┘  └────────────────┘
```

---

## Tech Stack

| Schicht | Technologie | Version |
|---------|-------------|---------|
| API | FastAPI + Uvicorn | 0.115 / 0.32 |
| ORM | SQLAlchemy (async) | 2.0 |
| Datenbank | PostgreSQL | 16 |
| Migrationen | Alembic | 1.14 |
| Task Queue | Celery + Redis | 5.4 / 7 |
| Frontend | Next.js (App Router) | 14.2 |
| UI-Bibliothek | Tailwind CSS + shadcn/ui | 3.4 |
| State | Zustand + TanStack Query | 5 / 5.6 |
| Auth | JWT + Refresh Tokens (jose) | – |
| CI/CD | GitHub Actions → GHCR → SSH | – |
| Reverse Proxy | Traefik | v3 |

---

## Mandantenfähigkeit (Multi-Tenancy)

Jeder Datensatz gehört zu einem **Tenant** (Arbeitgeber-Haushalt). Die Isolation erfolgt
durch `tenant_id`-Spalten auf allen Tabellen und durch den JWT-Kontext:

```python
# Jede Query filtert implizit auf den eigenen Tenant
select(Employee).where(Employee.tenant_id == current_user.tenant_id)
```

Ein Tenant hat:
- Eigene Users (admin/manager/employee)
- Eigene Mitarbeiter, Schichten, Abwesenheiten, Abrechnung
- Eigenes Holiday-Profil (Ferienzeiten, Feiertage)
- Eigene Vertragstypen und Benachrichtigungseinstellungen

**SuperAdmin** ist tenant-unabhängig (eigene `super_admins`-Tabelle, JWT-Typ `"superadmin"`).

---

## Datenbankmodell (Kernentitäten)

```
Tenant
  └── User (admin | manager | employee)
        └── Employee ──────────────────────────────────────────────┐
              ├── ContractHistory (SCD Type 2)                      │
              │     valid_from / valid_to / hourly_rate / ...       │
              │     contract_type_id? ──────────────────────────────┤
              ├── EmployeeContractTypeMembership (SCD Type 2)       │
              │     valid_from / valid_to / contract_type_id        │
              ├── Shift (planned | confirmed | completed | cancelled)│
              ├── EmployeeAbsence (vacation | sick | unpaid | ...)  │
              ├── PayrollEntry (draft | approved | paid)            │
              └── PushSubscription                                  │
                                                                    │
ContractType ───────────────────────────────────────────────────────┘
  └── ContractTypeHistory (SCD Type 2)
        valid_from / valid_to / hourly_rate / ...
```

### SCD Type 2 überall

VERA verwendet das Slowly-Changing-Dimension-Muster (Typ 2) für alle historisch
relevanten Daten:

- **ContractHistory**: Welche Konditionen galten für welchen Mitarbeiter wann?
- **ContractTypeHistory**: Wann haben sich die Konditionen eines Vertragstyps geändert?
- **EmployeeContractTypeMembership**: Wann war ein Mitarbeiter Mitglied in welchem Vertragstyp?

Schema: `valid_from DATE NOT NULL, valid_to DATE NULL` – `valid_to = NULL` bedeutet "aktuell gültig".

---

## Authentifizierung & Autorisierung

```
POST /auth/login → { access_token (15min), refresh_token (7d) }
POST /auth/refresh → neuer Access Token
```

**Dependency Injection** in FastAPI:
```python
CurrentUser   # Jeder eingeloggte User
AdminUser     # role IN ('admin')
ManagerOrAdmin # role IN ('manager', 'admin')
```

**RBAC auf Datensatz-Ebene:**
- `GET /employees` → Admin/Manager: `EmployeeOut` (inkl. Gehalt); Employee: `EmployeePublicOut`
- Schichten, Abwesenheiten, Payroll: Mitarbeiter sieht nur eigene Daten
- Compliance: Mitarbeiter sieht nur eigene Verstöße

---

## Vertragsverlauf-System (Contract History)

Das Herzstück der Lohnabrechnung. Drei getrennte Historien-Ebenen:

```
┌─────────────────────────────────────────────────────────┐
│ ContractType "Standard Minijob"                         │
│   └── ContractTypeHistory                               │
│         2024-01-01 → 2025-01-31: 12.41 €/h             │
│         2025-02-01 → heute:      13.00 €/h             │
└─────────────────────────────────────────────────────────┘
         ↓ Mitgliedschaft (Abo)
┌─────────────────────────────────────────────────────────┐
│ Employee "Melanie Britsch"                              │
│   └── EmployeeContractTypeMembership                    │
│         2024-04-01 → heute: Standard Minijob            │
└─────────────────────────────────────────────────────────┘
         ↓ Konditionen-Snapshot (für Payroll)
┌─────────────────────────────────────────────────────────┐
│ ContractHistory (Mitarbeiter-Ebene)                     │
│   2024-04-01 → 2025-01-31: 12.41 €/h (Quelle: Typ)    │
│   2025-02-01 → 2026-01-31: 13.00 €/h (Quelle: Typ)    │
│   2026-02-01 → heute:      13.50 €/h (Quelle: Typ)    │
└─────────────────────────────────────────────────────────┘
```

**Payroll-Logik:** Für jeden Abrechnungsmonat wird via `_get_contract_at(employee_id, month_start)`
der passende ContractHistory-Eintrag gesucht. Bei Satzwechsel innerhalb des Monats splittelt
`_get_contracts_for_month()` in mehrere `wage_detail`-Perioden.

---

## Benachrichtigungssystem

```python
NotificationService.dispatch(
    db=db,
    employee_id=...,
    event="shift_assigned",     # oder absence_approved, etc.
    message="...",
    data={...},
)
```

Kanäle: Telegram, SendGrid (E-Mail), Web Push (VAPID).
Quiet Hours werden in `Europe/Berlin` ausgewertet.
Graceful Degradation: kein Token konfiguriert → `(False, "nicht konfiguriert")`.

---

## Abrechnung (Payroll)

1. `POST /payroll/calculate/{employee_id}?month=YYYY-MM` → Berechnet alle bestätigten Schichten
2. Zuschläge nach §3b EStG: Früh 12.5%, Spät 12.5%, Nacht 25%, Sa 25%, So 50%, Feiertag 125%
3. Ist-Zeiten: Wenn `time_correction_status = "confirmed"`, werden `actual_start/end` verwendet
4. Status-Workflow: `draft` → `approved` → `paid`
5. PDF-Lohnzettel via reportlab (`GET /payroll/{id}/pdf`)

---

## CI/CD Pipeline

```
git push → GitHub Actions
  ├── Build Backend Image (Dockerfile.backend) → GHCR
  ├── Build Frontend Image (Dockerfile.frontend) → GHCR
  └── Deploy:
        SSH → VPS
        docker pull latest
        docker compose up -d
        alembic upgrade head
```

Layer-Caching (`type=gha`) reduziert Build-Zeit von ~8 min auf ~50 s ab dem 2. Push.

---

## Deployment-Struktur (Produktion)

```
/srv/vera/deploy/
  ├── docker-compose.yml      # Produkions-Compose
  ├── .env                    # Secrets (nicht im Git)
  └── traefik/
        └── traefik.yml       # TLS, Rate Limiting
```

Services: `vera-api`, `vera-frontend`, `vera-db` (PostgreSQL), `vera-redis`,
`vera-celery` (Worker), `vera-celery-beat` (Scheduler).

Domain: `vera.lab.halbewahrheit21.de` (Cloudflare DNS → Traefik → Container)

---

## Alembic-Migrationskette

```
0001 (initial)
  └── b7c8d9e0f1a2 (shift_types)
        └── c2d3e4f5a6b1 (contract_types + contract_history)
              └── d3e4f5a6b7c8 (shift_type_id in recurring_shifts)
                    └── e3f4a5b6c7d8 (employee_fields: weekly_hours, ...)
                          └── f5a6b7c8d9e0 (employee_availability_prefs)
                                └── a0b1c2d3e4f5 (auth_tokens: invite + reset)
                                      └── g1h2i3j4k5l6 (employee start_date)
                                            └── h2i3j4k5l6m7 (contract_type_history)
                                                  └── i3j4k5l6m7n8 (employee_contract_type_memberships)
```

HEAD: `i3j4k5l6m7n8` (10 Revisionen)

---

## Testarchitektur

**Backend:** pytest mit asyncio, SQLite (aiosqlite) als In-Memory-DB.
```
backend/tests/
  test_auth.py               # Login, Refresh, Change-Password
  test_employees.py          # CRUD, RBAC, ContractHistory-Endpoints
  test_shifts.py             # CRUD, Bulk, Compliance, Claim
  test_absences.py           # Workflow, Status-Filter
  test_payroll.py            # Berechnung, Historischer Satz, Splitting
  test_compliance.py         # ArbZG §4/§5, Minijob-Limit
  test_contract_scenarios.py # 9 Personen-Szenarien
  test_contract_scenarios_extended.py  # 16 weitere Szenarien
  test_start_date_and_edit.py          # 14 Tests: start_date, PUT/DELETE contracts
  ... (weitere)
```

**Frontend:** Vitest mit @testing-library/react, jsdom.
```
frontend/src/__tests__/
  recurringEventUtils.test.ts  # 15 Tests für Regeltermin-Kalender-Logik
  ... (weitere)
```

Stand: 238 Backend-Tests, 39+ Frontend-Tests.
