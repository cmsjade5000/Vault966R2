#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.vault966.server"
WATCHDOG_LABEL="com.vault966.watchdog"
MAINTENANCE_LABEL="com.vault966.maintenance"
DOMAIN="gui/$(id -u)"
SERVICE_TARGET="$DOMAIN/$LABEL"
WATCHDOG_TARGET="$DOMAIN/$WATCHDOG_LABEL"
MAINTENANCE_TARGET="$DOMAIN/$MAINTENANCE_LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WATCHDOG_PLIST="$HOME/Library/LaunchAgents/$WATCHDOG_LABEL.plist"
MAINTENANCE_PLIST="$HOME/Library/LaunchAgents/$MAINTENANCE_LABEL.plist"
SUPPORT_DIR="$HOME/Library/Application Support/Vault966"
APP_DIR="$SUPPORT_DIR/app"
DATA_DIR="$SUPPORT_DIR/data"
LOG_DIR="$SUPPORT_DIR/logs"
VENV_DIR="$SUPPORT_DIR/.venv"
PYTHON_DIR="$SUPPORT_DIR/python"
RUNTIME="$APP_DIR/scripts/vault_runtime.sh"
WATCHDOG="$APP_DIR/scripts/vault_watchdog.sh"
MAINTENANCE="$APP_DIR/scripts/sqlite_maintenance.py"
DATABASE="$DATA_DIR/vault.db"
STDOUT_LOG="$LOG_DIR/vault_service.log"
STDERR_LOG="$LOG_DIR/vault_service.error.log"
WATCHDOG_STDOUT_LOG="$LOG_DIR/vault_watchdog.log"
WATCHDOG_STDERR_LOG="$LOG_DIR/vault_watchdog.error.log"
MAINTENANCE_STDOUT_LOG="$LOG_DIR/vault_maintenance.log"
MAINTENANCE_STDERR_LOG="$LOG_DIR/vault_maintenance.error.log"
HEALTH_URL="http://127.0.0.1:8000/health"

usage() {
  cat <<USAGE
Usage: scripts/vault_service.sh <install|uninstall|start|stop|restart|status|logs|verify> [path]

  install    Install, load, and start the macOS background service
  uninstall  Stop and remove the background service
  start      Start an installed service
  stop       Stop and unload the service (the plist remains installed)
  restart    Reload the service and restart the Vault
  status     Show launchd state and check the HTTP health endpoint
  logs       Follow service output and error logs
  verify     Check a live route or asset path (default: /health)
USAGE
}

write_plist() {
  mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
  cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNTIME</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$STDERR_LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHON</key>
    <string>$VENV_DIR/bin/python</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
</dict>
</plist>
PLIST

  cat >"$WATCHDOG_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$WATCHDOG_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$WATCHDOG</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>$WATCHDOG_STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$WATCHDOG_STDERR_LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST

  cat >"$MAINTENANCE_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$MAINTENANCE_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_DIR/bin/python</string>
    <string>$MAINTENANCE</string>
    <string>backup</string>
    <string>--keep</string>
    <string>7</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>$MAINTENANCE_STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$MAINTENANCE_STDERR_LOG</string>
</dict>
</plist>
PLIST

  plutil -lint "$PLIST" >/dev/null
  plutil -lint "$WATCHDOG_PLIST" >/dev/null
  plutil -lint "$MAINTENANCE_PLIST" >/dev/null
}

prepare_database() {
  mkdir -p "$DATA_DIR"

  if [[ -L "$ROOT_DIR/vault.db" ]]; then
    return
  fi

  if [[ ! -f "$DATABASE" ]]; then
    if [[ ! -f "$ROOT_DIR/vault.db" ]]; then
      echo "Cannot install service: source vault.db is missing." >&2
      exit 1
    fi
    cp -p "$ROOT_DIR/vault.db" "$DATABASE"
  fi

  if [[ -f "$ROOT_DIR/vault.db" ]]; then
    backup="$ROOT_DIR/vault.db.before-service-$(date +%Y%m%d-%H%M%S).bak"
    mv "$ROOT_DIR/vault.db" "$backup"
    echo "Original database preserved at: $backup"
  fi
  ln -s "$DATABASE" "$ROOT_DIR/vault.db"
}

