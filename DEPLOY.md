# VERA – Deployment

## Voraussetzungen

- VPS mit Docker + Docker Compose
- Bestehendes `ai-lab` Docker-Netzwerk mit Traefik (Cloudflare-Cert-Resolver)
- DNS-Einträge für `vera.lab.yourdomain.de` und die Demo-Subdomain → VPS-IP
- GitHub SSH-Zugriff auf das Repository

## Erstinstallation

```bash
# Repo auf den Server klonen
git clone git@github.com:DEIN_USER/VERA.git /srv/vera
cd /srv/vera

# Erstinstallation (interaktiv: Domain abfragen, Secrets generieren)
./deploy/deploy.sh install

# SuperAdmin-Account anlegen
./deploy/deploy.sh superadmin

# Demo-Tenant einspielen (optional)
./deploy/deploy.sh seed-demo
```

Das `install`-Kommando erledigt automatisch:
1. Prüft Voraussetzungen (Docker, `ai-lab`-Netzwerk)
2. Erstellt `deploy/.env` aus `deploy/.env.example` mit zufälligen Secrets
3. Fragt die Basis-Domain ab
4. Baut alle Docker-Images (Backend + Frontend)
5. Startet die Container
6. Führt `alembic upgrade head` aus

## Konfiguration (`deploy/.env`)

```bash
cp deploy/.env.example deploy/.env
# Werte anpassen:
#   DOMAIN, DEMO_HOST, POSTGRES_PASSWORD, SECRET_KEY, ALLOWED_ORIGINS
```

| Variable | Beschreibung |
|---|---|
| `DOMAIN` | Basis-Domain, z.B. `yourdomain.de` → Frontend auf `vera.lab.yourdomain.de` |
| `DEMO_SLUG` | Pfad-Slug für Demo-Zugang, z.B. `demo-a3f9b2c1` → erreichbar unter `/demo-a3f9b2c1/` |
| `POSTGRES_PASSWORD` | PostgreSQL-Passwort (`openssl rand -hex 16`) |
| `SECRET_KEY` | JWT-Secret (`openssl rand -hex 32`) |
| `ALLOWED_ORIGINS` | Nur eine Domain nötig: `https://vera.lab.yourdomain.de` |

## Alltägliche Befehle

```bash
./deploy/deploy.sh update      # Neuen Stand deployen (pull + rebuild + migrate)
./deploy/deploy.sh status      # Container-Status + Health-Checks
./deploy/deploy.sh logs        # API-Logs (live)
./deploy/deploy.sh logs vera-db # DB-Logs
./deploy/deploy.sh backup      # PostgreSQL-Backup nach deploy/data/backups/
./deploy/deploy.sh migrate     # Nur Alembic-Migrationen ausführen
./deploy/deploy.sh restart     # Alle Container neu starten
./deploy/deploy.sh stop        # Alle Container stoppen
```

## Architektur

```
Browser
  └─→ Traefik (ai-lab-Netzwerk, Port 443, Cloudflare TLS)
        ├─→ vera.lab.DOMAIN / PathPrefix(/api, /calendar, /health)
        │     └─→ vera-api  (FastAPI, Port 8000, 2 Worker, 256MB)
        │           └─→ vera-db  (PostgreSQL 16, intern, 256MB)
        ├─→ vera.lab.DOMAIN /
        │     └─→ vera-web  (Next.js Standalone, Port 3000, 128MB)
        └─→ vera.lab.DOMAIN /demo-abc123/    →  vera-web  (Next.js Middleware)
                                                         setzt Cookie vera_demo=1
                                                         → Redirect auf /
                                                         → DemoBar sichtbar
```

## Datenpersistenz

```
deploy/data/
├── postgres/   ← PostgreSQL-Daten (Docker Volume)
└── backups/    ← pg_dump-Backups (deploy.sh backup, 30 Tage Rotation)
```

## Neue Modelländerungen deployen

```bash
# Lokal: Migration erstellen
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "kurze beschreibung"
# Migration prüfen, dann committen
git add alembic/versions/
git commit -m "migration: kurze beschreibung"
git push

# Auf dem Server: automatisch via update
./deploy/deploy.sh update
```

## Erstes Deployment – Checkliste

- [ ] DNS: `vera.lab.DOMAIN` → VPS-IP gesetzt und propagiert
- [ ] DNS: `DEMO_HOST` → VPS-IP gesetzt und propagiert
- [ ] `ai-lab` Traefik-Netzwerk existiert: `docker network ls | grep ai-lab`
- [ ] `deploy/.env` vollständig ausgefüllt (Domain, Secrets, ALLOWED_ORIGINS)
- [ ] `./deploy/deploy.sh install` ohne Fehler
- [ ] `./deploy/deploy.sh superadmin` – SuperAdmin angelegt
- [ ] `https://vera.lab.DOMAIN` erreichbar, Login funktioniert
- [ ] SuperAdmin-Login unter `https://vera.lab.DOMAIN/admin/login`
- [ ] (Optional) `./deploy/deploy.sh seed-demo` – Demo-Tenant eingespielt
- [ ] `https://vera.lab.DOMAIN/demo-SLUG/` öffnet die App mit sichtbarer DemoBar
