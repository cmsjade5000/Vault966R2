---
name: metadata-cleanup
description: Inspect movies flagged for Metadata cleanup, identify missing or inconsistent fields (runtime, year, genres, IDs), and propose corrections using OMDb/TMDb data. Use when asked to clean metadata, verify flagged records, or generate update patches for movies.
---

# Metadata Cleanup

## Goal
Inspect a flagged movie record, compare against official sources, and produce a safe update plan (patch file or API update).

## Workflow
1. Fetch the flagged movie and current metadata.
2. Identify missing or inconsistent fields.
3. Query official sources (TMDb/OMDb) deterministically.
4. Propose a minimal update payload and confirm with the user.
5. Apply updates via API or emit a patch file.

## Fetch current record
- Prefer API: `GET /movies/{id}/detail` and `GET /movies/{id}`.
- Use `GET /movies/flags` to find "Metadata cleanup" items.

## Validate and compare
Check for:
- Missing: `runtime`, `year`, `genres`, `imdb_id`, `tmdb_id`, `plot`.
- Inconsistent: release year vs. source year, runtime outliers, genre mismatches, duplicate IDs.
- Normalization: trim whitespace, dedupe `where_to_watch`, ensure proper casing.

## Source data (deterministic)
- Use existing utilities:
  - `api/services/movie_lookup.py` for TMDb lookup (requires `TMDB_API_KEY`).
  - `api/utils/omdb.py` for OMDb lookup (requires `OMDB_API_KEY`).
- Prefer TMDb for release year/runtime/genres; use OMDb for ratings and IMDb IDs when present.

## Output format
- Default to an update payload for `PATCH /movies/{id}`.
- If multiple records, generate a patch file with one JSON payload per movie.

Example payload:
```json
{
  "year": 2010,
  "runtime": 148,
  "genres": ["Science Fiction", "Thriller"],
  "plot": "Short official synopsis.",
  "imdb_id": "tt1375666",
  "tmdb_id": 27205
}
```

## Apply updates
- Use the admin token and `PATCH /movies/{id}`.
- If updates are speculative, ask for confirmation before applying.

## Notes
- Keep changes minimal; only update fields with high-confidence source matches.
- If sources conflict, present both values and ask for a decision.
