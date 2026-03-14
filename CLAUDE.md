# VERA – Claude Code Guide

VERA ist ein Schichtplanungs- und Abrechnungssystem für das Persönliche Budget (PAB) im Arbeitgebermodell.

---

## Projekt auf einen Blick

| | |
|---|---|
| **Primärnutzer** | Stefan (PAB-Inhaber), 2 Teilzeitkräfte + 5 Minijobber |
| **Bundesland** | Baden-Württemberg |
| **Backend** | FastAPI (Python 3.12), SQLAlchemy 2.0 async, PostgreSQL 16 |
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| **Auth** | JWT (access + refresh), bcrypt, Multi-Tenant |
| **Infra** | Docker Compose, Traefik, Hetzner VPS, GitHub Actions CI/CD |

---

## Repository-Struktur

```
VERA/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, Router-Registrierung
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings (liest .env)
│   │   │   ├── database.py      # AsyncEngine, get_db(), create_tables()
│   │   │   ├── security.py      # JWT create/decode, bcrypt
│   │   │   └── redis.py         # Redis-Client (optional)
│   │   ├── models/              # SQLAlchemy ORM-Models
│   │   │   ├── tenant.py        # Tenant (Multi-Mandant), settings JSON
│   │   │   ├── user.py          # User (login), invite/reset tokens
│   │   │   ├── employee.py      # Employee (Stammdaten, availability_prefs)
│   │   │   ├── shift.py         # Shift + ShiftTemplate
│   │   │   ├── absence.py       # EmployeeAbsence + CareRecipientAbsence
│   │   │   ├── payroll.py       # PayrollEntry
│   │   │   ├── contract_history.py  # SCD Type 2 Vertragsverlauf
│   │   │   ├── contract_type.py     # Gruppenverträge (Vorlagen)
│   │   │   ├── holiday_profile.py   # Ferienprofile (BW)
│   │   │   ├── recurring_shift.py   # Schuljahrdienste
│   │   │   ├── shift_type.py        # Diensttypen mit Erinnerungen
│   │   │   ├── notification.py      # NotificationLog + Preferences
│   │   │   └── push_subscription.py # Web Push VAPID
│   │   ├── schemas/             # Pydantic v2 Schemas (In/Out)
│   │   ├── api/
│   │   │   └── v1/              # Alle REST-Endpoints
│   │   │       ├── auth.py      # Login, Register, Refresh, Invite, Reset
│   │   │       ├── employees.py # CRUD + /me + assign-contract-type
│   │   │       ├── shifts.py    # CRUD, Bulk, Confirm, Claim, Korrektur
│   │   │       ├── payroll.py   # Calculate, PDF-Download
│   │   │       ├── admin_settings.py  # SMTP, Surcharges, General (frontend_url)
│   │   │       └── deps.py      # Dependency-Typen: CurrentUser, AdminUser, ...
│   │   └── services/
│   │       ├── payroll_service.py       # Lohnberechnung + §3b-Zuschläge
│   │       ├── compliance_service.py    # ArbZG §4/§5, Minijob-Limits
│   │       ├── notification_service.py  # Telegram, E-Mail, Web Push
│   │       ├── pdf_service.py           # Lohnzettel (reportlab)
│   │       └── recurring_shift_service.py
│   ├── alembic/
│   │   └── versions/            # Migrationsdateien (IMMER idempotent!)
│   ├── tests/
│   │   ├── conftest.py          # Fixtures: engine, db, client, tenant, admin_user
│   │   └── test_*.py            # 224 Tests
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pytest.ini               # asyncio_mode=auto
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/          # Login, Register, Invite, Reset-PW (kein Sidebar-Layout)
│       │   └── (dashboard)/     # Alle geschützten Seiten mit Sidebar
│       │       ├── page.tsx     # Dashboard
│       │       ├── shifts/      # Dienste + Regeltermine
│       │       ├── employees/   # Mitarbeiterverwaltung (Detail-View + Modals)
│       │       ├── absences/    # Abwesenheiten + Genehmigung
│       │       ├── payroll/     # Abrechnung + PDF
│       │       ├── calendar/    # react-big-calendar
│       │       ├── compliance/  # Compliance-Verstöße
│       │       ├── notifications/
│       │       ├── reports/
│       │       └── settings/    # 4 Tabs: Planung | Abrechnung | Profil | System
│       ├── lib/
│       │   └── api.ts           # axios-Client + alle API-Funktionen
│       ├── store/
│       │   └── auth.ts          # Zustand Auth-Store (JWT + User-Info)
│       └── components/
│           └── shared/          # ThemeToggle, AvailabilityGrid, ...
├── deploy/
│   ├── docker-compose.yml       # Produktion (GHCR-Images)
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── .env                     # Nur auf VPS, gitignored
├── .github/workflows/
│   └── deploy.yml               # CI/CD: Test → Build → Push → SSH-Deploy
└── docker-compose.yml           # Entwicklung (lokale Volumes, Hot-Reload)
```

