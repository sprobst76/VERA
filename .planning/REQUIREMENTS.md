# REQUIREMENTS — VERA Milestone 1
# Security, Hardening & Employee Self-Service

**Version:** 1.0
**Date:** 2026-03-27
**Status:** Active

---

## v1 Requirements

### Security (SEC)

- [x] **SEC-01**: API key scopes (read/write/admin) werden bei jedem Request in `deps.py` durchgesetzt — ein read-only Key kann keine Schreiboperationen ausführen
- [ ] **SEC-02**: Alle API-Endpoints werden systematisch auf konsistente Rollenprüfung geprüft; fehlende `ManagerOrAdmin`/`AdminUser`-Guards werden geschlossen
- [ ] **SEC-03**: Write-Schemas verwenden `ConfigDict(strict=True, extra="forbid")` — kein ungeprüfter User-Input passiert Pydantic-Validierung
- [x] **SEC-04**: Secrets-Audit abgeschlossen: CORS-Konfiguration überprüft, keine sensiblen Daten in Frontend-Bundles, `.env`-Handling dokumentiert
- [x] **SEC-05**: JWT-Revocation via `token_version`-Spalte auf `User`-Model — Logout-all-devices und Passwortänderung invalidieren alle bestehenden Sessions
- [x] **SEC-06**: `python-jose` ersetzt durch `PyJWT 2.12+` (CVE-2024-33663 in python-jose, Bibliothek aufgegeben)

### Infrastruktur / Deploy (INFRA)

- [x] **INFRA-01**: Deploy-Reihenfolge gefixt — Alembic läuft vollständig durch bevor der API-Server Requests annimmt (kein 5s-Race mehr)
- [x] **INFRA-02**: Legacy-Celery-Task `send_hourly_reminders` aus Beat-Schedule entfernt (ist ein No-Op, läuft aber stündlich)

### Technische Schulden — Payroll (DEBT)

- [x] **DEBT-01**: ContractHistory-Mirror-Divergenz behoben — `compliance_service.py`, `payroll_service.py`, `pdf_service.py`, `reports.py` lesen `contract_type`/`hourly_rate` aus aktiver `ContractHistory`, nicht aus Mirror-Feldern auf `Employee`
- [x] **DEBT-02**: `assign_contract_type` ohne `valid_from` legt automatisch einen `ContractHistory`-Eintrag mit `valid_from=heute` an — keine stillen Lohnfehler mehr
- [x] **DEBT-03**: Schulferien 2026/27 in `BW_SCHOOL_HOLIDAYS_2026_27` ergänzt (aktuell läuft die Liste im September 2026 ab)
- [x] **DEBT-04**: Demo-Tenant von Produktions-Tenant getrennt — Demo-Daten in eigenem `demo`-Tenant, keine Verwechslungsgefahr mit echten Mitarbeiterdaten

### Audit Trail (AUDIT)

- [x] **AUDIT-01**: `AuditLog`-Tabelle erhält composite Index auf `(tenant_id, entity_type, entity_id)` und `(tenant_id, created_at)` für performante Abfragen
- [x] **AUDIT-02**: `audit_service.write()` Hilfsfunktion (explizit, kein ORM-Event-Hook) wird in allen write-Endpoints aufgerufen: create/update/delete für Shift, Employee, PayrollEntry, ContractHistory, EmployeeAbsence
- [x] **AUDIT-03**: Payroll-Änderungen werden mit Before/After-JSON geloggt — `actual_hours`, `base_wage`, `total_gross` als strukturierte Felder
- [ ] **AUDIT-04**: Admin-UI-Seite zeigt Audit-Log filterbar nach Entity-Typ, User, Zeitraum; schreibgeschützt (nur Admin)
- [x] **AUDIT-05**: PostgreSQL REVOKE UPDATE, DELETE ON audit_logs FROM application_user — Audit-Log ist append-only auf DB-Ebene

### Employee Self-Service (ESS)

- [ ] **ESS-01**: Mitarbeiter kann Abwesenheit beantragen (`POST /api/v1/absences` mit `status=pending`); Admin genehmigt/lehnt ab mit Benachrichtigung an Mitarbeiter
- [ ] **ESS-02**: Mitarbeiter kann eigene Verfügbarkeitspräferenzen selbst aktualisieren (`PUT /api/v1/employees/me/availability`); Admin erhält Benachrichtigung über Änderung
- [ ] **ESS-03**: Mitarbeiter kann zugewiesene Schicht bestätigen/quittieren (`POST /api/v1/shifts/{id}/acknowledge`); Status `acknowledged_at` auf Shift sichtbar für Admin
- [ ] **ESS-04**: Mitarbeiter kann Schichttausch mit einem anderen Mitarbeiter beantragen (`POST /api/v1/shift-swaps`); beide Mitarbeiter + Admin erhalten Benachrichtigung; Admin genehmigt final; Compliance-Pre-Check (ArbZG) vor Durchführung
- [ ] **ESS-05**: Employee-Self-Service-Aktionen (Abwesenheitsantrag, Tausch, Quittierung) erscheinen im Audit-Log

