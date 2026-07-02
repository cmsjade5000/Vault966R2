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
SHUTDOWN_GRACE="${SHUTDOWN_GRACE:-10}"
SUPERVISOR_INTERVAL="${SUPERVISOR_INTERVAL:-1}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Vault Python environment is missing: $PYTHON" >&2
  exit 1
fi

cd "$ROOT_DIR"

child_pid=""
monitor_pid=""
stopping=0
runtime_state_dir="$(mktemp -d "${TMPDIR:-/tmp}/vault-runtime.XXXXXX")"
forced_shutdown_marker="$runtime_state_dir/forced-shutdown"

# kill -0 succeeds for zombies, but an exited process is no longer serviceable.
process_is_running() {
  local pid="$1"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi

  local state
  if ! state="$(ps -o state= -p "$pid" 2>/dev/null)"; then
    return 0
  fi
  state="${state//[[:space:]]/}"
  [[ -n "$state" && "$state" != Z* ]]
}

child_is_running() {
  process_is_running "$child_pid"
}

terminate_child() {
  if ! child_is_running; then
    return
  fi

  kill "$child_pid" 2>/dev/null || true

  local attempts
  attempts=$((SHUTDOWN_GRACE * 10))
  for ((i = 0; i < attempts; i++)); do
    if ! child_is_running; then
      return
    fi
    sleep 0.1
  done

  if child_is_running; then
    echo "Vault did not stop within ${SHUTDOWN_GRACE}s; forcing termination." >&2
    touch "$forced_shutdown_marker" 2>/dev/null || true
    kill -KILL "$child_pid" 2>/dev/null || true
  fi
}

# shellcheck disable=SC2329
stop_processes() {
  if (( stopping )); then
    return
  fi
  stopping=1

  if process_is_running "$monitor_pid"; then
    kill "$monitor_pid" 2>/dev/null || true
    wait "$monitor_pid" 2>/dev/null || true
  fi
  terminate_child
  if [[ -n "$child_pid" ]]; then
    wait "$child_pid" 2>/dev/null || true
  fi
  rm -rf "$runtime_state_dir" 2>/dev/null || true
}

# shellcheck disable=SC2329
handle_signal() {
  stop_processes
  exit 0
}

trap stop_processes EXIT
trap handle_signal INT TERM

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

  while child_is_running; do
    if curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
      failures=0
    else
      failures=$((failures + 1))
      echo "Vault health check failed ($failures/$HEALTH_FAILURE_LIMIT): $HEALTH_URL" >&2
      if (( failures >= HEALTH_FAILURE_LIMIT )); then
        echo "Vault is unhealthy; terminating it so launchd can restart it." >&2
        terminate_child
        return 137
      fi
    fi
    sleep "$HEALTH_INTERVAL"
  done
}

monitor_health &
monitor_pid=$!

while child_is_running; do
  if ! process_is_running "$monitor_pid"; then
    echo "Vault health monitor stopped unexpectedly; terminating Vault." >&2
    terminate_child
    break
  fi
  sleep "$SUPERVISOR_INTERVAL"
done

set +e
monitor_status=0
if [[ -n "$monitor_pid" ]]; then
  wait "$monitor_pid" 2>/dev/null
  monitor_status=$?
fi
wait "$child_pid"
status=$?
set -e
if [[ "$monitor_status" -eq 137 || -f "$forced_shutdown_marker" ]]; then
  status=137
fi
exit "$status"
