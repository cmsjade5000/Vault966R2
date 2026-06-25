#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
PID_FILE="${PID_FILE:-$ROOT_DIR/data/vault_server.pid}"
LOG_FILE="${LOG_FILE:-$ROOT_DIR/data/vault_server.log}"
RELOAD="${RELOAD:-1}"
FORCE=0
WATCH=0

usage() {
  cat <<USAGE
Usage: scripts/vault_server.sh <start|stop|restart|status|logs> [--force] [--no-reload] [--watch]

Environment overrides:
  PORT (default: 8000)
  HOST (default: 0.0.0.0)
  PID_FILE (default: data/vault_server.pid)
  LOG_FILE (default: data/vault_server.log)
  RELOAD (default: 1)

Examples:
  scripts/vault_server.sh start
  scripts/vault_server.sh start --watch
  scripts/vault_server.sh stop
  scripts/vault_server.sh status
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd lsof
require_cmd python3

cmd="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      ;;
    --no-reload)
      RELOAD=0
      ;;
    --watch)
      WATCH=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

mkdir -p "$(dirname "$PID_FILE")"

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  return 1
}

list_listeners() {
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN || true
}

kill_listener() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return
  fi
  kill "$pid" 2>/dev/null || true
  for _ in {1..8}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return
    fi
    sleep 0.25
  done
  kill -9 "$pid" 2>/dev/null || true
}

ensure_port_free() {
  local listeners
  listeners="$(list_listeners)"
  if [[ -z "$listeners" ]]; then
    return 0
  fi
  if [[ $FORCE -eq 0 ]]; then
    echo "Port $PORT is already in use:" >&2
    echo "$listeners" >&2
    echo "Re-run with --force to stop listeners." >&2
    exit 1
  fi
  while read -r line; do
    local pid
    pid="$(echo "$line" | awk '{print $2}')"
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      kill_listener "$pid"
    fi
  done <<<"$(echo "$listeners" | tail -n +2)"
}

start_server() {
  if is_running; then
    echo "Server already running (pid $(cat "$PID_FILE"))"
    exit 0
  fi
  ensure_port_free
  local args
  args=("-m" "uvicorn" "api.main:app" "--host" "$HOST" "--port" "$PORT")
  if [[ $RELOAD -eq 1 ]]; then
    args+=("--reload")
  fi

  if [[ $WATCH -eq 1 ]]; then
    nohup bash -c "while true; do python3 ${args[*]} ; sleep 1; done" \
      >"$LOG_FILE" 2>&1 &
  else
    nohup python3 "${args[@]}" >"$LOG_FILE" 2>&1 &
  fi
  echo $! >"$PID_FILE"
  echo "Server started on $HOST:$PORT (pid $!)"
  echo "Log: $LOG_FILE"
}

stop_server() {
  if ! is_running; then
    echo "No server pid found."
    list_listeners
    exit 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill_listener "$pid"
  rm -f "$PID_FILE"
  echo "Server stopped."
}

status_server() {
  if is_running; then
    echo "Server running (pid $(cat "$PID_FILE"))"
  else
    echo "Server not running."
  fi
  list_listeners
}

logs_server() {
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 120 "$LOG_FILE"
  else
    echo "No log file yet: $LOG_FILE"
  fi
}

case "$cmd" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    status_server
    ;;
  logs)
    logs_server
    ;;
  *)
    usage
    exit 1
    ;;
esac
