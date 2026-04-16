#!/bin/sh
set -eu

cd /app/apps/api-server

python - <<'PY'
import time
from sqlalchemy import create_engine, text
from eldercare_api.config import get_settings

engine = create_engine(get_settings().database_url, future=True, pool_pre_ping=True)
for attempt in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('database ready')
        break
    except Exception as exc:
        print(f'waiting for database: {exc}')
        time.sleep(2)
else:
    raise SystemExit('database not ready in time')
PY

alembic upgrade head
python - <<'PY'
from eldercare_api.scripts.seed import seed_demo_data_if_empty
created = seed_demo_data_if_empty()
print('seed applied' if created else 'seed skipped')
PY

exec python -m uvicorn eldercare_api.main:app --host 0.0.0.0 --port 8000
