# Vault Health Workflow Plan

Vault Health should be a dashboard first. It should answer three questions
before it asks an admin to take action:

1. What changed in the latest source?
2. What looks outdated or incorrect in the Vault?
3. What needs a decision before the Vault can be trusted?

The current implementation has the underlying records to answer those questions,
but the page presents implementation buckets directly. This makes the admin
interpret labels like `Differences`, `Ambiguous`, `Identity confidence`, and
`Source synchronization` instead of seeing a plain triage summary.

## Current Workflow

Source imports and reviews are backed by one shared data model:

- `SourceSnapshot`: uploaded CSV snapshot, with `draft`, `active`, or
  `superseded` status.
- `SourceMovieRow`: parsed source row from the uploaded collection file.
- `SourceReconciliationMatch`: the source row's relationship to a Vault movie.
- `SourceFieldDecision`: review decision history for source-vs-Vault field
  conflicts.
- `OwnedMovieCopy`: accepted source copy attached to a Vault movie.

There are two entry flows:

- Ongoing source sync is launched from the Source synchronization section on
  `/ui/movies/health`; its upload form posts to `/ui/source-sync/upload`,
  creates a draft snapshot, confirms it, and reconciles it against existing
  Vault entries.
- First import starts at `/ui/first-import`, creates the same kind of snapshot,
  auto-creates strict high-confidence matches, and routes leftovers into the
  same review queues.

The Vault Health page currently contains:

- Overview health cards.
- Review workbench.
- Missing details link.
- Source synchronization details, upload, and history.
- Maintenance action for updating the Vault.

The Review Workbench currently exposes seven tabs:

- `Differences`
- `Needs research`
- `Ambiguous`
- `New movies`
- `Duplicates`
- `Vault checks`
- `Flags`

These buckets are useful internally, but they do not explain what is wrong, why
it is wrong, or what will happen when the admin acts.

## Primary Pain Point

The biggest product problem is not the lack of data. It is that Vault Health does
not clearly communicate what is incorrect, stale, incomplete, or awaiting a
decision.

The page should stop leading with system mechanics and should instead lead with
admin-facing diagnoses.

## Proposed Health Model

Replace the current first impression with a dashboard-first triage model. The
first screen should summarize the Vault's state and then offer paths into action
queues.

### What Changed

Rows in the latest active source that represent import movement or unresolved
source decisions.

- New additions: high-confidence source rows created during first import.
- Possible duplicates: repeated source identities or duplicate conflicts.
- Unmatched/ambiguous rows: rows that might match a Vault entry but need a
  decision.

### What Is Outdated

Vault entries whose identity fields differ from the latest accepted source.

Examples:

- Source title differs from Vault title.
- Source year differs from Vault year.
- Source runtime differs from Vault runtime by more than the accepted tolerance.
- Source director differs from Vault director.

These should be presented as "Outdated Vault fields", not "Differences".

### What Is Incomplete Or Suspect

Vault records that need cleanup independent of the latest source upload.

Examples:

- Missing runtime, plot, poster, or external IDs.
- User/admin flags.
- Internal structural checks.
- Entries needing metadata repair.

## Proposed Page Structure

Vault Health should become a three-part admin console.

### 1. Status Summary

Purpose: answer "Can I trust the Vault right now?"

Show a compact priority summary:

- Needs decision now
- New additions
- Outdated fields
- Possible duplicates
- Missing metadata
- Flags

Each status row should include:

- Count.
- Meaning.
- Why it matters.
- Primary action.

Example copy:

> 12 new additions were accepted from the latest first import and assigned
> permanent Vault IDs.

### 2. Action Queue

Purpose: answer "What should I work next?"

Use plain task groups instead of exposing all implementation buckets at once:

- Source changes
- Vault cleanup
- Flags

Inside Source changes, keep the existing source buckets as subfilters:

- New additions
- Outdated fields
- Needs research
- Possible matches
- Possible duplicates

This preserves the existing backend queue behavior while reducing the first
decision from seven unrelated tabs to three work types.

The action queue should sit below the dashboard summary, not replace it.

### 3. Source And Imports

Purpose: answer "What source file is this based on, and how do I bring in more?"

Keep this section operational and visually secondary unless there is no active
source snapshot.

Include:

- Latest active source snapshot.
- Upload new source.
- First import entry point, if still needed.
- Snapshot history.
- Export links for source slices, including new additions.

