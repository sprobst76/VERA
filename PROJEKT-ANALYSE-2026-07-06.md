---
slug: VERA
live: true
kategorie: haerten
findings:
  kritisch: 1
  hoch: 7
  mittel: 11
  niedrig: 7
risiko: 0.6
wert: 0.72
empfehlung: "Härten + weiterbetreiben; Produktisierung nur als separates Vorhaben (ITSG-Compliance blockiert SaaS)."
---

# VERA — Vollanalyse

**Datum:** 2026-07-06
**Analysiert von:** Claude (read-only, keine Änderungen am Projekt)
**Projekt:** `/home/spro/development/VERA`
**Stack:** FastAPI (Python 3.12, SQLAlchemy 2.0 async) + Next.js 14 (App Router, TS) · PostgreSQL 16 · Docker/Traefik · Hetzner VPS
**Umfang:** ~26.000 LOC produktiv (Backend ~10.240, Frontend ~15.750), 18 Alembic-Migrationen, produktiv mit echten Mitarbeiter- und Lohndaten

---

## Executive Summary

VERA ist ein technisch überdurchschnittlich sauber gebautes Nischen-System (PAB-Arbeitgebermodell) mit ordentlicher Schichtung, 339 Backend-Tests und einem strukturierten GSD-Workflow. Der Auth-Kern ist nach dem pausierten Security-Milestone in gutem Zustand: PyJWT statt python-jose, bcrypt, token_version-Revocation, API-Key-Scope-Enforcement und TOTP-2FA für Superadmins sind vorhanden und greifen. Multi-Tenant-Isolation ist im Code konsistent umgesetzt (tenant_id-Filter an allen geprüften Stellen), aber **nur punktuell durch Tests abgesichert** — das größte latente IDOR-Risiko.

Es gibt **einen KRITISCHEN Fund**: ein Klartext-Drittanbieter-Passwort plus Prod-API-Key liegen unverschlüsselt in `backend/.env.shiftjuggler` (nicht committet, aber auf Platte). Auf DSGVO-Ebene sind Lohndaten weder at rest verschlüsselt noch sind Backups verschlüsselt/off-site — für Beschäftigten-/Lohndaten (Art. 32 DSGVO) der wichtigste Handlungsblock. JWTs haben einen schwachen hartkodierten Default-`SECRET_KEY` ohne Fail-Fast. Frontend speichert access+refresh Token in localStorage (XSS→Session-Takeover) und schützt Admin-Seiten nur per Nav-Filter, nicht per Route-Guard (Backend setzt aber durch).

Der Security-Milestone v1.0 ist mitten in Phase 3 (Audit-Trail) pausiert — an einem manuellen Visual-Verify-Checkpoint. **Wichtig:** Der Audit-Read-Endpoint und die Frontend-Seite (Commits df9bd26, 455c500) liegen nur in einem prunable Worktree-Branch und sind **nicht in `main` gemerged**; auf `main` fehlt der Router. Das Audit-*Schreiben* ist gemerged und aktiv. Die geplanten, aber offenen Punkte SEC-02 (systematische RBAC-Prüfung) und SEC-03 (Pydantic extra="forbid") sind für Phase 7 vorgesehen und noch nicht umgesetzt.

Business: Solides Eigenbetriebs-Werkzeug mit echtem Nischen-Wert. Produktisierung zu Multi-Mandanten-SaaS ist architektonisch angelegt (Multi-Tenant existiert), aber rechtlich hochgradig blockiert — ITSG/Lohnabrechnungs-Compliance wäre ein eigenes Großprojekt. Empfehlung: **härten + weiterbetreiben**, Produktisierung nur als bewusst separates Vorhaben.

**Findings gesamt: 26** — KRITISCH: 1 · HOCH: 7 · MITTEL: 11 · NIEDRIG: 7

---

## Teil 1 — Sicherheit

### 1.1 Auth-Flow (JWT, 2FA, Passwörter)

