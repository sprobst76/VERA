# Shiftjuggler-Historie-Import

Einmaliges Bulk-Import-Skript: `import_shiftjuggler_history.py`. Details und Begründung
(warum keine REST-API, sondern direkte ORM-Writes) stehen im Docstring der Datei.

## Voraussetzungen

- Läuft im laufenden `vera-api`-Container (braucht das `app`-Package + DB-Zugriff)
- `.env.shiftjuggler` wird NICHT ins Docker-Image gebaut (gitignored) — Zugangsdaten
  müssen beim `docker exec` explizit als Umgebungsvariablen übergeben werden

## Ausführen

```bash
# Auf dem VPS, nach einem Deploy der main-Branch (Skript ist dann im Image):
docker exec \
  -e SJ_BASE='https://claras-team.shiftjuggler.com' \
  -e SJ_USER='<shiftjuggler-email>' \
  -e SJ_PASS='<shiftjuggler-passwort>' \
  -e VERA_TENANT_SLUG='clarasteam' \
  vera-vera-api-1 python3 /app/scripts/import_shiftjuggler_history.py --dry-run

# Nach Prüfung der Dry-Run-Ausgabe: gleicher Befehl ohne --dry-run
```

Reihenfolge: immer erst `--dry-run` (zeigt exakte Zahlen, schreibt nichts), dann der
echte Lauf. Idempotent — mehrfaches Ausführen überspringt bereits importierte
Schichten/Abwesenheiten automatisch.

## Bekannte Eigenheiten

- Shiftjuggler-Admin-/Familienaccounts (isAdmin-Flag) werden nicht als Mitarbeiter
  behandelt und übersprungen.
- Stornierte Abwesenheiten (`status: canceled`) werden übersprungen — sie sind nie
  tatsächlich eingetreten.
- Genehmigter Import-Urlaub/-Krankheit storniert automatisch überlappende Schichten
  im selben Zeitraum (repliziert die Logik aus `PUT /absences/{id}`, aber ohne
  Benachrichtigungen/Webhooks).
- Nach dem Import fehlt weiterhin `ContractHistory` für die Jahre vor der ersten
  echten Vertragsanlage in VERA — rückwirkende Lohnberechnung für 2022-2025 ist mit
  dieser Migration NICHT automatisch möglich, nur die Schicht-/Abwesenheitshistorie
  selbst wird übernommen.
