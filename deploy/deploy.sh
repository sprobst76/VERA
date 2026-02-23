#!/bin/bash
# VERA – Deployment-Skript
# Verwendung: ./deploy/deploy.sh <command>
#
# Commands:
#   install     Erstinstallation auf dem VPS
#   update      Neuen Stand deployen (pull, rebuild, migrate)
#   migrate     Nur Alembic-Migrationen ausführen
#   seed-demo   Demo-Daten einspielen (vera-demo Tenant)
#   status      Container-Status und Health-Checks
#   logs [svc]  Logs anzeigen (Standard: vera-api)
#   backup      PostgreSQL-Backup
#   restart     Alle Container neu starten
#   stop        Alle Container stoppen

set -euo pipefail

DEPLOY_DIR="/srv/vera"
COMPOSE_FILE="deploy/docker-compose.yml"
REPO_URL="git@github.com:DEIN_GITHUB_USER/VERA.git"   # <-- anpassen

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# Ins Projekt-Verzeichnis wechseln (funktioniert auch wenn deploy.sh direkt aufgerufen wird)
if [ -f "$COMPOSE_FILE" ]; then
    :  # Schon im richtigen Verzeichnis
elif [ -f "../$COMPOSE_FILE" ]; then
    cd ..
elif [ -d "$DEPLOY_DIR" ]; then
    cd "$DEPLOY_DIR"
else
    error "Projekt-Verzeichnis nicht gefunden. Bitte erst 'install' ausführen."
fi

COMPOSE="docker compose -f $COMPOSE_FILE"

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_install() {
    info "VERA Erstinstallation..."

    # Voraussetzungen prüfen
    command -v docker >/dev/null 2>&1 || error "Docker ist nicht installiert"
    docker network ls | grep -q "ai-lab" || error "Das 'ai-lab' Docker-Netzwerk existiert nicht. Bitte zuerst Traefik aufsetzen."

    # Repo klonen
    if [ ! -d "$DEPLOY_DIR" ]; then
        info "Klone Repository nach $DEPLOY_DIR..."
        git clone "$REPO_URL" "$DEPLOY_DIR"
        cd "$DEPLOY_DIR"
    fi

    # .env erstellen
    if [ ! -f "deploy/.env" ]; then
        cp deploy/.env.example deploy/.env

        # Zufällige Secrets generieren
        POSTGRES_PASSWORD=$(openssl rand -hex 16)
        SECRET_KEY=$(openssl rand -hex 32)
        DEMO_SLUG=$(openssl rand -hex 6)

        sed -i "s/CHANGE_ME/$POSTGRES_PASSWORD/g" deploy/.env
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" deploy/.env
        sed -i "s/demo-XXXXXXXX/demo-$DEMO_SLUG/g" deploy/.env

        # Domain abfragen
        read -p "Basis-Domain (z.B. yourdomain.de): " DOMAIN
        sed -i "s/yourdomain.de/$DOMAIN/g" deploy/.env

        warning "deploy/.env wurde erstellt."
        warning "Demo-URL: https://vera.lab.$DOMAIN/demo-$DEMO_SLUG/"
        echo ""
        cat deploy/.env
        echo ""
        read -p "Drücke Enter um fortzufahren..."
    else
        warning "deploy/.env existiert bereits, wird nicht überschrieben."
    fi

    # Daten-Verzeichnisse
    mkdir -p deploy/data/postgres deploy/data/backups
    info "Daten-Verzeichnisse angelegt."

    # Images bauen und starten
    info "Baue Docker-Images..."
    $COMPOSE build

    info "Starte Container..."
    $COMPOSE up -d

    # Warten bis DB ready
    info "Warte auf Datenbank..."
    sleep 8
    until $COMPOSE exec -T vera-db pg_isready -U vera -d vera >/dev/null 2>&1; do
        sleep 2
    done
    info "Datenbank bereit."

    # Migrationen
    cmd_migrate

    echo ""
    info "Installation abgeschlossen!"
    warning "Nächste Schritte:"
    echo "  1. SuperAdmin anlegen:  ./deploy/deploy.sh superadmin"
    echo "  2. Demo-Daten:          ./deploy/deploy.sh seed-demo"
    echo "  3. Status prüfen:       ./deploy/deploy.sh status"
}