**Positiv / verifiziert im Code:**
- **JWT-Handling** (`backend/app/core/security.py`): PyJWT, `HS256`, Access-Token 60 min, Refresh 7 Tage. Token-Payload enthält `sub`, `tenant_id`, `role`, `type` (access/refresh) und `ver` (token_version). `decode_token` validiert Signatur + Ablauf sauber. Der `type`-Claim wird in den Guards geprüft (`deps.py:87`), sodass ein Refresh-Token nicht als Access-Token durchgeht.
- **Token-Revocation**: `token_version`-Spalte am User; Guard vergleicht `payload["ver"]` gegen `user.token_version` (`deps.py:100-102`). `logout-all` und `change-password` inkrementieren die Version (`auth.py:136,144`) → alle Sessions werden ungültig. Sauber gelöst, kein Redis-Blocklist nötig.
- **Passwort-Hashing**: direktes `bcrypt.hashpw`/`checkpw` (`security.py:11-19`). Kein veraltetes passlib. Mindestlänge 8 Zeichen (`auth.py:19-22`).
- **2FA**: TOTP via `pyotp` für Superadmins mit Challenge-Token-Flow (Passwort → 5-min-Challenge-Token → TOTP-Verify → 8h-Token). `superadmin.py:140-232`. Sinnvoll implementiert.
- **Self-Registration deaktiviert** (`auth.py:62-68`, 410 Gone). **User-Enumeration** bei forgot-password vermieden (immer 200, `auth.py:227`). Reset-/Invite-Token via `secrets.token_urlsafe(32)` mit Ablauf.

**Findings:**

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Schwacher hartkodierter Default-`SECRET_KEY`** = `"dev_secret_key_change_in_production_min_32_chars!!"` als Fallback. Kein Fail-Fast, der Start mit Default-Key (JWT-Signaturschlüssel!) verhindert. `DEBUG=True` ist ebenfalls Default → bei fehlender `.env` in Prod wären `/docs` offen und SQL-Echo an. | `backend/app/core/config.py:6,23` · `main.py:44` |
| MITTEL | **HS256 (symmetrisch)** — akzeptabel für Single-Service, aber Schlüsselkompromittierung erlaubt beliebige Token-Fälschung. Kein Algorithmus-Whitelisting-Problem (Liste fix), aber Rotation ist schwierig. | `security.py:83` |
| MITTEL | **Refresh rotiert Token, aber altes Refresh-Token bleibt bis Ablauf gültig** (kein Single-Use / keine jti-Invalidierung). Ein geleaktes Refresh-Token ist 7 Tage nutzbar, auch nach Rotation, solange token_version nicht steigt. | `auth.py:112-115` |
| NIEDRIG | Keine Passwort-Komplexitätsregeln außer Länge ≥8; keine Prüfung gegen Breach-Listen. | `auth.py:19-22` |
| NIEDRIG | Login hat kein applikationsseitiges Rate-Limiting/Lockout — nur Traefik-Rate-Limit (10/min Auth) auf Infra-Ebene. | `deploy/docker-compose.yml:78-90` |

### 1.2 Autorisierung — RBAC & fehlende Guards

**Systematische Endpoint-Prüfung** (alle `@router.{get,post,put,patch,delete}` in `app/api/v1/` gegen ihre Dependency-Guards abgeglichen):

**Ergebnis: Es gibt keine „vergessenen" Guards.** Jeder Endpoint hat entweder einen bewussten öffentlichen Zweck (Auth/Reset/Invite/iCal/vapid-key) oder einen der Guards `CurrentUser`, `ManagerOrAdmin`, `AdminUser`, `ParentViewerOrHigher`, `SuperAdminUser`. Die Guard-Hierarchie ist zentral in `deps.py:107-139` definiert. Das widerlegt die pessimistische Lesart von „Rollenprüfung inkonsistent" — die Guards *existieren* flächendeckend.

**ABER — die bekannten Punkte konkretisiert:**

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **„Rollenprüfung inkonsistent" = Feingranulare Prüfung liegt im Handler-Body, nicht im Guard, und ist nicht einheitlich.** Endpoints mit `CurrentUser`-Guard führen die eigentliche Rollen-/Ownership-Logik inline und copy-paste-artig aus. Beispiel Payroll: 3× nahezu identischer Employee-Ownership-Block (`payroll.py:38-53` list, `:337-345` detail, `:423-429` pdf). Ebenso `compliance.py:45-56`, `reports.py:44-60`, `employees.py:229-252`, `shifts.py:229-259` (Permission-Matrix nach shift.status). Jede dieser Stellen ist eine potenzielle Lücke, wenn sie beim Kopieren vergessen wird — es gibt keinen zentralen „scope to own employee"-Helper. | s. Belege |
| **HOCH** | **„API-Key-Scopes nicht durchgesetzt" ist tatsächlich seit Phase 1 GESCHLOSSEN — aber mit einem gefährlichen Rest.** Scope-Enforcement existiert (`deps.py:55-64`): Write-Methoden ohne `write`/`admin`-Scope → 403. ABER: **(a)** Ein API-Key authentifiziert immer als *irgendein* Admin-User des Tenants (`deps.py:46-53`, `role=="admin"`, `limit(1)`) — d.h. jeder gültige API-Key hat faktisch **volle Admin-Rechte auf alle Admin-only-Endpoints**, die Scopes trennen nur read/write, nicht Rollen. **(b)** `scopes` null/leer wird als `["admin"]` interpretiert (`deps.py:56`, D-14 Shiftjuggler-Kompat) — ein Key ohne gesetzte Scopes ist automatisch Vollzugriff. | `deps.py:34-68` |
| MITTEL | **Superadmin-Guard akzeptiert zwei Wege** (`superadmin.py:183` etc. haben `AdminUser,SuperAdminUser` — der Parser zeigt beide; effektiv ist `SuperAdminUser` maßgeblich). Sollte im Rahmen von SEC-02 verifiziert werden, dass kein Tenant-Admin Superadmin-Funktionen erreicht. | `superadmin.py:183-399` |
| MITTEL | **SEC-03 offen:** Write-Schemas nutzen kein `ConfigDict(extra="forbid")`. Unbekannte Felder in Write-Payloads werden still ignoriert statt abgelehnt — Mass-Assignment-Fläche. Für Phase 7 geplant, nicht umgesetzt. | `.planning/REQUIREMENTS.md:16` |

