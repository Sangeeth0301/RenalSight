# RenalSight frontend

```
frontend/
  web/            the finished website (React + Vite + Tailwind + TypeScript). Run: cd web && npm install && npm run dev
    src/lib/api.ts       typed API client for every endpoint + WebSocket helper
    src/i18n/*.json      English, Tamil, Bengali, Telugu (737 strings each)
    e2e/                 26 Playwright browser tests
  api/            api.ts and openapi.json exported from the running backend (kept in sync with web/src/lib/api.ts)
  i18n/           the same four language files + check_i18n.py (key and placeholder parity, care-plan codes)
```

## Running
Easiest: double-click `Start RenalSight.bat` in the project root. Manual: start the backend on port 8000, then `npm run dev` in `frontend/web`. Browser end-to-end tests: `npm run e2e` (backend and website must be running).

## Languages
The language popup (globe button, also shown on the first visit) switches the bundled JSON files **instantly and offline: no API key, no network call**. Only free-text AI answers use the providers configured in `backend/.env`; they are asked to reply in the chosen language. Tamil, Bengali and Telugu strings are first drafts: have a native-speaking clinician review them (especially `carePlan.*`, `wounds.*`, `stageDesc.*`). Doctor and admin screens are English only by design.
After editing a language file run `python i18n/check_i18n.py` (must print `RESULT: OK`), then copy the files to `web/src/i18n/`.

## Keeping the API client in sync
`web/src/lib/api.ts` is the source of truth. After changing the backend, re-export the spec (`python -c "import json; from app.main import app; print(json.dumps(app.openapi()))"` inside `backend/`) and update `api.ts`; copy it to `frontend/api/api.ts`.

## Pages
`/` landing, `/login`, `/register`, `/onboarding`, `/home`, `/reports`, `/kidney`, `/forecast`, `/care`, `/rx`, `/chat`, `/rooms`, `/buddy`, `/pulse` (public), `/rituals`, `/community`, `/care-hub`, `/offline`, `/research`, `/inbox`, `/notifications`, `/settings`, transplant hub `/hub`, `/hub/request/new`, `/hub/request/:id`, `/hub/donate`, `/hub/hospitals`, `/hub/journey`, `/hub/dialysis`, `/hub/id`, `/hub/desk` (staff), public `/r/:token` and `/e/:token`, doctor `/doctor`, `/doctor/queue`, `/doctor/patients/:id`, `/doctor/rx/:id`, admin `/admin`.
