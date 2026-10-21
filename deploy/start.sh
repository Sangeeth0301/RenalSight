#!/usr/bin/env bash
# Container start: run the service, seed demo data on first start, keep running.
set -e
cd /app/backend
PORT="${PORT:-8000}"
python -m uvicorn app.deploy:root --host 0.0.0.0 --port "$PORT" &
PID=$!
for i in $(seq 1 90); do curl -sf "http://127.0.0.1:$PORT/api/health" > /dev/null && break; sleep 1; done
if [ ! -f /app/.seeded ]; then
  python seed_demo.py "http://127.0.0.1:$PORT/api" || true
  if [ -n "$ADMIN_PASSWORD" ]; then python create_admin.py "${ADMIN_EMAIL:-admin@example.com}" "$ADMIN_PASSWORD" "Admin" || true; fi
  if [ "${SEED_COHORT:-1}" = "1" ]; then python seed_cohort.py || true; fi
  touch /app/.seeded
fi
wait $PID
