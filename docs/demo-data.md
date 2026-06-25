# Demo Data

Vault 966 needs public examples that exercise maintenance workflows without
exposing the live collection. Files under `data/samples/` are synthetic and safe
to use in docs, screenshots, tests, and issue reproduction.

## Legacy Import Sample

`data/samples/vault966_demo_legacy.csv` is a fictional 21-column legacy import
file. It follows the same header expected by `scripts/prepare_legacy_vault_csv.py`
and intentionally includes review cases:

- `Sample Moon` appears with two release years to exercise title/year review.
- `Paper Comet` reuses an IMDb-style ID to exercise duplicate identifier review.
- Poster URLs are blank so artwork audit workflows can demonstrate missing art
  without referencing real collection assets.

Generate staged output and a JSON review report outside the source tree:

```bash
.venv/bin/python scripts/prepare_legacy_vault_csv.py \
  --input data/samples/vault966_demo_legacy.csv \
  --output /tmp/vault966_demo_legacy.staged.csv \
  --report /tmp/vault966_demo_legacy.review.json
```

Expected result:

```text
Staged 5 rows; review issues: 2
```

Use this sample for contributor onboarding, screenshots, issue reproduction, and
Codex workflow examples. Do not replace it with rows from the private database or
with exports from the live service.
