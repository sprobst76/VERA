#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# vera-backup.sh  –  Tägliches PostgreSQL-Backup (pg_dump + gzip)
#
# Ablage:    /srv/vera/deploy/data/backups/vera_YYYY-MM-DD_HH-MM.sql.gz
# Retention: 30 Tage (ältere Dateien werden automatisch gelöscht)
# Cron:      0 2 * * * /srv/vera/deploy/backup.sh >> /srv/vera/deploy/data/backups/backup.log 2>&1
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="/srv/vera/deploy/data/backups"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="${BACKUP_DIR}/vera_${TIMESTAMP}.sql.gz"
CONTAINER="vera-vera-db-1"
RETENTION_DAYS=30

mkdir -p "${BACKUP_DIR}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starte Backup → ${BACKUP_FILE}"

docker exec "${CONTAINER}" pg_dump -U vera -d vera \
    --no-owner \
    --no-acl \
    | gzip -9 > "${BACKUP_FILE}"

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup abgeschlossen (${SIZE})"

# Alte Backups löschen (älter als RETENTION_DAYS Tage)
DELETED=$(find "${BACKUP_DIR}" -name "vera_*.sql.gz" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${DELETED} altes Backup/s gelöscht (>${RETENTION_DAYS} Tage)"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fertig."
