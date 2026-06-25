---
name: movie-import-review
description: Review new movie imports for required fields, validate values, fetch missing metadata from external APIs, and flag potential duplicates. Use when adding titles, importing data, or validating new movie records.
---

# Movie Import Review

## Goal
Validate new titles, enrich missing fields, and prevent duplicates before importing.

## Workflow
1. Inspect the incoming title list or payloads.
2. Validate required fields and value ranges.
3. Query external sources for missing metadata.
4. Detect duplicates and near-duplicates.
5. Normalize titles for sorting and display.
6. Produce a review report and update payloads.

## Required fields
- `title` (non-empty)
- `year` (1888–2100) if known
- `runtime` (non-negative) if known
- `genres` (list; allow empty but prefer at least one)
- IDs: `imdb_id`/`tmdb_id` if available

## Enrichment
- Use TMDb for release year, runtime, genres, poster/backdrop.
- Use OMDb for IMDb ID and ratings when present.
- Prefer deterministic API lookups using existing utilities:
  - `api/services/movie_lookup.py`
  - `api/utils/omdb.py`

## Duplicate checks
- Exact match on `imdb_id` or `tmdb_id`.
- Case-insensitive match on `title` + `year`.
- Near-duplicate titles (trim punctuation, collapse whitespace).

## Normalization
- Keep canonical `title` as the official title.
- Use a derived sort key by moving leading articles to the end:
  - "The Matrix" -> "Matrix, The"
  - "A Beautiful Mind" -> "Beautiful Mind, A"

## Output
- Summary report of missing fields and duplicates.
- Suggested update payloads for `POST /movies` or `PATCH /movies/{id}`.