---

## Entwicklung lokal starten

### Voraussetzungen
- Python 3.12, Node.js 20
- Backend läuft standalone mit SQLite (kein Postgres/Redis nötig)

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# .env anlegen (minimal):
cat > .env <<EOF
DATABASE_URL=sqlite+aiosqlite:///./vera.db
SECRET_KEY=dev_secret_min_32_chars_change_me!!
DEBUG=true
ALLOWED_ORIGINS=http://localhost:31368,http://192.168.0.144:31368
EOF

uvicorn app.main:app --host 0.0.0.0 --port 31367 --reload
```

### Frontend
```bash
cd frontend
npm install

# .env.local anlegen:
echo "NEXT_PUBLIC_API_URL=http://192.168.0.144:31367" > .env.local

npm run dev -- -p 31368
```

### Ports (lokal)
- Backend: `http://192.168.0.144:31367` (oder `localhost:31367`)
- Frontend: `http://192.168.0.144:31368`
- Produktion: `https://vera.lab.halbewahrheit21.de`

---

## Tests ausführen

```bash
# Backend (224 Tests, SQLite in-memory)
cd backend && python3 -m pytest tests/ -q

# Frontend (39 Tests, Vitest)
cd frontend && npx vitest run
```

**Wichtig für Backend-Tests:**
- `db.expire_all()` (synchron, KEIN `await`) nach HTTP-Mutations aufrufen, sonst
  hat der Test-DB-Session veraltete Objekte (SQLAlchemy identity map)
- `StaticPool` sorgt dafür, dass Test-Client und `db`-Fixture dieselbe SQLite-Verbindung nutzen
- Fixtures: `engine`, `db`, `client`, `tenant`, `admin_user`, `employee_user`, `admin_token`, `employee_token`

---

## Datenbankmigrationen (Alembic)

```bash
# Neue Migration erstellen
cd backend
alembic revision -m "beschreibung"

# Auf Produktion anwenden (passiert automatisch beim Deploy)
alembic upgrade head
```

### Kritische Regeln für Migrationen

1. **`down_revision` muss immer auf den echten HEAD zeigen** – nicht auf einen alten Wert. Falsch gewählter `down_revision` erzeugt "Multiple head revisions" beim Deploy.

2. **Migrationen MÜSSEN idempotent sein** (inspect-Check), weil `lifespan()` in `main.py` beim Start `create_tables()` aufruft (SQLAlchemy `metadata.create_all()`). Wenn eine Migration eine Tabelle anlegen will, die schon durch `create_all()` entstanden ist, schlägt der Alembic-Run fehl.

   ```python
   from sqlalchemy.engine.reflection import Inspector

   def upgrade() -> None:
       conn = op.get_bind()
       inspector = Inspector.from_engine(conn)
       if "my_table" not in inspector.get_table_names():
           op.create_table("my_table", ...)
       # Für Spalten:
       cols = [c["name"] for c in inspector.get_columns("existing_table")]
       if "new_column" not in cols:
           op.add_column("existing_table", sa.Column("new_column", ...))
   ```

3. **Migrationskette (Stand 2026-03-14, HEAD = `f5a6b7c8d9e0`):**
   ```
   8eefccc3f51f (initial)
   → a1b2c3d4e5f6 → b3c4d5e6f7a8 → c1d2e3f4a5b6 → d2e3f4a5b6c7
   → e3f4a5b6c7d8 → f4a5b6c7d8e9 → a5b6c7d8e9f0 → b1c2d3e4f5a6
   → c2d3e4f5a6b1 → d3e4f5a6b7c8 → a0b1c2d3e4f5 → f5a6b7c8d9e0
   ```

