#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# vera-backup.sh  –  Tägliches PostgreSQL-Backup (pg_dump + gzip)
#
# Ablage:    /srv/vera/deploy/data/backups/vera_YYYY-MM-DD_HH-MM.sql.gz
# Retention: 30 Tage (ältere Dateien werden automatisch gelöscht) — NUR wenn das
#            heutige Backup erfolgreich war, sonst würde ein Ausfalltag das
#            letzte gute Backup mit wegräumen (siehe Vorfall 2026-07-06).
# Cron:      0 2 * * * /srv/vera/deploy/backup.sh >> /srv/vera/deploy/data/backups/backup.log 2>&1
#
# Alerting (optional): Setze in deploy/.env zusätzlich zum vorhandenen
#   TELEGRAM_BOT_TOKEN auch OPS_ALERT_TELEGRAM_CHAT_ID=<deine Chat-ID>,
#   damit ein fehlgeschlagenes Backup dich per Telegram erreicht. Ohne diese
#   Variable läuft die Prüfung trotzdem — nur ohne Benachrichtigung.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

BACKUP_DIR="/srv/vera/deploy/data/backups"
ENV_FILE="/srv/vera/deploy/.env"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
BACKUP_FILE="${BACKUP_DIR}/vera_${TIMESTAMP}.sql.gz"
TMP_FILE="${BACKUP_FILE}.tmp"
CONTAINER="vera-vera-db-1"
RETENTION_DAYS=30
# Ein echter Dump gzipt auf mehrere KB; alles darunter ist mit hoher
# Wahrscheinlichkeit ein leerer/abgebrochener Dump (leeres gzip ≈ 20 Byte).
MIN_BACKUP_BYTES=1024

mkdir -p "${BACKUP_DIR}"
if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

alert() {
    local msg="$1"
    log "FEHLER: ${msg}"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${OPS_ALERT_TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${OPS_ALERT_TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=🔴 VERA-Backup FEHLGESCHLAGEN auf $(hostname): ${msg}" \
            > /dev/null || log "Telegram-Alert konnte nicht gesendet werden"
    fi
}

log "Starte Backup → ${BACKUP_FILE}"

docker exec "${CONTAINER}" pg_dump -U vera -d vera --no-owner --no-acl \
    2> "${TMP_FILE}.err" | gzip -9 > "${TMP_FILE}"
DUMP_STATUS=${PIPESTATUS[0]}

if [ "${DUMP_STATUS}" -ne 0 ]; then
    alert "pg_dump-Exitcode ${DUMP_STATUS}: $(tail -c 500 "${TMP_FILE}.err" 2>/dev/null)"
    rm -f "${TMP_FILE}" "${TMP_FILE}.err"
    exit 1
fi

ACTUAL_SIZE=$(stat -c%s "${TMP_FILE}" 2>/dev/null || echo 0)
if [ "${ACTUAL_SIZE}" -lt "${MIN_BACKUP_BYTES}" ]; then
    alert "Backup-Datei verdächtig klein (${ACTUAL_SIZE} Byte) — vermutlich leerer Dump. NICHT übernommen, alte Backups bleiben unangetastet."
    rm -f "${TMP_FILE}" "${TMP_FILE}.err"
    exit 1
fi

# Erst nach erfolgreicher Größenprüfung an den finalen Pfad verschieben —
# vorher existiert unter BACKUP_FILE keine (halbfertige) Datei.
mv "${TMP_FILE}" "${BACKUP_FILE}"
rm -f "${TMP_FILE}.err"

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
log "Backup abgeschlossen (${SIZE})"

# Alte Backups löschen (älter als RETENTION_DAYS Tage) — nur wenn wir bis
# hierhin gekommen sind, also das heutige Backup gültig ist.
DELETED=$(find "${BACKUP_DIR}" -name "vera_*.sql.gz" -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)
if [ "${DELETED}" -gt 0 ]; then
    log "${DELETED} altes Backup/s gelöscht (>${RETENTION_DAYS} Tage)"
fi

log "Fertig."
