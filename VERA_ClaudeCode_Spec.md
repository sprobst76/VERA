# VERA – Verwaltung, Einsatz, Reporting & Assistenz
## Claude Code Development Specification v1.0

> **Kontext**: Schichtplanungs- und Abrechnungssystem für Persönliches Budget (PAB) im Arbeitgebermodell.  
> **Primärnutzer**: PAB-Inhaber (Stefan) mit 2 Teilzeitkräften + 5 Minijobbern für Schulbegleitung & Assistenz.  
> **Ziel**: MVP für internen Einsatz, SaaS-ready Architektur für spätere Vermarktung.  
> **Bundesland**: Baden-Württemberg (Feiertage, Schulferien vorbelegt)

---

## 1. Tech Stack

```
Frontend:     Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand
Backend:      FastAPI (Python 3.12), SQLAlchemy 2.0 async, Pydantic v2
Database:     PostgreSQL 15 (Row-Level Security für Multi-Tenant)
Cache:        Redis 7
Task Queue:   Celery + Redis Broker
Notifications: SendGrid (E-Mail), Telegram Bot API, Matrix SDK
Cal-Sync:     iCal Feed (ics-Bibliothek), Google Calendar API (Phase 2), CalDAV (Phase 2)
Auth:         JWT + Refresh Tokens, bcrypt, Tenant-Context in JWT
API Docs:     OpenAPI / Swagger (automatisch via FastAPI)
Deployment:   Docker Compose, Traefik (Reverse Proxy + Let's Encrypt)
Hosting:      Hetzner VPS (bestehende Infrastruktur)
AI:           Regelbasiertes Matching MVP, Gemini API Phase 2
Testing:      pytest (Backend), Playwright (E2E), Vitest (Frontend)
```

---

## 2. Projektstruktur

```
vera/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── traefik/
│   └── traefik.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   └── redis.py
│   │   ├── models/
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── employee.py
│   │   │   ├── shift.py
│   │   │   ├── absence.py
│   │   │   ├── payroll.py
│   │   │   ├── notification.py
│   │   │   └── audit.py
│   │   ├── schemas/
│   │   │   └── (Pydantic-Schemas je Modul)
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── employees.py
│   │   │   │   ├── shifts.py
│   │   │   │   ├── absences.py
│   │   │   │   ├── payroll.py
│   │   │   │   ├── calendar.py
│   │   │   │   ├── notifications.py
│   │   │   │   ├── compliance.py
│   │   │   │   ├── reports.py
│   │   │   │   └── webhooks.py
│   │   ├── services/
│   │   │   ├── payroll_service.py
│   │   │   ├── compliance_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── calendar_service.py
│   │   │   ├── holiday_service.py
│   │   │   ├── matching_service.py
│   │   │   └── report_service.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── reminder_tasks.py
│   │   │   └── payroll_tasks.py
│   │   └── utils/
│   │       ├── ical.py
│   │       ├── pdf_generator.py
│   │       └── german_holidays.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── public/
    │   ├── manifest.json          # PWA
    │   └── sw.js                  # Service Worker
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── (auth)/
        │   │   ├── login/
        │   │   └── register/
        │   ├── (dashboard)/
        │   │   ├── page.tsx        # Übersicht
        │   │   ├── calendar/
        │   │   ├── employees/
        │   │   ├── shifts/
        │   │   ├── absences/
        │   │   ├── payroll/
        │   │   ├── notifications/
        │   │   ├── reports/
        │   │   └── settings/
        ├── components/
        │   ├── ui/                 # shadcn/ui Komponenten
        │   ├── calendar/
        │   ├── shifts/
        │   ├── employees/
        │   ├── payroll/
        │   └── shared/
        ├── hooks/
        ├── lib/
        │   ├── api.ts
        │   └── utils.ts
        └── store/
            └── (Zustand Stores)
```

---

## 3. Datenbank-Schema

