# Legacy Vault Import

This directory intentionally contains only public import guidance. Private legacy
CSV snapshots, staged import files, review JSON, and generated audit outputs must
remain outside Git.

Use `data/samples/vault966_demo_legacy.csv` for schema examples and tests. Keep
real collection snapshots in a local, ignored path and regenerate staging files
with `scripts/prepare_legacy_vault_csv.py` when needed.

Run `make vault.audit` to check database structure, source drift,
content-review anomalies, and a deterministic spot sample.
