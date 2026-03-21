# VERA – Feature-Backlog & Roadmap

Stand: 2026-03-16 (aktualisiert)

---

## ✅ Erledigt (MVP vollständig)

### Kernplanung
- [x] Schicht-CRUD + Bulk-Create via Template
- [x] Schicht-Templates (Name, Zeiten, Farbe, Wochentage)
- [x] Status-Workflow: planned → confirmed → completed / cancelled
- [x] Drag & Drop im Kalender (Admin/Manager)
- [x] Dienste-Pool: Mitarbeiter können offene Schichten annehmen (Claim)
- [x] Schuljahrdienste (Regeltermine): valid_from/valid_until, Ferien/Feiertage überspringen
- [x] Regeltermine im Kalender: anklickbar mit Info-Panel, keine Doppelanzeigeung, keine Anzeige in Ferien
- [x] "Ab Datum ändern" für Regeltermine
- [x] **Diensttyp in Regeltermin** – shift_type_id wählbar beim Anlegen/Bearbeiten, wird auf Dienste vererbt
- [x] **Ist-Zeit-Korrektur** – MA erfasst Ist-Zeiten, Admin bestätigt/lehnt ab; Abrechnung nutzt bestätigte Ist-Zeiten
- [x] **Kalender-Statusanzeige** – completed = Rahmen (transparent), confirmed = doppelter Rahmen
- [x] **Bestätigte Dienste editierbar (Admin)** – orangener Bearbeiten-Button auf confirmed-Diensten mit Warnbanner

### Mitarbeiterverwaltung
- [x] CRUD + Qualifikationen + Kontaktdaten
- [x] Vertragsverlauf (SCD Type 2): ContractHistory mit valid_from/valid_until
- [x] Jahressoll (annual_hours_target) für Vollzeit/Teilzeit
- [x] Mehrvertrag-Abrechnung: wage_details-Splitting bei Satzwechsel im Monat
- [x] Notfallkontakte
- [x] Resturlaubsverwaltung (vacation_days + vacation_carryover)
- [x] Mitarbeiter-Detailseite mit iCal-Token-Anzeige
- [x] **Vertragstypen (Gruppenverträge)** – Vorlagen anlegen, MA zuweisen, Bulk-ContractHistory bei Lohnänderung
- [x] **Eintrittsdatum (start_date)** – Rückwirkend Mitarbeiter anlegen; wird als valid_from des ersten ContractHistory-Eintrags verwendet
- [x] **Vertragsverlauf editierbar/löschbar** – PUT/DELETE /employees/{id}/contracts; Chain-Repair beim Löschen
- [x] **ContractType-Historisierung** – contract_type_history Tabelle; Verlauf in Einstellungen; Quelle-Spalte im Mitarbeiter-Verlauf
- [x] **Gruppenmitgliedschaft als eigenes Konzept** – employee_contract_type_memberships Tabelle; Verlauf-Tab statt Stammdaten; SCD-Type-2-History
- [x] **Vertragstyp-Badge im Mitarbeiterkopf** – Gruppenname als Badge in EmployeeDetailView-Header
- [x] **`_sync_employee_mirror()`** – Zentrale Hilfsfunktion für alle 8 ContractHistory-Spiegelfelder (fix: 0-Werte, fehlende Felder)
- [x] **Eltern-Portal (parent_viewer)** – Neue Rolle; sieht Kalender + Dienste (read-only),
      nur `EmployeePublicOut`, kein Lohn/Compliance/Einstellungen; Route Guard + Nav-Filter im Frontend
- [x] **Schicht-Notizfeld sichtbar** – `notes` als Fallback-Titel im Kalender (wenn kein Template);
      als Italic-Subtitle in Schicht-Karten der Dienste-Liste
- [x] **Mitarbeiter-Abwesenheiten im Kalender** – Genehmigte Abwesenheiten als farbige All-Day-Events
      (Urlaub=blau, Krank=rot, Schulurlaub=gelb); RBAC: Employee sieht nur eigene
- [x] **Datenbank-Restore-Script** – `deploy/restore.sh` mit Sicherheitsabfrage, Stop/Start Services,
      Alembic-Migrationen nach Restore; Backup-Dateien automatisch aufgelistet
- [x] **Shiftjuggler-Sync** – `backend/sync_shiftjuggler.py` (nicht in Git): SJ→VERA on-demand,
      Name-Matching, Duplikat-Check, `--dry-run`-Modus; Feldnamen müssen an echte API angepasst werden

