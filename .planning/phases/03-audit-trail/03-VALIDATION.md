---
phase: 3
slug: audit-trail
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-28
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_audit.py -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~70 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_audit.py -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 70 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-T1 | 01 | 1 | AUDIT-01 | unit | `cd backend && pytest tests/test_audit.py -k "model or index or migration" -x -q` | ❌ W0 | ⬜ pending |
| 3-01-T2 | 01 | 1 | AUDIT-01, AUDIT-05 | unit | `cd backend && pytest tests/test_audit.py -x -q` | ❌ W0 | ⬜ pending |
| 3-02-T1 | 02 | 2 | AUDIT-02 | integration | `cd backend && pytest tests/test_audit.py -k "shift" -x -q` | ❌ W0 | ⬜ pending |
| 3-02-T2 | 02 | 2 | AUDIT-02, AUDIT-03 | integration | `cd backend && pytest tests/test_audit.py -k "not api" -x -q` | ❌ W0 | ⬜ pending |
| 3-03-T1 | 03 | 3 | AUDIT-04 | integration | `cd backend && pytest tests/test_audit.py -k "api" -x -q` | ❌ W0 | ⬜ pending |
| 3-03-T2 | 03 | 3 | AUDIT-04 | e2e | `cd frontend && npx vitest run` | ❌ W0 | ⬜ pending |
| 3-03-T3 | 03 | 3 | AUDIT-04 | manual | See Manual-Only table | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_audit.py` — stubs for AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04 (Plan 01 Task 2 creates this single scaffold file covering all backend requirements)

*Note: No separate test_audit_api.py needed — API endpoint tests are included in test_audit.py. Frontend tests use the existing vitest suite.*

*Existing `backend/tests/conftest.py` with `client`, `db`, `admin_token` fixtures covers all phase requirements — no new fixtures needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL REVOKE on audit_log prevents UPDATE/DELETE | AUDIT-05 | SQLite (used in tests) does not support REVOKE; migration runs only against PostgreSQL | 1. Deploy to staging 2. Connect as `vera` user 3. Run `UPDATE audit_log SET action='x' WHERE 1=1` 4. Expect `ERROR: permission denied` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 70s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
