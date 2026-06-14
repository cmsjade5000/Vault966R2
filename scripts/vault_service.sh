#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.vault966.server"
DOMAIN="gui/$(id -u)"
SERVICE_TARGET="$DOMAIN/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SUPPORT_DIR="$HOME/Library/Application Support/Vault966"
APP_DIR="$SUPPORT_DIR/app"
DATA_DIR="$SUPPORT_DIR/data"
LOG_DIR="$SUPPORT_DIR/logs"
VENV_DIR="$SUPPORT_DIR/.venv"
PYTHON_DIR="$SUPPORT_DIR/python"
RUNTIME="$APP_DIR/scripts/vault_runtime.sh"
DATABASE="$DATA_DIR/vault.db"
STDOUT_LOG="$LOG_DIR/vault_service.log"
STDERR_LOG="$LOG_DIR/vault_service.error.log"
HEALTH_URL="http://127.0.0.1:8000/health"

usage() {
  cat <<USAGE
Usage: scripts/vault_service.sh <install|uninstall|start|stop|restart|status|logs>

  install    Install, load, and start the macOS background service
  uninstall  Stop and remove the background service
  start      Start an installed service
  stop       Stop and unload the service (the plist remains installed)
  restart    Reload the service and restart the Vault
  status     Show launchd state and check the HTTP health endpoint
  logs       Follow service output and error logs
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
  plutil -lint "$PLIST" >/dev/null
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

deploy_app() {
  command -v uv >/dev/null 2>&1 || {
    echo "Cannot install service: uv is required." >&2
    exit 1
  }

  mkdir -p "$APP_DIR" "$LOG_DIR"
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.pytest_cache/' \
    --exclude '.ruff_cache/' \
    --exclude '.uv-python/' \
    --exclude '.venv/' \
    --exclude 'node_modules/' \
    --exclude 'reports/' \
    --exclude 'data/*.log' \
    --exclude 'data/*.pid' \
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

is_loaded() {
  launchctl print "$SERVICE_TARGET" >/dev/null 2>&1
}

load_service() {
  if is_loaded; then
    launchctl bootout "$SERVICE_TARGET" >/dev/null 2>&1 || true
    for _ in {1..50}; do
      if ! is_loaded; then
        break
      fi
      sleep 0.1
    done
  fi
  if is_loaded; then
    echo "Service did not finish stopping; refusing to load a second copy." >&2
    exit 1
  fi
  launchctl bootstrap "$DOMAIN" "$PLIST"
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

case "${1:-}" in
  install)
    prepare_database
    deploy_app
    write_plist
    load_service
    wait_for_health
    echo "Vault service installed and started."
    echo "It will start automatically whenever this user logs in."
    ;;
  uninstall)
    if is_loaded; then
      launchctl bootout "$SERVICE_TARGET"
    fi
    rm -f "$PLIST"
    echo "Vault service stopped and removed."
    ;;
  start)
    if [[ ! -f "$PLIST" ]]; then
      echo "Service is not installed. Run: scripts/vault_service.sh install" >&2
      exit 1
    fi
    if ! is_loaded; then
      launchctl bootstrap "$DOMAIN" "$PLIST"
    else
      launchctl kickstart "$SERVICE_TARGET"
    fi
    wait_for_health
    echo "Vault service started."
    ;;
  stop)
    if is_loaded; then
      launchctl bootout "$SERVICE_TARGET"
      echo "Vault service stopped."
    else
      echo "Vault service is already stopped."
    fi
    ;;
  restart)
    prepare_database
    deploy_app
    write_plist
    load_service
    wait_for_health
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
  *)
    usage
    exit 1
    ;;
esac
