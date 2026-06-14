#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT}/health}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-30}"
HEALTH_FAILURE_LIMIT="${HEALTH_FAILURE_LIMIT:-3}"
STARTUP_GRACE="${STARTUP_GRACE:-20}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Vault Python environment is missing: $PYTHON" >&2
  exit 1
fi

cd "$ROOT_DIR"

child_pid=""
monitor_pid=""

stop_processes() {
  if [[ -n "$monitor_pid" ]] && kill -0 "$monitor_pid" 2>/dev/null; then
    kill "$monitor_pid" 2>/dev/null || true
  fi
  if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
    kill "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
}

trap stop_processes EXIT INT TERM

"$PYTHON" -m uvicorn api.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --log-level info \
  --access-log &
child_pid=$!

monitor_health() {
  sleep "$STARTUP_GRACE"
  local failures=0

  while kill -0 "$child_pid" 2>/dev/null; do
    if curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
      failures=0
    else
      failures=$((failures + 1))
      echo "Vault health check failed ($failures/$HEALTH_FAILURE_LIMIT): $HEALTH_URL" >&2
      if (( failures >= HEALTH_FAILURE_LIMIT )); then
        echo "Vault is unhealthy; terminating it so launchd can restart it." >&2
        kill "$child_pid" 2>/dev/null || true
        return
      fi
    fi
    sleep "$HEALTH_INTERVAL"
  done
}

monitor_health &
monitor_pid=$!

set +e
wait "$child_pid"
status=$?
set -e
exit "$status"
