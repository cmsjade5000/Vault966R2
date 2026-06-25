---
name: database-health-check
description: Scan the movies table for anomalies (duplicate titles, missing IDs, extreme runtimes) and generate a report of records needing attention. Use when asked to assess database health or audit movie records.
---

# Database Health Check

## Goal
Identify data anomalies in the movies table and produce a concise report.

## Workflow
1. Connect to the database used by the app (SQLite or Postgres).
2. Run anomaly queries.
3. Summarize findings with counts and sample IDs.
4. Provide a remediation list for follow-up.

## Anomaly checks
- Duplicate titles: case-insensitive `title` duplicates (optionally by year).
- Missing IDs: `imdb_id` or `tmdb_id` null/empty.
- Extreme runtimes: `< 40` or `> 240` minutes.
- Missing year or runtime where expected.

## Suggested queries (SQLAlchemy or raw SQL)
- Duplicates:
  - `SELECT lower(title), count(*) FROM movies GROUP BY lower(title) HAVING count(*) > 1;`
- Missing IDs:
  - `SELECT id, title FROM movies WHERE imdb_id IS NULL OR tmdb_id IS NULL;`
- Extreme runtimes:
  - `SELECT id, title, runtime FROM movies WHERE runtime IS NOT NULL AND (runtime < 40 OR runtime > 240);`

## Output format
- **Summary counts** for each anomaly type.
- **Top 10 sample records** with IDs/titles.
- **Next actions** (e.g., flag for metadata cleanup).