### 1.3 IDOR / Tenant-Isolation

- **Im Code sauber:** Das Muster `X.tenant_id == current_user.tenant_id` erscheint **116×** über alle Router — jede Query ist tenant-scoped. Objektzugriffe (`get_employee`, `get_payroll_entry`, `download_payroll_pdf`) filtern konsequent nach tenant_id *und* prüfen bei Rolle `employee` zusätzlich Ownership (`employee.user_id == current_user.id`). Kein offensichtlicher IDOR gefunden.

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Tenant-Isolation ist kaum getestet** — echte cross-tenant-Zugriffstests (Tenant A greift auf Ressource von Tenant B) existieren nur an 3 Stellen (`test_holiday_profiles.py:217`, `test_payroll_annual.py:145`, `test_users.py:157`). Für shifts, employees, absences, payroll-calculate, reports, superadmin gibt es **keine** Mandantentrennungs-Tests. Die Isolation hängt an 116 manuell duplizierten `.where()`-Klauseln — eine einzige vergessene Klausel = IDOR-Leak, der von der Testsuite nicht erkannt würde. | Testabdeckung |
| MITTEL | Kein zentraler tenant-scoped Query-Helper/Mixin → strukturelles Duplikationsrisiko (siehe HOCH oben). | `app/api/v1/*.py` (116 Fundstellen) |

### 1.4 Input-Validierung, SQL-Injection, File-Uploads

- **SQL-Injection: keine Fläche gefunden.** Durchgängig SQLAlchemy ORM mit parametrisierten `select()`. Kein `text()`, kein String-formatiertes SQL, keine raw execute. (Die `_raw`-Treffer in payroll_service/employees sind Variablennamen, kein SQL.)
- **File-Uploads: keine.** Kein `UploadFile`/`File(` im gesamten Backend — keine Upload-Angriffsfläche.
- **Input-Validierung:** Pydantic v2 an den Grenzen, `EmailStr`, field_validators. Schwäche: `extra="forbid"` fehlt (SEC-03, s.o.); teils `Any`/`Record<string,unknown>`-Payloads.

### 1.5 Secrets & Deploy-Pipeline

| Sev | Finding | Beleg |
|---|---|---|
| **KRITISCH** | **Klartext-Drittanbieter-Passwort + Prod-API-Key auf Platte:** `backend/.env.shiftjuggler` enthält `SJ_PASS=Shiftwurst1!`, `SJ_USER=stefanprobst@gmx.net` und `VERA_KEY=<Prod-API-Key>`. Datei ist gitignored (kein Commit-Risiko), liegt aber unverschlüsselt vor. **Beide Credentials rotieren** (Passwort steht jetzt zudem in mehreren Analyse-Kontexten). | `backend/.env.shiftjuggler` · `.gitignore:2` |
| MITTEL | **Auto-Deploy auf `main` ohne im Repo erzwungenes Approval-Gate.** Jeder Push auf main deployt nach Prod. `environment: production` gesetzt, aber Required-Reviewer hängt von GitHub-Env-Settings ab (nicht im Code verifizierbar). | `.github/workflows/deploy.yml:3-5,136` |
| NIEDRIG | `NEXT_PUBLIC_DEMO_SLUG` als Build-Arg ins Frontend-Image → landet im Client-Bundle. Die beabsichtigte „Verschleierung" ist wirkungslos (kein echtes Secret). | `deploy.yml:126` · `Dockerfile.frontend:8-10` |

