# VERA – Technische Herausforderungen & Lösungen

Dieses Dokument hält wiederkehrende Probleme, nicht-offensichtliche Lösungen und
wichtige Designentscheidungen fest, damit sie bei künftiger Entwicklung nicht neu
herausgearbeitet werden müssen.

---

## 1. SQLAlchemy Async + Relationship-Lazy-Load (MissingGreenlet)

**Problem:** In async-SQLAlchemy-Kontexten führt der Zugriff auf Relationship-Attribute
(z. B. `profile.vacation_periods`) zu einem `MissingGreenlet`-Fehler mit `aiosqlite`
(SQLite für Tests), weil ein impliziter Lazy-Load ausgelöst wird. Mit `asyncpg`
(PostgreSQL, Produktion) wird der Fehler oft verdeckt, taucht aber unter Last auf.

**Lösung:** Immer `selectinload()` oder `joinedload()` verwenden:
```python
result = await db.execute(
    select(HolidayProfile)
    .options(
        selectinload(HolidayProfile.vacation_periods),
        selectinload(HolidayProfile.custom_holidays),
    )
    .where(...)
)
```
Nie `profile.vacation_periods = [...]` direkt zuweisen – das triggert ebenfalls einen Lazy-Load.

**Betroffen:** `holiday_profiles.py`, `recurring_shifts.py`

---

## 2. SQLite in Tests vs. PostgreSQL in Produktion

**Problem:** `aiosqlite` für Tests zeigt Fehler, die `asyncpg` in Produktion versteckt
(Lazy-Load, Decimal-Typen, ARRAY-Typen). Außerdem fehlen SQLite-Features wie
`ON DELETE CASCADE` bei manchen Versionen, UUID-Spalten verhalten sich anders.

**Lösung:**
- `StaticPool` + `check_same_thread: False` in der Test-DB-Konfiguration
- Keine PostgreSQL-spezifischen Features (ARRAY, JSONB-Operatoren) in ORM-Queries
- Alle Tests müssen mit SQLite grün sein – das sichert gleichzeitig korrekte async-Nutzung
- Decimal-Werte in Assertions mit `float()` casten, da SQLite Decimal als String zurückgibt

---

## 3. Alembic-Migrationen auf Produktions-DB

**Problem:** Wenn die lokale `vera.db` zu alt ist und `alembic_version` nicht mit dem
tatsächlichen Schema übereinstimmt, schlägt `alembic upgrade head` mit `DuplicateTable`
fehl (Tabellen existieren, aber Alembic kennt sie nicht).

**Lösung lokal:** `vera.db` löschen und `create_tables()` via `lifespan` neu erstellen.
Alembic ist für Produktion (PostgreSQL) – lokal kein Alembic nötig.

**Lösung Produktion:** Idempotente Migrationen schreiben:
```python
# Statt:
op.create_table("shift_types", ...)
# Besser:
if not op.get_bind().dialect.has_table(op.get_bind(), "shift_types"):
    op.create_table("shift_types", ...)
# Oder für Spalten:
op.execute("ALTER TABLE t ADD COLUMN IF NOT EXISTS col TYPE")
```

**Gelernt:** Migration `e3f4a5b6c7d8` musste nachträglich mit `IF NOT EXISTS` versehen
werden, da die Tabelle auf Produktion bereits durch `create_all()` existierte.

---

## 4. Next.js Build-Fehler: "Cannot find name 'vi'"

**Problem:** `npx next build` schlägt fehl mit `Cannot find name 'vi'` weil Vitest-Globals
im TypeScript-Compiler sichtbar sind (via `vitest.config.ts globals: true`).

**Lösung:** In `frontend/tsconfig.json` die Test-Verzeichnisse excluden:
```json
{
  "exclude": ["node_modules", "src/__tests__", "src/test"]
}
```

**Ursache:** Next.js nutzt `tsc --noEmit` beim Build und sieht alle Dateien im `src`-Verzeichnis,
inklusive Vitest-Testdateien die `vi`, `describe`, `it` ohne Import verwenden.

---

## 5. Regeltermine im Kalender – Doppelte Anzeige

**Problem (2026-03-14):** Nach der Umstellung von `backgroundEvents` auf reguläre Events
erschienen Regeltermine und echte Dienste gleichzeitig am selben Tag.

**Ursache:** `recurringEvents` und `events` (echte Dienste) wurden beide in `allEvents`
gemergt ohne zu prüfen ob für einen Tag bereits ein echter Dienst existiert.

**Lösung:** Regeltermine nur rendern wenn:
1. Kein echter Dienst am gleichen Tag (`shiftDates`-Set)
2. Tag liegt nicht in Schulferien (`vacation_periods`)
3. Tag ist kein Feiertag (`public_holidays`, wenn `skip_public_holidays = true`)
4. Tag liegt im `valid_from`/`valid_until`-Bereich des Regeltermin-Eintrags

Logik extrahiert in `frontend/src/lib/recurringEventUtils.ts` mit 15 Unit-Tests.

---

## 6. React Big Calendar: backgroundEvents sind nicht interaktiv

**Problem:** `backgroundEvents` in react-big-calendar sind by design nicht anklickbar –
sie rendern als farbige Streifen ohne Event-Handler. Das führt dazu, dass Regeltermine
nicht angeklickt werden können.

**Lösung:** Regeltermine als normale Events rendern (in `allEvents` statt `backgroundEvents`)
mit visueller Differenzierung (25 % Deckkraft, gleiche Farbe). `draggableAccessor` und
`resizableAccessor` explizit `false` für `type === "recurring_shift"` zurückgeben.

