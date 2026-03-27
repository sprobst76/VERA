# Phase 1: Discussion Log

**Date:** 2026-03-27
**Areas discussed:** Logout-all behavior, CORS & Secrets

---

## Area: Logout-all behavior

**Q: When `POST /auth/logout-all` is called, what happens to the current session?**
Options: All sessions revoked incl. current / Other sessions only
→ **Selected: All sessions revoked incl. current**

**Q: Should changing password auto-revoke all sessions?**
Options: Yes auto-revoke / No keep sessions
→ **Selected: Yes, auto-revoke all sessions**

**Q: Single `POST /auth/logout` in addition to logout-all?**
Options: Logout-all only / Both single + all
→ **Selected: Logout-all only**

---

## Area: CORS & Secrets

**Q: Does anything call the API from a browser using X-API-Key?**
Options: No browser API-key calls / Yes, browser uses X-API-Key
→ **Selected: Yes, browser uses X-API-Key**

**Q: Biggest worry in secrets/config audit?**
Options: Frontend bundle exposure / VPS .env hygiene / Both equally
→ **Selected: VPS .env hygiene**

---

## Areas NOT discussed (Claude's discretion)

- **Shiftjuggler scope**: Read Shiftjuggler sync script, assign appropriate scope (write — creates/updates shifts)
- **PyJWT/passlib migration**: Pure technical replacement — no user decision needed
- **Deploy race fix**: Technical fix to deploy.yml — alembic before API start