### Urlaubs- & Abwesenheitsverwaltung
- [x] Abwesenheits-Genehmigungsworkflow (pending → approved/rejected)
- [x] Status-Filter + Sidebar-Badge für offene Anträge
- [x] Abwesenheit betreute Person (CareRecipientAbsence) mit Shift-Handling
- [x] Ferienprofile (HolidayProfile + VacationPeriod + CustomHoliday + BW-Preset)

### Compliance & Arbeitsrecht
- [x] ArbZG §4 Pausen-Check
- [x] ArbZG §5 Ruhezeit-Check (11h)
- [x] Minijob-Jahres-€-Limit (556 €/Monat, 6.672 €/Jahr)
- [x] Compliance-Seite mit RBAC (Mitarbeiter sehen nur eigene Verstöße)
- [x] Compliance-Report in Berichte-Seite

### Abrechnung & Lohn
- [x] Lohnberechnung mit §3b-EStG-Zuschlägen (Früh, Spät, Nacht, Sa, So, Feiertag)
- [x] Historischer Stundenlohn via ContractHistory
- [x] Jahressoll-Fortschritt (YTD-Stunden, Monatssoll, Restpuffer)
- [x] wage_details-Splitting bei Satzwechsel im Monat
- [x] PDF Lohnzettel-Download (reportlab)
- [x] Status-Workflow: draft → approved → paid
- [x] Minijob-Limit-Status-Report
- [x] **Genehmigungswarnung** – Inline-Bestätigungsblock vor draft→approved und approved→paid
- [x] **Jahresübersicht** – Monat/Jahr-Toggle; 12-Monats-Grid (MA × Monat), farbcodiert nach Status
- [x] **Jahres-CSV-Export** – `GET /payroll/export?year=` (Excel-kompatibel, UTF-8-BOM, Semikolon)

### Benachrichtigungen
- [x] Telegram-Bot-Benachrichtigungen
- [x] SendGrid E-Mail-Benachrichtigungen
- [x] Web Push (VAPID, Service Worker)
- [x] Quiet Hours (Europe/Berlin)
- [x] Persönliche Präferenzen (Kanäle + Events)
- [x] Ereignisse: Schicht zugewiesen, geändert, offener Pool-Dienst, Claim, Minijob-Warnung 80/95 %
- [x] Diensttyp-Erinnerungen (Celery Beat, X Minuten vor Schichtbeginn)
- [x] Abwesenheit genehmigt/abgelehnt

### Kalender & Integration
- [x] iCal-Feed (`/calendar/{token}.ics`): Employee → eigene, Admin → alle
- [x] iCal VALARM-Erinnerungen konfigurierbar
- [x] Kalenderfreigabe-UI (Token kopieren)
- [x] Swipe-Navigation (mobil)

### Mobile & UX
- [x] PWA (manifest.json, Icons, Offline-Caching via Service Worker)
- [x] Catppuccin-Theme Latte/Mocha (Dark Mode)
- [x] DemoBar mit One-Click User-Switch
- [x] Responsive Layout

### API & Berichte
- [x] API-Key-Verwaltung (Scopes: read/write/admin)
- [x] Webhook-System (CRUD + Events + Dispatch)
- [x] Reports: Stundenbericht, Minijob-Auslastung, Surcharge-Breakdown, Compliance, CSV-Export
- [x] Abwesenheits-Jahresbericht (`GET /reports/absences?year=`)
- [x] Mitarbeiter-Matching (Vorschläge für offene Schichten)

### Infrastruktur
- [x] Docker Compose (Backend + Frontend + PostgreSQL + Redis + Celery + Beat)
- [x] CI/CD: GitHub Actions → GHCR → VPS SSH-Deploy mit Layer-Caching
- [x] Traefik TLS (Cloudflare), Rate Limiting auf Auth-Endpunkten
- [x] SuperAdmin mit 2FA (TOTP)
- [x] Alembic-Migrationen (idempotent, inspect-Check gegen create_tables()-Race)
- [x] **Node.js 24 in CI** – actions/checkout@v5, setup-node@v5 (Node 24), build-push-action@v6
- [x] **PostgreSQL automatische Backups** – `deploy/backup.sh` (pg_dump + gzip, 30-Tage-Retention, Cron 02:00)