**Positiv:** GitHub Secrets korrekt genutzt, kein Secret geloggt, GHCR-Login via `--password-stdin`, Test-Gate erzwungen (build needs test), SSH-Key-basiert. In git-getrackten Dateien **keine** Prod-Secrets (nur Demo-`demo1234`).

### 1.6 Infrastruktur-Härtung

**Positiv:** Postgres/Redis in Prod **nicht** nach außen exponiert (kein `ports:`), Container laufen non-root (uid 1000/1001), TLS via Traefik, HSTS 1J + includeSubdomains, `contentTypeNosniff`, `frameDeny`, Traefik-Rate-Limiting auf Login. Healthchecks auf db/api/web.

| Sev | Finding | Beleg |
|---|---|---|
| MITTEL | **Fehlende Security-Header:** keine `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy` (repo-weit nirgends). | `deploy/docker-compose.yml:100-103,176-179` |
| NIEDRIG | Postgres als Bind-Mount `./data/postgres` statt Named Volume → Daten direkt im Host-FS. | `deploy/docker-compose.yml:20` |
| NIEDRIG | Kein Healthcheck auf redis/celery-worker/celery-beat. Dev-Compose exponiert Postgres/Redis auf Host (`5432`,`6379`). Version-Drift: Dev `postgres:15`, Prod `postgres:16`. | `docker-compose.yml:12,24` |

### 1.7 Dependency-Check (statisch, ohne Installation)

- **Backend** (`requirements.txt`): Versionen weitgehend aktuell (fastapi 0.115, sqlalchemy 2.0.36, pydantic 2.10). **PyJWT ≥2.12** — CVE-2024-33663 (python-jose) ist eliminiert (Phase 1). `bcrypt==4.0.1` (etwas alt, unkritisch). Keine offensichtlichen CVE-Träger. `python-multipart==0.0.18` ist eine gepatchte Version (ältere hatten DoS-CVE) — gut.
- **Frontend** (`package.json`):

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Next.js auf `14.2.0` gepinnt** — verwundbar für **CVE-2025-29927** (Middleware-Auth-Bypass via `x-middleware-subrequest`, gefixt in 14.2.25) sowie weitere 14.2.x-Advisories. **Realer Impact hier gering**, weil `middleware.ts` nur ein Demo-Cookie setzt und keine Auth-Entscheidung trifft — aber die Version sollte auf ≥14.2.25 (besser aktueller Patch) angehoben werden. | `frontend/package.json` · `src/middleware.ts:13-22` |

### 1.8 DSGVO / Datenschutz (Lohn- & Beschäftigtendaten)

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Lohndaten unverschlüsselt at rest.** Repo-weit 0 Treffer für encrypt/fernet/pgcrypto/cipher. `hourly_rate`, `total_gross`, `annual_salary_limit` etc. liegen im Klartext in Postgres; Schutz hängt allein an optionaler Host-Disk-Verschlüsselung. Für Beschäftigten-/Lohndaten (Art. 32 DSGVO) ist mind. Volume-, besser Feldverschlüsselung empfohlen. | `backend/app/models/*` · `deploy/docker-compose.yml:20` |
| **HOCH** | **Backups unverschlüsselt, selber Host, kein Off-Site.** `pg_dump \| gzip` → `vera_*.sql.gz` mit allen Lohndaten im Klartext, 30 Tage Retention, per Cron, in `./data/backups` auf demselben VPS. | `deploy/backup.sh:7,21-24` |
| MITTEL | **Lohnbeträge & PII im Klartext in `NotificationLog`.** Der volle Notification-`body` (bei Minijob-Warnungen inkl. `ytd_gross`, `annual_limit`, Namen; bei Abwesenheiten Freitext) wird dauerhaft in der DB gespeichert — keine Retention/Löschung. | `notification_service.py:79-121,495-509` |
| MITTEL | **SMTP-Passwort im Klartext** in `tenant.settings` (JSON in DB). | `admin_settings.py:63-66` · `notification_service.py:150-162` |
| MITTEL | **Unauthentifizierter iCal-Feed mit PII:** `GET /calendar/{token}.ics` (public, kein JWT) liefert Mitarbeiter-Namen + Dienst-/Ortsdaten. Schutz nur durch 32-Byte-Token in der URL (kann in Proxy-Logs landen). Rotation möglich. | `calendar.py:118-119,80-90` |
| NIEDRIG | SQL-Echo (`echo=DEBUG`) loggt bei DEBUG=True PII/hashed_password in `data/logs/backend.log`. In Prod DEBUG=false → nur bei Fehlkonfiguration relevant (siehe 1.1 HOCH). | `database.py:13` |

