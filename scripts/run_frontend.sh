#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

PID_FILE="$PID_DIR/frontend.pid"
LOG_FILE="$LOG_DIR/frontend.log"

mkdir -p "$PID_DIR" "$LOG_DIR"

usage() {
  echo "Usage: $0 {start|stop|restart|status|logs}" >&2
  exit 2
}

is_running() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start() {
  # 이미 실행 중이면 중복 실행 차단
  if [[ -f "$PID_FILE" ]]; then
    existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if is_running "$existing_pid"; then
      echo "[frontend] already running (pid $existing_pid)"
      exit 0
    else
      rm -f "$PID_FILE"
    fi
  fi

  command -v npm >/dev/null || { echo "npm not found"; exit 1; }

  cd "$FRONTEND_DIR"

  # 필요한 경우에만 설치
  if [[ ! -d node_modules ]]; then
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  fi

  # 백그라운드 실행 + 로그 저장
  # macOS/Linux 호환: setsid 없이도 동작하도록 단순화
  echo "[frontend] starting… logs: $LOG_FILE"
  # 기존 로그 백업
  if [[ -f "$LOG_FILE" ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d%H%M%S).bak" || true
  fi

  # 백그라운드 실행
  nohup npm run dev >>"$LOG_FILE" 2>&1 &
  new_pid="$!"
  echo "$new_pid" > "$PID_FILE"

  # 짧게 확인: 바로 죽었는지 체크 (포트점유/빌드실패 등)
  sleep 1
  if ! is_running "$new_pid"; then
    echo "[frontend] failed to start. recent logs:"
    tail -n 50 "$LOG_FILE" || true
    rm -f "$PID_FILE"
    exit 1
  fi

  echo "[frontend] started (pid $new_pid)"
}

stop() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "[frontend] not running"
    return 0
  fi

  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if ! is_running "$pid"; then
    echo "[frontend] not running (stale pid file?)"
    rm -f "$PID_FILE"
    return 0
  fi

  echo "[frontend] stopping pid $pid…"
  kill -TERM "$pid" 2>/dev/null || true
  # 최대 5초 대기 후 강제 종료
  for i in {1..5}; do
    sleep 1
    is_running "$pid" || break
  done
  if is_running "$pid"; then
    echo "[frontend] force killing $pid"
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "[frontend] stopped"
}

status() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if is_running "$pid"; then
      echo "[frontend] running (pid $pid)"
      exit 0
    fi
  fi
  echo "[frontend] not running"
  exit 1
}

logs() {
  [[ -f "$LOG_FILE" ]] || { echo "no log file yet: $LOG_FILE"; exit 1; }
  tail -f "$LOG_FILE"
}

cmd="${1:-start}"
case "$cmd" in
  start)   start ;;
  stop)    stop ;;
  restart) stop || true; start ;;
  status)  status ;;
  logs)    logs ;;
  *)       usage ;;
esac
