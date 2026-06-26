# Legacy ETL Lifecycle

`legacy/etl/` is archived-but-supported maintenance code. It is not the preferred
place for new import features, but it remains part of the supported maintainer
workflow for historical CSV/JSON imports, TMDb enrichment, retry files, and
recovery tasks that still depend on its behavior.

## Support Contract

- Keep `legacy/etl/etl_seed.py`, `legacy/etl/enrich_tmdb.py`, and
  `legacy/etl/retry_missing_ids.py` runnable unless a future issue retires the
  whole workflow in one coordinated change.
- Keep the active wrappers in `scripts/import_latest_enriched_csv.py` and
  `scripts/enriched_csv_orchestrator.py` pointed at `legacy/etl/` while this
  lifecycle is supported.
- Keep sample files under `legacy/etl/samples/` available for tests and
  maintainer dry runs.
- Keep `tests/legacy/` coverage for archived importer behavior that active
  scripts still rely on.

## Boundaries

- Do not add broad new importer features under `legacy/etl/`; prefer modern
  scripts under `scripts/` and shared validation in `core/` where practical.
- Small compatibility fixes, bug fixes, and data-safety fixes are allowed.
- If `legacy/etl/` is retired later, remove or replace the caller scripts,
  tests, samples, and documentation in the same change so no supported script
  points at a retired importer path.

## Current Callers

- `scripts/import_latest_enriched_csv.py` imports the selected
  `enriched_movies*.csv` through `legacy/etl/etl_seed.py`, then refreshes poster
  cache data after successful non-dry-run imports.
- `scripts/enriched_csv_orchestrator.py` may call `legacy/etl/enrich_tmdb.py`
  for TMDb enrichment and delegates final import to
  `scripts/import_latest_enriched_csv.py` unless `--skip-import` is used.

