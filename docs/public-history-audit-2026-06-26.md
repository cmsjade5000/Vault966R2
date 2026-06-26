# Public History Audit - 2026-06-26

## Scope

Audit target: `origin/public-main` at `e2a573e`.

The review checked the history reachable from the planned public branch for
secrets, private database artifacts, logs, personal import snapshots, generated
collection reports, and other files that should not be made public.

## Method

- Enumerated all paths reachable from `origin/public-main`.
- Checked tracked and historical filenames for `.env`, private keys, SQLite
  databases, WAL/SHM files, backups, dumps, logs, token files, `data/`, and
  `reports/` artifacts.
- Scanned reachable text blobs for high-signal secret markers and credential
  names while keeping matched values out of this report.
- Reviewed large historical blobs for unexpected database or report artifacts.
- Manually reviewed the intentionally tracked `data/` and `reports/` files.

## Findings

- No live SQLite database, WAL/SHM file, database dump, log file, generated CSV
  report, or private key file was found in `origin/public-main` history.
- No concrete API keys, access tokens, session secrets, or private key material
  were found by the local pattern scan.
- The tracked `data/` and `reports/` files are limited to public guidance,
  README content, and demo sample data.
- Historical revisions did include private legacy-import metadata in
  documentation: source snapshot naming, checksum/count-style audit details, and
  generated import result summaries. Current files have been scrubbed in this
  branch, but those old versions remain reachable from the existing Git history.

## Decision

Do not make the existing `origin/public-main` history public as-is if the launch
standard requires that private import metadata and generated collection-report
details are not reachable in history.

Use one of these release paths before changing visibility:

1. Publish from a clean public branch or repository created from the scrubbed
   current tree.
2. Rewrite the existing public branch history to remove the historical
   legacy-import metadata, then force-push only after confirming no collaborators
   depend on the old history.

The cleaner, lower-risk launch path is a clean public branch/repository because
it avoids preserving the pre-scrub documentation history.

## Follow-Up Checklist

- Re-run the history scan on the final branch or repository that will be made
  public.
- Confirm `.env`, live database files, generated report outputs, and private
  import snapshots remain ignored.
- Keep only demo data, public READMEs, and source code in tracked `data/` and
  `reports/` paths.
