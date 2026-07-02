# Vault Maintenance Modernization Plan

The current Vault Health maintenance tool is a single dropdown that starts a
bundled background job. It is useful, but the UI does not clearly explain the
job's purpose, risk, expected duration, or relationship to review decisions.

## Current Behavior

The button calls:

```text
POST /api/collection-health/update/run
```

That starts `run_update_tasks()` in `api/services/vault_update.py`. The current
task sequence is:

1. Normalize genres.
2. Backfill moods.
3. Backfill posters, if TMDb or OMDb access is configured.
4. Backfill backdrops, if TMDb access is configured.

Status is written to:

```text
data/vault_update_status.json
```

The status endpoint is:

```text
GET /api/collection-health/update/status
```

## Boundaries

Maintenance is metadata and artwork cleanup. It should not be presented as a
general Vault Health fix-all action.

It does not:

- Accept source rows.
- Assign Vault IDs.
- Resolve source sync differences.
- Resolve flags.
- Approve first-import rows.

It can:

- Normalize genre labels.
- Refresh mood assignments.
- Fill poster URLs.
- Fill backdrop URLs.
- Generate maintenance CSV reports.

## Phase 1: Clarify The Existing Tool

Status: implemented baseline.

- Rename the dropdown from `Vault maintenance` to `Metadata maintenance`.
- Replace the generic `Update Vault` button with `Run full metadata maintenance`.
- Show the four included jobs before the admin runs them.
- State that the tool does not accept source rows, assign Vault IDs, or resolve
  review decisions.
- Show per-step summaries in the status chips when scripts emit useful output.

This phase also added basic runner safety: a lock file prevents overlapping
runs, stale running state can recover, and each script has a timeout.

## Phase 2: Add Preview And Impact Counts

Status: implemented.

Add read-only preflight data before any write action:

- Movies with missing posters.
- Movies with missing backdrops.
- Movies without moods.
- Movies with genre labels that would normalize differently.
- Whether TMDb and OMDb access is available.

The dropdown should become a Maintenance Center summary:

```text
Metadata maintenance
8 missing posters
5 missing backdrops
17 movies without moods
TMDb available
OMDb missing
```

No data should change during preview.

## Phase 3: Split Actions

Status: implemented baseline.

The UI now shows separate buttons and the run endpoint accepts a task selector:

- Normalize genres.
- Refresh moods.
- Refresh posters.
- Refresh backdrops.
- Run all metadata maintenance.

Current coverage:

- A clear write warning.
  - Implemented in the center copy.
- Its own latest report link.
  - Implemented for generated CSV reports through constrained report URLs.
- Its own status.
  - Implemented in each task card through the `task_statuses` status payload.

This already prevents a small artwork cleanup from running unrelated genre/mood
updates, while keeping the existing `/api/collection-health/update/run` route
compatible through a `task` query parameter.

## Phase 4: Safer Job Runner

Status: implemented baseline.

Move from ad hoc background tasks to a small job runner contract:

- Job ID.
- Job type.
- Started by profile ID.
- Started/finished timestamps.
- State: queued, running, success, failed, cancelled.
- Records scanned, changed, and skipped when the underlying script emits that
  detail in its step summary or CSV report.
- Report path.
- Error summary.

The current implementation stores maintenance jobs in `maintenance_jobs`,
including run ID, task ID, state, starter profile, timestamps, steps, error
summary, and report metadata. The JSON status file remains as a compatibility
snapshot for the active run and local fallback state.

## Phase 5: Slow Network Job Controls

Status: implemented baseline.

Poster and backdrop refreshes are the highest-risk jobs because they depend on
external network calls.

Current coverage:

- Per-job timeouts.
- Clear skipped states when API keys are missing.
- Cancel support that stops before the next queued task and records the run as
  `cancelled`.

Known limit:

- Cancellation is cooperative. It does not forcibly kill a subprocess that is
  already running; the timeout remains the guardrail for an in-flight script.

Still possible later:

- Worker limits shown in the UI.
- Retry/backoff summaries.

## Phase 6: Dashboard Integration

Status: implemented baseline.

Connect the Vault Health dashboard cards to maintenance actions:

- Missing poster count -> Refresh posters.
- Missing backdrop count -> Refresh backdrops.
- Missing moods -> Refresh moods.
- Genre cleanup count -> Normalize genres.

The dashboard should explain the fix path:

```text
8 movies are missing posters.
Run poster refresh or review the artwork report.
```

The dashboard now links metadata completeness into the Maintenance Center, and
the center itself shows missing-artwork previews, per-task actions, latest
status, and report links.

## Test Plan

Each phase should include focused tests:

- UI text appears on Vault Health.
- Status endpoint remains public/read-only.
- Run endpoint still requires admin authorization.
- Preview endpoints do not mutate data.
- Split run endpoints invoke only the requested job.
- Missing API keys produce skipped states instead of failures.

## Live-Service Rule

After each application change, restart the deployed service:

```text
scripts/vault_service.sh restart
```

Then verify:

```text
scripts/vault_service.sh verify /health
```

For Health page changes, also verify `/ui/movies/health` is responsive through
the live service.
