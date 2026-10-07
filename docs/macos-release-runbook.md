# Vault966 macOS release

This workflow builds the main app from a clean commit and installs its exact hashed
Python lock into a new release directory. The release manifest identifies the source
commit/tree, code and file modes, dependency lock, schema contract and Alembic head.
The target is macOS arm64 with Python 3.12. This public source branch excludes the
Board prototype, collection snapshots, artwork and model. Generic catalog export
helpers remain to preserve the installed main app's runtime file set; they contain
no collection data and do not make Board part of this release.

## Build and test in an independent checkout

```sh
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python --require-hashes requirements-dev.lock
npm ci --ignore-scripts
DATABASE_URL=sqlite:// scripts/codex_check.sh full -q --tb=short -m 'not integration'
DATABASE_URL=sqlite:// make openapi.check
.venv/bin/python scripts/vault_release.py build --output /tmp/vault966.tar.gz
.venv/bin/python scripts/vault_release.py verify --artifact /tmp/vault966.tar.gz
shasum -a 256 /tmp/vault966.tar.gz
```

Commit intentional changes before `build`. Its payload comes from Git objects,
not loose working files. Record the artifact SHA256 outside the artifact: a manifest
provides integrity relative to that reviewed digest, not a publisher signature.
Release tarballs do not contain `.env`, databases, logs, import inputs, dependencies,
or Board data. Keep locally generated catalogs, artwork, logs and backups private;
they are not publication inputs.

The public branch has fresh history based on `public-main`. It does not inherit
the private Board commits. The previously installed release remains
`bfce432ab496-2fd0a741db5e`, with source commit
`bfce432ab49665e7f55a6380c23e419fdf71c2d6` and runtime payload SHA256
`2fd0a741db5e36e28171156d2bfc8241932a9c6c3b934daeb8f97611e3c1d5e1`.
The public source preserves those runtime file bytes and modes, but its source
commit/tree, release ID and rebuilt archive digest differ. Publishing this branch
does not reinstall or relabel that existing deployment.

The macOS CI job repeats the locked checks and artifact build. The existing Linux
job covers the broader Docker/development path. The new macOS job uses the arm64
`macos-15` runner listed in [GitHub's runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Remote CI must pass after any authorized push; local checks do not establish that.

## Rehearse using synthetic data

Choose a disposable support root outside the live support directory. Stage with
`--support-dir`, `--python` and `--expected-sha256`. Staging verifies the reviewed
archive, installs the hashed runtime lock, records the interpreter and all package
versions, and hashes the installed runtime files. A repeated stage rechecks those
identities and never silently repairs a partial or changed installation.

`schema-check` opens an explicitly named existing SQLite file in read-only mode.
It checks required table/column names and the three movie identity indexes and
their columns. It does not read movie rows or apply migrations. The contract permits
extra tables/columns and does not prove historical migration correctness or every
column type/constraint. `generate_release_schema.py` freezes all models imported by
the main app; tests detect a stale model contract or a dependency-lock mismatch.

For activation rehearsal, create a previous app directory, previous virtualenv,
synthetic `.env`, and synthetic `data/vault.db` with the required model shape.
Record database and credential checksums. Fingerprint the previous app; activate
with its exact fingerprint and `--stopped`. Verify the staged release, start its
runtime on loopback at an unused port, then test `/readyz`, login, protected routes
and the useful browsing flows. Stop this synthetic process and use the returned
rollback receipt to restore the previous app/runtime. Compare the checksums again.

## Live deployment gate — separate approval required

The reconciliation work does not authorize replacing the live app, restarting its
jobs, or inspecting/changing its database or credentials. Before an approved live
installation:

1. Confirm the reviewed source commit and artifact SHA256, clean local/remote
   provenance and successful tests. Recheck the live code fingerprint; abort if
   somebody has changed the deployment since review.
2. Obtain approval for live staging, a brief outage, read-only schema/config checks,
   a consistent SQLite backup, activation and rollback if needed. Confirm the
   effective database configuration points to the existing support database, and
   that existing launchd plists still point to `support/app` and `support/.venv`.
   Preserve the current authentication settings and provider credentials.
3. Stage into the live support root with `--allow-live-target`. Verify the exact
   runtime and manifest with `verify-staged`; staging does not switch active paths.
4. Stop server, watchdog and maintenance through the existing service helper.
   Confirm the jobs are unloaded and no manually started Vault server is running.
   Make and verify the approved consistent backup. Check the live schema against
   this contract. If incompatible, stop here; plan any migration separately.
5. Activate with `--expected-current`, `--stopped` and `--allow-live-target`.
   Activation preserves the old app and virtualenv by renaming them into a rollback
   directory, copies the existing credential file without printing it, binds the
   existing database, and switches the two app/runtime pointers. Save its receipt.
6. Use `vault_service.sh start`, which loads existing plists without redeploying.
   Check the source/runtime identities, `/readyz`, unauthenticated redirects,
   actual login and a read-only iPad browsing route. Inspect fresh errors without
   copying personal data into a report. If checks fail, stop all jobs, rollback
   with the saved receipt and explicit live flags, then start the previous app.

The release runtime fails before serving when its database binding/schema differs
from the contract; it does not run SQLite bootstrap. Supervision checks `/readyz`
so database failures trigger recovery. Legacy `install` and `restart` reject a
release app pointer to prevent an accidental working-tree redeploy. Use `stop` /
`start` to restart an activated release. Existing auth failures and missing setup
credentials remain failures; this workflow does not disable auth to pass health.

Rollback restores code and runtime pointers and checks the preserved fingerprints.
It does not revert database changes made by normal app use. Avoid schema migration
in this release, retain the consistent backup, and keep all old resources until the
release has been accepted. No automatic cleanup, remote push, provider call or
Board-device deployment is part of this workflow.

## Dependency or schema updates

Update intended requirements, regenerate both locks with Python 3.12 on macOS
arm64 using `uv pip compile --generate-hashes`, and rerun the complete checks.
Regenerate the contract with `DATABASE_URL=sqlite:// .venv/bin/python
scripts/generate_release_schema.py` after an intentional model change. A changed
schema contract requires a compatibility/migration review before live activation;
a newer Alembic source head alone does not establish the state of an old SQLite DB.