### Tests
- [x] **268 Backend-Tests** (pytest, asyncio)
- [x] **61 Frontend-Tests** (vitest)
- [x] Tests für: Shifts, Templates, Employees, Auth, Absences, Payroll, Compliance,
      Calendar, Webhooks, Users, ShiftTypes, RecurringShifts, recurringEventUtils,
      ContractScenarios (25 Tests: Personas Clara/Marc/Sophie/Jan/Nina/Gregor/Lena+Kai/Patricia/Emma/Felix),
      Membership-Endpoints (8 Tests), Payroll-Annual/Export (11 Tests), ParentViewer (9 Tests)

---

## 🔄 Offen / Nächste Schritte

### Hoch priorisiert
- [ ] **Demo-Tenant auf Produktion re-seeden** – `seed_demo.py --reset` via SSH ausführen,
      um echte Namen (Melanie Britsch, Anita Erhardt, Lena Reinbold-Holz) zu ersetzen.
      Befehl: `docker compose -p vera exec vera-api python3 seed_demo.py --reset`
- [ ] **Notification-Events auf Produktion testen** – Telegram-Token und SendGrid-Key prüfen +
      Benachrichtigungen end-to-end testen (Schicht zugewiesen, Minijob-Warnung)

### Verträge & Abrechnung
- [ ] **ContractType-Badge für inaktive Typen** – Quelle-Spalte zeigt leer wenn Typ deaktiviert

### Mittel priorisiert
- [ ] **Utilization-Report** – `GET /reports/utilization?from=&to=` (Auslastung pro MA in %)
- [ ] **Diensttyp-Erinnerungen testen** – Celery Beat konfiguriert, aber End-to-End-Test
      auf Produktion steht noch aus
- [ ] **Shiftjuggler-Sync testen** – `backend/sync_shiftjuggler.py --dry-run` ausführen,
      Feldnamen in fetch_sj_employees/fetch_sj_shifts an echte SJ-API anpassen

### Niedrig priorisiert / Phase 2
- [ ] **KI-Unterstützung** – Claude API für Präferenz-Lernen und Schichtvorschläge
      (regelbasiertes Matching ist MVP-fertig)
- [ ] **Tauschpool** – Mitarbeiter können Dienste zum Tausch anbieten; Admin muss genehmigen
- [ ] **Backup-Restore dokumentieren** – `deploy/restore.sh` vorhanden, produktiver Test
      mit echtem Backup noch ausstehend
- [ ] **Rate Limiting Application-Level** – Traefik-Rate-Limiting ist aktiv, aber kein
      Application-Level-Fallback (z. B. slowapi) für nicht-Traefik-Deployments
- [ ] **Steuerberater-Review** – Zuschlagsberechnung (§3b EStG) von Steuerberater prüfen lassen
- [ ] **Feiertage BW 2026/27 einpflegen** – Ferienprofile für neues Schuljahr anlegen

---

## 📋 Bekannte Einschränkungen / Technische Schulden

- **Seed-Demo und echte Daten gemischt** – Die Produktions-DB hat durch early adoption echte
  Mitarbeiter (Melanie Britsch, Anita Erhardt, Lena Reinbold-Holz) zusammen mit Demo-Seed-Daten.
  Empfehlung: separaten Demo-Tenant anlegen.
- **Celery/Redis in Entwicklung nicht gestartet** – Lokale Entwicklung nutzt SQLite + uvicorn
  direkt, kein Celery. Zeitgesteuerte Tasks (Erinnerungen, Cleanup) nur auf Produktion aktiv.
- **Alembic-Migrations-Check fehlt in CI** – `alembic upgrade head` wird im Deploy-Script
  aufgerufen, aber die Pipeline prüft nicht ob die Migration erfolgreich war.

---

## 🏗️ Schuljahrdienste – Offene Fragen (ursprüngliche Planung, Stand MVP)

Die folgenden Fragen wurden beim Konzept gestellt; Stand der Implementierung:

| Frage | Status |
|-------|--------|
| Ferien-Profile konfigurierbar pro Tenant? | ✅ Ja – HolidayProfile mit VacationPeriod |
| Feiertage hardcodiert oder konfigurierbar? | ✅ BW per workalendar + CustomHoliday-Tabelle |
| Was passiert mit `confirmed` Diensten beim "Ab Datum"-Update? | ✅ Nur `planned`-Dienste werden aktualisiert |
| Regeltermin im Kalender als "Schiene" sichtbar? | ✅ Ja – farbiger Block (25 % Deckkraft), anklickbar |
