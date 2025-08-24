#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

usage() {
  echo "Usage: $0 {start|stop|restart|logs}" >&2
  exit 2
}

cmd="${1:-start}"

cd "$BACKEND_DIR"

case "$cmd" in
  start)
    ./scripts/dev_up.sh start
    ;;
  stop)
    ./scripts/dev_up.sh stop
    ;;
  restart)
    ./scripts/dev_up.sh stop || true
    ./scripts/dev_up.sh start
    ;;
  logs)
    # dev_up.sh에 logs 서브커맨드가 있으면 사용, 없으면 docker compose 로그로 폴백
    ./scripts/dev_up.sh logs || docker compose logs -f
    ;;
  *)
    usage
    ;;
esac