**Hinweis:** Die ursprüngliche Entscheidung für `backgroundEvents` war sinnvoll (nicht
versehentlich klickbar/verschiebbar), aber die Nutzeranforderung war Anklickbarkeit für
Informationszwecke. Der Kompromiss: normale Events, aber nicht draggable.

---

## 7. Demo-Daten und echte Produktionsdaten gemischt

**Problem (2026-03-14):** `seed_demo.py` wurde auf das Produktionssystem angewendet, das
bereits echte Mitarbeiter (Melanie Britsch, Anita Erhardt, Lena Reinbold-Holz) und
Regeltermine des Betreibers enthielt. Die Demo-Schichten (396 Stück mit Template-Zuordnung)
überlagerten die echten Daten.

**Symptom:** Kalender zeigte für jeden Tag zwei Einträge – echten Dienst + Demo-Schicht.

**Identifikation:** Demo-Schichten haben `template_id IS NOT NULL` (verweisen auf
Demo-Templates wie "Schulbegleitung Vormittag"). Echte Schichten haben `template_id IS NULL`
(wurden aus Regeltermin "Schule" generiert, der selbst kein Template referenziert).

**Bereinigung:**
```sql
DELETE FROM shifts WHERE template_id IS NOT NULL;  -- 396 Demo-Artefakte
DELETE FROM shift_templates;                        -- 5 Demo-Templates
-- Verbleibend: 124 echte Schichten
```

**Empfehlung:** Demo-Daten nur in separatem Tenant einspielen. Nie `seed_demo.py` auf
einen Tenant anwenden, der bereits echte Nutzerdaten enthält.

---

## 8. seed_demo.py: Schulferien beim Generieren überspringen

**Problem:** Der ursprüngliche Seed generierte Wochenend-Schichten ohne Rücksicht auf
Ferienzeiten. Schichten an Oster-Samstagen/-Sonntagen wurden angelegt.

**Lösung:** `SKIP_DATES`-Set in `seed_demo.py` aus Ferienperioden + BW-Feiertagen berechnen:
```python
SKIP_DATES = _build_skip_set()  # vacation_periods + BW_HOLIDAYS_2025_26

elif wd == 5 and current not in SKIP_DATES:  # Samstag, kein Ferientag
    ...
```

**Lerneffekt:** Seed-Daten müssen die gleiche Ferienlogik anwenden wie der produktive Code
(`recurring_shift_service.py`). Am sichersten: Seed ruft `RecurringShiftService` auf
statt eigene Datum-Iteration zu implementieren.

---

## 9. SSH-Verbindung zum VPS für DB-Operationen

**Konfiguration:** SSH-Key `id_ed25519`, User `aiplatform`, Host `91.99.200.244`.
VERA-Deployment liegt unter `/srv/vera/deploy/`.

**Nützliche Befehle:**
```bash
# PostgreSQL-Query direkt
ssh aiplatform@91.99.200.244 "cd /srv/vera/deploy && docker compose exec vera-db psql -U vera -d vera -c 'SELECT ...'"

# Alembic manuell
ssh aiplatform@91.99.200.244 "cd /srv/vera/deploy && docker compose exec vera-api alembic upgrade head"

# Container-Status
ssh aiplatform@91.99.200.244 "cd /srv/vera/deploy && docker compose ps"

# Logs
ssh aiplatform@91.99.200.244 "cd /srv/vera/deploy && docker compose logs vera-api --tail=50"
```

**Hinweis:** `docker compose` (ohne Bindestrich) nutzen – nicht das veraltete `docker-compose`.

---

## 10. CI/CD Layer-Caching

**Problem:** Erster Docker-Build ohne Cache dauerte ~8 Minuten. Jeder folgende Push war
ebenfalls langsam.

**Lösung:** GitHub Actions Cache mit `type=gha,scope=backend|frontend`:
```yaml
cache-from: type=gha,scope=backend
cache-to: type=gha,scope=backend,mode=max
```

**Ergebnis:** Ab dem 2. Push ~50 Sekunden gesamt (Backend ~27 s, Frontend ~2 min,
Deploy ~24 s). Backend-Image profitiert mehr vom Cache da Python-Dependencies stabiler.

---

## 11. Payroll: Historischer Stundenlohn

**Problem:** Wenn der Stundenlohn eines Mitarbeiters sich ändert, sollen vergangene
Abrechnungen den damals gültigen Satz behalten.

**Lösung:** `_get_contract_at(employee_id, month_start)` sucht den `ContractHistory`-Eintrag
dessen `valid_from <= month_start` und `valid_to IS NULL OR valid_to > month_start`.
Fallback auf `employee.hourly_rate` wenn keine History vorhanden.

**Erweiterung:** `_get_contracts_for_month()` gibt alle Perioden zurück die sich mit
dem Monat überschneiden – für Splitting wenn Satz mitten im Monat wechselt.

---

## 12. Minijob-Limit-Prüfung in Notification

**Problem:** `entry.contract_type` existiert nicht auf `PayrollEntry` – das Modell hat
keinen direkten Contract-Type. Der Fehler trat erst zur Laufzeit auf.

**Lösung:** `emp.contract_type` vom verknüpften `Employee`-Objekt lesen:
```python
emp = await db.get(Employee, entry.employee_id)
if emp and emp.contract_type == "minijob" and emp.annual_salary_limit:
    ...
```

---

*Zuletzt aktualisiert: 2026-03-14*
