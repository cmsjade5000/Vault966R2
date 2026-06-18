# Plan: Second User Permissions and Flagging

**Generated**: 2026-01-25
**Estimated Complexity**: Medium

## Overview
Introduce profile roles so User A is the admin and User B is a limited reviewer. Enforce role‑based access for Collection Health and admin‑only movie operations, while allowing User B to submit “incorrect” flags. Update login to allow selecting the profile, hide admin UI for User B, and re‑enable login enforcement at the end.

## Prerequisites
- Confirm how User A/B are selected at login (buttons vs dropdown, shared credentials).
- Decide whether admin token should still be required for add/edit/delete/resolve (or if admin profile is sufficient).
- Confirm whether User B should see the flags list or only submit flags.

## Sprint 1: Add Roles and Profile Context
**Goal**: Add explicit roles to profiles and expose role context per request.
**Demo/Validation**:
- Login as User A and User B; verify role is resolved and surfaced in templates.
- Verify existing users are backfilled with correct default roles.

### Task 1.1: Add profile role column + model updates
- **Location**: `api/models/profile.py`, `alembic/versions/`
- **Description**: Add a role field (e.g., `admin`, `reviewer`) to `Profile`, update model, and create Alembic migration with backfill defaults.
- **Complexity**: 5
- **Dependencies**: None
- **Acceptance Criteria**:
  - DB migration adds `profiles.role` with defaults.
  - Existing profile rows are assigned roles.
- **Validation**:
  - Run migration; query profiles to confirm roles.

### Task 1.2: Set default roles for User A/B
- **Location**: `api/services/profiles.py`
- **Description**: When `_ensure_default_profiles` seeds profiles, assign role `admin` to User A and `reviewer` to User B.
- **Complexity**: 3
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Fresh DB seeds create two profiles with correct roles.
- **Validation**:
  - Reset DB or use a temp DB and verify roles.

### Task 1.3: Add role lookup helpers
- **Location**: `api/services/profiles.py`, `api/deps/auth.py`, `api/main.py`
- **Description**: Add helpers to load the active profile and role for the current request (e.g., `get_active_profile` or `get_active_profile_role`). Store role on `request.state` in middleware or a dependency.
- **Complexity**: 4
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - `request.state.profile_role` is set for authenticated requests.
- **Validation**:
  - Log or inspect template context for role presence.

### Task 1.4: Login profile selection UI
- **Location**: `templates/login.html`, `static/css/login.css`, `static/js/login.js`
- **Description**: Add a simple selector (User A/User B) to set `profile_id` on login instead of a hidden field.
- **Complexity**: 4
- **Dependencies**: Task 1.2
- **Acceptance Criteria**:
  - User can choose A or B at login.
  - Session cookie reflects selected profile.
- **Validation**:
  - Login as each profile and confirm role in UI.

## Sprint 2: Role‑Gated UI and Routes
**Goal**: Restrict Collection Health/admin features to User A only.
**Demo/Validation**:
- User A sees Collection Health and admin controls.
- User B cannot access `/ui/movies/health` or admin pages even via direct URL.

### Task 2.1: Add role‑based dependency
- **Location**: `api/deps/auth.py`
- **Description**: Implement `require_profile_role(*roles)` to enforce session‑based role checks (403 on mismatch).
- **Complexity**: 5
- **Dependencies**: Task 1.3
- **Acceptance Criteria**:
  - Role checks block unauthorized requests with clear error codes.
- **Validation**:
  - Unit tests for role mismatch responses.

### Task 2.2: Gate Collection Health UI routes
- **Location**: `api/routers/ui/grid.py`, `api/routers/ui/flags.py`
- **Description**: Apply `require_profile_role("admin")` to `/ui/movies/health`, `/ui/movies/health/missing`, and `/ui/flags`.
- **Complexity**: 4
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - User B gets 403 or redirect on health/flags pages.
- **Validation**:
  - Manual checks on both profiles.

