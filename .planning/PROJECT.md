# VERA — Schichtplanung & Abrechnung (PAB)

## What This Is

VERA ist ein Schichtplanungs- und Abrechnungssystem für Stefan (PAB-Inhaber im Arbeitgebermodell, Baden-Württemberg). Es verwaltet 2 Teilzeitkräfte und 5 Minijobber, berechnet §3b-Zuschläge, prüft ArbZG-Compliance und erzeugt Lohnzettel als PDF. Die App läuft produktiv auf einem Hetzner VPS mit echten Mitarbeiterdaten.

## Core Value

Korrekte, rechtssichere Lohnabrechnung für das PAB-Arbeitgebermodell — wenn die Lohnberechnung falsch ist, ist alles andere irrelevant.

## Requirements

### Validated

*(was bereits produktiv funktioniert)*

- ✓ JWT-Authentifizierung (access + refresh tokens, bcrypt) — v0
- ✓ Multi-Tenancy mit vollständiger tenant_id-Isolation — v0
- ✓ CRUD für Mitarbeiter inkl. Stammdaten und Verfügbarkeitspräferenzen — v0
- ✓ Schichtplanung: Erstellen, Bearbeiten, Bestätigen, Bulk-Operationen — v0
- ✓ §3b-Lohnzuschläge (Früh, Spät, Nacht, Sa, So, Feiertag) konfigurierbar — v0
- ✓ Lohnabrechnung mit PDF-Export — v0
- ✓ ArbZG-Compliance-Prüfung (§4 Pausen, §5 Ruhezeiten) — v0
- ✓ Abwesenheitsverwaltung (Mitarbeiter + Pflegeempfänger) — v0
- ✓ Kalenderansicht mit Overnight-Splitting und Mitarbeiterfarben — v0
- ✓ Benachrichtigungen: Telegram, E-Mail, Web Push — v0
- ✓ Rollenhierarchie: admin > manager > employee > parent_viewer — v0
- ✓ Regeltermine (recurring shifts) mit Schuljahr-Awareness — v0
- ✓ Vertragshistorie (SCD Type 2) mit ContractTypes — v0
- ✓ API-Key-Authentifizierung (X-API-Key Header, SHA-256) — v0
- ✓ Shiftjuggler-Sync-Script (manuell ausgeführt) — v0
- ✓ CI/CD: GitHub Actions → GHCR → VPS rolling restart — v0
- ✓ Superadmin-Bereich mit TOTP 2FA — v0
- ✓ 268 Backend-Tests, 61 Frontend-Tests — v0

### Active

*(Milestone 1: Security, Hardening & Employee Self-Service)*

#### Security & Hardening

- [ ] **SEC-01**: API-Key-Scopes werden serverseitig durchgesetzt (read/write/admin — aktuell nur gespeichert, nie geprüft)
- [ ] **SEC-02**: Alle API-Endpoints haben konsistente Rollenprüfung — systematische Lückenanalyse und Schließung
- [ ] **SEC-03**: Input-Validierung an allen Systemgrenzen: Pydantic-Schemas erzwingen strikte Typen, kein ungeprüfter User-Input
- [ ] **SEC-04**: Secrets-Audit: keine sensiblen Daten in Frontend-Bundles, .env-Handling überprüft, CORS gehärtet
- [ ] **SEC-05**: Session-Management gehärtet: Token-Rotation bei Refresh, Logout-all-devices, Token-Revocation-Mechanismus

#### Technische Schulden (kritisch)

- [ ] **DEBT-01**: ContractHistory-Mirror-Divergenz beheben — payroll/compliance liest heute von Mirror-Feldern statt aktiver History
- [ ] **DEBT-02**: `assign_contract_type` ohne `valid_from` muss immer einen ContractHistory-Eintrag anlegen
- [ ] **DEBT-03**: Demo-Daten von Produktions-Tenant trennen (separater `demo`-Tenant)
- [ ] **DEBT-04**: Schulferien 2026/27 ergänzen (aktuell nur bis Sommer 2026 korrekt) oder `workalendar` einbinden
- [ ] **DEBT-05**: Legacy `send_hourly_reminders` Celery-Task entfernen (ist ein No-Op, läuft aber stündlich)

#### Employee Self-Service

- [ ] **ESS-01**: Mitarbeiter können Schichttausch beantragen (Antrag → Admin-Genehmigung → automatischer Tausch)
- [ ] **ESS-02**: Mitarbeiter können Abwesenheit beantragen (Antrag → Admin-Genehmigung/Ablehnung mit Benachrichtigung)
- [ ] **ESS-03**: Mitarbeiter können Verfügbarkeitspräferenzen selbst aktualisieren (Admin erhält Benachrichtigung)
- [ ] **ESS-04**: Mitarbeiter können zugewiesene Schichten bestätigen/quittieren (Acknowledge-Status)

#### Audit Trail

