# Schichtfabrik → VERA Migration

Standalone-Skript für den einmaligen Datenumzug.

## Voraussetzungen

```bash
pip install requests
```

## Konfiguration

Entweder Umgebungsvariablen setzen:

```bash
export SF_BASE_URL='https://meine-firma.shiftjuggler.com'
export SF_EMAIL='admin@meine-firma.de'
export SF_PASSWORD='meinpasswort'
export SF_DATE_FROM='2024-01-01'
export SF_DATE_TO='2026-03-31'
```

Oder die Konstanten direkt oben in `extract_schichtfabrik.py` anpassen.

## Ausführen

```bash
cd migration/
python extract_schichtfabrik.py
```

## Ausgabe (`output/`)

| Datei | Inhalt |
|-------|--------|
| `raw_employees.json` | Mitarbeiter-Rohdaten von Schichtfabrik |
| `raw_shifts.json` | Schichten-Rohdaten |
| `raw_absences.json` | Abwesenheits-Rohdaten |
| `raw_absence_types.json` | Abwesenheitstypen |
| `vera_import.json` | Aufbereitete Daten im VERA-Format |

## Nächste Schritte nach dem Export

1. `vera_import.json` öffnen → `employees`-Array prüfen
2. Für jeden Mitarbeiter `hourly_rate`, `contract_type`, `weekly_hours` eintragen
3. Mitarbeiter in VERA über die UI anlegen
4. Falls Schichten-Import gewünscht: `_sf_emp_id` → VERA-`employee_id` mappen
