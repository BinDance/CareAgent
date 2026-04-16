#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -d .venv ]; then
  echo 'missing .venv, run sh ./scripts/bootstrap.sh first' >&2
  exit 1
fi

. .venv/bin/activate
pytest apps/api-server/tests
