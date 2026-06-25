# Power-Outage Recovery

This runbook covers power-loss preparation, recovery, and controlled validation
for the Mac mini that hosts Vault 966 for the iPad.

## Recovery Target

- **Service target:** Vault 966 should be healthy and reachable from the iPad
  within 15 minutes after stable utility power and the home network return.
- **Data target:** A graceful UPS shutdown should produce no committed-data loss.
  If the database or disk is damaged, recovery is limited to the newest verified
  off-host backup.

The power and network dependencies are:

1. Utility power or UPS battery power.
2. Mac mini boot.
3. Router and any required modem, access point, or Ethernet switch.
4. Vault 966 service start.
5. SQLite and application health verification.

## Current Service Limitation

`scripts/vault_service.sh` currently installs
`~/Library/LaunchAgents/com.vault966.server.plist` and loads it in the
`gui/<user-id>` launchd domain. `RunAtLoad` and `KeepAlive` restart Vault after a
process failure, but a LaunchAgent does not start until its user logs in.

After an unattended reboot, the Mac may be powered on while Vault remains
unavailable. Until the LaunchDaemon migration is implemented, recovery requires:

1. Log in to the Vault host account.
2. Run `scripts/vault_service.sh status`.
3. If necessary, run `scripts/vault_service.sh restart`.
4. Verify `http://127.0.0.1:8000/health` and then verify the iPad UI.

## Required Host Configuration

### Restart after power failure

macOS must be configured to boot automatically when AC power returns:

```bash
sudo pmset -a autorestart 1
pmset -g custom
```

On this Apple silicon Mac mini, System Settings > Energy currently shows **Start
up after power is connected: Always**. `pmset` reports
`autorestartatconnect 1` while the legacy `autorestart` field remains `0`; the
System Settings value is the authoritative host-facing control for this model.
Record both the UI value and `pmset -g custom` output during quarterly drills.

Automatic boot alone does not overcome the current LaunchAgent login limitation
or the FileVault unlock requirement.

### FileVault boundary

FileVault is enabled on the current host. After a full power loss, encrypted
storage remains unavailable until an authorized user unlocks the Mac at the
preboot login screen. Neither a LaunchAgent nor a LaunchDaemon can access the
deployed application or database before that unlock.

Do not disable FileVault solely to make Vault start unattended. The practical
availability controls are:

- Use a UPS to bridge short outages and avoid a full shutdown.
- Configure graceful shutdown before UPS exhaustion.
- After a long outage, unlock the Mac once power and networking are stable.
- Let launchd and the independent Vault watchdog complete application recovery.

A LaunchDaemon can still reduce dependency on a fully initialized GUI session,
but it cannot bypass FileVault.

### UPS and network

- Put the Mac mini, router, modem or fiber terminal, primary access point, and
  required Ethernet switch on UPS-backed outlets.
- Do not put printers, displays, or other high-draw equipment on battery-backed
  outlets.
- Size the UPS for at least 15 minutes at the measured load, with enough time for
  network equipment to reconnect and for a controlled shutdown during a long
  outage.
- Where supported, connect the UPS data cable to the Mac and configure macOS or
  the vendor software for automatic shutdown before battery exhaustion.
- Enable UPS self-test and battery-replacement alerts. Review battery age
  quarterly and replace it according to the manufacturer's guidance.
- Confirm the router, access point, and switch return without a manual button
  press. Preserve any DHCP reservation or stable hostname used by the iPad.

A UPS protects availability and allows clean shutdown. It is not a database
backup, and a backup stored only on the Mac mini does not protect against disk
failure or loss of the host.

## Independent Watchdog and Maintenance

`scripts/vault_service.sh install` and `restart` manage three per-user launchd
jobs:

- `com.vault966.server`: the application and internal health monitor.
- `com.vault966.watchdog`: an independent one-minute health check that force
  restarts the complete server job after three failed attempts.
- `com.vault966.maintenance`: a daily 3:30 AM validated online SQLite backup
  retaining the newest seven completed backups.