```sql
-- ============================================================
-- MULTI-TENANT BASIS
-- ============================================================
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    plan        VARCHAR(50) DEFAULT 'free',  -- free | pro | enterprise
    state       VARCHAR(50) DEFAULT 'BW',    -- Bundesland für Feiertage/Schulferien
    settings    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- BENUTZER & ROLLEN
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(50) DEFAULT 'admin',  -- admin | employee | parent_viewer
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Row-Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ============================================================
-- MITARBEITER
-- ============================================================
CREATE TABLE employees (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES users(id),
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    email               VARCHAR(255),
    phone               VARCHAR(50),
    contract_type       VARCHAR(50) NOT NULL,  -- minijob | part_time | full_time
    hourly_rate         DECIMAL(8,2) NOT NULL,
    monthly_hours_limit DECIMAL(6,2),           -- Soll-Stunden/Monat (z.B. 27h für Minijob)
    annual_salary_limit DECIMAL(10,2),          -- Jahresgrenze Minijob (Standard: 6672€)
    vacation_days       INTEGER DEFAULT 20,     -- Urlaubsanspruch in Tagen
    qualifications      JSONB DEFAULT '[]',     -- Skills/Qualifikationen
    notification_prefs  JSONB DEFAULT '{}',     -- Persönliche Benachrichtigungseinstellungen
    ical_token          VARCHAR(100) UNIQUE,    -- Für persönlichen iCal-Feed
    telegram_chat_id    VARCHAR(100),
    matrix_user_id      VARCHAR(255),
    quiet_hours_start   TIME DEFAULT '21:00',
    quiet_hours_end     TIME DEFAULT '07:00',
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SCHICHT-VORLAGEN (Regeltermine)
-- ============================================================
CREATE TABLE shift_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    weekdays        INTEGER[] NOT NULL,         -- 0=Mo, 1=Di, ... 6=So
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    break_minutes   INTEGER DEFAULT 0,
    location        VARCHAR(255),
    notes           TEXT,
    required_skills JSONB DEFAULT '[]',
    is_active       BOOLEAN DEFAULT TRUE,
    valid_from      DATE,
    valid_until     DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- DIENSTE
-- ============================================================
CREATE TABLE shifts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id         UUID REFERENCES employees(id),
    template_id         UUID REFERENCES shift_templates(id),
    date                DATE NOT NULL,
    start_time          TIME NOT NULL,
    end_time            TIME NOT NULL,
    break_minutes       INTEGER DEFAULT 0,
    location            VARCHAR(255),
    notes               TEXT,
    status              VARCHAR(50) DEFAULT 'planned',
    -- planned | confirmed | completed | cancelled | cancelled_absence
    cancellation_reason VARCHAR(255),          -- Bei status=cancelled_absence
    actual_start        TIME,                  -- Tatsächliche Arbeitszeit
    actual_end          TIME,
    -- Compliance-Flags (automatisch berechnet)
    is_holiday          BOOLEAN DEFAULT FALSE,
    is_weekend          BOOLEAN DEFAULT FALSE,
    is_sunday           BOOLEAN DEFAULT FALSE,
    rest_period_ok      BOOLEAN DEFAULT TRUE,
    break_ok            BOOLEAN DEFAULT TRUE,
    minijob_limit_ok    BOOLEAN DEFAULT TRUE,
    -- Übertrag
    hours_carried_over  DECIMAL(5,2) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_shifts_date ON shifts(date);
CREATE INDEX idx_shifts_employee ON shifts(employee_id);

-- ============================================================
-- ABWESENHEITEN (Mitarbeiter)
-- ============================================================
CREATE TABLE employee_absences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     UUID REFERENCES employees(id),
    type            VARCHAR(50) NOT NULL,
    -- vacation | sick | school_holiday | other
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    days_count      DECIMAL(5,1),              -- Arbeitstage (halbe möglich)
    status          VARCHAR(50) DEFAULT 'pending',  -- pending | approved | rejected
    notes           TEXT,
    approved_by     UUID REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ABWESENHEITEN DER BETREUTEN PERSON
-- ============================================================
CREATE TABLE care_recipient_absences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    type            VARCHAR(50) NOT NULL,
    -- vacation | rehab | hospital | sick | other
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    description     TEXT,
    notes           TEXT,
    -- Wie werden betroffene Dienste behandelt?
    shift_handling  VARCHAR(50) DEFAULT 'cancelled_unpaid',
    -- cancelled_unpaid | carry_over | paid_anyway
    notify_employees BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- STUNDEN-ÜBERTRAG
-- ============================================================
CREATE TABLE hours_carryover (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     UUID REFERENCES employees(id),
    from_month      DATE NOT NULL,             -- Erster Tag des Quellmonats
    to_month        DATE NOT NULL,             -- Erster Tag des Zielmonats
    hours           DECIMAL(6,2) NOT NULL,     -- Positiv = Stunden fehlen, negativ = Guthaben
    reason          TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- LOHNABRECHNUNG
-- ============================================================
CREATE TABLE payroll_entries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id             UUID REFERENCES employees(id),
    month                   DATE NOT NULL,             -- Erster Tag des Monats
    -- Stunden
    planned_hours           DECIMAL(6,2),
    actual_hours            DECIMAL(6,2),
    carryover_hours         DECIMAL(6,2) DEFAULT 0,
    paid_hours              DECIMAL(6,2),
    -- Zuschläge (Stunden)
    early_hours             DECIMAL(6,2) DEFAULT 0,
    late_hours              DECIMAL(6,2) DEFAULT 0,
    night_hours             DECIMAL(6,2) DEFAULT 0,
    weekend_hours           DECIMAL(6,2) DEFAULT 0,
    sunday_hours            DECIMAL(6,2) DEFAULT 0,
    holiday_hours           DECIMAL(6,2) DEFAULT 0,
    -- Vergütung
    base_wage               DECIMAL(10,2),
    early_surcharge         DECIMAL(10,2) DEFAULT 0,
    late_surcharge          DECIMAL(10,2) DEFAULT 0,
    night_surcharge         DECIMAL(10,2) DEFAULT 0,
    weekend_surcharge       DECIMAL(10,2) DEFAULT 0,
    sunday_surcharge        DECIMAL(10,2) DEFAULT 0,
    holiday_surcharge       DECIMAL(10,2) DEFAULT 0,
    total_gross             DECIMAL(10,2),
    -- Minijob-Tracking
    ytd_gross               DECIMAL(10,2),            -- Jahr-zu-Datum kumuliert
    annual_limit_remaining  DECIMAL(10,2),
    -- Status
    status                  VARCHAR(50) DEFAULT 'draft',  -- draft | approved | paid
    notes                   TEXT,
    pdf_path                VARCHAR(500),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_payroll_employee_month ON payroll_entries(employee_id, month);

-- ============================================================
-- BENACHRICHTIGUNGEN
-- ============================================================
CREATE TABLE notification_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    employee_id     UUID REFERENCES employees(id),
    channel         VARCHAR(50) NOT NULL,      -- email | telegram | matrix | push
    event_type      VARCHAR(100) NOT NULL,     -- shift_assigned | shift_changed | reminder_1h | etc.
    subject         VARCHAR(500),
    body            TEXT,
    status          VARCHAR(50) DEFAULT 'pending',  -- pending | sent | failed
    sent_at         TIMESTAMPTZ,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- COMPLIANCE-AUDIT
-- ============================================================
CREATE TABLE compliance_checks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    shift_id        UUID REFERENCES shifts(id),
    check_type      VARCHAR(100) NOT NULL,     -- rest_period | break_time | minijob_limit
    result          VARCHAR(50) NOT NULL,      -- ok | warning | violation
    details         JSONB,
    checked_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AUDIT-LOG (alle Änderungen)
-- ============================================================
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id),
    user_id         UUID REFERENCES users(id),
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID,
    action          VARCHAR(50) NOT NULL,      -- create | update | delete
    old_values      JSONB,
    new_values      JSONB,
    ip_address      VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- API-KEYS (externe API-Zugriffe)
-- ============================================================
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    key_hash        VARCHAR(255) UNIQUE NOT NULL,
    scopes          JSONB DEFAULT '["read"]',
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- WEBHOOKS
-- ============================================================
CREATE TABLE webhooks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    url             VARCHAR(1000) NOT NULL,
    events          JSONB NOT NULL,            -- Array von Event-Typen
    secret          VARCHAR(255),              -- HMAC-Signierung
    is_active       BOOLEAN DEFAULT TRUE,
    last_triggered  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Feature-Gruppen & Implementierungsdetails

### Gruppe 1: Kernplanung (MVP)

**Ziel**: Dienste erstellen, bearbeiten, löschen und übersichtlich darstellen.

- Kalender-Ansichten: Tag, Woche, Monat (FullCalendar.io oder react-big-calendar)
- Drag & Drop: Dienste verschieben mit automatischer Compliance-Prüfung
- Regeltermine: Wiederkehrende Dienste aus Templates generieren (bis zu 1 Jahr im Voraus)
- Offene Dienste: Rot markiert, Push-to-Pool möglich
- Farbkodierung: Pro Mitarbeiter + Status (geplant/bestätigt/abgeschlossen/abgesagt)

**API-Endpunkte:**
```
GET    /api/v1/shifts?from=&to=&employee_id=
POST   /api/v1/shifts
PUT    /api/v1/shifts/{id}
DELETE /api/v1/shifts/{id}
POST   /api/v1/shifts/bulk          # Aus Template generieren
GET    /api/v1/shift-templates
POST   /api/v1/shift-templates
PUT    /api/v1/shift-templates/{id}
```

---

### Gruppe 2: Mitarbeiterverwaltung (MVP)

**Ziel**: Vollständige Stammdatenpflege für alle Vertragstypen.

- Vertragstyp: Minijob / Teilzeit mit je eigenem Vergütungsmodell
- Stundenkontingent: Monats-Soll pro Mitarbeiter (z.B. 27h)
- Qualifikations-Badges: Schulbegleitung, Erste Hilfe, etc. (JSONB-Array)
- Notfallkontakte
- Kündigungsfristen-Tracking

**Wichtig für Minijob:**
```python
class EmployeeContractType(Enum):
    MINIJOB = "minijob"          # Bezahlung nach tatsächlichen Stunden
    PART_TIME = "part_time"      # Festgehalt nach Vertrag
    FULL_TIME = "full_time"