**Positiv:** PDF-Lohnzettel werden nicht auf Platte gespeichert (reine bytes), Download-Autorisierung korrekt (Ownership + tenant_id + `Cache-Control: no-cache`).

### 1.9 Frontend-Sicherheit

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Access- UND Refresh-Token in `localStorage`** (Klartext, für jedes JS auf der Origin lesbar). Eine einzige XSS-Lücke = vollständige, langlebige Session-Übernahme. Best Practice: Refresh-Token in httpOnly-Cookie. Entlastend: kein `dangerouslySetInnerHTML`/`eval`/`innerHTML` im gesamten `src` → XSS-Fläche klein, aber Impact maximal. | `src/store/auth.ts:36-37` · `src/lib/api.ts:14,38-39` · `accept-invite/page.tsx:38-39` |
| MITTEL | **Admin-Seiten nur per Nav-Filter versteckt, keine Route-Guards.** `layout.tsx:131-134` blendet `adminOnly`-Links für Employees aus, aber `/employees` (2625 Z.) und `/reports` haben keinen clientseitigen Guard — direkte URL-Eingabe lädt die Komponente. **Backend setzt die Autorisierung durch** (403), daher kein Datenleck, aber schlechtes UX/Defense-in-Depth. Einzige echte Guard existiert für `parent_viewer`. | `src/app/(dashboard)/layout.tsx:74-79,131-134` |
| MITTEL | Token-Refresh ohne Mutex → bei parallelen 401ern Race Condition (mehrere Refresh-Requests, Rotation kann sich selbst invalidieren). 401 ohne Refresh-Token → kein sauberer Logout/Redirect. | `src/lib/api.ts:22-53` |
| NIEDRIG | Interne IP `192.168.0.144:31367` 4× als Fallback hartkodiert, landet im Client-Bundle (Info-Leak Netz-Topologie). | `src/lib/api.ts:3` u.a. |

---

## Teil 2 — Architektur & Struktur

### 2.1 Backend-Schichtung

Sauberes 3-Schichten-Layout (`api/v1` / `services` / `models`). Models sind reine SQLAlchemy-Deklarationen ohne Logik. Payroll und Compliance delegieren korrekt an Services.

| Sev | Finding | Beleg |
|---|---|---|
| MITTEL | **Geschäftslogik in Routern:** Nur 8 von 19 Routern nutzen überhaupt einen Service. `reports.py` (478 Z.) macht Aggregation/Rundung/CSV komplett inline und ruft sogar Handler-aus-Handler (`export_csv` ruft `hours_summary`, `:395`). `employees.py` (776 Z.) trägt `_sync_employee_mirror()` und Vacation-Berechnung im Router. `superadmin.py`/`calendar.py` mit je ~18 inline `select()`. | `reports.py`, `employees.py:75`, `superadmin.py`, `calendar.py` |
| MITTEL | **Geld als `float` statt `Decimal`** in `payroll_service.py` (durchgängig `float(...)`, viele `round(...,2)`) und `compliance_service.py` (Money-Vergleiche float-basiert). Modell-Felder sind `NUMERIC`, werden aber sofort nach float gecastet → Rundungsrisiko bei Lohn-/Zuschlagsakkumulation, besonders an der Minijob-Grenze. **Für ein Lohnabrechnungssystem der gravierendste Qualitätsmangel.** | `payroll_service.py:87,173,337` · `compliance_service.py:151,166` |
| NIEDRIG | **Minijob-Grenze `6672` an 3 Stellen dupliziert** und jahres-hartkodiert (`compliance_service.py:34-35`, `payroll_service.py:188`, `reports.py:220`) — kein gemeinsames, zeitraumbezogenes Konstanten-Modul. Zuschlagssätze immerhin als benanntes Dict. | s. Belege |

### 2.2 Frontend-Struktur

| Sev | Finding | Beleg |
|---|---|---|
| MITTEL | **God-Components:** `settings/page.tsx` (2800 Z.) und `employees/page.tsx` (2625 Z.) enthalten Types, Sub-Components, Modals und Business-Logik in je einer Datei. Schwer testbar, hohe kognitive Last. | s. Pfade |
| NIEDRIG | `API_URL`-Konstante 4× dupliziert; viel `any`/`Record<string,unknown>` → schwache Typsicherheit. | `src/lib/api.ts:3` u.a. |

### 2.3 Testabdeckung (real eingeschätzt)