clean_stale_deploy_artifacts() {
  rm -rf \
    "$APP_DIR/.git" \
    "$APP_DIR/.agents" \
    "$APP_DIR/.codex" \
    "$APP_DIR/.pytest_cache" \
    "$APP_DIR/.ruff_cache" \
    "$APP_DIR/.uv-python" \
    "$APP_DIR/.venv" \
    "$APP_DIR/node_modules" \
    "$APP_DIR/reports" \
    "$APP_DIR/skills"

  find "$APP_DIR" -maxdepth 1 -type f \( \
    -name 'vault.db-journal' \
    -o -name 'vault.db*.bak' \
    -o -name '* 2.py' \
    -o -name '* 2.js' \
    -o -name '* 2.css' \
  \) -delete
}

deploy_app() {
  command -v uv >/dev/null 2>&1 || {
    echo "Cannot install service: uv is required." >&2
    exit 1
  }

  mkdir -p "$APP_DIR" "$LOG_DIR"
  clean_stale_deploy_artifacts
  rsync -a --delete \
    --exclude '.git' \
    --exclude '.agents/' \
    --exclude '.codex/' \
    --exclude '.DS_Store' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '.uv-python/' \
    --exclude '.venv/' \
    --exclude 'node_modules/' \
    --exclude 'reports/' \
    --exclude 'skills/' \
    --exclude 'data/*.log' \
    --exclude 'data/*.pid' \
    --exclude '*.bak' \
    --exclude '* 2.py' \
    --exclude '* 2.js' \
    --exclude '* 2.css' \
    --exclude 'vault.db' \
    --exclude 'vault.db-journal' \
    --exclude 'vault.db.*.bak' \
    "$ROOT_DIR/" "$APP_DIR/"

  ln -sfn "$DATABASE" "$APP_DIR/vault.db"
  if [[ -f "$APP_DIR/.env" ]]; then
    chmod 600 "$APP_DIR/.env"
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    uv python install 3.12 --install-dir "$PYTHON_DIR" --no-bin
    managed_python="$(find "$PYTHON_DIR" -type f -path '*/bin/python3.12' -print -quit)"
    if [[ -z "$managed_python" ]]; then
      echo "Installed Python 3.12 could not be located under $PYTHON_DIR." >&2
      exit 1
    fi
    uv venv --python "$managed_python" "$VENV_DIR"
  fi
  uv pip install --python "$VENV_DIR/bin/python" -r "$APP_DIR/requirements.txt"
}

is_target_loaded() {
  launchctl print "$1" >/dev/null 2>&1
}

is_loaded() {
  is_target_loaded "$SERVICE_TARGET"
}

bootstrap_target() {
  local target="$1"
  local plist="$2"
  local attempts="${LAUNCHCTL_BOOTSTRAP_ATTEMPTS:-5}"
  local delay="${LAUNCHCTL_BOOTSTRAP_DELAY:-0.25}"
  local last_error
  last_error="$(mktemp "${TMPDIR:-/tmp}/vault966-bootstrap-error.XXXXXX")"

  if is_target_loaded "$target"; then
    rm -f "$last_error"
    return
  fi

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    : >"$last_error"
    if launchctl bootstrap "$DOMAIN" "$plist" 2>"$last_error"; then
      rm -f "$last_error"
      return
    fi

    if is_target_loaded "$target"; then
      rm -f "$last_error"
      return
    fi

    if ((attempt < attempts)); then
      launchctl bootout "$target" >/dev/null 2>&1 || true
      sleep "$delay"
    fi
  done

  echo "Could not load launchd job after $attempts attempts: $target" >&2
  if [[ -s "$last_error" ]]; then
    cat "$last_error" >&2
  fi
  rm -f "$last_error"
  exit 1
}

bootout_target() {
  local target="$1"
  if is_target_loaded "$target"; then
    launchctl bootout "$target" >/dev/null 2>&1 || true
    for _ in {1..50}; do
      if ! is_target_loaded "$target"; then
        return
      fi
      sleep 0.1
    done
  fi
  if is_target_loaded "$target"; then
    echo "Service did not finish stopping: $target" >&2
    exit 1
  fi
}

stop_all_targets() {
  bootout_target "$WATCHDOG_TARGET"
  bootout_target "$MAINTENANCE_TARGET"
  bootout_target "$SERVICE_TARGET"
}

load_service() {
  stop_all_targets
  bootstrap_target "$SERVICE_TARGET" "$PLIST"
}

load_auxiliary_services() {
  bootstrap_target "$MAINTENANCE_TARGET" "$MAINTENANCE_PLIST"
  bootstrap_target "$WATCHDOG_TARGET" "$WATCHDOG_PLIST"
}

ensure_auxiliary_services() {
  if ! is_target_loaded "$MAINTENANCE_TARGET"; then
    bootstrap_target "$MAINTENANCE_TARGET" "$MAINTENANCE_PLIST"
  fi
  if ! is_target_loaded "$WATCHDOG_TARGET"; then
    bootstrap_target "$WATCHDOG_TARGET" "$WATCHDOG_PLIST"
  fi
}