```

---

### Gruppe 3: Urlaubs- & Abwesenheitsverwaltung (MVP)

**Genehmigungsworkflow:**
1. Mitarbeiter stellt Antrag (App oder E-Mail-Link)
2. Admin erhält Benachrichtigung
3. Admin genehmigt/lehnt ab (mit Begründung)
4. Mitarbeiter wird informiert
5. Betroffene Dienste werden markiert (nicht auto-gelöscht!)

**Schulferien BW 2025/26 (vorbelegt):**
```python
BW_SCHOOL_HOLIDAYS_2025_26 = [
    {"name": "Herbstferien", "start": "2025-10-27", "end": "2025-10-30"},
    {"name": "Weihnachten",  "start": "2025-12-22", "end": "2026-01-05"},
    {"name": "Ostern",       "start": "2026-03-30", "end": "2026-04-11"},
    {"name": "Pfingsten",    "start": "2026-05-26", "end": "2026-06-05"},
    {"name": "Sommer",       "start": "2026-07-30", "end": "2026-09-12"},
]
```

---

### Gruppe 4: Compliance & Arbeitsrecht (MVP)

**Automatische Validierung bei jeder Schicht-Erstellung/-Änderung:**

```python
class ComplianceService:

    async def check_shift(self, shift: Shift, employee: Employee) -> ComplianceResult:
        violations = []
        warnings = []

        # 1. Ruhezeit (ArbZG §5): min. 11h zwischen Diensten
        prev_shift = await self.get_previous_shift(shift.employee_id, shift.date)
        if prev_shift:
            rest_hours = self.calc_rest_hours(prev_shift.end_time, shift.start_time)
            if rest_hours < 11:
                violations.append(f"Ruhezeit unterschritten: {rest_hours:.1f}h (min. 11h)")

        # 2. Pausenpflicht
        work_hours = self.calc_work_hours(shift.start_time, shift.end_time)
        if work_hours > 9 and shift.break_minutes < 45:
            violations.append("Nach 9h Arbeitszeit: mind. 45 Min Pause erforderlich")
        elif work_hours > 6 and shift.break_minutes < 30:
            violations.append("Nach 6h Arbeitszeit: mind. 30 Min Pause erforderlich")

        # 3. Minijob-Limit-Check (monatlich + jährlich)
        if employee.contract_type == "minijob":
            monthly_gross = await self.calc_monthly_gross(employee.id, shift.month)
            if monthly_gross > 556:  # 2025
                warnings.append(f"Minijob-Monatsgrenze überschritten: {monthly_gross:.2f}€")
            ytd_gross = await self.calc_ytd_gross(employee.id, shift.year)
            if ytd_gross > 6672:
                violations.append(f"Minijob-Jahresgrenze überschritten: {ytd_gross:.2f}€")

        # 4. Feiertag-Info
        if await self.is_holiday(shift.date):
            warnings.append(f"Feiertag: {await self.get_holiday_name(shift.date)}")

        return ComplianceResult(violations=violations, warnings=warnings)
