# VERA – Feature-Backlog & Roadmap

Stand: 2026-03-14

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

### Mitarbeiterverwaltung
- [x] CRUD + Qualifikationen + Kontaktdaten
- [x] Vertragsverlauf (SCD Type 2): ContractHistory mit valid_from/valid_until
- [x] Jahressoll (annual_hours_target) für Vollzeit/Teilzeit
- [x] Mehrvertrag-Abrechnung: wage_details-Splitting bei Satzwechsel im Monat
- [x] Notfallkontakte
- [x] Resturlaubsverwaltung (vacation_days + vacation_carryover)
- [x] Mitarbeiter-Detailseite mit iCal-Token-Anzeige
- [x] **Vertragstypen (Gruppenverträge)** – Vorlagen anlegen, MA zuweisen, Bulk-ContractHistory bei Lohnänderung

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
- [x] Alembic-Migrationen (12 Versionen, HEAD: d3e4f5a6b7c8)
- [x] Idempotente Migrationen (inspect-Check gegen create_tables()-Race)

### Tests
- [x] 199 Backend-Tests (pytest, asyncio)
- [x] 61 Frontend-Tests (vitest)
- [x] Tests für: Shifts, Templates, Employees, Auth, Absences, Payroll, Compliance,
      Calendar, Webhooks, Users, ShiftTypes, RecurringShifts, recurringEventUtils

---

## 🔄 Offen / Nächste Schritte

### Hoch priorisiert
- [ ] **iCal-Einbindungsanleitung** – In-App-Hilfe für Apple Kalender (iOS/macOS),
      Thunderbird, Outlook, Google Calendar: Schritt-für-Schritt mit Screenshots oder
      Texterklärung, wie der iCal-Feed-Link eingebunden wird.
- [ ] **Demo-Tenant re-seeden** – Produktions-Demo-Daten neu aufsetzen mit korrekten
      Mitarbeiternamen (keine echten Mitarbeiter im Demo-Tenant)
- [ ] **Notification-Events testen auf Produktion** – Telegram-Token und SendGrid-Key in
      `deploy/.env` prüfen und Benachrichtigungen end-to-end testen.

### Mittel priorisiert
- [ ] **Utilization-Report** – `GET /reports/utilization?from=&to=` (Auslastung pro MA)
      ist in der Spec erwähnt aber noch nicht implementiert.
- [ ] **Eltern-Portal (Phase 2)** – Separater Login (Rolle `parent_viewer`), lesender Zugriff
      auf Dienste, keine Gehalts-/Compliance-Daten.
- [ ] **Diensttyp-Erinnerungen testen** – Celery Beat konfiguriert, aber End-to-End-Test
      auf Produktion steht noch aus.
- [ ] **Node.js 24 GitHub Actions** – Deprecation-Warnings in CI (Node.js 20 EOL Juni 2026).
      `actions/checkout`, `actions/setup-python`, `actions/setup-node` auf v5/neueste aktualisieren.

### Niedrig priorisiert / Phase 2
- [ ] **KI-Unterstützung** – Claude API für Präferenz-Lernen und Schichtvorschläge
      (regelbasiertes Matching ist MVP-fertig).
- [ ] **Tauschpool** – Mitarbeiter können Dienste zum Tausch anbieten; Admin muss genehmigen.
- [ ] **Backup-Restore testen** – `deploy.sh backup` läuft, aber Restore-Prozess ist nicht
      dokumentiert/getestet.
- [ ] **PostgreSQL automatische Backups** – Tägliches Backup mit 30-Tage-Retention konfigurieren
      (z. B. via Cron auf VPS oder Hetzner Snapshots).
- [ ] **Rate Limiting Application-Level** – Traefik-Rate-Limiting ist aktiv, aber kein
      Application-Level-Fallback (z. B. slowapi) für nicht-Traefik-Deployments.
- [ ] **Steuerberater-Review** – Zuschlagsberechnung (§3b EStG) von Steuerberater prüfen lassen.
- [ ] **Feiertage BW 2026/27 einpflegen** – Ferienprofile für neues Schuljahr anlegen.

---

## 📋 Bekannte Einschränkungen / Technische Schulden

- **Einzelne Schichten ohne Template zeigen nur Mitarbeitername** im Kalender-Titel
  (da kein `template.name` verfügbar). Verbesserung: optionales `notes`-Feld als Fallback-Titel.
- **Seed-Demo und echte Daten gemischt** – Die Produktions-DB hat durch early adoption echte
  Mitarbeiter (Melanie Britsch, Anita Erhardt, Lena Reinbold-Holz) zusammen mit Demo-Seed-Daten.
  Empfehlung: separaten Demo-Tenant anlegen.
- **Celery/Redis in Entwicklung nicht gestartet** – Lokale Entwicklung nutzt SQLite + uvicorn
  direkt, kein Celery. Zeitgesteuerte Tasks (Erinnerungen, Cleanup) nur auf Produktion aktiv.
- **Alembic auf Produktion manuell** – `alembic upgrade head` wird zwar im Deploy-Script
  aufgerufen, aber die CI/CD-Pipeline prüft nicht ob die Migration erfolgreich war.

---

## 🏗️ Schuljahrdienste – Offene Fragen (ursprüngliche Planung, Stand MVP)

Die folgenden Fragen wurden beim Konzept gestellt; Stand der Implementierung:

| Frage | Status |
|-------|--------|
| Ferien-Profile konfigurierbar pro Tenant? | ✅ Ja – HolidayProfile mit VacationPeriod |
| Feiertage hardcodiert oder konfigurierbar? | ✅ BW per workalendar + CustomHoliday-Tabelle |
| Was passiert mit `confirmed` Diensten beim "Ab Datum"-Update? | ✅ Nur `planned`-Dienste werden aktualisiert |
| Regeltermin im Kalender als "Schiene" sichtbar? | ✅ Ja – farbiger Block (25 % Deckkraft), anklickbar |
