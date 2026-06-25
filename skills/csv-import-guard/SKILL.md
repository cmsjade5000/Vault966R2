---
name: csv-import-guard
description: Validate incoming movie CSVs (required columns, types, ranges), preview diffs, and generate a clean import file. Use when importing or reviewing CSV data.
---

# CSV Import Guard

## Goal
Validate CSV inputs before import and produce a cleaned file plus a report.

## Workflow
1. Load CSV and validate required headers.
2. Validate types and ranges (year/runtime).
3. Normalize text fields (trim, collapse whitespace).
4. Flag duplicates by title/year or IDs.
5. Emit a cleaned CSV and a review report.

## Required columns (minimum)
- `title`
- `year` (if available)

## Validation
- Year in range 1888–2100.
- Runtime non-negative.
- IDs (imdb_id/tmdb_id) match expected formats.

## Output
- Cleaned CSV file (same columns).
- Report of rows with issues.

## Notes
- Do not silently drop rows; mark them for review.