```

---

### Gruppe 5: Abrechnung & Lohn (MVP)

**Vergütungsmodell Minijobber:**
```python
class PayrollService:

    SURCHARGE_RATES = {
        "early":   0.125,  # 12.5% für Frühdienst (vor 06:00)
        "late":    0.125,  # 12.5% für Spätdienst (nach 20:00)
        "night":   0.25,   # 25%   für Nachtarbeit (23:00–06:00)
        "weekend": 0.25,   # 25%   Samstag
        "sunday":  0.50,   # 50%   Sonntag
        "holiday": 1.25,   # 125%  Feiertag
    }

    async def calculate_monthly_payroll(
        self, employee_id: UUID, month: date
    ) -> PayrollEntry:
        employee = await self.get_employee(employee_id)
        shifts = await self.get_completed_shifts(employee_id, month)
        carryover = await self.get_carryover(employee_id, month)

        total_hours = 0
        total_gross = 0
        surcharge_breakdown = defaultdict(float)

        for shift in shifts:
            if shift.status in ("completed", "confirmed"):
                net_hours = self.calc_net_hours(shift)
                base_pay = net_hours * float(employee.hourly_rate)
                surcharges = self.calc_surcharges(shift, employee.hourly_rate)
                total_hours += net_hours
                total_gross += base_pay + sum(surcharges.values())
                for k, v in surcharges.items():
                    surcharge_breakdown[k] += v

        # Übertrag berücksichtigen
        paid_hours = total_hours + carryover

        # Neuen Übertrag berechnen
        if employee.monthly_hours_limit:
            new_carryover = paid_hours - float(employee.monthly_hours_limit)
            paid_hours = min(paid_hours, float(employee.monthly_hours_limit))

        return PayrollEntry(
            employee_id=employee_id,
            month=month,
            actual_hours=total_hours,
            carryover_hours=carryover,
            paid_hours=paid_hours,
            total_gross=round(paid_hours * float(employee.hourly_rate) + sum(surcharge_breakdown.values()), 2),
            **surcharge_breakdown
        )
