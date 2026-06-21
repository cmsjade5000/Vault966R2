# Vault 966 Architecture Audit

Generated: 2026-06-21

## Scope

This audit reviewed the Vault 966 web app across security/auth, data lineage and integrity, SQLite lifecycle, frontend/product architecture, operations/deploy behavior, and test/CI coverage.

Subagent lanes:

- Security/backend: auth middleware, route protection, same-origin coverage, token exposure, validation, logging, public endpoints.
- Data architecture: SQLite lifecycle, schema/migration drift, source sync, backfills, provenance, generated clients.
- Frontend/product: templates, static JS/CSS ownership, accessibility semantics, browser state, health/review workflows.

Main-agent lane:

- Operations/deploy/test: launchd service behavior, health checks, CI, Makefile targets, lint/test commands, live-deploy assumptions.

## Already Addressed During This Audit Cycle

- Draft PR #90, `codex/same-origin-mutation-guards`: adds same-origin protection to key session-cookie mutation routes.
- Draft PR #89, `codex/shared-collection-integrity`: introduces shared structural-integrity checks for Vault Health and the audit script.

These reduce two earlier audit findings but do not remove the need for the remaining architecture work below.

## Executive Summary

Vault 966 has a strong local-app foundation: explicit auth middleware, role-based UI routes, CSP/security headers, good source-sync tests, SQLite reliability pragmas, a launchd deployment path, and a meaningful integrity audit script.

The main architectural risk is that several important concepts are duplicated or split across surfaces:

- Authentication is split between profile sessions and browser-stored admin bearer tokens.
- SQLite schema management is split between Alembic migrations and startup-time SQLite repair.
- Collection health, source sync, and review queues are converging into a large coupled UI route.
- Data provenance is strong for some flows but incomplete for enrichment/backfill scripts.
- Frontend state is spread across query params, cookies, hidden inputs, and JavaScript local state.

The next work should focus on unifying those contracts rather than adding new features.

## Priority Findings

### P0: Login Sessions Need Real Credential Verification

`LOGIN_ACCESS_KEY*` and `LOGIN_PASSCODE*` settings exist in `api/config.py`, but `api/routers/ui/login.py` currently creates a signed session when a posted `profile_id` matches an existing profile. Because the default first profile is admin in `api/services/profiles.py`, anyone who can reach the app can post profile 1 and obtain an admin session.

Recommended PR:

- Require a configured login access key/passcode before issuing profile sessions.
- Support profile-specific credentials where the existing settings imply that model.
- Keep local test/dev behavior explicit through `DISABLE_AUTH=true`.
- Add tests for missing, invalid, and valid credentials.

### P0: Remove Admin Tokens From Browser Storage

The UI already knows admin session role state, but movie editing and collection-health update actions still use browser-stored bearer tokens:

- `static/js/movie_detail_edit.js` prompts for an admin token and stores it in `sessionStorage`.
- `static/js/collection_health.js` reads `localStorage.vaultAdminToken`.
- Corresponding JSON mutation routes still use bearer-token admin auth in `api/routers/movies.py`.

Recommended PR:

- Move movie edit/delete and collection-health update actions to session-role authorization.
- Add `require_profile_role(ROLE_ADMIN)` and `require_same_origin` to the session-backed mutation routes.
- Remove token prompt/storage behavior from frontend JavaScript.
- Keep bearer-token APIs only where a non-browser automation use case is explicit.

### P1: Replace Startup SQLite Repair With Migration-Aware Checks

`api/main.py` runs `bootstrap_sqlite_schema()` on SQLite startup. That calls `Base.metadata.create_all()` and hand-written repair DDL in `api/db.py`. This is useful for legacy local databases but is not equivalent to Alembic migrations and can drift from model constraints.

Known drift risk:

- Startup repair creates some indexes/columns manually.
- Alembic contains schema history that is not fully represented by the startup repair path.
- App startup is doing schema mutation before serving requests.

Recommended PR:

- Add a migration-aware SQLite bootstrap command or maintenance script.
- On app startup, verify required schema invariants and fail loudly on drift instead of mutating broadly.
- Include a clear live-service workflow: backup active DB, run migration/check, then restart.

### P1: Fix Backfill Backup Targeting and Standardize Provenance

Some backfill scripts mutate the database while backup/provenance behavior is uneven.

Specific concern:

- `scripts/backfill_clear_external_matches.py` uses `SessionLocal`, but its backup path copies `ROOT_DIR / "vault.db"`, which may not be the active live DB under `~/Library/Application Support/Vault966/data/vault.db`.

Broader concern:

- External-ID repair records provider provenance.
- Poster, backdrop, and ratings backfills mutate enrichment fields without equivalent first-class provenance.

