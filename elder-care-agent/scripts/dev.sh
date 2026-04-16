#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -d .venv ]; then
  echo 'missing .venv, run sh ./scripts/bootstrap.sh first' >&2
  exit 1
fi

. .venv/bin/activate

cleanup() {
  kill 0 >/dev/null 2>&1 || true
}

trap cleanup INT TERM EXIT

(
  cd "$ROOT/apps/api-server"
  python -m uvicorn eldercare_api.main:app \
    --reload \
    --reload-dir "$ROOT/apps/api-server" \
    --reload-dir "$ROOT/packages/agent-core" \
    --host 0.0.0.0 \
    --port 8000
) &

(
  cd "$ROOT/apps/mcp-server"
  python -m eldercare_mcp.main
) &

if command -v pnpm >/dev/null 2>&1; then
  (
    cd "$ROOT"
    pnpm --filter elder-web dev
  ) &
  (
    cd "$ROOT"
    pnpm --filter family-web dev
  ) &
else
  (
    cd "$ROOT"
    npm run dev -w apps/elder-web
  ) &
  (
    cd "$ROOT"
    npm run dev -w apps/family-web
  ) &
fi

wait
