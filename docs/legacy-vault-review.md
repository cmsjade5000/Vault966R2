# Legacy Vault Review

Reviewed repository: `cmsjade5000/Vault-966`

Canonical repository: `cmsjade5000/Vault966R2`

The old repository should remain separate and receive an archive notice only after the
useful behavior below is either present in R2 or recorded for deliberate follow-up.

## Already Superseded In R2

- Database-backed movie library, profiles, authentication, flags, and review navigation.
- Flic presets, runtime and decade filters, mood and genre scoring, and double features.
- Manual add with TMDb/OMDb lookup and duplicate-ID protection.
- Collection health, missing metadata views, poster backfill, and title correction tools.
- Curated collections, semantic search, watchlists, and movie detail pages.

## Migrated During This Review

- Shared metadata normalization for lookup, manual add, API create, and bulk ETL.
- Legacy directors and top cast imported into people and roles.
- Certificates and keywords preserved as first-class movie fields.
- Legacy Vault IDs retained in ingest provenance.
- Offline TMDb-only and explicit title/year imports.
- Identifier conflicts quarantined instead of overwriting another movie.
- Legacy CSV staging with exact-schema validation and a machine-readable review report.

## Worth Rebuilding In R2

1. Filtered CSV export from the current database-backed library.
2. Flic reachability audit for movies that have too little metadata to appear in picks.
3. Batch correction review with approve, skip, and undo before writes.
4. Spotlight diversity/history so daily picks avoid recent repeats and overrepresented eras.
5. Richer metadata coverage reporting for certificates, keywords, ratings, people, and providers.
6. Provider/poster reachability checks that distinguish missing URLs from broken URLs.
7. Optional TMDb/OMDb identity verification that detects cross-wired title, year, IMDb, and
   TMDb combinations and sends proposed corrections to review.

## Integrity Baseline

The first database audit reported:

- 969 movies
- 0 structural issues
- 0 changes from the staged source
- 11 intentional source exclusions
- 90 content-review items

Browser spot checks found source-level identity problems that a source-drift check alone
cannot detect. Examples include `Smile` carrying a 1975 year with the IMDb identity for the
2022 film, and `Resident Evil` combining the 2002 IMDb identity with the TMDb identity for
`Resident Evil: Damnation` (2012). These should be corrected through a review queue, not an
automatic overwrite.

## Ideas To Keep, Not Code To Copy

- Prefer the more complete record when duplicate metadata cache entries collide.
- Use deterministic daily selection, but incorporate recent-history and diversity penalties.
- Preview bulk metadata changes before applying them.
- Keep import and cleanup reports as durable artifacts.

## Do Not Port

- Streamlit runtime and the 4,000-line single-file application structure.
- Date/version-based CSV files as the primary database.
- File-based metadata and daily-pick caches.
- Inline credentials or PINs.
- First-result TMDb matching without confidence review.
- Broad exception swallowing and direct in-place cache mutation.