### PWA / Mobile (PWA)

- [ ] **PWA-01**: Web App Manifest (`app/manifest.ts`) konfiguriert — App ist installierbar auf iOS und Android
- [ ] **PWA-02**: Service Worker via Serwist (`@serwist/next`) — Webpack-Build (kein Turbopack)
- [ ] **PWA-03**: Caching-Strategie pro Route dokumentiert und implementiert:
  - `NetworkOnly`: alle Auth-Endpoints, Payroll-Endpoints
  - `NetworkFirst` (1h TTL): Kalender, Schichten
  - `CacheFirst` (24h TTL): statische Assets
- [ ] **PWA-04**: Offline-Fallback: Kalender und eigene Schichten sind offline aus Cache ansehbar; deutliche UX-Anzeige bei Offline-Modus
- [ ] **PWA-05**: Web Push über Service Worker verbessert — Push-Klick öffnet relevante Seite (Deep Link), nicht nur die App-Root
- [ ] **PWA-06**: Mobile UX: Touch-Targets ≥44px, Kalender-Navigation per Swipe, Formulare scroll-fähig auf kleinen Bildschirmen

---

## v2 Requirements (deferred)

- **Per-Device-Logout** (JTI-Blocklist in Redis) — `token_version` deckt Milestone 1 ab; per-device erst wenn User danach fragt
- **Audit-Log-Export** (CSV/PDF) — Admin-UI-Ansicht reicht für v1
- **Minijob-Zwei-Monats-Ausnahme-Tracking** — §8 Abs. 2a SGB IV; selten genutzt, erhöht Komplexität
- **iOS Background Sync** — iOS 17+ unterstützt Background Sync API eingeschränkt; testen nach PWA-Launch
- **ShiftSwap-Benachrichtigungsmatrix verfeinern** — v1: einfache Benachrichtigungen; v2: konfigurierbare Eskalation
- **Eltern-Portal-Erweiterungen** — parent_viewer hat aktuell Read-only; Self-Service für Eltern ist separates Milestone-Thema

---

## Out of Scope

- **Native Mobile App (iOS/Android)** — PWA reicht für diese Nutzerzahl; kein App-Store-Aufwand
- **DATEV/Lexware-Integration** — PDF-Export ist für PAB-Modell ausreichend
- **Multi-Bundesland** — VERA ist explizit für Baden-Württemberg
- **Öffentliche API / Webhook-Marketplace** — kein Bedarf über Shiftjuggler-Sync hinaus
- **Biometrische Zeiterfassung** — Schichten werden manuell geplant
- **Vollständige Neuentwicklung Auth mit OAuth/SSO** — JWT reicht, kein Google/GitHub-Login nötig

---

## Traceability

| Req-ID | Phase | Status |
|--------|-------|--------|
| SEC-01 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| SEC-05 | Phase 1 | Complete |
| SEC-06 | Phase 1 | Complete |
| INFRA-01 | Phase 1 | Complete |
| DEBT-01 | Phase 2 | Complete |
| DEBT-02 | Phase 2 | Complete |
| DEBT-03 | Phase 2 | Complete |
| DEBT-04 | Phase 2 | Complete |
| INFRA-02 | Phase 2 | Complete |
| AUDIT-01 | Phase 3 | Complete |
| AUDIT-02 | Phase 3 | Complete |
| AUDIT-03 | Phase 3 | Complete |
| AUDIT-04 | Phase 3 | Pending |
| AUDIT-05 | Phase 3 | Complete |
| ESS-01 | Phase 4 | Pending |
| ESS-02 | Phase 4 | Pending |
| ESS-03 | Phase 4 | Pending |
| ESS-05 | Phase 4 | Pending |
| PWA-01 | Phase 5 | Pending |
| PWA-02 | Phase 5 | Pending |
| PWA-03 | Phase 5 | Pending |
| PWA-04 | Phase 5 | Pending |
| PWA-05 | Phase 5 | Pending |
| PWA-06 | Phase 5 | Pending |
| ESS-04 | Phase 6 | Pending |
| SEC-02 | Phase 7 | Pending |
| SEC-03 | Phase 7 | Pending |
