# Contributor Release Summary: PRs #141-#150

July 2, 2026 launch-prep work tightened the public Vault966R2 surface around the Library, collection-health maintenance, import safety, and contributor-facing security/demo assets. This note covers merged PRs #141 through #150.

## Public Launch Improvements

- PR #141 consolidated browsing around the Library by redirecting the legacy Discover UI, cleaning up generated OpenAPI clients, and adding CSP-compatible cached YouTube trailer playback on movie detail pages.
- PR #148 documented the backend API surface decisions for public launch, kept compatibility redirects explicit, retained `/api/discover/refresh` for client compatibility, and removed an unused internal genre-repair mutation helper.
- PR #150 added public-safe screenshots for the Library, Review flags, and Flic views, captured from a temporary synthetic SQLite database and documented in `docs/demo-data.md` plus `reports/demo-screenshots/README.md`.

## Library and Review Workflow

- PR #141 tightened Library filtering, invalid cookie-backed filter handling, active filter chips, and source-sync manual-add controls.
- PR #142 introduced structured toast feedback with success, notice, and error tones so movie detail, edit, source-sync, and global-pick actions report clearer status.
- PR #143 made unfiltered Library browsing discovery-oriented with persisted random ordering, added trusted-pick and double-feature actions that honor active filters, and tracked the new recommendation events.
- PR #145 refreshed the Library list view with poster-backed rows, inline view preferences, clickable table sorting, preserved filters, and a Random sort option.
- PR #148 kept review-related compatibility routes documented and admin-gated while routing stale UI aliases toward the current health workbench.

## Import and Vault Health

- PR #144 finished the metadata maintenance center by tightening Vault health update behavior and exposing clearer collection-health controls.
- PR #146 added a durable `retired_vault_ids` registry so manual/API creates, first import, source sync, legacy ETL, API deletion, duplicate cleanup, and integrity audits no longer reuse retired Vault IDs.
- PR #147 expanded first-import and source-sync upload handling from CSV-only assumptions to bounded CSV/XLSX detection, first-sheet XLSX parsing, common header aliases, and runtime/year normalization such as `1h 56m`, `117 min`, and `2016.0`.

## Security and Demo Data

- PR #149 added a lightweight CodeQL workflow for Python and JavaScript/TypeScript, documented how it fits alongside Dependabot and local audits, and added a workflow configuration guard test.
- PR #150 formalized screenshot provenance and demo-data boundaries so contributors have public examples without private collection data, local paths, logs, credentials, or profile names.
- PR #146 and PR #147 both documented security/privacy validation for live checks: schema and route verification avoided exposing private database rows, logs, credentials, or `.env` values.

## Contributor Notes

- The public contributor path now has clearer evidence for what is intentionally public: launch docs, API-surface decisions, security automation, demo data rules, and synthetic screenshots.
- The Library is the primary browsing surface; Discover compatibility remains where needed for generated clients and older callers.
- Import and Vault-health code now has stricter boundaries around file size, row counts, ID allocation, retired IDs, and live-service verification.

## Merged PRs Covered

| PR | Title | Main contributor-facing change |
| --- | --- | --- |
| #141 | Clean up movie library workflows | Library consolidation, trailers, filter cleanup, source-sync manual add |
| #142 | Add structured toast feedback | Consistent UI feedback payloads and tones |
| #143 | Improve library recommendations | Random browsing, trusted picks, double-feature flow |
| #144 | Finish metadata maintenance center | Collection-health metadata update controls |
| #145 | Refresh library list sorting | Poster-backed list view and table sorting |
| #146 | Prevent retired Vault ID reuse | Retired ID registry and allocation safeguards |
| #147 | Expand first-import file format mapping | CSV/XLSX upload detection and field normalization |
| #148 | Document backend API surface decisions | Public API compatibility audit and unused helper removal |
| #149 | Add lightweight CodeQL security automation | Scheduled/manual CodeQL workflow and docs |
| #150 | Add public-safe demo screenshots | Synthetic-data screenshots and provenance docs |

## Verification Snapshot

Across the merged PRs, validation included focused Python tests, browser-side JavaScript tests, `make codex.check`, generated client/OpenAPI updates where applicable, workflow guard tests, live service restarts, and unauthenticated route/health checks through `http://127.0.0.1:8000`.
