#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo 'created .env from .env.example'
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./packages/agent-core -e ./apps/api-server -e ./apps/mcp-server pytest

if command -v pnpm >/dev/null 2>&1; then
  pnpm install
else
  npm install
fi

echo 'bootstrap complete'
echo 'next: docker compose up -d db redis'
echo 'then: sh ./scripts/dev.sh'
