# Reports

This folder contains generated or dated evidence from audits, imports, performance
checks, and visual QA. Reports are supporting artifacts, not application inputs.

## Naming

Prefer:

```text
<topic>-YYYY-MM-DD.md
<topic>-YYYY-MM-DD.csv
<topic>-YYYY-MM-DD/
```

Existing legacy filenames may remain unchanged when renaming would break an audit
trail or make an active change harder to review.

## Contents

- `performance-benchmark-2026-06-13.md`: local service latency baseline and optimization results
- `ipad-landscape-audit-2026-06-11/`: iPad visual and interaction audit
- `clear_external_matches_*`: external-match cleanup previews and applied results
- `poster_backfill_*`: poster matching and backfill runs
- `duplicates*`, `invalid_imdb_id.csv`, `missing_imdb_id.csv`: import integrity findings

## Rules

- Do not treat report CSVs as canonical source data.
- Do not store credentials, session tokens, or private logs.
- Prefer a dry-run report before any bulk database mutation.
- Record the command, date, target, and whether changes were applied when practical.
- Keep large disposable screenshots and temporary benchmark scripts outside the repository.
