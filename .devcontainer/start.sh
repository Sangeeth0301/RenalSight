#!/usr/bin/env bash
# Runs every time you open the Codespace: starts the backend and the website, and seeds demo accounts once.
cd "$(dirname "$0")/.."
mkdir -p .logs
if ! curl -sf http://127.0.0.1:8000/health > /dev/null; then
  (cd backend && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../.logs/backend.log 2>&1 &)
  for i in $(seq 1 60); do curl -sf http://127.0.0.1:8000/health > /dev/null && break; sleep 1; done
fi
if ! curl -sf http://127.0.0.1:5173 > /dev/null; then
  (cd frontend/web && nohup npx vite --host 0.0.0.0 --port 5173 > ../../.logs/web.log 2>&1 &)
fi
(cd backend && python seed_demo.py > ../.logs/seed.log 2>&1; python create_admin.py admin@example.com "Demo@12345" "Admin" >> ../.logs/seed.log 2>&1) || true
echo "RenalSight is starting. Open the forwarded port 5173. Sign in: asha@example.com or dr.rao@example.com, password Demo@12345."
echo "Optional: cd backend && python seed_cohort.py   (adds 320 demo patients)"
