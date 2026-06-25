# Legacy Vault Import

Source snapshot:

- `Vault966_MovieDB_20250724_v03.csv`
- 980 rows, 21 columns
- SHA-256: `2ff67a93cea229b1402543002259e216fe41be71a7361ded4f34a9d377c35e8b`

Generated artifacts:

- `Vault966_MovieDB_20250724_v03.staged.csv`: canonicalized, non-destructive staging file.
- `Vault966_MovieDB_20250724_v03.review.json`: duplicate and year-conflict review report.

Verified isolated import:

- 969 inserted
- 0 updated
- 5 duplicate input rows skipped
- 6 identifier conflicts quarantined
- 65 title/year records imported without IMDb or TMDb IDs

The source CSV is immutable. Regenerate the staged files with
`scripts/prepare_legacy_vault_csv.py`; do not edit the source snapshot in place.

Run `make vault.audit` to check database structure, source drift, content-review
anomalies, and a deterministic 20-movie spot sample.