**Backend: ~339 Tests in 26 Dateien** (Doku sagt 268 — inzwischen mehr). Gut abgedeckt: auth (21+8), payroll (service+annual+reports), compliance-service, shifts/recurring, employees/contracts, holiday-profiles, absences, calendar, webhooks, audit-write.

**Frontend: 61 Tests in 4 Dateien** — **ausschließlich Utility-/Logik-Tests** (Vitest: recurring-shift-utils, api-payload-shaping). **Kein einziger Component-Test** (obwohl testing-library installiert), **kein E2E** (kein Playwright/Cypress). Die „61 Tests" sagen nichts über UI-, Auth- oder Guard-Verhalten aus.

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Tenant-Isolation/IDOR kaum getestet** (nur 3 Stellen) — siehe 1.3. | Testabdeckung |
| MITTEL | **Ungetestete Router:** `superadmin.py` (424 Z., cross-tenant Adminfunktionen — größte ungetestete Angriffsfläche!), `api_keys.py`, `admin_settings.py`, `notifications.py`, `matching_service.py`, compliance-Router (nur Service getestet). | s. Dateien |
| MITTEL | **Tests laufen gegen SQLite in-memory** (`conftest.py:24`), Prod ist Postgres. NUMERIC/Decimal, JSONB, FK-`ondelete`, partielle Indizes und die Postgres-REVOKE-Migration werden nie real getestet (`test_audit.py:130` skippt Migration unter SQLite). Rundungs-/Präzisionsbugs bei Geld werden so nicht zuverlässig erkannt. | `conftest.py:24` · `test_audit.py:130` |

### 2.4 Technische Schulden, größte Dateien, Alembic

- **Top-Dateien Backend:** employees.py (776), shifts.py (531), contract_types.py (523), notification_service.py (512), reports.py (478), payroll_service.py (477).
- **Alembic:** 18 Revisionen, lineare Kette, genau EIN Head, keine Branches — sauber. Revision-IDs ab `a0b1c2...` sind manuell/nicht-hex vergeben (kosmetisch). **Parallel existieren Legacy-Ad-hoc-Migrationsskripte** außerhalb Alembic (`migrate_add_*.py`, `cleanup_*.py` im backend-Root) — Migrationszustand nicht vollständig konsolidiert.
- **0 TODO/FIXME/HACK-Kommentare** — offene Arbeit steckt stattdessen in geskippten Tests.

### 2.5 Zustand des pausierten Security-Milestones

**Milestone v1.0 „Security, Hardening & Employee Self-Service"** — 7 Phasen, 28/28 Requirements gemappt.

- **Phase 1 (Security Foundation):** ✅ komplett — CVE weg, JWT-Revocation, API-Key-Scopes, CORS-Fix, Deploy-Race-Fix.
- **Phase 2 (Payroll Correctness):** ✅ komplett — ContractHistory-Mirror-Divergenz behoben.
- **Phase 3 (Audit Trail):** ⏸ **hier pausiert.** Plan 03-01 (Foundation) + 03-02 (Wiring aller Write-Endpoints) sind **in `main` gemerged und aktiv** (`audit_service.write()` in shifts/employees/payroll/absences). Plan 03-03 (Read-Endpoint + Frontend-Seite) ist an **Task 3, einem manuellen Visual-Verify-Checkpoint** pausiert (`HANDOFF.json`, `.continue-here.md`). Sobald der Nutzer „approved" sagt, soll ein Continuation-Agent Task 3 abschließen.
- **Phasen 4-7 (ESS, PWA, Shift-Swap, RBAC-Audit):** nicht begonnen. **SEC-02 (systematische RBAC-Prüfung) und SEC-03 (Pydantic extra="forbid") liegen in Phase 7 und sind offen.**

| Sev | Finding | Beleg |
|---|---|---|
| **HOCH** | **Audit-Read-Endpoint & Frontend-Seite sind NICHT in `main` gemerged.** Commits `df9bd26` (Backend `audit_log.py`) und `455c500` (Frontend-Seite) liegen nur im prunable Worktree-Branch `worktree-agent-a715c3c9`. Auf `main` (HEAD `4f37087`) fehlt der `audit_log_router` in `main.py` — d.h. **das Audit-Log ist aktuell nicht abrufbar**, obwohl geschrieben wird. Die 3 Read-Endpoint-Tests in `test_audit.py:481,509,534` sind entsprechend `@pytest.mark.skip`. Vor Weiterarbeit muss dieser Branch-Zustand geklärt/gemerged werden. | `git`: `df9bd26`/`455c500` nicht Ancestor von HEAD; `git show HEAD:backend/app/main.py` ohne audit |