---

## API-Konventionen

### Auth-Dependencies (aus `api/deps.py`)

```python
CurrentUser    # jeder eingeloggte User (role: admin | manager | employee)
AdminUser      # nur role="admin"
ManagerOrAdmin # role="admin" oder "manager"
SuperAdminUser # SuperAdmin (separates JWT-Typ "superadmin")
DB             # AsyncSession
```

Alle Typ-Aliase sind `Annotated[..., Depends(...)]` → direkt als Parameter-Typen verwenden:

```python
@router.get("/something")
async def get_something(current_user: CurrentUser, db: DB):
    ...
```

### Multi-Tenancy

Jeder User gehört zu einem `Tenant`. Alle Queries MÜSSEN `tenant_id` filtern:

```python
result = await db.execute(
    select(Employee).where(
        Employee.tenant_id == current_user.tenant_id,
        Employee.id == employee_id,
    )
)
```

### Response-Schemas

- Alle Endpoints haben `response_model=...` mit Pydantic-Schemas aus `app/schemas/`
- `EmployeePublicOut`: nur Name + Qualifikationen (für alle sichtbar)
- `EmployeeOut`: alles inkl. Gehalt (nur Admin + eigene Person)

### Admin-Settings (Tenant-Konfiguration)

Gespeichert in `Tenant.settings` (JSON-Spalte):
- `settings["smtp"]` – SMTP-Konfiguration
- `settings["surcharges"]` – Zuschlagsätze
- `settings["general"]["frontend_url"]` – Frontend-URL für Links in E-Mails

```python
tenant.settings = {**(tenant.settings or {}), "smtp": {...}}
```

### Neuen API-Endpoint hinzufügen

1. Datei in `backend/app/api/v1/` anlegen oder erweitern
2. Router in `backend/app/main.py` registrieren: `app.include_router(router, prefix="/api/v1")`
3. Bei neuen DB-Feldern: Alembic-Migration mit idempotent-Check
4. Schema in `backend/app/schemas/` anlegen
5. Methode in `frontend/src/lib/api.ts` hinzufügen

---

## Frontend-Konventionen

### API-Client (`src/lib/api.ts`)

Alle API-Aufrufe gehen über die axios-Instanz `api`. Neue Methoden in den entsprechenden Export-Objekten ergänzen:

```typescript
export const employeesApi = {
  list: (activeOnly = true) => api.get("/employees", { params: { active_only: activeOnly } }),
  // ...
};
```

### Datenabruf: TanStack Query

```typescript
const { data, isLoading } = useQuery({
  queryKey: ["employees"],
  queryFn: () => employeesApi.list().then(r => r.data),
});
```

### Neue Dashboard-Seite anlegen

1. Verzeichnis `frontend/src/app/(dashboard)/mein-feature/` anlegen
2. `page.tsx` mit `"use client"` erstellen
3. Nav-Link in `frontend/src/app/(dashboard)/layout.tsx` hinzufügen

### Theme

Catppuccin Latte (light) + Mocha (dark). CSS-Variablen im Format `rgb(var(--ctp-blue))`:

```tsx
// Farben
style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
style={{ color: "rgb(var(--ctp-green))" }}

// Semantic tokens (Tailwind)
className="bg-card text-foreground border-border bg-muted"
```

### tsconfig-Pflicht

`src/__tests__` und `src/test` müssen in `tsconfig.json` unter `exclude` stehen, sonst schlägt der Next.js-Build mit `"Cannot find name 'vi'"` fehl.

---

## CI/CD Pipeline

Jeder Push auf `main` triggert:

1. **Backend Tests** + **Frontend Tests** (parallel)
2. **Backend Image** bauen + nach `ghcr.io/sprobst76/vera-backend:latest` pushen
3. **Frontend Image** bauen + nach `ghcr.io/sprobst76/vera-frontend:latest` pushen
4. **Deploy to VPS** via SSH:
   - `git pull --ff-only` auf `/srv/vera`
   - `docker compose pull` (neue Images ziehen)
   - Rolling restart: erst Backend, dann `alembic upgrade head`, dann Frontend + Celery
   - `docker image prune -f`

**Build-Argumente für Frontend-Image** (GitHub Variables):
- `NEXT_PUBLIC_API_URL` → Produktions-Backend-URL
- `NEXT_PUBLIC_DEMO_SLUG` → Demo-Tenant-Slug