- [ ] **AUDIT-01**: Unveränderliches Audit-Log für alle Write-Operationen (create/update/delete) mit User, Timestamp, Vorher/Nachher
- [ ] **AUDIT-02**: Audit-Log für Lohndaten-Änderungen (besonders schützenswert)
- [ ] **AUDIT-03**: Admin-UI: Audit-Trail abrufbar, filterbar nach Entity, User, Zeitraum

#### PWA / Mobile

- [ ] **PWA-01**: App ist installierbar (Web App Manifest, Service Worker, HTTPS)
- [ ] **PWA-02**: Offline-Fähigkeit: Kalender und eigene Schichten offline ansehbar (cached)
- [ ] **PWA-03**: Push-Benachrichtigungen über Service Worker (Web Push verbessert, VAPID bereits vorhanden)
- [ ] **PWA-04**: Mobile UX optimiert: Touch-Targets, Kalender-Scrolling, Formulare auf kleinen Bildschirmen

### Out of Scope

- **Native Mobile App (iOS/Android)** — PWA reicht für die Nutzerzahl aus; nativer App-Store-Overhead nicht gerechtfertigt
- **Multi-Bundesland-Unterstützung** — VERA ist explizit für Baden-Württemberg; andere Bundesländer haben andere Feiertage/Regelungen
- **Zeiterfassung per Stempeluhr / Biometrie** — Schichten werden manuell geplant, kein physisches Erfassungsgerät
- **Payroll-Integration mit DATEV/Lexware** — manueller PDF-Export ist für PAB-Modell ausreichend
- **Öffentliche API / Marketplace** — keine Drittanbieter-Anbindung über das bestehende Sync-Script hinaus

## Context

**Produktionsumgebung:** Hetzner VPS (`91.99.200.244`), Docker Compose, Traefik. Echte Mitarbeiterdaten. Änderungen brauchen sorgfältige Migrationen (Alembic, idempotent).

**Bekannte kritische Lücken:**
- API-Key-Scopes werden nicht durchgesetzt → "read-only" Key hat faktisch Admin-Rechte
- ContractHistory-Mirror kann von echter History divergieren → stille Lohnfehler möglich
- Kein Audit-Log → keine Nachvollziehbarkeit wer was geändert hat

**Technischer Stand:**
- Backend: FastAPI + SQLAlchemy 2.0 async, 268 Tests, PostgreSQL 16
- Frontend: Next.js 14 App Router, TanStack Query, Catppuccin Theme
- Auth: JWT (access 15min / refresh 7d), bcrypt, RBAC

**Team:** Stefan (PAB-Inhaber, Admin), 2 Teilzeitkräfte, 5 Minijobber — alle Mitarbeiter nutzen die App

## Constraints

- **Datenschutz**: Echte Gehaltsdaten — kein Logging von Payroll-Inhalten in Klartext, keine Secrets in Bundle
- **Migrationen**: Alembic-Migrationen müssen idempotent sein (Inspector-Check), da `create_tables()` vor `alembic upgrade` läuft
- **Backward Compatibility**: Kein Breaking Change für bestehende Shiftjuggler-Sync-Integration (X-API-Key)
- **Tests**: Alle neuen Features brauchen Backend-Tests (pytest asyncio), kritische Pfade brauchen Integration Tests
- **Deployment**: Rolling restart (erst Backend → alembic → Frontend) — Zero-Downtime-fähige Migrationen

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PWA statt Native App | Nutzerzahl und Budget rechtfertigen keinen App-Store-Aufwand | — Pending |
| Audit-Log als eigene Tabelle, nicht Event-Stream | Einfacher zu implementieren, kein Kafka/Event-Bus-Overhead für 7 User | — Pending |
| Employee Self-Service mit Admin-Approval-Flow | Direkte Änderungen zu riskant bei Live-Payroll-Daten | — Pending |
| API-Key-Scope-Enforcement als Priorität | Aktuell hat ein "read-only" Key faktisch Admin-Rechte — inakzeptables Sicherheitsrisiko | — Pending |

---

## Evolution

Dieses Dokument entwickelt sich bei Phase-Übergängen und Milestone-Abschlüssen weiter.

**Nach jeder Phase** (via `/gsd:transition`):
1. Anforderungen ungültig? → In Out of Scope verschieben mit Begründung
2. Anforderungen validiert? → In Validated verschieben mit Phase-Referenz
3. Neue Anforderungen entstanden? → In Active eintragen
4. Entscheidungen zu dokumentieren? → Key Decisions ergänzen
5. "What This Is" noch korrekt? → Aktualisieren wenn abgedriftet

**Nach jedem Milestone** (via `/gsd:complete-milestone`):
1. Vollständige Überprüfung aller Abschnitte
2. Core Value Check — noch die richtige Priorität?
3. Out of Scope prüfen — Begründungen noch valide?
4. Context mit aktuellem Stand aktualisieren

---
*Last updated: 2026-03-27 after initial project initialization*