```

**Stunden-Übertrag Logik:**
- Nicht geleistete Stunden werden als positiver Übertrag ins Folgemonat gebucht
- Guthaben (mehr als Soll gearbeitet) als negativer Übertrag
- Manueller Übertrag mit Kommentar möglich
- Übertrag verfällt nach konfigurierbarer Frist (Standard: 3 Monate)

---

### Gruppe 6: Benachrichtigungen & Kalender-Synchronisation (MVP)

#### 6a – Kanäle
| Kanal | Bibliothek | Priorität |
|-------|-----------|-----------|
| E-Mail | SendGrid Python SDK | MVP |
| Telegram | python-telegram-bot | MVP |
| Matrix | matrix-nio | MVP |
| Push (PWA) | Web Push Protocol | Phase 2 |
| SMS | Twilio | Phase 2 |

#### 6b – Ereignis-Typen
```python
class NotificationEvent(Enum):
    SHIFT_ASSIGNED       = "shift_assigned"
    SHIFT_CHANGED        = "shift_changed"       # Zeit/Ort geändert
    SHIFT_CANCELLED      = "shift_cancelled"
    SHIFT_REMINDER       = "shift_reminder"       # X Stunden vorher
    VACATION_REQUESTED   = "vacation_requested"
    VACATION_APPROVED    = "vacation_approved"
    VACATION_REJECTED    = "vacation_rejected"
    POOL_SHIFT_OPEN      = "pool_shift_open"
    COMPLIANCE_WARNING   = "compliance_warning"
    MINIJOB_LIMIT_80     = "minijob_limit_80"     # 80% der Monatsgrenze
    MINIJOB_LIMIT_95     = "minijob_limit_95"     # 95% der Monatsgrenze
    CARE_ABSENCE_NEW     = "care_absence_new"     # Betreute Person abwesend
    PAYROLL_READY        = "payroll_ready"
```

#### 6c – Persönliche Einstellungen (JSONB in employees.notification_prefs)
```json
{
  "channels": {
    "email": true,
    "telegram": true,
    "matrix": false
  },
  "events": {
    "shift_assigned": ["email", "telegram"],
    "shift_changed": ["email", "telegram"],
    "shift_reminder": ["telegram"],
    "vacation_approved": ["email"],
    "compliance_warning": ["email"]
  },
  "reminders": [
    {"hours_before": 24},
    {"hours_before": 2}
  ],
  "quiet_hours": {
    "enabled": true,
    "start": "21:00",
    "end": "07:00"
  },
  "digest_mode": false,
  "digest_time": "08:00",
  "change_threshold_minutes": 30
}
```

#### 6d – Kalender-Synchronisation
```python
# iCal-Feed (MVP) – dynamische URL pro Mitarbeiter
# GET /api/v1/calendar/{ical_token}/feed.ics
class CalendarService:
    def generate_ical_feed(self, employee: Employee, shifts: list[Shift]) -> str:
        cal = Calendar()
        cal.add('prodid', '-//VERA//Schichtplanner//DE')
        cal.add('version', '2.0')
        cal.add('x-wr-calname', f'VERA – {employee.first_name}')
        cal.add('refresh-interval;value=duration', 'PT1H')  # Stündlich aktualisieren

        for shift in shifts:
            event = Event()
            event.add('summary', f'Dienst – {shift.location or "Einsatz"}')
            event.add('dtstart', datetime.combine(shift.date, shift.start_time))
            event.add('dtend', datetime.combine(shift.date, shift.end_time))
            event.add('description', shift.notes or '')
            event.add('location', shift.location or '')
            event.add('status', 'CONFIRMED' if shift.status == 'confirmed' else 'TENTATIVE')
            cal.add_component(event)

        return cal.to_ical().decode('utf-8')
