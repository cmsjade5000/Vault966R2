# Personal authentication preserved with reviewed dependencies

This local candidate starts from dependency commit
`a6647022c62ea387e9f3cd4a178f3aa115329c1d` and restores the approved application
behavior installed as release `2c0ee37dfcd2-8e086af29f36`. It retains the reviewed
requirements, hashed runtime/development locks, CI pins, formatter policy,
dependency compatibility tests, and generated-client tooling.

Archived profiles retain their credentials and preferences for reversible recovery.
Those retained credentials cannot authenticate. Protected routes, assistant session
access, and the public login redirect each require an active profile and the signed
session's current profile revision. Archive and restore invalidate sessions and
unlock cookies. Personal mode requires direct personal credentials and does not
fall back to environment credentials or a shared unlock/profile-selection flow.
Legacy mode retains its explicit shared unlock and revision-zero session behavior.

The browser-bound, one-use owner claim, strict origin checks, local setup guard,
reversible archive services, existing profile menu, Picker UI, and public login
artwork are preserved. Setup forms retain the origin policy needed for ordinary
browser POSTs. These restored files are existing approved application behavior,
rather than a new live account reset or schema change.

The schema contract and Alembic head match the installed personal-auth release.
Activation must use the immutable macOS release runbook, verify the existing schema
read-only, preserve the database binding and configuration, and make a consistent
private backup while writers are stopped. This dependency deployment applies no
migration, stamp, profile archive/restore, credential replacement, or auth setting
change. Its rollback restores code/runtime pointers while retaining the current
database. Code predating personal authentication is not a safe rollback target.

`tests/test_dependency_auth_lifecycle.py` adds synthetic regression checks across
credential login, switch-person, ordinary UI/API, assistant session access, public
login redirects, missing profiles, missing revision claims, personal-mode shared
unlocks, profile-cookie spoofing, and setup state with only archived credentials.
Restored setup/archive tests cover races, transaction failures, origin rejection,
grant expiry/reissue, preference retention, and replacement-account recovery.

Real login acceptance requires the owner to enter their credentials personally.
Synthetic acceptance and anonymous service checks do not establish that result.
No public push or merge is part of this local release; remote CI for its dependency
base does not establish remote CI for the combined local commit.
