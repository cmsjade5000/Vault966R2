# Vault 966 Project Hub

This file is the starting point for understanding and maintaining Vault 966.

## Current Shape

- Source repository: `/Users/corystoner/Documents/Vault 966 Project`
- Live deployed app: `~/Library/Application Support/Vault966/app`
- Canonical live database: `~/Library/Application Support/Vault966/data/vault.db`
- Local service: `http://127.0.0.1:8000`
- Active implementation branch: `codex/unify-metadata-import`

The repository is the editable source of truth. The deployed app is refreshed by
`scripts/vault_service.sh restart` and should not be edited directly.

## Where Things Belong

| Area | Purpose |
| --- | --- |
| `api/` | FastAPI application, routes, schemas, models, and services |
| `core/` | Shared movie-domain, metadata, filtering, and scoring logic |
| `templates/` | Server-rendered Jinja pages and reusable partials |
| `static/` | Browser CSS, JavaScript, images, and PWA assets |
| `tests/` | Python tests and browser-side tests under `tests/js/` |
| `scripts/` | Service management, imports, audits, backfills, and maintenance |
| `docs/` | Long-lived product, architecture, and operating documentation |
| `reports/` | Dated or generated audit, QA, and benchmark results |
| `data/import/` | Source-controlled import inputs and review metadata |
| `legacy/` | Archived compatibility and ETL code |
| `client_py/`, `client_ts/` | Generated or maintained API clients |
| `openapi/` | Frozen API specification |
| `skills/` | Project-specific reusable Codex workflows |

## Working Rules

1. Read `AGENTS.md` before changing the project.
2. Preserve the live database and never expose `.env`, credentials, or private
   log/database contents.
3. Keep implementation work in the established folders instead of adding new
   top-level areas.
4. Put durable guidance in `docs/` and dated outputs in `reports/`.
5. Run focused tests while iterating and the full relevant suite before completion.
6. After application changes, restart the service and verify the affected live
   route or asset through `127.0.0.1:8000`.

## Common Commands

```bash
pytest
npm run lint
scripts/vault_service.sh status
scripts/vault_service.sh restart
scripts/vault_service.sh logs
```

## Documentation

- `README.md`: setup, runtime, and developer commands
- `AGENTS.md`: durable Codex and review instructions
- `docs/README.md`: documentation index and ownership
- `reports/README.md`: generated-report conventions
- `CHANGELOG.md`: user-facing release history

## Current Work

The working tree contains substantial coordinated UI, authentication, metadata,
service, and test changes. Do not reorganize or relocate active source files until
that work is committed. Use `git status --short` before every new task and keep
unrelated edits separate.