---

## Teil 3 — Business Case

### 3.1 Ist-Nutzen

VERA liefert Stefan echten, konkreten Wert: rechtssichere §3b-Zuschlagsberechnung, ArbZG-Compliance-Prüfung (§4/§5), Minijob-Limit-Überwachung, PDF-Lohnzettel, Schichtplanung mit Schuljahr-/Ferien-Awareness (BW), Vertragshistorie (SCD Type 2) und Self-Service-Ansätze — alles zugeschnitten auf das **PAB-Arbeitgebermodell** (Persönliches Budget, Assistenz-Arbeitgeber). Das ist eine reale, unterversorgte Nische in DE: Menschen mit Behinderung, die als Arbeitgeber ihrer Assistenzkräfte auftreten, haben faktisch dieselben Lohn-/Arbeitsrechtspflichten wie ein Kleinbetrieb, aber keine passende Standardsoftware. VERA füllt genau diese Lücke für den Eigenbetrieb.

### 3.2 Verallgemeinerungspotenzial → Multi-Mandanten-SaaS

**Architektonisch klein, rechtlich groß.** Die technische Basis für Multi-Mandanten-Betrieb ist bereits da: durchgängige `tenant_id`-Isolation, Superadmin-Tenant-Verwaltung mit 2FA, pro-Tenant SMTP/Surcharge-Settings, Plan-Feld am Tenant. Ein zweiter zahlender Mandant wäre technisch mit überschaubarem Aufwand aufschaltbar.

**Der Schritt zum SaaS wird nicht durch Technik, sondern durch Recht & Betrieb blockiert:**

1. **Lohnabrechnungs-Compliance / ITSG-Zertifizierung (größte Hürde):** VERA berechnet aktuell **Bruttolohn + Zuschläge**, aber **keine Sozialversicherung/Lohnsteuer** (`SURCHARGE_RATES` vorhanden, aber keine SV-Sätze). Eine echte Lohnabrechnung für Dritte erfordert in DE die Meldung an Sozialversicherungsträger (SV-Meldeverfahren, DEÜV), Lohnsteueranmeldung (ELStAM/ELSTER) und für die maschinelle Verarbeitung faktisch **ITSG-System-Untersuchung/GKV-Zertifizierung** der Ausfüllhilfe (sv.net-Äquivalent). Das ist ein eigenes, mehrjähriges Compliance-Projekt mit laufender Pflege bei jeder Gesetzesänderung.
2. **Auftragsverarbeitung (AVV) & DSGVO Art. 32:** Als SaaS-Betreiber für fremde Lohndaten wäre Stefan Auftragsverarbeiter — die aktuellen DSGVO-Lücken (keine Verschlüsselung at rest, unverschlüsselte Backups, PII in Logs/NotificationLog) müssten **zwingend** geschlossen werden.
3. **Betrieb/Support:** SLAs, Mandanten-Onboarding, Backup-Restore-Garantien, Support für Nicht-Techniker.
4. **BW-Spezifität:** Feiertage/Ferien sind explizit BW-only (bewusst Out-of-Scope). Multi-Bundesland wäre für andere Mandanten nötig.

### 3.3 Minimaler Weg zur Produktisierung

Ein realistischer MVP-SaaS würde **die Lohnabrechnung nicht selbst zertifizieren**, sondern als **Schichtplanungs- + Vorerfassungs-Tool** positionieren, das strukturierte Daten an eine zertifizierte Lohn-Software / einen Steuerberater / ein Lohnbüro **exportiert** (DATEV-Lohn-Import, oder Stunden-/Zuschlags-Export). Damit umgeht man die ITSG-Hürde vollständig. Minimal nötig:
- DSGVO-Härtung (Verschlüsselung at rest + Backups, AVV-Vorlage, Löschkonzept, PII aus Logs).
- Multi-Bundesland-Feiertage/Ferien.
- Self-Service-Onboarding + Billing.
- Export-Schnittstellen (DATEV/CSV) statt eigener SV-Berechnung.
- Vollständige RBAC-Härtung (SEC-02/03) und IDOR-Testabdeckung.

### 3.4 Empfehlung

**Härten + weiterbetreiben.** VERA ist als Eigenbetriebs-Werkzeug ausgereift und wertvoll; die Priorität liegt auf dem Schließen der Security-/DSGVO-Lücken (unten), nicht auf Feature-Ausbau. **Produktisierung nur als bewusst separates, gefördertes Vorhaben** — der Nischen-Bedarf ist real (Assistenz-Arbeitgeber in DE), aber die Lohnabrechnungs-Compliance macht eine „echte" SaaS-Lohnabrechnung unwirtschaftlich für einen Einzelbetreiber. Der gangbare Produkt-Pfad ist „Planungs-/Vorerfassungs-SaaS mit Export an zertifizierte Lohnsysteme", der die ITSG-Hürde vermeidet.

