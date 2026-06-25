# Codex Skill Examples

Use these examples to choose the right repo-scoped Codex skill for contributor
or maintainer work. Skills live in `skills/` and are exposed through
`.agents/skills/`.

## Data Import

Use `csv-import-guard` when the task starts with a CSV file and needs validation
before import.

Example request:

```text
Use csv-import-guard to validate data/samples/vault966_demo_legacy.csv and
produce a cleaned import file plus review report.
```

Expected output: required-column checks, year/runtime/ID validation, duplicate
warnings, a cleaned CSV path, and a review report path. The skill should not
silently drop rows.

Use `movie-import-review` when adding or reviewing titles, especially if missing
metadata or duplicate detection is part of the work.

Example request:

```text
Use movie-import-review on this list of five titles, enrich missing runtime and
IDs when source keys are configured, and flag likely duplicates before import.
```

Expected output: a concise import review, missing-field notes, duplicate
candidates, and suggested `POST /movies` or `PATCH /movies/{id}` payloads.

## Metadata And Collection Quality

Use `metadata-cleanup` for records already flagged for missing or inconsistent
metadata.

Example request:

```text
Use metadata-cleanup on movies flagged "Metadata cleanup" and propose safe
patches for missing runtime, year, genres, IMDb ID, or TMDb ID.
```

Expected output: current values, source-backed corrections when API keys are
available, minimal patch payloads, and a clear note when values need maintainer
confirmation.

Use `duplicate-resolution` when records may represent the same movie.

Example request:

```text
Use duplicate-resolution to inspect likely duplicate title/year and IMDb ID
matches, then propose canonical records and merge notes.
```

Expected output: duplicate groups, confidence basis, canonical record
recommendations, merge payloads, and no deletes unless explicitly approved.

Use `database-health-check` for broad collection audits.

Example request:

```text
Use database-health-check to scan for duplicate titles, missing IDs, extreme
runtimes, and missing years, then summarize the top follow-ups.
```

Expected output: anomaly counts, sample IDs/titles, and suggested next actions
such as metadata cleanup, duplicate resolution, or import review.

Use `flag-triage` when the goal is prioritizing open review flags.

Example request:

```text
Use flag-triage to group open flags by reason, rank the highest-impact items,
and route each group to the right cleanup skill.
```

Expected output: ordered flagged items, reason groups, recommended follow-up
skill, and no automatic flag resolution without confirmation.

## Artwork And Facets

Use `poster-backdrop-audit` for missing or low-quality movie artwork.

Example request:

```text
Use poster-backdrop-audit to find movies missing posters or backdrops and
propose TMDb replacement URLs without overwriting curated art.
```

Expected output: affected movies, current art state, suggested replacement URLs,
and patch payloads that require confirmation before overwriting custom art.

Use `genre-mood-normalizer` when filters or facets have inconsistent terms.

Example request:

```text
Use genre-mood-normalizer to find genre and mood casing variants, aliases, and
typos, then propose a canonical mapping table.
```

Expected output: canonical vocabulary, old-to-new mappings, update plan, and
filter/facet verification notes.

Use `llm-filters-evaluator` when AI-generated search filters do not match real
facets.

Example request:

```text
Use llm-filters-evaluator on this LLM filter payload and return only valid
genres, moods, and year ranges for the current collection.
```

Expected output: invalid values, safe replacements when clear, dropped filters
when not clear, and a cleaned filter payload.

## Verification, Security, And Release Work

Use `test-suite-runner` when the task is to run tests and report results.

Example request:

```text
Use test-suite-runner to run backend and JavaScript tests, then summarize
failures, warnings, and the next fix if anything fails.
```

Expected output: `pytest` status, `npm test` status, concise failure excerpts,
and no full log dump unless requested.

Use `vault-security-audit` for security scanning and remediation planning.

Example request:

```text
Use vault-security-audit to run configured Python and frontend security checks,
then summarize findings by severity with concrete fixes.
```

Expected output: scanner availability, findings with file/line when available,
risk statements, and remediation steps. Do not include secrets or private data in
reports.

Use `release-notes-generator` when turning merged work into release notes.

Example request:

```text
Use release-notes-generator for the last seven days of merged PRs and draft
release notes grouped by movies, code changes, and fixes.
```

Expected output: short user-facing release notes with date range, grouped
bullets, and any breaking changes called out.

## Review Checklist

For every skill-assisted contribution:

- Keep private databases, logs, credentials, and real exports out of the prompt
  and PR.
- Prefer synthetic examples under `data/samples/` for reproduction.
- Run focused verification first, then the narrowest Codex wrapper that proves
  the change.
- Mention the skill used and verification command in the PR body.
