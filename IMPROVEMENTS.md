# VERA – Verbesserungsanalyse

Stand: 2026-03-14 | Analyse nach vollständiger Implementierung des Vertragsverlauf-Systems.

---

## Kritisch (sollte bald behoben werden)

### 1. Membership ohne ContractHistory inkonsistent

**Problem:** Wenn `assign_contract_type` ohne `valid_from` aufgerufen wird (z. B. reine
FK-Umhängung), wird die Membership mit `date.today()` gesetzt, aber **kein ContractHistory-Eintrag**
angelegt. Das Ergebnis: Membership sagt "Mitglied seit heute" aber ContractHistory zeigt
die alten Konditionen – keine Quelle-Badge im Verlauf, Payroll rechnet mit altem Satz.

**Lösung:** Option A: `valid_from` immer erzwingen (nicht optional). Option B: Immer auch
einen ContractHistory-Eintrag anlegen wenn ein Typ zugewiesen wird.

**Empfehlung:** Im Frontend-Formular "Konditionen übernehmen"-Checkbox standardmäßig an;
bei Deaktivieren explizit warnen.

### 2. ContractType-Badge zeigt leer wenn Typ inaktiv

**Problem:** Die "Quelle"-Spalte im Mitarbeiter-Verlauf und der Vorlage-Dropdown in
ContractHistoryModal laden nur **aktive** Vertragstypen (`ct.is_active`). Wenn ein Typ
deaktiviert wird, zeigt die Spalte nichts mehr, obwohl der ContractHistory-Eintrag noch
`contract_type_id` gesetzt hat.

**Lösung:** `contractTypesApi.list()` auch inaktive zurückgeben (neuer Parameter
`include_inactive=true`), oder im Backend alle referenzierten Typen mitladen.

### 3. Fehlende Tests für neue Endpoints

**Problem:** `GET /employees/{id}/memberships`, `PUT/DELETE /employees/{id}/contracts`,
`GET /contract-types/{id}/history` sind nicht in der Test-Suite abgedeckt.

**Lösung:** Tests in `test_employees.py` + `test_contract_scenarios.py` ergänzen.

---

## Wichtig (mittelfristig)

### 4. employees/page.tsx ist monolithisch

**Problem:** Die Datei hat >2200 Zeilen und enthält EmployeeModal, ContractHistoryModal,
EmployeeCard, EmployeeDetailView und alle Verwaltungslogik in einer Komponente.
Das macht Tests, Wartung und Code-Reviews schwierig.

**Lösung:** Aufteilen in:
```
src/components/employees/
  EmployeeCard.tsx
  EmployeeModal.tsx
  ContractHistoryModal.tsx
  MembershipSection.tsx
  EmployeeDetailView.tsx
```

### 5. Employee-Mirror-Felder können aus der Sync laufen

**Problem:** `Employee.hourly_rate`, `contract_type`, etc. sind denormalisierte Spiegel-Felder
die manuell synchron gehalten werden. Wenn ContractHistory direkt per SQL editiert wird,
oder ein Edge-Case in der Mirror-Logik auftritt, divergieren Mirror und History.

**Lösung:** Computed Property beim Lesen: `employee.current_rate` löst immer aus
ContractHistory auf. Mirror-Felder werden nur noch für Abwärtskompatibilität gespeichert,
nicht mehr als Source of Truth.

### 6. Mitarbeiter anlegen ohne ContractType-Zuweisung

**Problem:** Beim Anlegen eines neuen Mitarbeiters gibt es keine Möglichkeit, direkt
einen Vertragstyp zu verknüpfen. Der Admin muss danach in den Verlauf-Tab wechseln.
Ein Schritt, der leicht vergessen wird.

**Lösung:** Im Anlege-Formular optional einen Vertragstyp wählen; Backend-Endpoint
`POST /employees` unterstützt `contract_type_id` als optionales Feld.

### 7. Keine Volltextsuche in Mitarbeiterliste

**Problem:** Bei mehr als ~15 Mitarbeitern gibt es keinen Filter/Suche. Alle werden
immer angezeigt.

**Lösung:** Suchfeld oben in der Mitarbeiterliste; filtert client-seitig auf
`first_name + last_name + contract_type`.

### 8. Retroaktive Membership-History unvollständig

**Problem:** Die Backfill-Migration erstellt für bestehende Mitarbeiter nur **einen**
Membership-Eintrag (den aktuellen). Historische Typ-Wechsel (z. B. von Typ A zu Typ B
letztes Jahr) sind nicht rekonstruierbar, da ContractHistory zwar `contract_type_id`
enthält, aber keine separate Membership-History existierte.

