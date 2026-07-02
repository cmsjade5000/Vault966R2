# Backend API Surface Audit

Date: 2026-07-02

This audit resolves the stale-surface candidates from GitHub issue #119. The
goal is to separate supported API/UI compatibility surfaces from dead internal
code so future cleanup does not accidentally remove generated-client or
bookmark contracts.

## Decisions

| Surface | Decision | Rationale | Follow-up |
| --- | --- | --- | --- |
| `api/services/genre_repair.py` | Remove | No runtime, script, test, or generated-client caller referenced this service. It was an internal one-off database mutation helper rather than a supported API. | Removed in this change. |
| `GET /api/discover/refresh` | Keep as compatibility API | The endpoint remains in generated Python/TypeScript clients and offers a JSON refresh contract for Discover without loading the rendered page. Query parameters already have strict bounds. | Added an inline compatibility comment. Revisit only with an API-version/deprecation issue. |
| `GET /api/profiles` | Keep as active API | Browser-side preference flows and tests use this endpoint to read available profiles and the active profile. It is session-gated by the login middleware and intentionally returns only profile IDs/names. | Existing inline comment documents the cookie-scoped profile contract. |
| `POST /api/profiles/active` | Keep as active API | Browser-side preference flows use this endpoint to set the active profile. It requires same-origin requests and rejects switching away from the authenticated profile session. | Existing inline comment documents the cookie-scoped profile contract. |
| `GET /ui/flags` | Keep as compatibility redirect | Older bookmarks and generated clients may still target this route. It redirects to the Health workbench flags view and is admin-gated. | Added an inline compatibility comment. |
| `GET /ui/review` | Keep as compatibility redirect | Older review links and generated clients may still target this route. It preserves query parameters and redirects to the Health workbench. | Added an inline compatibility comment. |
| `GET /ui/source-sync` | Keep as compatibility redirect | Older source-sync bookmarks and generated clients may still target this route. Upload and history now live in the Health workbench. | Added an inline compatibility comment. |
| `GET /ui/movies/review` | Keep as compatibility redirect | Older standalone review-mode links may still target this route. It redirects to Vault checks in the Health workbench. | Added an inline compatibility comment. |

## Client Impact

No public route was removed or renamed, so OpenAPI/client regeneration is not
required for this audit. The only removal is an unreferenced internal service
module.

## Verification

- `rg` confirmed no remaining references to `genre_repair` or
  `repair_source_created_genres`.
- Focused UI/profile/source-sync tests cover the kept routes and profile API.
- Full `make codex.check` should remain the final verification gate for this
  cleanup.