```

**Phasenstrategie Kalender:**
- **MVP**: iCal-Feed-URL (funktioniert mit Apple Calendar, Google Calendar, Outlook, Nextcloud)
- **Phase 2**: Google Calendar API (bidirektionale Push-Sync)
- **Phase 2**: CalDAV (für Nextcloud / Baikal – passt zu deiner Infrastruktur!)

---

### Gruppe 7: Mobile & UX (MVP)

**PWA-Konfiguration:**
```json
// public/manifest.json
{
  "name": "VERA – Schichtplanner",
  "short_name": "VERA",
  "theme_color": "#1E3A5F",
  "background_color": "#ffffff",
  "display": "standalone",
  "orientation": "portrait",
  "start_url": "/",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- Dark Mode: next-themes + Tailwind `dark:` Klassen
- Mobile-Kalender: Swipe zwischen Wochen/Tagen
- Offline: Service Worker cached Kalenderansicht + letzte Abrechnung

---

### Gruppe 8: KI & Automatisierung (Phase 2)

**MVP (regelbasiert):**
```python
class MatchingService:
    async def suggest_employees(self, shift: Shift) -> list[EmployeeSuggestion]:
        """Regelbasiertes Matching ohne KI für MVP"""
        candidates = []
        for emp in await self.get_active_employees(shift.tenant_id):
            score = 0
            reasons = []

            # Verfügbar (kein anderer Dienst, kein Urlaub)
            if not await self.has_conflict(emp.id, shift):
                score += 30
            else:
                continue

            # Qualifikation vorhanden
            if self.has_required_skills(emp, shift.required_skills):
                score += 25
                reasons.append("✓ Qualifikation")

            # Kontingent noch nicht ausgeschöpft
            remaining = await self.get_remaining_hours(emp.id, shift.month)
            if remaining >= shift.duration_hours:
                score += 20
                reasons.append(f"✓ {remaining:.1f}h verfügbar")

            # Ruhezeit ok
            if await self.rest_period_ok(emp.id, shift):
                score += 15
                reasons.append("✓ Ruhezeit eingehalten")

            candidates.append(EmployeeSuggestion(employee=emp, score=score, reasons=reasons))

        return sorted(candidates, key=lambda x: x.score, reverse=True)
```

**Phase 2**: Gemini API für Präferenz-Lernen und Langzeit-Muster

---

### Gruppe 9: Kollaboration / Pool (Phase 2)

- Mitarbeiter können Dienste in einen Tauschpool einstellen
- Andere Mitarbeiter können Pool-Dienste annehmen (mit Compliance-Check)
- Admin muss Tausch genehmigen
- Benachrichtigung an alle qualifizierten Mitarbeiter bei offenem Pool-Dienst

---

### Gruppe 10: Abwesenheit der betreuten Person (MVP)

```python
class CareAbsenceService:
    async def create_absence(
        self,
        absence: CareRecipientAbsence,
        tenant_id: UUID
    ) -> list[AffectedShift]:
        # Alle betroffenen Dienste im Zeitraum finden
        affected = await self.get_shifts_in_range(
            tenant_id, absence.start_date, absence.end_date
        )

        results = []
        for shift in affected:
            if absence.shift_handling == "cancelled_unpaid":
                shift.status = "cancelled_absence"
                shift.cancellation_reason = f"{absence.type}: {absence.description}"
            elif absence.shift_handling == "carry_over":
                shift.status = "cancelled_absence"
                await self.create_carryover(shift)  # Stunden in Folgemonat
            # "paid_anyway" -> Status bleibt confirmed, wird normal abgerechnet

            await self.save_shift(shift)
            results.append(shift)

        # Betroffene Mitarbeiter benachrichtigen
        if absence.notify_employees:
            employees = list({s.employee_id for s in results})
            for emp_id in employees:
                await self.notification_service.send(
                    employee_id=emp_id,
                    event=NotificationEvent.CARE_ABSENCE_NEW,
                    context={"absence": absence, "shifts": [s for s in results if s.employee_id == emp_id]}
                )

        return results
```

---

### Gruppe 11: Eltern-Portal (Phase 2)

- Separater Login (Rolle: `parent_viewer`)
- Lesend: Welcher Schulbegleiter ist wann eingeplant
- Abwesenheits-Anfragen der betreuten Person stellen
- Keine Gehalts- oder Compliance-Daten sichtbar
- DSGVO: AV-Vertrag mit Eltern notwendig

---

### Gruppe 12: API & Auswertungen (MVP: Basis-API, Phase 2: erweiterte Reports)

**API-Key-Authentifizierung:**
```python
# Header: X-API-Key: vera_live_xxxxxxxxxxxxx
# Scopes: read | write | admin
```

**Report-Endpunkte:**
```
GET /api/v1/reports/hours-summary?employee_id=&from=&to=
GET /api/v1/reports/surcharge-breakdown?month=
GET /api/v1/reports/utilization?from=&to=
GET /api/v1/reports/absences?year=
GET /api/v1/reports/minijob-limit-status
GET /api/v1/reports/compliance-violations?from=&to=
GET /api/v1/reports/export/csv?report=hours-summary&...
GET /api/v1/reports/export/pdf?report=payroll&month=
```

**Webhook-Events:**
```python
WEBHOOK_EVENTS = [
    "shift.created", "shift.updated", "shift.cancelled",
    "absence.approved", "payroll.created",
    "compliance.violation", "care_absence.created"
]
```

**n8n-Integration**: Webhooks direkt in bestehende n8n-Workflows integrierbar (z.B. Abrechnung → Google Sheets)

---

### Gruppe 13: SaaS-Infrastruktur (Phase 3)

- Multi-Tenant: Row-Level Security bereits im Schema implementiert
- Tenant-Onboarding: Wizard (Bundesland, Mitarbeiter, Dienst-Vorlagen)
- Pricing: Freemium (1 Betreuter, 5 MA) / Pro (unbegrenzt)
- Admin-Dashboard: Tenant-Übersicht, Usage, Fehler
- Stripe-Integration für Abonnements

---

## 5. Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: vera
      POSTGRES_USER: vera_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vera_user -d vera"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.vera-api.rule=Host(`api.vera.yourdomain.de`)"
      - "traefik.http.routers.vera-api.tls.certresolver=letsencrypt"
    volumes:
      - ./backend:/app
      - media_data:/app/media

  celery:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    env_file: .env
    depends_on:
      - redis
      - backend

  celery-beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    env_file: .env
    depends_on:
      - redis

  frontend:
    build: ./frontend
    env_file: .env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.vera.rule=Host(`vera.yourdomain.de`)"
      - "traefik.http.routers.vera.tls.certresolver=letsencrypt"

volumes:
  postgres_data:
  redis_data:
  media_data:
```

---

## 6. Implementierungs-Timeline (realistisch, nebenberuflich)

| Phase | Dauer | Inhalt |
|-------|-------|--------|
| **Woche 1–2** | Foundation | Docker Setup, DB-Schema, Alembic Migrations, JWT Auth, Basis-API |
| **Woche 3–4** | Core Backend | Schicht-CRUD, Compliance-Service, Urlaubs-Workflow, Feiertage BW |
| **Woche 5–6** | Core Frontend | Kalender (Tag/Woche/Monat), Mitarbeiterverwaltung, Auth-Flow |
| **Woche 7–8** | Abrechnung | PayrollService, Stunden-Übertrag, Lohnzettel-PDF |
| **Woche 9–10** | Benachrichtigungen | E-Mail, Telegram, Reminder-Tasks, iCal-Feed |
| **Woche 11–12** | Care Absences + API | Betreuten-Abwesenheiten, Basis-Reports, API-Keys, Webhooks |
| **Woche 13–14** | PWA + Testing | Service Worker, Mobile UX, pytest, Playwright E2E |
| **Woche 15–16** | Buffer + Go-Live | Security Audit, DSGVO-Docs, Steuerberater-Test, Dry-Run |
| **Phase 2** (Monat 5–8) | Advanced Features | KI-Matching, Pool, Eltern-Portal, CalDAV, erw. Reports |
| **Phase 3** (Monat 9+) | SaaS | Tenant-Onboarding, Stripe, Admin-Dashboard |

> **Hinweis**: Timeline gilt für ~10h/Woche Entwicklungszeit nebenberuflich.

---

## 7. Gesetzliche Rahmenbedingungen

| Thema | Regelung | Implementierung |
|-------|----------|-----------------|
| Ruhezeit | ArbZG §5: min. 11h zwischen Diensten | ComplianceService.check_rest_period() |
| Pausen | 6h→30min, 9h→45min (ArbZG §4) | ComplianceService.check_break() |
| Minijob 2025 | 556€/Monat, 6.672€/Jahr | PayrollService.check_minijob_limit() |
| Zeiterfassung | Pflicht, 2 Jahre Aufbewahrung | audit_log Tabelle, kein Löschen |
| Urlaub | min. 4 Wochen / Jahr | employee.vacation_days (Standard: 20) |
| Feiertage BW | Gesetzliche Feiertage automatisch | HolidayService (workalendar-Bibliothek) |
| DSGVO | Gesundheitsdaten (betreute Person) | AV-Verträge, Datenlöschkonzept |

---

## 8. Zuschlagssätze (konfigurierbar je Tenant)

| Zuschlag | Zeitraum | Satz (Standard) |
|----------|----------|-----------------|
| Frühdienst | vor 06:00 Uhr | 12,5% |
| Spätdienst | nach 20:00 Uhr | 12,5% |
| Nachtarbeit | 23:00–06:00 Uhr | 25% |
| Samstag | ganztägig | 25% |
| Sonntag | ganztägig | 50% |
| Feiertag | ganztägig | 125% |

> Zuschläge sind steuerlich begünstigt (§ 3b EStG). Steuerberater zur finalen Abstimmung empfohlen.

---

## 9. DSGVO-Checkliste

- [ ] Datenschutzbeauftragter bestimmt (ab 20 MA mit personenbezogenen Daten)
- [ ] Auftragsverarbeitungsvertrag (AVV) mit Hetzner (Hosting)
- [ ] AVV mit SendGrid, Telegram (Benachrichtigungen)
- [ ] Verarbeitungsverzeichnis (Mitarbeiterdaten, Gesundheitsdaten betreute Person)
- [ ] Datenlöschkonzept (Zeiterfassung 2 Jahre, Lohnunterlagen 10 Jahre)
- [ ] Einwilligung Mitarbeiter zur Benachrichtigung via Telegram/Matrix
- [ ] Datenschutzerklärung für Eltern-Portal

---

## 10. Go-Live Checkliste

- [ ] SSL-Zertifikate via Traefik/Let's Encrypt aktiv
- [ ] PostgreSQL automatische Backups (täglich, 30 Tage Retention)
- [ ] `.env` Secrets nicht im Git-Repository
- [ ] Rate Limiting auf API-Endpunkten
- [ ] Alembic-Migrations getestet (Up + Down)
- [ ] Steuerberater hat Zuschlagsberechnung geprüft
- [ ] Minijob-Zentrale Regelungen aktuell (jährlich prüfen)
- [ ] Feiertage BW für neues Jahr eingepflegt
- [ ] Telegram Bot Token + SendGrid API Key hinterlegt
- [ ] iCal-Feed mit Apple Calendar + Google Calendar getestet
- [ ] Mitarbeiter onboarded + erste Schichten eingeplant
- [ ] Backup-Restore getestet

---

## 11. Empfohlene Python-Pakete (backend/requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic[email]==2.10.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
celery[redis]==5.4.0
redis==5.2.0
icalendar==6.1.0
workalendar==17.0.0         # Deutsche Feiertage
sendgrid==6.11.0
python-telegram-bot==21.9
matrix-nio==0.25.2
reportlab==4.2.5             # PDF-Generierung
python-multipart==0.0.18
httpx==0.28.0
```

---

## 12. Empfohlene npm-Pakete (frontend/package.json)

```json
{
  "dependencies": {
    "next": "14.2.0",
    "react": "^18.3.0",
    "typescript": "^5.7.0",
    "tailwindcss": "^3.4.0",
    "@shadcn/ui": "latest",
    "zustand": "^5.0.0",
    "@tanstack/react-query": "^5.62.0",
    "react-big-calendar": "^1.15.0",
    "date-fns": "^4.1.0",
    "axios": "^1.7.0",
    "next-themes": "^0.4.4",
    "react-hook-form": "^7.54.0",
    "zod": "^3.24.0",
    "recharts": "^2.14.0",
    "react-hot-toast": "^2.4.0"
  }
}
```

---

*Dokument erstellt: Februar 2026 | Version: 1.0 | Projekt: VERA*  
*Nächster Schritt: `claude code` im Projektverzeichnis starten und mit Week 1 Foundation beginnen*