---

## Priorisierte Maßnahmenliste

### Sofort (KRITISCH/HOCH — Sicherheit produktiver Personendaten)
1. **[KRITISCH]** `backend/.env.shiftjuggler`: **Shiftjuggler-Passwort und Prod-`VERA_KEY` rotieren.** Beide sind kompromittiert-verdächtig (Klartext auf Platte, jetzt in Analyse-Kontexten).
2. **[HOCH]** `config.py`: **Fail-Fast einbauen** — App-Start abbrechen, wenn `SECRET_KEY` == Default oder < 32 Zeichen; `DEBUG` in Prod hart auf false erzwingen (`APP_ENV`-Check).
3. **[HOCH]** **DSGVO: Lohndaten & Backups verschlüsseln** — mind. verschlüsseltes Backup-Ziel + Off-Site; mittelfristig Volume-/Feldverschlüsselung (Art. 32). Backup-Skript um `gpg`/`age` erweitern.
4. **[HOCH]** **Next.js auf ≥14.2.25 patchen** (CVE-2025-29927 + weitere 14.2.x-Advisories).
5. **[HOCH]** **Refresh-Token aus localStorage in httpOnly-Cookie** verlagern (XSS→Session-Takeover-Impact senken).
6. **[HOCH]** **API-Key-Modell schärfen:** Keys nicht pauschal als Admin auflösen; null/leere Scopes NICHT als admin interpretieren (D-14 überdenken); ggf. eigene service-account-Rolle statt „irgendein Admin".

### Kurzfristig (HOCH/MITTEL — Milestone fortsetzen)
7. **[HOCH]** **Branch-Zustand klären:** Audit-Read-Endpoint (`df9bd26`/`455c500`) aus `worktree-agent-a715c3c9` nach `main` mergen oder neu bauen — aktuell ist das Audit-Log nicht abrufbar. Dann Phase 3 Task 3 (Visual-Verify) abschließen.
8. **[HOCH]** **IDOR-/Tenant-Isolationstests** für shifts, employees, payroll, reports, superadmin ergänzen (Tenant A → Ressource Tenant B = 404/403).
9. **[HOCH]** **Geld auf `Decimal` umstellen** in payroll_service/compliance_service/reports — Rundungsrisiko an der Minijob-Grenze eliminieren.
10. **[MITTEL]** **SEC-02 umsetzen:** feingranulare Ownership-Prüfung aus den Handler-Bodies in einen zentralen Helper ziehen (statt 3-4× copy-paste pro Ressource).
11. **[MITTEL]** **SEC-03:** `ConfigDict(extra="forbid")` auf allen Write-Schemas (Mass-Assignment-Schutz).
12. **[MITTEL]** **CSP + Referrer-Policy + Permissions-Policy** in Traefik-Labels ergänzen.
13. **[MITTEL]** Tests für superadmin/api_keys/admin_settings/notifications hinzufügen; Testsuite gegen Postgres (testcontainers) statt SQLite.

### Mittelfristig (MITTEL/NIEDRIG — Härtung & Wartbarkeit)
14. **[MITTEL]** PII/Lohnbeträge aus `NotificationLog` entfernen oder Retention/Löschkonzept einführen; SMTP-Passwort in DB verschlüsseln.
15. **[MITTEL]** God-Components `settings`/`employees` aufteilen; `reports`/`superadmin`/`calendar` in Service-Schicht ziehen.
16. **[MITTEL]** Minijob-Grenze & SV-relevante Konstanten in ein zentrales, jahresbezogenes Modul.
17. **[NIEDRIG]** Frontend: Route-Guards für Admin-Seiten (Defense-in-Depth), Refresh-Mutex, sauberer Logout bei 401; hartkodierte interne IP entfernen.
18. **[NIEDRIG]** Legacy-Ad-hoc-Migrationsskripte in Alembic konsolidieren; Approval-Gate für Prod-Deploy in GitHub-Environment erzwingen; Dev/Prod-Postgres-Version angleichen.

---

*Analyse rein statisch/lesend durchgeführt — keine Änderungen am Projekt, keine Requests an den Prod-Server, keine venv/Installation. Test- und Endpoint-Zahlen stammen aus grep/AST-Auswertung, nicht aus einem Testlauf.*
