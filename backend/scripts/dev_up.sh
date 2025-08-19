#!/usr/bin/env bash
# scripts/dev_up.sh
# 개발 환경 부트스트랩 (uv + docker + uvicorn), background 실행
# 사용법:
#   ./scripts/dev_up.sh               # start (기본)
#   ./scripts/dev_up.sh start
#   ./scripts/dev_up.sh restart
#   ./scripts/dev_up.sh init-db       # ✅ Postgres named volume 삭제 후 재생성(완전 초기화)
#   ./scripts/dev_up.sh seed-db       # 기존 DB에 ./postgres/init/*.sql 적용
#   ./scripts/dev_up.sh stop
#   ./scripts/dev_up.sh status
#   ./scripts/dev_up.sh logs

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
PID_FILE=".uvicorn.pid"
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/app.log"

# docker compose 서비스명 (기본: postgres)
service_name="${COMPOSE_SERVICE_POSTGRES:-postgres}"

# compose 프로젝트명(기본: 현재 폴더명). 볼륨 이름은 "<project>_jd_postgres_data"로 가정
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(basename "$ROOT_DIR")}"
POSTGRES_VOLUME_NAME_DEFAULT="${PROJECT_NAME}_jd_postgres_data"
POSTGRES_VOLUME_NAME="${POSTGRES_VOLUME_NAME:-$POSTGRES_VOLUME_NAME_DEFAULT}"

# ===== 공통 유틸 =====
log() { printf '%s %s\n' "[$(date '+%Y-%m-%d %H:%M:%S')]" "$*"; }
exists() { command -v "$1" >/dev/null 2>&1; }

load_env() {
  if [ -f .env ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs)
  fi
}

ensure_prereq() {
  mkdir -p "$LOG_DIR"
  if ! exists uv; then
    log "❌ uv 가 설치되어 있지 않습니다. https://docs.astral.sh/uv/ 참고하여 설치하세요."
    exit 1
  fi
  if ! exists docker || ! docker compose version >/dev/null 2>&1; then
    log "❌ docker / docker compose 를 사용할 수 없습니다."
    exit 1
  fi
}

compose_up_db() {
  log "🐘 PostgreSQL 컨테이너 시작 (${service_name})"
  docker compose up -d "${service_name}"
}

wait_for_db() {
  log "⏳ DB 준비 대기..."
  for _ in {1..30}; do
    if docker compose exec -T "${service_name}" bash -lc \
      'pg_isready -h 127.0.0.1 -p 5432 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" >/dev/null 2>&1'
    then
      log "✅ DB ready"
      return 0
    fi
    sleep 1
  done
  log "❌ DB 연결 실패 (타임아웃)"
  exit 1
}

ensure_uv_env() {
  if [ ! -d ".venv" ]; then
    log "📦 .venv 없으므로 uv venv 생성"
    uv venv
  fi
  log "📥 의존성 설치 (pyproject.toml)"
  uv pip install .
}

is_running() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" || true)"
    if [ -n "${pid:-}" ] && ps -p "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

start_app() {
  if is_running; then
    log "ℹ️ 이미 실행 중입니다 (PID: $(cat "$PID_FILE")). 'restart' 또는 'stop' 사용을 고려하세요."
    return 0
  fi

  log "🚀 FastAPI(uvicorn) 백그라운드 실행 (포트: ${APP_PORT})"
  PYTHONPATH=src nohup uv run uvicorn main:app \
    --host "$APP_HOST" \
    --port "$APP_PORT" \
    --reload \
    > "$LOG_FILE" 2>&1 &

  echo $! > "$PID_FILE"
  log "✅ 서버 시작됨 (PID: $(cat "$PID_FILE"))"
  log "   - http://localhost:${APP_PORT}/healthz"
  log "   - 로그: $(realpath "$LOG_FILE")"
}

stop_app() {
  if is_running; then
    pid="$(cat "$PID_FILE")"
    log "🛑 서버 종료 시도 (PID: $pid)"
    kill "$pid" || true
    for _ in {1..10}; do
      if ps -p "$pid" >/dev/null 2>&1; then sleep 1; else break; fi
    done
    if ps -p "$pid" >/dev/null 2>&1; then
      log "⚠️ 강제 종료(SIGKILL)"
      kill -9 "$pid" || true
    fi
    rm -f "$PID_FILE"
    log "✅ 서버 종료"
  else
    log "ℹ️ 실행 중인 서버가 없습니다."
  fi
}

restart_app() {
  stop_app
  start_app
}

status_app() {
  if is_running; then
    log "✅ 실행 중 (PID: $(cat "$PID_FILE"))"
  else
    log "❌ 정지 상태"
  fi
}

# ===== DB 초기화(볼륨 삭제 후 재생성) & 시드 =====
reset_db_volume() {
  log "🧨 Postgres 컨테이너 정지 및 제거"
  docker compose down "${service_name}" || true

  log "🧹 Postgres named volume 제거: ${POSTGRES_VOLUME_NAME}"
  if docker volume inspect "${POSTGRES_VOLUME_NAME}" >/dev/null 2>&1; then
    docker volume rm "${POSTGRES_VOLUME_NAME}"
    log "✅ 볼륨 삭제 완료"
  else
    log "ℹ️ 볼륨이 존재하지 않습니다: ${POSTGRES_VOLUME_NAME}"
  fi
}

init_db() {
  # 완전 초기화: 볼륨 삭제 → 컨테이너 재생성 → init.sql 자동 실행
  reset_db_volume
  compose_up_db
  wait_for_db
  log "✅ DB 완전 초기화 완료 (.env 반영 + /docker-entrypoint-initdb.d/*.sql 실행)"
}

seed_db() {
  # 기존 DB에 ./postgres/init/*.sql을 재적용 (파괴적 아님)
  compose_up_db
  wait_for_db
  log "🧰 DB 시드 적용 (/docker-entrypoint-initdb.d/*.sql)"
  docker compose exec -T "${service_name}" bash -lc '
    shopt -s nullglob
    SQL_DIR="/docker-entrypoint-initdb.d"
    if [ ! -d "$SQL_DIR" ]; then
      echo "No init dir: $SQL_DIR"; exit 0
    fi
    FILES=("$SQL_DIR"/*.sql)
    if [ ${#FILES[@]} -eq 0 ]; then
      echo "No *.sql files in $SQL_DIR"; exit 0
    fi
    for f in "${FILES[@]}"; do
      echo ">> Applying: $f"
      PGPASSWORD="${POSTGRES_PASSWORD:-postgres}" psql \
        -h 127.0.0.1 -p 5432 \
        -U "${POSTGRES_USER:-postgres}" \
        -d "${POSTGRES_DB:-postgres}" \
        -v ON_ERROR_STOP=1 \
        -f "$f"
    done
  '
  log "✅ DB 시드 적용 완료"
}

tail_logs() {
  log "📜 로그 tail: $LOG_FILE"
  touch "$LOG_FILE"
  tail -n 200 -f "$LOG_FILE"
}

# ===== 엔트리 포인트 =====
load_env
ensure_prereq

cmd="${1:-start}"
case "$cmd" in
  start)
    compose_up_db
    wait_for_db
    ensure_uv_env
    start_app
    ;;
  restart)
    compose_up_db
    wait_for_db
    ensure_uv_env
    restart_app
    ;;
  init-db)
    init_db
    ;;
  seed-db)
    seed_db
    ;;
  stop)
    stop_app
    ;;
  status)
    status_app
    ;;
  logs)
    tail_logs
    ;;
  *)
    echo "사용법: $0 [start|restart|init-db|seed-db|stop|status|logs]"
    exit 1
    ;;
esac