cmd_update() {
    info "VERA Update..."

    git pull
    info "Repository aktualisiert."

    info "Baue neue Images..."
    $COMPOSE build

    info "Starte Container neu..."
    $COMPOSE up -d

    sleep 5
    cmd_migrate

    info "Update abgeschlossen."
    cmd_status
}

cmd_migrate() {
    info "Führe Alembic-Migrationen aus..."
    $COMPOSE exec -T vera-api sh -c "alembic upgrade head"
    info "Migrationen angewendet."
}

cmd_seed_demo() {
    info "Spiele Demo-Daten ein..."
    $COMPOSE exec -T vera-api sh -c "python seed_demo.py"
    info "Demo-Daten eingespielt."
}

cmd_superadmin() {
    read -p "E-Mail für SuperAdmin: " SA_EMAIL
    read -s -p "Passwort (mind. 8 Zeichen): " SA_PASSWORD
    echo ""
    $COMPOSE exec -T vera-api sh -c "python create_superadmin.py '$SA_EMAIL' '$SA_PASSWORD'"
    info "SuperAdmin '$SA_EMAIL' angelegt."
}

cmd_status() {
    echo ""
    echo "═══════════════════════════════════════"
    echo "  VERA – Container Status"
    echo "═══════════════════════════════════════"
    $COMPOSE ps
    echo ""

    # Health-Check auf API
    if $COMPOSE exec -T vera-api curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        info "API Health: OK"
    else
        warning "API Health: nicht erreichbar"
    fi

    # DB-Check
    if $COMPOSE exec -T vera-db pg_isready -U vera -d vera >/dev/null 2>&1; then
        info "Datenbank: OK"
    else
        warning "Datenbank: nicht erreichbar"
    fi

    # Alembic-Stand
    echo ""
    echo "Migrations-Stand:"
    $COMPOSE exec -T vera-api sh -c "alembic current 2>/dev/null" || true
    echo ""
}

cmd_logs() {
    SERVICE="${2:-vera-api}"
    $COMPOSE logs -f --tail=100 "$SERVICE"
}

cmd_backup() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="deploy/data/backups/vera_$TIMESTAMP.sql.gz"

    info "Erstelle Backup: $BACKUP_FILE"
    $COMPOSE exec -T vera-db pg_dump -U vera vera | gzip > "$BACKUP_FILE"
    info "Backup erstellt: $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"

    # Backups älter als 30 Tage löschen
    find deploy/data/backups -name "vera_*.sql.gz" -mtime +30 -delete 2>/dev/null || true
}

cmd_restart() {
    info "Starte alle Container neu..."
    $COMPOSE restart
    info "Container neu gestartet."
    sleep 3
    cmd_status
}

cmd_stop() {
    warning "Stoppe alle Container..."
    $COMPOSE down
    info "Container gestoppt."
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMAND="${1:-help}"

case "$COMMAND" in
    install)    cmd_install ;;
    update)     cmd_update ;;
    migrate)    cmd_migrate ;;
    seed-demo)  cmd_seed_demo ;;
    superadmin) cmd_superadmin ;;
    status)     cmd_status ;;
    logs)       cmd_logs "$@" ;;
    backup)     cmd_backup ;;
    restart)    cmd_restart ;;
    stop)       cmd_stop ;;
    *)
        echo "VERA Deployment-Skript"
        echo ""
        echo "Verwendung: ./deploy/deploy.sh <command>"
        echo ""
        echo "Commands:"
        echo "  install     Erstinstallation auf dem VPS"
        echo "  update      Pull + rebuild + migrate"
        echo "  migrate     Nur Alembic-Migrationen"
        echo "  seed-demo   Demo-Tenant einspielen"
        echo "  superadmin  SuperAdmin-Account anlegen"
        echo "  status      Container-Status + Health"
        echo "  logs [svc]  Logs (Standard: vera-api)"
        echo "  backup      PostgreSQL-Backup"
        echo "  restart     Alle Container neu starten"
        echo "  stop        Alle Container stoppen"
        ;;
esac