The independent watchdog covers a wrapper process that remains present but stops
serving traffic. The maintenance job refuses to publish or rotate backups when
the source or completed backup fails validation.

## Optional LaunchDaemon Migration

Move Vault from the per-login LaunchAgent to a system LaunchDaemon if service
startup before a full GUI session remains valuable after accounting for the
FileVault unlock requirement.

The implementation should:

- Install a root-owned, mode `0644` plist at
  `/Library/LaunchDaemons/com.vault966.server.plist`.
- Load it in the `system/com.vault966.server` domain with `RunAtLoad` and
  `KeepAlive`.
- Run the process as the dedicated Vault account using explicit `UserName` and
  `GroupName` values rather than running the web application as root.
- Keep explicit absolute paths for the deployed app, Python environment, working
  directory, database, and logs under
  `~/Library/Application Support/Vault966`.
- Verify that the service account can traverse every parent directory and read
  the deployed app while retaining read/write access to the database and logs.
- Preserve the existing runtime health monitor and the `/health` startup check.
- Prevent simultaneous LaunchAgent and LaunchDaemon instances from binding port
  `8000`.
- Provide install, restart, status, log, rollback, and uninstall operations for
  the system domain.

This is a future service-management change, not a manual plist-only operation.
The current `scripts/vault_service.sh` always writes and reloads the LaunchAgent.
After migration, it must not be used until it is updated to manage the
LaunchDaemon; otherwise it can recreate the login-bound service or start a
conflicting instance.

Migration acceptance criteria:

1. The old LaunchAgent is unloaded and its plist is removed.
2. The LaunchDaemon starts at boot with no user logged in.
3. `curl --fail http://127.0.0.1:8000/health` succeeds after reboot.
4. The iPad can load and authenticate to Vault after the network returns.
5. A failed Uvicorn process is restarted by launchd.
6. Logs contain no credentials, database contents, or other sensitive data.
7. Rollback to the existing LaunchAgent is documented and tested.

## Post-Outage Recovery

Run these steps from the repository root. Do not edit the deployed app directly
and do not replace or delete the live database during initial diagnosis.

### 1. Establish power and network stability

- Confirm utility power is stable and the UPS is no longer discharging.
- Confirm the router and required network equipment are online.
- Confirm the Mac mini has booted.
- If the LaunchAgent is still in use, log in to the Vault host account.

### 2. Check the service

```bash
scripts/vault_service.sh status
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

If the service is unavailable:

```bash
scripts/vault_service.sh restart
scripts/vault_service.sh status
```

If restart fails, inspect logs without copying sensitive contents into tickets or
chat:

```bash
scripts/vault_service.sh logs
```

### 3. Check SQLite and create a recovery backup

The live database is
`~/Library/Application Support/Vault966/data/vault.db`. Run the project's
read-only quick check before creating a backup:

```bash
.venv/bin/python scripts/sqlite_maintenance.py check --quick
```

The JSON result must contain `"healthy": true` and `"messages": ["ok"]`. If it
does not, stop writes and follow the failed-integrity guidance below.

Create a validated online backup:

```bash
.venv/bin/python scripts/sqlite_maintenance.py backup --keep 7
```

This command uses SQLite's online backup API, includes committed WAL data,
validates the completed backup with `integrity_check`, publishes it atomically
with mode `0600`, and retains the newest seven completed backups. It prints JSON
containing the source, new backup path, and any rotated paths. It refuses to
publish or rotate backups if validation fails.

Move or replicate verified backups to an encrypted off-host destination using
the established host backup system. Backups under `Application Support` are
recovery staging files, not the only retained copy.

### 4. Run full database and domain integrity checks

Run the project's full read-only SQLite integrity check:

```bash
.venv/bin/python scripts/sqlite_maintenance.py check
```

The JSON result must contain `"healthy": true` and `"messages": ["ok"]`. Then run
the repository's domain audit without including sample movie records in its
temporary output:

```bash
STAMP="$(date +%Y%m%d-%H%M%S)"
.venv/bin/python scripts/audit_vault_integrity.py \
  --database-url "sqlite:///$HOME/Library/Application Support/Vault966/data/vault.db" \
  --sample-size 0 \
  --output "/tmp/vault966-integrity-$STAMP.json"
