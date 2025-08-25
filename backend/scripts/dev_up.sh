#!/usr/bin/env bash
# scripts/dev_up.sh
# 개발 환경 부트스트랩 (uv + docker + uvicorn), background 실행
# 사용법:
#   ./scripts/dev_up.sh               # start (기본)
#   ./scripts/dev_up.sh start
#   ./scripts/dev_up.sh restart
#   ./scripts/dev_up.sh init-db       # ✅ Postgres named volume 삭제 후 재생성(완전 초기화)
#   ./scripts/dev_up.sh seed-db       # 기존 DB에 ./postgres/init/*.sql 적용
#   ./scripts/dev_up.sh sync-prompts  # ✅ src/prompts → DB 동기화 (수동 실행)
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

# 프롬프트 동기화 제어
AUTO_SYNC_PROMPTS="${AUTO_SYNC_PROMPTS:-1}"     # 1/true/yes/on → 자동 동기화
PROMPT_ROOT="${PROMPT_ROOT:-src/prompts}"       # YAML 루트
PROMPT_LANG="${PROMPT_LANG:-}"                  # 특정 언어만 (예: ko). 비어있으면 전체

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

# 빈 포트 찾기 (49152~65535에서 검색)
pick_free_port() {
  local port
  for port in $(seq 55000 65535); do
    if ! lsof -i :"$port" >/dev/null 2>&1; then
      echo "$port"; return 0
    fi
  done
  return 1
}

ensure_host_port() {
  if [ -z "${PGPORT:-}" ] || [ "${PGPORT}" = "auto" ]; then
    local free
    free="$(pick_free_port)" || { log "❌ 사용 가능한 포트를 찾지 못했습니다"; exit 1; }
    export PGPORT="$free"
    log "🔌 호스트 DB 포트 자동 선택: ${PGPORT}"
  else
    log "🔌 호스트 DB 포트 지정됨: ${PGPORT}"
  fi
}

compose_up_db() {
  log "🐘 PostgreSQL 컨테이너 시작 (${service_name})"
  docker compose up -d "${service_name}"
}

wait_for_db() {
  log "⏳ DB 준비 대기..."
  for _ in {1..60}; do
    if docker compose exec -T "${service_name}" env -u PGPORT -u PGHOST bash -lc \
      'pg_isready -h 127.0.0.1 -p 5432 -U "${POSTGRES_USER:-postgres}" -d postgres' >/dev/null 2>&1; then
      log "✅ DB ready"
      return 0
    fi
    sleep 1
  done
  log "❌ DB 연결 실패 (타임아웃)"
  exit 1
}


# 컨테이너 내부에 PGDATABASE가 없으면 생성
ensure_db_exists_in_container() {
  log "🔍 DB 존재 보장 (컨테이너 내 PGDATABASE 기준)"
  docker compose exec -T "${service_name}" env -u PGPORT -u PGHOST bash -lc '
    set -euo pipefail
    DB="${PGDATABASE:-${POSTGRES_DB:-postgres}}"
    USER="${POSTGRES_USER:-postgres}"
    echo ">> PGDATABASE: $DB / POSTGRES_USER: $USER (PGPORT/PGHOST unset)"
    if [ "$DB" = "postgres" ]; then
      echo "base DB(postgres) 사용 → 생성 생략"; exit 0
    fi
    EXISTS="$(psql -h 127.0.0.1 -p 5432 -U "$USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='\''$DB'\''" | tr -d "[:space:]")"
    if [ "$EXISTS" = "1" ]; then
      echo "DB already exists: $DB"
    else
      echo "Creating DB: $DB"
      psql -h 127.0.0.1 -p 5432 -U "$USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "CREATE DATABASE \"$DB\" TEMPLATE template0 ENCODING '\''UTF8'\'';"
    fi
  '
}