### Task 2.3: Hide admin navigation and actions
- **Location**: `templates/base.html`, `templates/movies_health.html`, `templates/partials/movies/collection_health.html`
- **Description**: Conditionally render Collection Health link, update buttons, and admin controls only for admin role.
- **Complexity**: 3
- **Dependencies**: Task 1.3
- **Acceptance Criteria**:
  - User B never sees Collection Health or update controls in UI.
- **Validation**:
  - Visual check on iPhone/desktop.

### Task 2.4: Restrict manual add/preview UI
- **Location**: `api/routers/ui/manual_add.py`, template that links manual add
- **Description**: Gate preview endpoint and any manual‑add UI entry points to admin role to avoid confusing User B.
- **Complexity**: 3
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - User B cannot access manual add preview or submission endpoints.
- **Validation**:
  - Direct URL tests return 403 for User B.

## Sprint 3: Reviewer Flagging Flow
**Goal**: Allow User B to flag movies as incorrect without admin access.
**Demo/Validation**:
- User B can flag a movie; User A can view/manage flags.
- User B cannot clear or resolve flags.

### Task 3.1: Add reviewer flag endpoint
- **Location**: `api/routers/movies.py`, `api/schemas/movie.py`
- **Description**: Add a new endpoint (e.g., `POST /movies/{movie_id}/flag/report`) that allows roles `reviewer` and `admin`, with strict reason whitelist and note length limit. Keep `DELETE /flag` admin‑only.
- **Complexity**: 6
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - User B can create a flag; cannot delete it.
  - Reasons are validated against `FLAG_REASONS` and notes length is capped.
- **Validation**:
  - API tests for 201 on reviewer, 403 on delete.

### Task 3.2: Track reporter (optional but recommended)
- **Location**: `api/models/movie_flag.py`, Alembic migration
- **Description**: Add `reported_by_profile_id` to `MovieFlag` for auditability; populate on reviewer submissions.
- **Complexity**: 5
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - Flags show who reported them.
- **Validation**:
  - Query DB after a reviewer report.

### Task 3.3: Update UI to show reviewer flag action
- **Location**: `templates/movie_detail.html`, `static/js/movie_detail.js`, `static/css/movie_detail.css`
- **Description**: Add a “Report incorrect” action for non‑admin profiles that calls the reviewer endpoint. Keep admin resolve/clear actions restricted.
- **Complexity**: 5
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - User B sees report option; User A sees admin flag controls.
- **Validation**:
  - Manual UI test in iPhone/desktop.

## Sprint 4: Re‑enable Login Enforcement
**Goal**: Turn login back on and ensure role gating works end‑to‑end.
**Demo/Validation**:
- App redirects to `/login` when unauthenticated.
- User A/B roles enforce access as expected.

### Task 4.1: Disable auth bypass
- **Location**: `.env`, `api/config.py`, `api/main.py`
- **Description**: Set `DISABLE_AUTH=false` in `.env` and confirm session auth middleware is active.
- **Complexity**: 2
- **Dependencies**: Prior sprints
- **Acceptance Criteria**:
  - Unauthenticated users are redirected to `/login`.
- **Validation**:
  - Manual browser test; ensure authenticated flow works.

## Testing Strategy
- **Unit/API**: `pytest` for role‑based access (admin vs reviewer), flag endpoints, and role validation.
- **Manual UI**: Login as User A and User B; verify nav visibility, page access, and flag submission on iPhone portrait and desktop.

## Potential Risks
- Role resolution adds DB lookups per request; mitigate with lightweight caching or request‑scoped profile fetch.
- Inconsistent UI gating could expose admin‑only links; enforce server‑side role checks regardless of UI.
- Flag reason validation changes may break existing clients if not aligned.

## Rollback Plan
- Revert Alembic migration (or add follow‑up migration to drop `role`/`reported_by_profile_id`).
- Remove role dependency checks and restore previous UI links.
- Set `DISABLE_AUTH=true` to restore current bypass if needed.
