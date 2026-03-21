#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# vera-restore.sh  –  Datenbank aus Backup wiederherstellen
#
# Verwendung:
#   ./restore.sh <backup.sql.gz>
#
# Beispiel:
#   ./restore.sh /srv/vera/deploy/data/backups/vera_2026-03-20_02-00.sql.gz
#
# Voraussetzungen:
#   - Docker Compose Stack läuft (vera-vera-db-1 muss erreichbar sein)
#   - Script muss als Benutzer mit Docker-Zugriff ausgeführt werden
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_FILE="${1:-}"
CONTAINER="vera-vera-db-1"
COMPOSE_FILE="/srv/vera/deploy/docker-compose.yml"
COMPOSE="docker compose -p vera -f ${COMPOSE_FILE}"

# ── Eingabeprüfung ────────────────────────────────────────────────────────────

if [[ -z "${BACKUP_FILE}" ]]; then
    echo "Fehler: Kein Backup-Datei angegeben."
    echo "Verwendung: $0 <backup.sql.gz>"
    echo ""
    echo "Verfügbare Backups:"
    ls -lht /srv/vera/deploy/data/backups/vera_*.sql.gz 2>/dev/null | head -10 || echo "  (keine Backups gefunden)"
    exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "Fehler: Datei nicht gefunden: ${BACKUP_FILE}"
    exit 1
fi

# ── Sicherheitsabfrage ───────────────────────────────────────────────────────

echo "════════════════════════════════════════════════════════════════"
echo "  VERA Datenbank-Restore"
echo "════════════════════════════════════════════════════════════════"
echo "  Backup-Datei: ${BACKUP_FILE}"
echo "  Größe:        $(du -sh "${BACKUP_FILE}" | cut -f1)"
echo ""
echo "  ACHTUNG: Die aktuelle Datenbank wird vollständig überschrieben!"
echo "  Alle Daten seit dem Backup-Zeitpunkt gehen verloren."
echo ""
read -r -p "  Wirklich fortfahren? [ja/NEIN] " CONFIRM

if [[ "${CONFIRM}" != "ja" ]]; then
    echo "Abgebrochen."
    exit 0
fi

echo ""

# ── Services stoppen ─────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stoppe API und Web-Services..."
${COMPOSE} stop vera-api vera-web vera-celery-worker vera-celery-beat 2>/dev/null || true

# ── Datenbank neu aufsetzen ──────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Lösche bestehende Datenbank..."
docker exec "${CONTAINER}" psql -U vera -d postgres -c "DROP DATABASE IF EXISTS vera;" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Erstelle leere Datenbank..."
docker exec "${CONTAINER}" psql -U vera -d postgres -c "CREATE DATABASE vera OWNER vera;" 2>&1

# ── Restore ──────────────────────────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restore aus ${BACKUP_FILE}..."
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER}" psql -U vera -d vera -q

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Datenbankinhalt wiederhergestellt."

# ── Services starten + Migrationen ──────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starte API-Service..."
${COMPOSE} start vera-api

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Warte auf API-Start (10s)..."
sleep 10

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Führe Alembic-Migrationen aus..."
API_CONTAINER=$(${COMPOSE} ps -q vera-api)
docker exec "${API_CONTAINER}" alembic upgrade head

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starte verbleibende Services..."
${COMPOSE} start vera-web vera-celery-worker vera-celery-beat 2>/dev/null || true

# ── Verifikation ─────────────────────────────────────────────────────────────

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Status nach Restore:"
${COMPOSE} ps

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Restore abgeschlossen!"
echo "  Bitte prüfen: https://vera.lab.halbewahrheit21.de"
echo "════════════════════════════════════════════════════════════════"
