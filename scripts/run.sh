# scripts/dev_all.sh
#!/usr/bin/env bash
set -Eeuo pipefail

# -------- paths & dirs --------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

LOG_DIR="$ROOT_DIR/.logs"
PID_DIR="$ROOT_DIR/.pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

BACKEND_STARTED=0

# -------- helpers --------
stop_backend() {
  if [[ $BACKEND_STARTED -eq 1 ]]; then
    echo "[backend] stopping…"
    (cd "$BACKEND_DIR" && ./scripts/dev_up.sh stop) || true
    BACKEND_STARTED=0
  fi
}

stop_frontend() {
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[frontend] killing pid $pid…"
      kill "$pid" || true
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" || true
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi
}

cleanup_on_error() {
  local code=$?
  if [[ $code -ne 0 ]]; then
    echo "✖ 오류 발생. 모두 중단합니다."
  fi
  stop_frontend || true
  stop_backend || true
  exit $code
}
trap cleanup_on_error ERR

start_backend() {
  echo "[backend] starting…"
  # dev_up.sh 가 내부에서 docker compose -d 등을 쓰는 케이스 고려 → PID 관리 대신 stop 훅만 사용
  (cd "$BACKEND_DIR" && ./scripts/dev_up.sh start \
      1>"$LOG_DIR/backend.out" 2>"$LOG_DIR/backend.err")
  BACKEND_STARTED=1
  echo "[backend] start command ok"
}

start_frontend() {
  echo "[frontend] starting…"
  cd "$FRONTEND_DIR"

  # node_modules 없으면 설치
  if [[ ! -d node_modules ]]; then
    echo "[frontend] installing deps (npm ci → fallback npm install)…"
    npm ci 1>"$LOG_DIR/frontend.npm.out" 2>"$LOG_DIR/frontend.npm.err" \
      || npm install 1>>"$LOG_DIR/frontend.npm.out" 2>>"$LOG_DIR/frontend.npm.err"
  fi

  # dev 서버 백그라운드 실행
  nohup npm run dev 1>"$LOG_DIR/frontend.out" 2>"$LOG_DIR/frontend.err" &
  local pid=$!
  echo "$pid" > "$FRONTEND_PID_FILE"
  echo "[frontend] pid=$pid"

  # 초반 즉시 크래시 감지
  sleep 2
  kill -0 "$pid" 2>/dev/null || { echo "[frontend] failed to stay running. see $LOG_DIR/frontend.err"; exit 1; }

  cd "$ROOT_DIR"
}

status() {
  echo "== status =="
  echo "[backend] dev_up.sh로 구동됨(상태는 해당 스크립트/도커에서 확인)"
  if [[ -f "$FRONTEND_PID_FILE" ]] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
    echo "[frontend] running (pid $(cat "$FRONTEND_PID_FILE"))"
  else
    echo "[frontend] not running"
  fi
}

logs() {
  echo "== tail logs (Ctrl-C to exit) =="
  tail -n 200 -f "$LOG_DIR"/backend.out "$LOG_DIR"/backend.err \
                 "$LOG_DIR"/frontend.out "$LOG_DIR"/frontend.err
}

case "${1:-start}" in
  start)
    start_backend
    start_frontend
    # 정상 종료 시에는 cleanup 트랩 해제(백그라운드 유지)
    trap - ERR
    echo "✓ backend + frontend started."
    echo "  logs: $LOG_DIR"
    echo "  commands: $0 stop | $0 status | $0 logs"
    ;;
  stop)
    stop_frontend
    stop_backend
    trap - ERR
    echo "✓ stopped."
    ;;
  status) status ;;
  logs) logs ;;
  *)
    echo "Usage: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