wait_for_health() {
  for _ in {1..50}; do
    if curl --fail --silent --show-error --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
      echo "Health: healthy ($HEALTH_URL)"
      return
    fi
    sleep 0.2
  done

  echo "Vault service did not become healthy: $HEALTH_URL" >&2
  echo "Check logs with: scripts/vault_service.sh logs" >&2
  exit 1
}

verify_path() {
  local path="${1:-/health}"
  if [[ "$path" != /* ]]; then
    path="/$path"
  fi

  local url="http://127.0.0.1:8000$path"
  local headers
  headers="$(mktemp "${TMPDIR:-/tmp}/vault966-verify-headers.XXXXXX")"
  local body
  body="$(mktemp "${TMPDIR:-/tmp}/vault966-verify-body.XXXXXX")"
  local status

  if ! status="$(curl --silent --show-error --location --max-time 10 \
    --dump-header "$headers" \
    --output "$body" \
    --write-out '%{http_code}' \
    "$url")"; then
    rm -f "$headers" "$body"
    echo "Live verify failed: $url could not be reached" >&2
    exit 1
  fi

  local content_type
  content_type="$(sed -n '/^[Cc]ontent-[Tt]ype:/ { s/\r$//; p; q; }' "$headers")"
  rm -f "$headers" "$body"

  if [[ ! "$status" =~ ^[23] ]]; then
    echo "Live verify failed: $url returned HTTP $status" >&2
    exit 1
  fi

  echo "Live verify: $url HTTP $status"
  if [[ -n "$content_type" ]]; then
    echo "$content_type"
  fi
}

case "${1:-}" in
  install)
    prepare_database
    deploy_app
    write_plist
    load_service
    wait_for_health
    load_auxiliary_services
    echo "Vault service installed and started."
    echo "It will start automatically whenever this user logs in."
    ;;
  uninstall)
    bootout_target "$WATCHDOG_TARGET"
    bootout_target "$MAINTENANCE_TARGET"
    bootout_target "$SERVICE_TARGET"
    rm -f "$PLIST" "$WATCHDOG_PLIST" "$MAINTENANCE_PLIST"
    echo "Vault service stopped and removed."
    ;;
  start)
    if [[ ! -f "$PLIST" ]]; then
      echo "Service is not installed. Run: scripts/vault_service.sh install" >&2
      exit 1
    fi
    if ! is_loaded; then
      bootstrap_target "$SERVICE_TARGET" "$PLIST"
    else
      launchctl kickstart -k "$SERVICE_TARGET"
    fi
    wait_for_health
    ensure_auxiliary_services
    echo "Vault service started."
    ;;
  stop)
    if is_loaded || is_target_loaded "$WATCHDOG_TARGET" || is_target_loaded "$MAINTENANCE_TARGET"; then
      stop_all_targets
      echo "Vault service stopped."
    else
      echo "Vault service is already stopped."
    fi
    ;;
  restart)
    prepare_database
    stop_all_targets
    deploy_app
    write_plist
    bootstrap_target "$SERVICE_TARGET" "$PLIST"
    wait_for_health
    load_auxiliary_services
    echo "Vault service restarted."
    ;;
  status)
    if is_loaded; then
      launchctl print "$SERVICE_TARGET" | awk '
        /^[[:space:]]*state =/ ||
        /^[[:space:]]*pid =/ ||
        /^[[:space:]]*last exit code =/ {
          sub(/^[[:space:]]*/, "")
          key = $0
          sub(/[[:space:]]*=.*/, "", key)
          if (!seen[key]++) {
            print
          }
        }
      '
    else
      echo "Service: stopped"
    fi
    if is_target_loaded "$WATCHDOG_TARGET"; then
      echo "Watchdog: loaded"
    else
      echo "Watchdog: stopped"
    fi
    if is_target_loaded "$MAINTENANCE_TARGET"; then
      echo "Maintenance: loaded"
    else
      echo "Maintenance: stopped"
    fi
    if curl --fail --silent --show-error --max-time 5 "$HEALTH_URL" >/dev/null; then
      echo "Health: healthy ($HEALTH_URL)"
    else
      echo "Health: unavailable"
      exit 1
    fi
    ;;
  logs)
    mkdir -p "$LOG_DIR"
    touch "$STDOUT_LOG" "$STDERR_LOG"
    tail -n 80 -F "$STDOUT_LOG" "$STDERR_LOG"
    ;;
  verify)
    verify_path "${2:-/health}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