**Lösung (pragmatisch):** Aus bestehenden ContractHistory-Einträgen mit gesetztem
`contract_type_id` Membership-Einträge ableiten (Migration die die Gruppen zusammenfasst).

---

## Nice-to-have (langfristig)

### 9. Urlaubsplanung-Kalenderansicht

**Problem:** Genehmigte Urlaube aller Mitarbeiter sind nur in der Abwesenheits-Liste
sichtbar, nicht als Kalender-Overlay.

**Lösung:** Im Kalender optional "Urlaub" als Hintergrundlayer einblenden (analog zu
Schulferien), mit Farbe pro Mitarbeiter.

### 10. Bulk-Aktionen in Mitarbeiterverwaltung

**Problem:** Mehrere Mitarbeiter gleichzeitig einem Vertragstyp zuweisen ist nicht möglich;
jeder muss einzeln zugewiesen werden.

**Lösung:** Checkbox-Auswahl in der Mitarbeiterliste + "Vertragstyp zuweisen"-Button für
alle Ausgewählten.

### 11. Jahresübersicht Payroll

**Problem:** Die Payroll-Seite zeigt nur monatliche Einträge. Ein Jahresblick
(12 Monate, Summen, Minijob-Ausschöpfung) fehlt.

**Lösung:** `GET /payroll?year=YYYY` + Jahresübersichts-Ansicht im Frontend mit
Monats-Kacheln und Jahressumme.

### 12. Vertragstyp im Mitarbeiterkopf / Detailseite

**Problem:** Die Mitarbeiterkarte zeigt den Vertragstyp-Badge, aber in der Mitarbeiter-
Detailseite (Tab-Ansicht) ist die Gruppenmitgliedschaft nicht sofort sichtbar – man muss
erst den Verlauf-Tab öffnen.

**Lösung:** Im Header der Detailseite neben Name/Status: "Gruppe: Standard Minijob".

### 13. Automatische Compliance-Prüfung bei ContractType-Update

**Problem:** Wenn ein ContractType seine Jahresgehaltsgrenze ändert und alle verknüpften
Mitarbeiter neue ContractHistory-Einträge bekommen, wird keine Compliance-Prüfung ausgeführt.
Ein Mitarbeiter könnte dadurch unbemerkt unter die Minijob-Grenze fallen.

**Lösung:** Nach Bulk-Update: Compliance-Check für alle betroffenen Mitarbeiter
(Celery-Task); Benachrichtigung wenn Warnschwelle überschritten.

### 14. Passwort-Policy & Session-Management

**Problem:** Aktuell keine Passwort-Komplexitätsregeln (außer min. 8 Zeichen im Invite/Reset).
Refresh-Tokens werden nicht invalidiert beim Passwort-Wechsel.

**Lösung:** Passwort-Policy konfigurierbar (Großbuchstabe, Sonderzeichen); Refresh-Token-
Revocation-Liste in Redis; "Alle Geräte abmelden"-Funktion.

### 15. Datenexport / Steuerberater-Schnittstelle

**Problem:** Der Steuerberater braucht Lohndaten in einem standardisierten Format
(DATEV, CSV, oder PDF-Gesamtliste). Aktuell nur einzelne PDF-Lohnzettel.

**Lösung:** `GET /payroll/export?year=YYYY&format=datev|csv` mit aggregierten Jahresdaten
pro Mitarbeiter, aufbereitet für Steuerberater-Software.

---

## Architektur-Langfristziele

### A. API-Versionierung

Aktuell alles unter `/api/v1/`. Wenn Breaking Changes kommen (z. B. neue Payroll-Logik),
sollte `/api/v2/` parallel betrieben werden können.

### B. Event Sourcing für Audit-Trail

Aktuell gibt es eine `audit_log`-Tabelle, aber kein vollständiges Event-Sourcing.
Für arbeitsrechtlich kritische Systeme wäre ein unveränderliches Event-Log
(wer hat wann was geändert?) wichtig.

### C. Mehrmandanten-Skalierung

Die aktuelle Row-Level-Security per `tenant_id` skaliert gut bis ~100 Tenants.
Für mehr wäre Schema-Isolation (ein PostgreSQL-Schema pro Tenant) oder separate DBs sinnvoll.

---

*Prioritäten nach: Korrektheit → Vollständigkeit → UX → Performance → Features*