# 컨테이너 내부에 스키마(prompts)가 없으면 ./postgres/init/*.sql 적용
ensure_schema_or_seed() {
  log "🧱 스키마 보장(prompts 등)"
  docker compose exec -T "${service_name}" env -u PGPORT -u PGHOST bash -lc '
    set -euo pipefail
    DB="${PGDATABASE:-${POSTGRES_DB:-postgres}}"
    USER="${POSTGRES_USER:-postgres}"

    echo ">> DB=$DB USER=$USER (PGPORT/PGHOST unset; using 127.0.0.1:5432)"
    HAVE="$(psql -h 127.0.0.1 -p 5432 -U "$USER" -d "$DB" -tAc "SELECT to_regclass('\''public.prompts'\'') IS NOT NULL")"
    if [ "$HAVE" = "t" ]; then
      echo "✅ schema already exists → skip init SQL"
      exit 0
    fi

    echo "⚙️  schema missing → apply /docker-entrypoint-initdb.d/*.sql"
    shopt -s nullglob
    FILES=(/docker-entrypoint-initdb.d/*.sql)
    if [ ${#FILES[@]} -eq 0 ]; then
      echo "❌ no *.sql in /docker-entrypoint-initdb.d — cannot create schema"
      exit 1
    fi
    for f in "${FILES[@]}"; do
      echo ">> applying: $f"
      PGPASSWORD="${POSTGRES_PASSWORD:-postgres}" psql \
        -h 127.0.0.1 -p 5432 \
        -U "$USER" -d "$DB" \
        -v ON_ERROR_STOP=1 -f "$f"
    done
    echo "✅ schema created"
  '
}

ensure_uv_env() {
  if [ ! -d ".venv" ]; then
    log "📦 .venv 없으므로 uv venv 생성"
    uv venv
  fi
  log "🔄 의존성 동기화 (uv sync)"
  uv sync
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

# ===== Prompt Sync =====
sync_prompts() {
  log "🧩 YAML 프롬프트 DB 동기화 시작"
  local -a args
  args=(--root "$PROMPT_ROOT")
  if [ -n "$PROMPT_LANG" ]; then
    args+=(--lang "$PROMPT_LANG")
  fi
  # PYTHONPATH=src 로 모듈 경로 보장
  if PYTHONPATH=src uv run python -m infrastructure.prompt.sync "${args[@]}"; then
    log "✅ 프롬프트 동기화 완료"
  else
    log "⚠️ 프롬프트 동기화 실패 (앱은 계속 기동할 수 있음)"
    return 1
  fi
}

maybe_auto_sync_prompts() {
  # macOS bash 3.2 호환: 소문자 변환을 tr로 처리
  local flag="${AUTO_SYNC_PROMPTS:-1}"
  flag="$(printf '%s' "$flag" | tr '[:upper:]' '[:lower:]')"

  case "$flag" in
    1|true|yes|on)
      sync_prompts || true
      ;;
    *)
      log "ℹ️ AUTO_SYNC_PROMPTS 비활성화 → 프롬프트 동기화 생략"
      ;;
  esac
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
  maybe_auto_sync_prompts
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
        -d "${PGDATABASE:-${POSTGRES_DB:-postgres}}" \
        -v ON_ERROR_STOP=1 \
        -f "$f"
    done
  '
  log "✅ DB 시드 적용 완료"
  ensure_uv_env
  maybe_auto_sync_prompts
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
  debug)
    compose_up_db
    wait_for_db
    ensure_db_exists_in_container
    ensure_uv_env
    maybe_auto_sync_prompts
    ;;
  start)
    log "♻️ 기존 컨테이너 종료 및 정리"
    docker compose down || true
    ensure_host_port
    compose_up_db
    wait_for_db
    ensure_db_exists_in_container
    ensure_schema_or_seed
    ensure_uv_env
    maybe_auto_sync_prompts   # ✅ 앱 시작 전 자동 동기화
    start_app
    ;;
  restart)
    compose_up_db
    wait_for_db
    ensure_db_exists_in_container
    ensure_uv_env
    maybe_auto_sync_prompts   # ✅ 재시작 전 자동 동기화
    restart_app
    ;;
  init-db)
    init_db
    ;;
  seed-db)
    seed_db
    ;;
  sync-prompts)               # ✅ 수동 동기화
    compose_up_db
    wait_for_db
    ensure_uv_env
    sync_prompts
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
    echo "사용법: $0 [start|restart|init-db|seed-db|sync-prompts|stop|status|logs]"
    exit 1
    ;;
esac