---

## Wichtige Regeln & Limits

### Arbeitsrecht (Deutschland)
- Minijob 2025: max. 556 €/Monat, 6.672 €/Jahr
- Ruhezeit: mindestens 11h zwischen Schichten (ArbZG §5)
- Pausen: >6h → 30 min, >9h → 45 min (ArbZG §4)

### Lohnzuschläge (§3b EStG, konfigurierbar)
- Früh (vor 06:00): 12,5%
- Spät (nach 20:00): 12,5%
- Nacht (23:00–06:00): 25%
- Samstag: 25%
- Sonntag: 50%
- Feiertag: 125%

### Rollen-Hierarchie
- `admin` > `manager` > `employee`
- SuperAdmin: separates System ohne Tenant-Kontext, TOTP 2FA

---

## Bekannte Fallstricke

### SQLAlchemy async
- **`selectinload()` statt Relationship-Direktzuweisung** bei async Sessions:
  ```python
  # FALSCH – triggert lazy-load:
  profile.vacation_periods = [...]
  # RICHTIG:
  select(HolidayProfile).options(selectinload(HolidayProfile.vacation_periods))
  ```
- **`db.expire_all()`** (synchron, KEIN await!) in Tests nach HTTP-Calls aufrufen,
  wenn man danach die DB direkt abfragen will

### ContractHistory (SCD Type 2)
- `valid_to = None` bedeutet: aktuell aktiver Eintrag
- Bei Vertragsänderung: alten Eintrag schließen (`valid_to = today`), neuen anlegen
- `assign-contract-type`-Endpoint macht das automatisch wenn `valid_from` übergeben wird

### Payroll-Schema-Felder
Richtige Feldnamen: `actual_hours`, `base_wage`, `total_gross`
(nicht `total_hours`, `base_pay`, `gross_pay`)

### ShiftCreate hat kein `status`-Feld
Status nach Erstellen per PUT setzen:
```python
r = await client.post("/api/v1/shifts", json={...})
await client.put(f"/api/v1/shifts/{r.json()['id']}", json={"status": "completed"})
```

### Frontend-URL in E-Mails
`FRONTEND_URL` in `backend/app/core/config.py` ist der Fallback (default: `localhost`).
Produktions-URL über Admin-Settings in der UI setzen:
**Einstellungen → System → Frontend-URL** (gespeichert in `Tenant.settings["general"]["frontend_url"]`).

---

## Produktions-Infra

- **VPS**: Hetzner, `91.99.200.244`, User `aiplatform`, Pfad `/srv/vera`
- **SSH**: `ssh aiplatform@91.99.200.244`
- **Docker Compose Project**: `vera` (`docker compose -p vera -f deploy/docker-compose.yml ...`)
- **Services**: `vera-api`, `vera-web`, `vera-postgres`, `vera-redis`, `vera-celery-worker`, `vera-celery-beat`
- **Traefik**: TLS via Cloudflare, Rate Limiting auf `/api/v1/auth/*`

### Konfiguration (deploy/.env auf VPS, nicht im Repo)
Wichtige Variablen:
```
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=...
FRONTEND_URL=https://vera.lab.halbewahrheit21.de
TELEGRAM_BOT_TOKEN=...
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
REDIS_URL=redis://vera-redis:6379/0
```
SMTP + Frontend-URL können auch über die Admin-UI gesetzt werden (werden in Tenant.settings gespeichert).

---

## Demo-System

```bash
cd backend && python3 seed_demo.py
```
- Erstellt Tenant + 9 User + ShiftTemplates + ~400 Schichten
- Demo-Credentials: alle `demo1234` | `stefan@vera.demo` (Admin)
- DemoBar: fixed bottom bar mit One-Click User-Switch (nur im Demo-Modus)

---

## Availability-Prefs Format

```json
{
  "0": { "available": true,  "from_time": "08:00", "to_time": "20:00", "note": "" },
  "1": { "available": true,  "from_time": "08:00", "to_time": "20:00", "note": "" },
  "5": { "available": false, "from_time": "08:00", "to_time": "20:00", "note": "" },
  "6": { "available": false, "from_time": "08:00", "to_time": "20:00", "note": "" }
}
```
Keys 0–6 = Montag–Sonntag (Python `weekday()`-Konvention).