## Language Changes

Rename implementation-oriented labels:

- `Differences` -> `Outdated fields`
- `Needs research` -> `Needs verification`
- `Ambiguous` -> `Possible matches`
- `New movies` -> `New additions`
- `Duplicates` -> `Possible duplicates`
- `Vault checks` -> `Vault cleanup`
- `Source synchronization` -> `Source and imports`
- `Identity confidence` -> `Open decisions`

Avoid presenting a count without an interpretation. A count should always say
whether it is a problem, a queue, or a completed status.

## New Additions Export

Add a download from Vault Health containing only new additions from a source
snapshot.

### Definition

The default definition should be:

```text
new additions = SourceMovieRow records from the selected SourceSnapshot
where SourceReconciliationMatch.match_type == "auto_create"
```

This means the export excludes:

- Existing exact or likely matches.
- Manually matched rows.
- Low-confidence rows that still need review.
- Ambiguous rows.
- Duplicate rows.
- Dismissed duplicates.
- Field differences for existing Vault entries.

This definition intentionally exports high-confidence rows that were accepted
and created during first import. It avoids mixing accepted additions with
unresolved source-only candidates that still need a human decision.

### Format

Implemented baseline:

1. CSV endpoint for lightweight Excel-openable exports.
2. `.xlsx` export remains a follow-up after the iPad Health route is stable.

CSV remains useful for automation and quick inspection. It opens directly in
Excel without adding runtime workbook-generation work to the live Health path.

### Proposed Routes

```text
GET /ui/source-sync/{snapshot_id}/new-additions.csv
```

Vault Health should link to the latest active snapshot export when available.

### Columns

Use only source data and source review state; do not expose private database
contents beyond what the admin already uploaded.

Recommended columns:

- `source_snapshot_id`
- `source_row_id`
- `vault_id`
- `match_confidence`
- `row_number`
- `title`
- `year`
- `runtime`
- `director`
- `genre`
- `content_rating`
- `release_date`
- `hd`
- `status`

Where `status` is `high_confidence_added`.

Optional future columns:

- `review_url`
- `notes`
- `lookup_status`
- `candidate_count`

### Storage

Do not commit generated exports. They should be runtime downloads, or written to
an ignored local output directory when a script is explicitly run.

This follows the public launch guidance that private movie exports, import
snapshots, staged CSVs, and generated review reports stay out of version
control.

## Standardization Targets

The plan should eliminate or reduce one-off implementations:

- Treat first import and ongoing source sync as modes of the same Source and
  Imports workflow.
- Prefer source snapshot records over ad hoc CSV side effects.
- Move manual-add CSV side effects toward the same provenance/review model.
- Keep all import acceptance decisions visible in Vault Health.
- Keep generated reports/downloads behind authenticated admin routes.

## Implementation Phases

### Phase 1: Clarity Pass

- Rename queue labels and overview cards.
- Add short explanations to each health status.
- Reduce duplicate "open workbench" calls to action.
- Make the default workbench view prioritize the largest or most severe open
  queue.
- Remove the duplicate global success message or ensure the top message also
  supports undo where appropriate.

### Phase 2: New Additions Export

- Add a service function that returns high-confidence `auto_create` rows for a
  snapshot.
- Add authenticated admin download route for CSV.
- Add Vault Health link for latest active snapshot.
- Add tests proving the export includes only `auto_create` rows.

### Phase 3: Unified Source And Imports

- Fold first-import entry points into Source and Imports.
- Make first-import report point to exactly one next best action.
- Keep first-import routes as redirects or compatibility pages until tests and
  links are updated.

### Phase 4: Cleanup And Consolidation

- Remove dead non-admin Vault Health template branches if the route remains
  admin-only.
- Remove unused health-era CSS selectors after the new structure ships.
- Review manual add CSV side effects and standardize them against movie
  provenance and SourceSnapshot workflows.

## Open Decisions

1. Should Vault Health remain admin-only, or should reviewers eventually see a
   read-only health summary?
2. Should the dashboard use severity ordering, workflow ordering, or a fixed
   layout regardless of counts?
3. Should first import remain a separate route, or should it be fully folded
   into Source and Imports on Vault Health?

## Recommended Next Step

Finish Phase 1 by turning the Review Workbench into a secondary action queue
below the dashboard summary. Then move Phase 3 forward by folding first import
entry points into Source and Imports.
