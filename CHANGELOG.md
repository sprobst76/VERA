# VERA – Changelog

Alle nennenswerten Änderungen werden hier dokumentiert.
Format: [Semantic Versioning](https://semver.org/), neueste Version zuerst.

---

## [0.16.0] – 2026-03-14

### Hinzugefügt
- **Vertragstyp-Zuweisung mit Startdatum** – `POST /employees/{id}/assign-contract-type`
  akzeptiert jetzt ein optionales `valid_from`-Datum. Wenn angegeben, wird der aktuell offene
  ContractHistory-Eintrag geschlossen und ein neuer mit den Parametern des Vertragstyps angelegt.
  Employee-Spiegel (contract_type, hourly_rate, etc.) wird automatisch aktualisiert.
  Frontend: Datumsfeld „Gültig ab" erscheint, sobald eine andere Vorlage gewählt wird.
- **25 Vertrags-Szenarien-Tests** – `test_contract_scenarios.py` (9 Tests) +
  `test_contract_scenarios_extended.py` (16 Tests). Personas: Clara Vogel (Kündigung),
  Marc Becker (Vollzeit-Wechsel), Sophie Kramer (3 Stufen), Jan Hartmann (Typ A→B),
  Nina Schulz (Gruppenupdate), Gregor Fischer (retroaktiv), Lena+Kai (geteilter Typ, Lena kündigt),
  Patricia Hagen (manuell+Typ+Update), Emma Braun (Payroll mit echten Schichten),
  Felix Neumann (Typ entfernen + neu zuweisen). Inkl. Randfälle und Payroll-Verifikation.

### Behoben
- **Bug: assign-contract-type ohne ContractHistory** – Die Zuweisung eines Vertragstyps
  erstellte bisher nur den FK, aber keinen Vertragseintrag → Payroll konnte keinen historischen
  Satz finden. Jetzt korrekt.

### Infrastruktur
- Backend-Tests: 224 ✓ (war 208)

---

## [0.15.0] – 2026-03-14

### Hinzugefügt
- **Einladungslink** – Admin kann per `POST /users/{id}/invite` einen Einladungslink erzeugen.
  Bei konfiguriertem SMTP wird die E-Mail automatisch gesendet; sonst wird der Link in die
  Zwischenablage kopiert (Toast). Token 7 Tage gültig.
- **Passwort-Reset** – „Passwort vergessen?"-Link auf der Login-Seite → E-Mail-Eingabe →
  `POST /auth/forgot-password` schickt Reset-Link; Token 1 Stunde gültig. Kein User-Enumeration-Leak.
- **Neue Auth-Seiten** – `/auth/forgot-password`, `/auth/reset-password?token=`, `/auth/accept-invite?token=`
  (alle im `(auth)`-Layout ohne Sidebar).
- **Kalender: Bestätigen & Löschen im Detail-Popup** – Admin/Manager sehen Schaltflächen
  direkt im Schicht-Detail-Popup: grüner „Bestätigen"-Button (für geplante Dienste) und
  roter „Löschen"-Button (für nicht-abgeschlossene Dienste).
- **Kalender: Status-Badge** – Status wird farbig im Popup angezeigt (geplant=gelb,
  bestätigt=blau, abgeschlossen=grün, storniert=rot).
- **Kalender: Legende** – Neue Einträge „Bestätigt (•)" und „Abgeschlossen (✓)" in der Legende.

### Infrastruktur
- Migration `a0b1c2d3e4f5`: `invite_token`, `invite_expires_at`, `reset_token`, `reset_expires_at`
  auf `users`-Tabelle; `FRONTEND_URL` in `config.py`.
- Alembic HEAD: `a0b1c2d3e4f5` (13 Migrationen)
- Backend-Tests: 199 ✓

---

## [0.14.0] – 2026-03-14

### Hinzugefügt
- **Vertragstypen (Gruppenverträge)** – Admin kann benannte Vertragsvorlagen anlegen
  (z. B. „Minijob Standard"). Eine Vorlage enthält: Vertragsart, Stundenlohn, Stundenlimits,
  Jahresgehaltsgrenze, Jahresstundensoll, Wochenstunden.
  - `POST /contract-types` erstellt eine Vorlage; `PUT /contract-types/{id}` mit `apply_from`
    erzeugt automatisch neue ContractHistory-Einträge für alle verknüpften Mitarbeiter.
  - `POST /employees/{id}/assign-contract-type` weist eine Vorlage einem Mitarbeiter zu.
  - `GET /contract-types/{id}/employees` listet alle Mitarbeiter einer Vorlage.
  - Frontend: VertragstypenSection in den Einstellungen (CRUD); Zuweisung per Dropdown im
    Mitarbeiter-Bearbeitungsdialog; aktive Vorlage als grauer Badge in der Mitarbeiterkarte.
- **Diensttyp in Regeltermin** – `shift_type_id` ist jetzt im RecurringShift-Model vorhanden
  und wird beim Anlegen/Bearbeiten eines Regeltermins über ein Dropdown gesetzt.
  Generierte Dienste erben automatisch den `shift_type_id` aus dem Regeltermin.
- **Ist-Zeit-Korrektur mit Admin-Bestätigungs-Workflow**
  - Mitarbeiter können nach einem bestätigten/abgeschlossenen Dienst Ist-Zeiten nacherfassen
    (`actual_start`, `actual_end`, `actual_break_minutes`, Notiz).
  - Admin/Manager bestätigt oder lehnt ab (`time_correction_status`: none → pending → confirmed/rejected).
  - Abrechnung nutzt Ist-Zeiten nur wenn `time_correction_status = "confirmed"`.
  - UI: gelber Badge „Korrektur ausstehend", grüne Ist-Zeit bei Bestätigung, roter Text bei Ablehnung.
- **Kalender-Statusanzeige für vergangene Dienste** – Optische Unterscheidung je Status:
  `completed` = transparenter Hintergrund + farbiger Rahmen + `✓`-Prefix;
  `confirmed` = doppelter Rahmen + `•`-Prefix; `cancelled` = durchgestrichen (unverändert).

### Behoben
- **Diensttyp nicht bearbeitbar in Regeltermin** – `shift_type_id` fehlte im RecurringShift-Model,
  allen Schemas (`Create`, `Update`, `UpdateFrom`) und im recurring_shift_service. Fix: Migration
  `d3e4f5a6b7c8` fügt die Spalte hinzu; Service vererbt den Typ auf generierte Dienste.

### Infrastruktur
- **Migration `c2d3e4f5a6b1` idempotent** – `create_tables()` im FastAPI-Lifespan kann Tabellen
  anlegen bevor `alembic upgrade head` läuft. Fix: Migrationen prüfen via `inspect(conn)` ob
  Tabellen/Spalten schon existieren (DuplicateTable-Schutz).
- Alembic HEAD: `d3e4f5a6b7c8` (12 Migrationen)
- Backend-Tests: 199 ✓

---

## [0.13.0] – 2026-03-14

### Hinzugefügt
- **Abwesenheit betreute Person im Kalender** – CareAbsences werden im Kalender als
  hellroter Hintergrundblock angezeigt (analog zu Urlaubsanzeige).
- **Abwesenheits-Jahresbericht** – Backend: `GET /reports/absences?year=` mit RBAC.
  Frontend: neue Sektion in Berichte-Seite (Typ-Chips + Tabelle).

### Behoben
- Regeltermine in Schulferien und an Feiertagen wurden im Kalender fälschlicherweise angezeigt.
  Fix: `recurringEventUtils.ts` filtert korrekt nach `vacation_periods`, `public_holidays`,
  `valid_from`/`valid_until` und vorhandenen DB-Schichten.

---

## [0.12.0] – 2026-03-14

### Behoben
- **Regeltermine im Kalender (Ferien/Feiertage)** – Regeltermine wurden in Schulferien und
  an Feiertagen angezeigt, obwohl keine Dienste geplant waren. Ursache: Die Kalender-Komponente
  prüfte bisher nur ob ein echter Dienst am Tag existiert, aber nicht ob der Tag in einer
  Ferienperiode oder ein Feiertag liegt.
  Fix: Logik in `lib/recurringEventUtils.ts` extrahiert, filtert jetzt korrekt nach
  `vacation_periods`, `public_holidays`, `valid_from`/`valid_until` und vorhandenen Schichten.
- **Doppelte Anzeige im Kalender** – Regeltermine und echte Dienste wurden gleichzeitig am
  selben Tag angezeigt. Fix: Regeltermine werden ausgeblendet wenn an dem Tag bereits ein
  echter Dienst in der DB existiert.
- **Regeltermine nicht anklickbar** – Regeltermine wurden als `backgroundEvents` (nicht
  interaktiv) gerendert. Fix: Regeltermine sind jetzt normale klickbare Events mit
  Hintergrundfarbe (25 % Deckkraft) und öffnen ein Info-Panel mit Vorlage, Uhrzeit und Pause.
- **Produktions-DB bereinigt** – 396 Demo-Seed-Schichten (mit Template-Zuordnung) und
  5 Demo-Templates wurden von der Produktions-Datenbank entfernt. Die 124 echten Schichten
  aus den Regeltermin-Mustern bleiben erhalten.
- **Osterferien-Schichten gelöscht** – 3 Wochenend-Schichten (04.04., 05.04., 11.04.2026)
  lagen in den Osterferien und wurden aus der Produktions-DB entfernt.

### Hinzugefügt
- **Abwesenheits-Jahresbericht** – Neuer Backend-Endpoint `GET /reports/absences?year=`
  mit Tage-Summe pro Typ und RBAC (Mitarbeiter sehen nur eigene). Neue Sektion in der
  Berichte-Seite mit Typ-Zusammenfassung (Chips) und tabellarischer Ansicht.
- **`lib/recurringEventUtils.ts`** – Reine, testbare Hilfsbibliothek für Regeltermin-Events.
  Funktionen: `buildSkipSet`, `buildRecurringEventsForShift`, `buildAllRecurringEvents`.
- **15 neue Frontend-Unit-Tests** für `recurringEventUtils` (61 Tests gesamt).
- **`cleanup_easter_shifts.py`** – Einmal-Script zum sicheren Löschen von Schichten in einem
  Ferienzeitraum auf der Produktions-DB (mit Vorschau + Bestätigungsabfrage).

---

## [0.11.0] – 2026-03-14

### Hinzugefügt
- **Jahressoll (annual_hours_target)** – Vollzeit/Teilzeit-Mitarbeiter können ein Jahresstunden-
  Soll bekommen. Abrechnung berechnet Monatssoll, YTD-Stunden, anteiliges Soll bei
  unterjährigem Eintritt und verbleibende Stunden.
- **Mehrvertrag-Abrechnung (wage_details)** – Wenn sich Stundenlohn oder Vertragsart mitten
  im Monat ändert, werden Dienste exakt aufgesplittet. `wage_details`-JSON enthält pro Periode:
  Zeitraum, Stunden, Satz, Betrag.
- **Vertragsverlauf-Vorschau** – Beim Anlegen einer neuen Vertragsperiode erscheint eine
  Vorschau-Box mit Monatssoll und geschätztem Gehalt.
- **Pool-Schicht Notifications** – `notify_pool_shift_open`: Alle aktiven Mitarbeiter werden
  per Telegram/E-Mail benachrichtigt wenn eine Schicht ohne Mitarbeiter angelegt wird.
- **Claim-Notification** – `notify_shift_claimed`: Admin/Manager wird benachrichtigt wenn
  ein Mitarbeiter eine offene Schicht annimmt.
- **Minijob-Limit Warnings** – `notify_minijob_limit`: Warnung bei 80 % und 95 % des
  Jahresgehaltslimits nach Abrechnung.
- **Drag & Drop im Kalender** – Admin/Manager können Dienste per Drag & Drop verschieben
  und in der Größe ändern (react-big-calendar DnD-Addon). Compliance-Prüfung bei Fehler.
- **Notfallkontakte** – Mitarbeiter können Notfallkontakt (Name + Telefon) hinterlegen.
- **Resturlaubsverwaltung** – `vacation_days`, `vacation_carryover` an Mitarbeitern;
  Urlaubsstatus in Abwesenheits-Verwaltung; Übersicht auf Dashboard.
- **Diensttypen (ShiftTypes)** – Konfigurierbare Diensttypen mit Farbe, Beschreibung und
  optionalen Erinnerungsbenachrichtigungen. Celery Beat feuert Erinnerungen X Minuten vor
  Schichtbeginn.
- **Diensttypen-Report** – Auswertung der Schichten pro Diensttyp in der Berichte-Seite.
- **Benutzerverwaltung** – Admin kann alle Nutzer des Tenants verwalten (Einstellungen-Seite).
- **Kalenderfreigabe-UI** – iCal-Feed-URL per Knopfdruck kopieren; VALARM-Erinnerungen im
  iCal-Feed konfigurierbar.
- **Webhook-System** – Admin kann Webhooks anlegen (URL, Events). Automatischer Dispatch bei
  Schicht-Events, Abwesenheiten, Abrechnungsfreigabe.
- **API-Key-Verwaltung** – Admin kann API-Keys anlegen (Scopes: read/write/admin) und widerrufen.
- **Mitarbeiter-Matching** – `GET /shifts/{id}/suggest` gibt rangierende Mitarbeiter-Vorschläge
  basierend auf Verfügbarkeit, Qualifikation, Stundenkontingent und Ruhezeit zurück.
- **Swipe-Navigation** – Mobiles Wischen zwischen Kalenderwochen/-tagen.
- **Offline-Caching** – Service Worker cached Kalender und letzte Abrechnung (Stale-While-Revalidate).

### Behoben
- Alembic-Migration `shift_types` idempotent (IF NOT EXISTS) für Produktions-Upgrades.
- Lucide-Icon-Titel via `<span title>` statt LucideProps (TypeScript-Fehler).
- `tsconfig.json` excludes `__tests__` und `test` damit `vi` nicht im Next.js-Build auftaucht.

---

## [0.10.0] – 2026-02-28

### Hinzugefügt
- **Dienste-Pool / Claim** – Offene Schichten (ohne `employee_id`) sind für Mitarbeiter
  sichtbar. `POST /shifts/{id}/claim` weist die Schicht dem anfragenden Mitarbeiter zu
  (Compliance-Check, 409 wenn bereits belegt, 403 für Admins).
- **Vertragsverlauf (SCD Type 2)** – `ContractHistory`-Modell; `POST /employees/{id}/contracts`
  schließt alte Periode und legt neue an; Payroll nutzt historischen Stundenlohn via
  `_get_contract_at()`.
- **Abwesenheits-Genehmigungsworkflow** – `PUT /absences/{id}` mit Status approved/rejected;
  `GET /absences?status=pending`; Sidebar-Badge zählt offene Anträge (Admin/Manager).
- **Web Push Notifications** – VAPID-Keys, `PushSubscription`-Modell, Service Worker Push-Handler.
- **Telegram + SendGrid** – `NotificationService.dispatch()` mit Quiet Hours, graceful
  degradation, Kanal-Präferenzen pro Mitarbeiter.
- **Compliance-Seite** – Verstöße nach ArbZG §4 (Pausen), §5 (Ruhezeit), Minijob-Limit;
  Mitarbeiter sehen nur eigene Verstöße.
- **PDF Lohnzettel-Download** – `GET /payroll/{id}/pdf` generiert Lohnzettel via reportlab.
- **SuperAdmin 2FA** – TOTP (RFC 6238, Google Authenticator kompatibel).

---

## [0.9.0] – 2026-02-15

### Hinzugefügt
- **Schuljahrdienste (Regeltermine)** – `RecurringShift`-Modell mit `valid_from`, `valid_until`,
  `holiday_profile_id`, `skip_public_holidays`. Bulk-Generierung, "Ab Datum ändern",
  Vorschau der generierten Dienste.
- **Ferienprofile** – `HolidayProfile` + `VacationPeriod` + `CustomHoliday`; BW-Preset;
  Kalender-Hintergrundfarben für Ferien und Feiertage.
- **Abwesenheit betreute Person** – `CareRecipientAbsence` mit Shift-Handling-Optionen
  (cancelled_unpaid, carry_over, paid_anyway); Mitarbeiter-Benachrichtigung.
- **iCal-Feed** – `GET /calendar/{token}.ics`; öffentlich, kein JWT;
  Employee-Token → eigene Dienste; Admin-Token → alle Dienste.
- **Recurring Shifts vollständig bearbeitbar** – Label, Zeiten, Ferien-Profil, "Ab Datum" UI.

---

## [0.8.0] – 2026-02-01

### Hinzugefügt
- **Abrechnung (Payroll)** – Lohnberechnung mit §3b-EStG-Zuschlägen (Früh 12.5 %, Spät 12.5 %,
  Nacht 25 %, Sa 25 %, So 50 %, Feiertag 125 %); Status-Workflow (draft → approved → paid);
  CSV-Export; Minijob-Limit-Status-Report.
- **Berichte** – Stundenbericht, Minijob-Auslastung, Compliance-Warnungen, Surcharge-Breakdown,
  CSV-Export.
- **Kalender** – react-big-calendar; Monat-/Woche-/Tagesansicht; Feiertagshintergrund (BW).
- **RBAC** – `EmployeePublicOut` vs `EmployeeOut`; Mitarbeiter sehen nur eigene Schichten,
  Abwesenheiten, Abrechnung, Compliance.

---

## [0.7.0] – 2026-01-15

### Hinzugefügt
- **MVP-Kern** – Tenants, Users (admin/manager/employee), JWT-Auth, Refresh Tokens.
- **Mitarbeiterverwaltung** – CRUD, Qualifikationen, Kontaktdaten, Vertragsart.
- **Dienste** – CRUD, Bulk-Create via Template, Status-Workflow, Compliance-Check bei Anlage.
- **Schicht-Templates** – Wiederverwendbare Vorlagen (Name, Zeiten, Farbe, Wochentage).
- **Abwesenheiten** – Urlaub, Krank, Unbezahlt, Sonstiges.
- **Docker Compose** – Backend + Frontend + PostgreSQL + Redis + Celery; Traefik TLS.
- **CI/CD** – GitHub Actions → GHCR → VPS SSH-Deploy; Layer-Caching (~50 s ab 2. Push).
- **SuperAdmin** – Eigene Auth-Tabelle, Tenant-Verwaltung, `/admin`-Bereich.
- **PWA** – manifest.json, Icons, Service Worker.
- **Catppuccin-Theme** – Latte (hell) + Mocha (dunkel); CSS-Variablen, ThemeToggle.

---

*Dieses Projekt folgt [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).*