```

The audit exits nonzero for structural issues, source drift, or missing source
IDs. A nonzero result requires review; do not run a backfill, import, restore, or
bulk repair as an automatic outage response.

If either SQLite check is unhealthy, stop writes, preserve the database and its
`-wal`/`-shm` companions, and recover from a verified backup only after the
failure has been assessed. The maintenance backup command intentionally skips
backup and rotation when its source quick check fails. Do not use `.dump`,
`VACUUM`, or repair commands against the sole live copy.

### 5. Validate from the client

- Load Vault from the iPad using its normal bookmark or PWA entry.
- Confirm login succeeds.
- Open the library and one movie detail page.
- Perform read-only navigation; do not use an outage drill to test destructive
  edits.
- Record power-restored, host-booted, health-ready, and iPad-ready timestamps.
- Compare the iPad-ready time with the 15-minute recovery target.

## Quarterly Outage Drill

Run the drill once per quarter and after changes to launchd, UPS, router, storage,
or host power settings. Schedule it during a maintenance window.

### Safety controls

- Obtain explicit approval before disconnecting AC power or forcing a reboot.
- Confirm no import, backfill, migration, or database maintenance is running.
- Create a verified SQLite backup and confirm an off-host backup exists.
- Do not pull power from the Mac mini without a working UPS and a tested shutdown
  policy.
- Use a planned reboot as the default drill. A real AC-loss test is a separate,
  explicitly approved phase.

### Drill checklist

- [ ] Record date, operator, approved scope, and expected recovery target.
- [ ] Record System Settings > Energy as `Always` and capture
      `pmset -g custom`; on this host confirm `autorestartatconnect 1`.
- [ ] Record current service mode: LaunchAgent or LaunchDaemon.
- [ ] Run `scripts/vault_service.sh status` and verify `/health`.
- [ ] Run `scripts/sqlite_maintenance.py check --quick`; confirm it is healthy.
- [ ] Run `scripts/sqlite_maintenance.py backup --keep 7`; record the backup path.
- [ ] Confirm the most recent encrypted off-host backup and its retention date.
- [ ] Confirm UPS status, estimated runtime, self-test result, and battery age.
- [ ] Confirm router, modem or fiber terminal, access point, and required switch
      are on UPS-backed outlets.
- [ ] Perform the approved planned reboot.
- [ ] Before login, test `/health` from another device. Record whether unattended
      service recovery succeeded.
- [ ] If still on the LaunchAgent, log in and verify the documented limitation.
- [ ] Verify local `/health`, iPad login, library, and movie detail access.
- [ ] Run the full `scripts/sqlite_maintenance.py check`.
- [ ] Run `scripts/audit_vault_integrity.py` with `--sample-size 0`.
- [ ] Record boot, network-ready, health-ready, and iPad-ready timestamps.
- [ ] Record pass/fail against the 15-minute target and open follow-up work for
      every failed check.

For an explicitly approved AC-loss phase, disconnect utility input to the UPS,
not individual protected devices. Observe UPS operation and restore utility input
before the shutdown threshold unless testing the configured graceful shutdown.
Never bypass the UPS to simulate an abrupt database power loss.

## Controlled Validation Record

Keep each drill record outside source control with:

- Date, operator, and approval reference.
- Service mode and plist location.
- `pmset` result, excluding unrelated identifying details.
- UPS model, battery age, runtime estimate, and self-test result.
- Backup timestamp and verification result, without database contents.
- SQLite and domain-audit pass/fail summaries.
- Recovery timestamps and measured recovery duration.
- Deviations, corrective owner, and due date.

Do not attach `.env` files, database files, raw logs, credentials, or reports that
contain movie records or user data.
