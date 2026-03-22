# VERA – Changelog

Alle nennenswerten Änderungen werden hier dokumentiert.
Format: [Semantic Versioning](https://semver.org/), neueste Version zuerst.

---

## [0.22.0] – 2026-03-22

### Hinzugefügt

- **Eltern-Portal (`parent_viewer`-Rolle)** – Neue Benutzerrolle mit eingeschränktem Lesezugriff:
  sieht Kalender + Dienstliste, aber keine Lohnabrechnung, keine Einstellungen, keine Mutationen.
  Route Guard leitet automatisch auf `/calendar` um. Navigation zeigt nur erlaubte Einträge.
  Mitarbeiter werden nur als `EmployeePublicOut` (kein Gehalt) zurückgegeben.
  9 neue Backend-Tests (`test_parent_viewer.py`).

- **Schicht-Notizfeld sichtbar** – Im Kalender wird das `notes`-Feld als Fallback-Titel angezeigt
  (wenn kein Template). In Schicht-Karten der Dienste-Liste als kursive Subtitle-Zeile.

- **Mitarbeiter-Abwesenheiten im Kalender** – Genehmigte MA-Abwesenheiten erscheinen als farbige
  All-Day-Events: Urlaub (🏖️ blau), Krank (🤒 rot), Schulurlaub (📚 gelb), Sonstiges (📅 grau).
  RBAC: Mitarbeiter sehen nur eigene Abwesenheiten.

- **Shiftjuggler→VERA Sync** – `backend/sync_shiftjuggler.py` (gitignored):
  - Basic-Auth gegen `claras-team.shiftjuggler.com`, POST `/api/shift.getList`
  - Unix-Timestamps → Europe/Berlin, `assignedEmployees[0]` für MA-Daten
  - Name-Matching, Duplikat-Check (employee_id + date + start_time)
  - `--dry-run` und `--inspect` Modus
  - Konfiguration via `backend/.env.shiftjuggler` (gitignored)
  - Synced: Jan–März + März 22–April 30 (über 80 Dienste)

- **API-Key-Authentifizierung** – `X-API-Key`-Header wird jetzt tatsächlich validiert
  (SHA-256-Hash gegen `api_keys`-Tabelle). Vorher war das CRUD-only ohne echte Validierung.
  `last_used_at` wird bei jeder API-Key-Nutzung aktualisiert.

- **Restore-Script** – `deploy/restore.sh`: stoppt Services, löscht/erstellt DB,
  gunzip | psql Restore, alembic upgrade head, startet neu. Mit Sicherheitsabfrage.

- **Demo-Tenant Re-seed** – `seed_demo.py --reset`: löscht bestehenden Demo-Tenant
  per CASCADE, seedet komplett neu mit fiktiven Namen.

### Kalender-Verbesserungen

- **Overnight-Dienste gesplittet** – Dienste über Mitternacht (z.B. 21:30–06:00) werden
  als zwei zusammenhängende Events dargestellt: Teil 1 bis 00:00, Teil 2 ab 00:00 (Prefix `↳`).
  Beide Events öffnen denselben Dienst-Dialog.

- **Start bei 06:00** – Kalender scrollt automatisch auf 06:00 statt Mitternacht.

- **Stundentrennung** – Ungerade Stunden leicht heller für bessere optische Lesbarkeit.

- **Einheitlicher dünner Rahmen** – Alle Events mit `1px solid` Rahmen; `confirmed` und
  `completed` zusätzlich mit 4px linkem Akzentbalken.

- **Mitarbeiterspezifische Farben** – Events ohne Template/ShiftType erhalten eine konsistente
  Catppuccin-Farbe aus einer festen Palette pro Mitarbeiter (statt alle `#1E3A5F` navy).

### Mitarbeiter

- **5 neue Mitarbeiterinnen** in VERA angelegt (via Shiftjuggler-Daten):
  Violeta Gjocaj, Maja Juric, Rita Häusler, Nadja Kruschinski, Bärbel Many Ndengue.
  Stundenlohn + Vertragsdaten müssen noch ausgefüllt werden.

### Tests

- **268 Backend-Tests** (vorher 224) – +44 Tests:
  - `test_parent_viewer.py`: 9 Tests (Zugriffskontrolle parent_viewer-Rolle)
  - Bestehende Tests angepasst für `HTTPBearer(auto_error=False)` (401 statt 403 bei fehlendem Token)
- **61 Frontend-Tests** (vorher 39) – +22 Tests (Payroll-Annual/Export, Membership-Endpoints, ParentViewer)

---

## [0.21.0] – 2026-03-16

### Hinzugefügt

- **Bestätigte Dienste editierbar (Admin/Manager)** – In der Dienstliste erscheint
  für `confirmed`-Dienste ein orangefarbener Stift-Button. Das Edit-Modal erlaubt
  Korrekturen an geplanten Zeiten, Ist-Zeiten und Notiz mit Warn-Banner
  „Änderungen können die Abrechnung beeinflussen".

- **Warnmeldung beim Fixieren der Monatsabrechnung** – Klick auf „Genehmigen"
  (draft → approved) oder „Als bezahlt markieren" (approved → paid) öffnet jetzt
  einen Bestätigungs-Block mit Brutto-Summe und Hinweistext, bevor die Aktion
  ausgeführt wird. Verhindert unbeabsichtigtes Fixieren.

- **GitHub Actions auf Node.js 24 / Actions v5/v6 aktualisiert** – Beseitigt
  Deprecation-Warnings vor dem erzwungenen Wechsel am 2. Juni 2026
  (`actions/checkout v5`, `actions/setup-node v5`, `docker/build-push-action v6`).

### Tests

- **2 neue Backend-Tests** in `test_shifts.py`:
  - `test_admin_can_edit_confirmed_shift_times`: Admin darf Zeiten auf
    bestätigtem Dienst korrigieren; Status bleibt `confirmed`.
  - `test_employee_cannot_edit_confirmed_shift`: Mitarbeiter erhält 403.

---

## [0.20.1] – 2026-03-15

### Refactoring

- **Zentrale `_sync_employee_mirror()` Hilfsfunktion** – 5 verstreute, manuelle Sync-Blöcke
  (in `add_contract`, `update_contract`, `delete_contract`, `assign_contract_type` und dem
  Bulk-Update in `update_contract_type`) wurden durch eine einheitliche Funktion ersetzt.
  Behebt dabei drei stille Bugs:
  - `delete_contract`: fehlte `annual_hours_target`, `full_time_percentage`, `monthly_salary`
    beim Zurücksetzen des Employee-Spiegels auf den Vorgänger-Eintrag.
  - `update_contract_type` Bulk: Falsy-Check (`if ct.field:`) statt `is not None` –
    ein Feldwert von `0` würde den Mirror-Wert nicht überschreiben.
  - `assign_contract_type`: gleicher Falsy-Check-Bug in beiden Branches (in-place + neu).

---

## [0.20.0] – 2026-03-15

### Fehlerbehebungen

- **Einladungslink / Passwort-Reset-Link: falscher URL-Pfad** – Die generierten Links
  enthielten `/auth/accept-invite` und `/auth/reset-password`. Da Next.js App-Router-Gruppen
  wie `(auth)` nicht im URL erscheinen, sind die korrekten Pfade `/accept-invite` und
  `/reset-password`. Betroffen: alle Einladungs- und Passwort-Reset-E-Mails.

- **ContractTypeHistory: rückwärts-Einträge (`valid_to < valid_from`)** – Wenn ein
  Vertragstyp mit `apply_from` aus der Vergangenheit aktualisiert wurde, der aktuelle
  History-Eintrag aber ein neueres `valid_from` hatte, entstand ein rückwärts-Eintrag.
  Fix: Wenn `effective_from ≤ prev_cth.valid_from`, wird der bestehende Eintrag
  in-place aktualisiert statt ein neuer Eintrag mit kaputten Datumsangaben angelegt.

- **`assign_contract_type`: Zero-Length-Einträge** – Beim Zuweisen eines Vertragstyps
  ohne `valid_from` (Fallback: `date.today()`) entstand ein Zero-Length-Eintrag wenn
  der Mitarbeiter bereits einen `ContractHistory`-Eintrag mit demselben Datum hatte.
  Fix: gleicher In-place-Mechanismus – wenn `effective_from ≤ current_entry.valid_from`,
  wird der offene Eintrag direkt aktualisiert.

- **`PUT /contract-types/{id}/history/{hist_id}`: Mitarbeiter-ContractHistory nicht
  mitgezogen** – Eine Datumskorrektur an einem `ContractTypeHistory`-Eintrag hatte
  keinen Effekt auf die verknüpften `ContractHistory`-Einträge der Mitarbeiter.
  Fix: Der Endpoint aktualisiert nun alle Mitarbeiter-Einträge mit `valid_from == altes_Datum`
  und repariert deren Vorgänger-Einträge (`valid_to`-Korrektur).

- **Quelle-Spalte: inaktive und gelöschte Vertragstypen** – Einträge mit inaktivem
  Vertragstyp zeigten kein Badge. Fix: Inaktive Typen erhalten einen grauen
  "(inaktiv)"-Badge, gelöschte Typen (FK = NULL) einen "(gelöscht)"-Hinweis.

### Hinzugefügt

- **Edit/Delete für `ContractTypeHistory`-Einträge** – In der Konditions-Verlauf-Tabelle
  (Einstellungen → Vertragstypen → History-Icon) gibt es pro Zeile:
  - **Stift-Icon**: `valid_from` direkt in der Tabelle korrigieren (Inline-Datepicker)
  - **Papierkorb-Icon**: Eintrag löschen; die Kette (`valid_to` des Vorgängers) wird
    automatisch repariert

- **`PUT /contract-types/{id}/history/{hist_id}`** – Neuer Endpoint zum Korrigieren
  von `valid_from` und `note` eines History-Eintrags; zieht Mitarbeiter-Einträge mit.

- **`DELETE /contract-types/{id}/history/{hist_id}`** – Neuer Endpoint zum Löschen
  eines History-Eintrags (mindestens 1 Eintrag bleibt erhalten); repariert Kette.

- **8 neue Backend-Tests** in `test_memberships.py`:
  `GET /memberships` (leer), Zuweisung mit/ohne `valid_from`, Typ-Wechsel
  (Membership + ContractHistory geschlossen), Entfernung, RBAC, Name-Join.

### Datenbereinigung Produktion

- **6 kaputte Datenbankeinträge manuell entfernt** (direkte SQL-Transaktion auf VPS):
  - 2 `contract_type_history`-Einträge (Zero-Length und rückwärts, `valid_from=2026-03-14`)
  - 4 `contract_history`-Einträge bei 2 Mitarbeitern (je 1 Zero-Length + 1 rückwärts)
  - Ursache: Vertragstyp-Zuweisung wurde vor dem In-place-Fix mehrfach ausgeführt

### Infrastruktur

- `contractTypesApi.updateHistory(id, histId, data)` in `api.ts`
- `contractTypesApi.deleteHistory(id, histId)` in `api.ts`
- Backend-Tests: 246 ✓

---

## [0.19.0] – 2026-03-14

### Geändert (Breaking UX)
- **Gruppenmitgliedschaft aus Stammdaten entfernt** – Der Vertragstyp-Dropdown ist nicht mehr
  Teil der Mitarbeiter-Stammdaten. Begründung: Ein Vertragstyp ist keine Eigenschaft eines
  Mitarbeiters (wie Name oder Stundenlohn), sondern eine Gruppenzugehörigkeit – konzeptuell
  ein "Abo" auf einen Gruppenvertrag, der zukünftige Lohnänderungen automatisch mitgibt.

### Hinzugefügt
- **Neue Tabelle `employee_contract_type_memberships`** – Verlauf der Gruppenzegehörigkeit
  (SCD Type 2: valid_from / valid_to). Jede Zuweisung zu einem Vertragstyp hinterlässt einen
  datierbaren Eintrag. Backfill-Migration überträgt bestehende Zuweisungen mit
  `COALESCE(start_date, created_at::date)` als `valid_from`.
- **`GET /employees/{id}/memberships`** – Neuer Endpoint liefert den kompletten Verlauf
  inkl. aufgelöstem `contract_type_name`.
- **Verlauf-Tab: Gruppenzugehörigkeit-Block** – Ganz oben im Verlauf-Tab erscheint ein
  neuer Block mit:
  - Aktuelle Mitgliedschaft als grüner Badge (`● Standard Minijob seit 01.04.2024`)
  - "Kein Gruppenvertrag"-Badge wenn nicht zugewiesen
  - "Ändern"-Button → Inline-Formular (Typ, Gültig-ab, Notiz, Checkbox "Konditionen übernehmen")
  - Aufklappbarer Verlauf wenn > 1 Eintrag vorhanden

### Infrastruktur
- Migration `i3j4k5l6m7n8`: Neue Tabelle `employee_contract_type_memberships` + Index + Backfill
- `assign_contract_type`-Endpoint legt nun automatisch Membership-History-Einträge an
- Backend-Tests: 238 ✓

---

## [0.18.0] – 2026-03-14

### Hinzugefügt
- **ContractType-Historisierung** – Neue Tabelle `contract_type_history` speichert Lohnparameter-
  Änderungen an Vertragstypen als SCD-Type-2-Timeline. Beim Anlegen eines Typs entsteht
  automatisch der erste Eintrag; bei Lohnänderungen via PUT wird der offene Eintrag geschlossen
  und ein neuer angelegt.
- **`GET /contract-types/{id}/history`** – Endpoint für den Konditions-Verlauf eines Typs.
- **Einstellungen: History-Icon pro Vertragstyp** – Klappt eine Verlaufstabelle aus
  (Ab | Bis | €/h | Std-Limit/Mo | Jahresgrenze), aktueller Eintrag grün hervorgehoben.
- **"Quelle"-Spalte im Mitarbeiter-Verlauf** – Zeigt den ContractType-Namen als Badge
  wenn ein ContractHistory-Eintrag automatisch durch einen Vertragstyp erzeugt wurde.
  Dafür: `contract_type_id` jetzt Teil von `ContractHistoryOut`.
- **Vertragstyp-Vorlage in Verlaufs-Formular** – Beim Hinzufügen einer neuen Vertragsperiode
  kann ein bestehender Vertragstyp als Vorlage ausgewählt werden. Felder (Stundenlohn,
  Limits etc.) werden vorausgefüllt und können individuell angepasst werden.

### Infrastruktur
- Migration `h2i3j4k5l6m7`: Neue Tabelle `contract_type_history` + Index
- `ContractHistoryOut`-Schema: `contract_type_id` ergänzt
- `contractTypesApi.getHistory(id)` in `api.ts`
- Backend-Tests: 238 ✓

---

## [0.17.0] – 2026-03-14

### Hinzugefügt
- **Eintrittsdatum (start_date)** – Mitarbeiter können jetzt mit einem rückwirkenden
  Eintrittsdatum angelegt werden. `start_date` wird als `valid_from` des ersten
  ContractHistory-Eintrags verwendet (statt `date.today()`). UI: Datumsfeld in beiden
  Formularen (Inline + Modal).
- **Vertragsverlauf editierbar** – Pro Vertragsperiode in der Verlaufs-Tabelle gibt es jetzt
  Stift- und Papierkorb-Buttons:
  - `PUT /employees/{id}/contracts/{contract_id}` – ändert Felder der Periode; spiegelt auf
    Employee wenn es die aktuelle Periode ist.
  - `DELETE /employees/{id}/contracts/{contract_id}` – löscht Periode und repariert die Kette
    (Vorgänger bekommt valid_to des gelöschten Eintrags). 422 wenn nur noch 1 Eintrag vorhanden.
    Spiegelt Vorgänger-Konditionen auf Employee bei Löschen des aktuellen Eintrags.

### Behoben
- **Bug: delete_contract Mirror-Reihenfolge** – Mirror-Logik lief nach `prev.valid_to`-Änderung,
  weshalb `new_current`-Query keinen Treffer fand. Fix: Mirror BEFORE Chain-Repair.
- **Testsuite: auto-today-Problem** – Tests die Einträge mit Vergangenheitsdatum anlegen,
  nutzten `start_date` nicht → der erste Eintrag landete auf `today` und rückwirkende Inserts
  fanden keinen Container. Alle betroffenen Tests mit `start_date` behoben.

### Infrastruktur
- Migration `g1h2i3j4k5l6`: `start_date DATE NULL` auf `employees`-Tabelle
- `contractsApi.update()` + `contractsApi.delete()` in `api.ts`
- Backend-Tests: 238 ✓

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