Recommended PR:

- Resolve the active SQLite database path from `engine.url` before any apply-mode backup.
- Refuse apply-mode backfills if the active DB cannot be backed up.
- Add consistent `MovieIngestProvenance` or equivalent enrichment provenance for poster, backdrop, rating, and external-ID changes.

### P1: Split Vault Health Into View-Specific Context Builders

`/ui/movies/health` in `api/routers/ui/grid.py` builds collection health, source snapshots, profiles, and review context together. `api/routers/ui/review.py` builds all review queues and groups, while `templates/partials/movies/review_workbench.html` branches across source conflicts, source-only rows, duplicates, vault checks, flags, and external repair.

Recommended PR:

- Introduce view-specific context builders for source conflicts, source-only/new rows, duplicates, vault checks, and flags.
- Load only the data needed by the selected tab/view.
- Keep a thin top-level health route that composes summary cards plus one selected workbench context.

### P2: Add Client/OpenAPI Drift Gates

OpenAPI and client generation exists:

- `scripts/generate_openapi.py`
- `scripts/generate_clients.py`
- `client_py/`
- `client_ts/`

But CI does not visibly verify that generated OpenAPI/client artifacts are current after route/schema changes.

Recommended PR:

- Add a CI check or local test target that regenerates OpenAPI/clients and fails on git diff.
- Document when generated clients must be refreshed.

### P2: Clean Up Frontend Semantics and Asset Hygiene

The frontend has good CSP-compatible patterns overall, but some structure needs attention:

- `templates/base.html` already provides `<main>`, while `templates/movies_grid.html` nests another `<main>`.
- Filter and edit dialogs lack consistent `aria-labelledby`/`aria-describedby`; the flag dialog in `templates/movie_detail.html` is a good local model.
- Duplicate static asset copies exist: `static/js/discover_page 2.js` and `static/js/library_page 2.js`.
- `static/css/movies.css` is very large and spans multiple UI surfaces.

Recommended PR:

- Remove nested landmarks and add consistent dialog labels/descriptions.
- Delete duplicate static JS copies after confirming they are unintended.
- Add tests for core landmarks/dialog attributes.
- Start splitting CSS by durable surfaces only when touching related UI work.

### P2: Simplify Browser Filter State

The library page currently combines query params, cookies, hidden inputs, and JavaScript-maintained state. This works, but it raises the cost of adding filters and makes regressions more likely.

Recommended PR:

- Define one server-authored filter state payload.
- Let JavaScript mutate that state and serialize it back to URL/form state from a single source of truth.
- Add focused JS tests for new filter state transitions.

### P3: Tighten Operational and CI Polish

Operational foundations are solid: `scripts/vault_service.sh` deploys into the live app copy, waits on `/health`, and manages watchdog/maintenance agents. SQLite maintenance has tests. CI runs Python lint, JS lint, and tests.

Remaining polish:

- `/health` is public and exposes a masked database DSN. This is acceptable for a local app but should be documented as intentional or reduced to backend/driver only.
- Ruff config uses deprecated top-level settings, which produces warnings.
- CI only runs on `main`, `master`, `reliability-hardening`, and pull requests; that is likely fine, but the branch exception should be documented or removed.

Recommended PR:

- Move Ruff settings under `[tool.ruff.lint]`.
- Decide whether `/health` should expose DSN details or only status/backend.
- Add a small service-doc note explaining source tree versus deployed copy and which checks are required before calling work complete.

## Recommended PR Sequence

1. **Require login credentials before issuing sessions.**
   Highest security impact and relatively contained.

2. **Remove browser-stored admin tokens from UI flows.**
   Aligns admin UX with the profile-session model and unlocks cleaner frontend code.

3. **Migration-aware SQLite startup check.**
   Prevents schema drift from being quietly papered over at service startup.

4. **Backfill backup/provenance standardization.**
   Reduces risk for data-changing maintenance scripts.

5. **Vault Health view-model split.**
   Makes ongoing health/review/source-sync work less brittle.

6. **Accessibility and asset hygiene.**
   Quick quality win: landmarks, dialog labels, duplicate JS files.

7. **OpenAPI/client drift gate and Ruff config cleanup.**
   Keeps generated contracts and tooling honest.

## Suggested Definition of Done For Future Architecture PRs

- Include focused tests for the changed contract.
- Run the full Python suite for backend/data changes.
- Run JS tests and Prettier lint for frontend changes.
- For app/template/static/dependency changes, restart `scripts/vault_service.sh restart` and verify an affected route through `http://127.0.0.1:8000`.
- Do not include `.env`, database contents, service logs, database backups, generated caches, or duplicate local artifacts in commits.

