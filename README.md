<div align="center">

# RenalSight

### Detect · Stage · Forecast · Treat · Connect

**An AI platform for chronic kidney disease (CKD), built for patients, doctors and families, in English, Tamil, Bengali and Telugu.**

![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-003b57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-58%20backend%20%C2%B7%2030%20browser-16a34a)
![Languages](https://img.shields.io/badge/languages-EN%20%C2%B7%20TA%20%C2%B7%20BN%20%C2%B7%20TE-f59e0b)
![Status](https://img.shields.io/badge/runs-on%20localhost%20%C2%B7%20Codespaces-64748b)
[![CI](https://github.com/Sangeeth0301/RenalSight/actions/workflows/ci.yml/badge.svg)](https://github.com/Sangeeth0301/RenalSight/actions/workflows/ci.yml)

<img src="assets/screens/living-kidney.jpg" alt="The Living Kidney: a kidney that visibly wounds as kidney function falls" width="880">

</div>

> **Learning and demonstration project.** RenalSight gives decision-support estimates, not diagnoses, and is not a medical device. Read [Honest limits](#honest-limits) before relying on any number.

---

## Why RenalSight

Kidney disease is silent until it is advanced. Most people meet it as a creatinine number they cannot interpret, a doctor who sees too many patients, and a family that does not know how to help, or how to find a donor.

RenalSight turns a handful of lab values into something a person can *see and act on*:

- a **Living Kidney** that is visibly wounded in proportion to what the labs show, and heals when they improve
- a **forecast** of how fast kidney function may fall, as a range, never a date
- a **care plan and draft prescription** that a doctor reviews, overrides if needed, and signs
- a **doctor console** that ranks every patient by severity and opens any record in one click
- a **transplant and donor hub** that writes a polished appeal and shares it in one click, from the website or from any AI assistant through MCP
- **agentic helpers** that explain, draft and plan, but never act without human approval

---

## Sign in and two portals

One sign-in page, two different experiences. After signing in, patients and caregivers land in the warm, personal **patient app**; doctors land in a bright, professional **doctor console** with a navy sidebar. Roles are enforced on the server, not just hidden in the interface.

<table>
  <tr>
    <td colspan="2" align="center"><img src="assets/screens/login.jpg" alt="Sign-in page" width="760"><br><sub><b>Sign in.</b> Language, theme and translation controls are available before login; local demo accounts fill in with one tap.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="assets/screens/patient-home.jpg" alt="Patient portal"><br><sub><b>Patient portal.</b> Living Kidney status, care plan, forecast, prescriptions, Buddy, direct line to the doctor, transplant hub.</sub></td>
    <td width="50%"><img src="assets/screens/doctor-dashboard.jpg" alt="Doctor portal"><br><sub><b>Doctor portal.</b> Every patient in one ranked table; touch a patient for a quick view, open the full record, message, draft a prescription.</sub></td>
  </tr>
</table>

| | Patient or caregiver | Doctor |
|---|---|---|
| **Home** | Living Kidney, care plan, notifications, ask-anything box | KPIs, stage chart, needs-attention list, sortable patient table |
| **Records** | Own labs, forecast and what-if sliders | Any linked patient: labs table, trend, forecast, prescriptions |
| **Messages** | Direct line to their doctor, consult rooms, community | Inbox with patient stage and urgent flags, consult rooms |
| **Prescriptions** | Request a plan; see doses only after a doctor signs | Safety-checked editor, override with reason, sign, PDF |
| **Extras** | Rituals, report guidance, donor appeals, dialysis log, emergency ID | Review queue, schedule, Copilot, Outreach, coordinator desk |

---

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="assets/screens/patient-home.jpg" alt="Patient home"><br><sub><b>Patient home.</b> Kidney status, care plan, notifications and a question box.</sub></td>
    <td width="50%"><img src="assets/screens/doctor-dashboard.jpg" alt="Doctor dashboard"><br><sub><b>Doctor dashboard.</b> KPIs, stage distribution, needs-attention list and a sortable patient table.</sub></td>
  </tr>
  <tr>
    <td><img src="assets/screens/forecast.jpg" alt="Time machine forecast"><br><sub><b>Time machine.</b> Fast, expected and slow paths with what-if sliders.</sub></td>
    <td><img src="assets/screens/doctor-drawer.jpg" alt="Doctor patient quick view"><br><sub><b>Touch a patient.</b> A quick view with labs, trend, forecast and one-click actions.</sub></td>
  </tr>
  <tr>
    <td><img src="assets/screens/translated-chat.jpg" alt="Chat translated into Telugu"><br><sub><b>Translate everything.</b> A doctor's English messages read in Telugu with one toggle; the original is one click away.</sub></td>
    <td align="center"><img src="assets/screens/mobile-kidney-ta.jpg" alt="Tamil mobile view" height="420"><br><sub><b>Mobile, in Tamil.</b> The Living Kidney with tappable marks on a phone.</sub></td>
  </tr>
  <tr>
    <td><img src="assets/screens/transplant-hub.jpg" alt="Transplant hub"><br><sub><b>Transplant and donor hub.</b> Appeals, registry, hospitals, journey, dialysis log.</sub></td>
    <td><img src="assets/screens/donor-appeal.jpg" alt="Donor appeal composer"><br><sub><b>Donor appeal.</b> Hospital, patient and blood group in; a polished message out.</sub></td>
  </tr>
  <tr>
    <td><img src="assets/screens/living-kidney-dark.jpg" alt="Dark theme"><br><sub><b>Light and dark themes</b> that still shift teal, amber and rose with severity.</sub></td>
    <td><img src="assets/screens/population-pulse.jpg" alt="Population Pulse"><br><sub><b>Population Pulse.</b> CKD cases by region and year, with care needs and scenarios.</sub></td>
  </tr>
  <tr>
    <td><img src="assets/screens/lab-reports.jpg" alt="Lab reports"><br><sub><b>Lab reports.</b> Type, paste, upload, or fill from a real dataset sample.</sub></td>
    <td><img src="assets/screens/doctor-record.jpg" alt="Doctor patient record"><br><sub><b>Patient record.</b> Overview, labs, prescriptions and live messages in tabs.</sub></td>
  </tr>
</table>

---

## Features

| Area | What it does |
|---|---|
| **Living Kidney** | SVG kidney with five stages from healthy to destroyed. Wounds map to real labs: cracks for eGFR, leaking drops for urine protein, swollen veins for blood pressure, pallor for anaemia, flicker for potassium. Tap a mark to learn why it is there. The whole app shifts teal, amber or rose with severity. |
| **Clinical engine** | CKD-EPI 2021 eGFR, KDIGO G and A staging, a CKD detector (XGBoost with SHAP reasons), KFRE dialysis-risk, progression forecast with fast, expected and slow ranges, what-if sliders, group survival outlook from NHANES. |
| **Lab reports** | Manual entry, history chart, paste or upload TXT, CSV or text PDF (units converted, you confirm before saving), photo OCR when Tesseract is installed, and one-click **real sample records** for each kidney-function band. |
| **Rx Studio** | Care plan, draft medicines from KDIGO-style rules, a deterministic safety engine (renal doses, interactions, NSAIDs, potassium), doctor review, written override (audit-logged), e-signature and PDF. Patients never see unsigned doses. |
| **Doctor console** | Bright, clinical theme. Patient table with stage, eGFR, trend sparkline, change per year and severity. Click a patient for a quick-view drawer, then a full record with labs, prescriptions and live chat. Review queue and schedule. |
| **Connect** | Direct line (WebSocket chat with typing, read ticks, attachments), consult rooms with a six-digit code and shared checklist, community channels with reporting and auto-hide, care hub and appointments. |
| **Translate everything** | One toggle translates chat messages, previews, AI answers and posts into the chosen language, with the original one click away. Translations are cached. |
| **Transplant and donor hub** | Hospital directory with autocomplete, donor appeals with a public QR page, ABO compatibility and living-donor matching, a donor registry (kidney and liver while alive; heart, kidney, liver, lungs, eyes and tissue after death), coordinator verification, dialysis seat board, 10-step transplant journey, dialysis log, emergency ID with QR, FHIR export and referral-letter PDF. |
| **MCP server** | Any MCP assistant can search hospitals, compose the appeal, create a request and return a WhatsApp link, with the same safety rules as the website. |
| **One-click sharing** | Type a hospital, patient, blood group and phone. RenalSight writes a message in four languages and three tones and opens WhatsApp, Telegram, SMS or e-mail. An optional local bridge sends to chosen chats automatically. |
| **AI helpers** | Nephro Buddy, Doctor Copilot, Outreach assistant and Population Analyst share one tool registry. A multi-provider router falls back across Groq, Gemini, OpenAI, Grok and Ollama, and finally to rule-based answers. |
| **Population Pulse** | CKD cases by region and year from UN age-sex projections and the NHANES pattern, calibrated to a published national anchor, with stages, care needs, scenarios and a capacity gap. |
| **Access** | Instant offline language switch, voice in and out, large text, high contrast, mobile layout, installable PWA that opens offline, printable offline care pack and emergency card. |

---

## How it works

### System architecture

<img src="assets/architecture.svg" alt="RenalSight system architecture" width="100%">

The browser talks to a FastAPI backend over REST and WebSocket. Every capability is written once in a **tool registry**: the same function backs a button in the website and a tool the AI helpers can call, with role checks in one place. A multi-provider LLM router handles quota limits and outages by moving to the next provider, and finally to rule-based answers, so the app is useful with no AI key at all.

### From lab values to a plan a doctor signs

<img src="assets/pipeline.svg" alt="Detect, stage, forecast, treat" width="100%">

### Donor appeal: from a hospital name to one-click sharing

<img src="assets/donor-flow.svg" alt="Donor appeal flow" width="100%">

### Data sources and the agentic helpers

<img src="assets/agents.svg" alt="Data sources and agentic helpers" width="100%">

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, framer-motion, recharts, Radix UI, zustand, TanStack Query, react-i18next, service-worker PWA |
| Backend | FastAPI, SQLAlchemy and SQLite, pydantic v2, JWT with bcrypt, WebSockets, APScheduler |
| ML | scikit-learn, XGBoost, SHAP, lifelines (Cox), statsmodels, pandas, NumPy |
| AI | OpenAI-compatible HTTP router for Groq, Gemini, OpenAI, Grok and Ollama, with rule-based fallback |
| Integration | MCP server, local WhatsApp bridge (Playwright over Chrome DevTools), FHIR export with LOINC codes |
| Quality | pytest (58 tests), Playwright (30 browser tests against a real backend), i18n parity checker |

---

## Quick start

> Setting this up on another machine, or handing it to someone (or their AI assistant)? Follow the step-by-step guide in [`SETUP.md`](SETUP.md): clone, backend, website, demo logins, optional AI keys and WhatsApp.

**Windows, one step:** double-click `Start RenalSight.bat` (or run `.\run-dev.ps1`). It installs what is missing, starts the backend and the website, creates demo accounts and opens http://127.0.0.1:5173.

**Manual:**

```bash
# backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000

# website (new terminal)
cd frontend/web
npm install
npm run dev
```

API documentation is served at http://127.0.0.1:8000/docs.

### Demo data

```bash
cd backend
python seed_demo.py       # a handful of named demo accounts
python seed_cohort.py     # 320 patients, 8 doctors, donor pledges, requests, dialysis logs
```

The cohort uses real adult lab records from NHANES 2005-2014 for each patient's latest values. Earlier visits, names, cities and doctors are synthetic. All demo accounts use the password `Demo@12345` and are for local use only.

| Account | Role | What to look at |
|---|---|---|
| `asha@example.com` | patient (Tamil), stage 4 | Living Kidney, forecast, hub, WhatsApp button |
| `ravi@example.com` | patient (Telugu), urgent values | urgent banner, doctor alerts |
| `meena@example.com` | patient (Bengali), healthy | healthy kidney |
| `dr.rao@example.com` | doctor | dashboard, record, review queue, Copilot |
| `patient001@example.com` … `patient320@example.com` | patients | a large, varied cohort |
| `admin@example.com` | admin | provider status, capacity, moderation |

### AI providers (optional)

Put keys in `backend/.env`. They never reach the website. With no keys, everything still works and the helpers answer in basic mode from saved data.

```ini
LLM_CHAIN=groq,gemini,openai,xai,ollama,rules
GROQ_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
OLLAMA_ENABLED=true
```

---

## MCP server: let an AI assistant do the appeal

RenalSight ships a **Model Context Protocol (MCP)** server, so any MCP-compatible assistant can search hospitals, write the donor appeal in four languages, create a request and hand back a one-click WhatsApp link, using the same rules as the website.

<img src="assets/mcp.svg" alt="MCP flow" width="100%">

| Tool | What it does |
|---|---|
| `search_hospitals` | find AIIMS, KMCH, a Kolkata hospital... (directory names, unverified unless marked) |
| `compose_request_message` | polished appeal in English, Tamil, Bengali or Telugu; warm, formal or urgent |
| `whatsapp_link` | a `wa.me` link; the person taps send |
| `create_kidney_request` | saves the request and returns its public page `/r/<token>` |
| `find_compatible_donors` | ABO-compatible living-donor pledges with masked phones |
| `list_my_requests` | the account's requests and offers |

```json
{
  "mcpServers": {
    "renalsight": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": { "RENALSIGHT_EMAIL": "asha@example.com", "RENALSIGHT_PASSWORD": "Demo@12345" }
    }
  }
}
```

Then ask the assistant: *"Ask KMCH Coimbatore for a kidney donor for Ravi Kumar, blood group B+, contact 98765 43210, in Tamil."* Nothing is sent automatically. Full setup in [`mcp_server/README.md`](mcp_server/README.md).

---

## One-click WhatsApp sending (optional, local)

The **Send on WhatsApp** button opens a summary and a short list of allowed chats. For a true one-click send, a local bridge drives **your own** WhatsApp Web in a normal Chrome window:

1. Click **Link WhatsApp** once. Chrome opens on WhatsApp Web; scan the QR code with your phone.
2. Keep that Chrome window open (minimising is fine).
3. Tick the people and click **Send now**.

Safeguards: only chats on an allowlist (`WHATSAPP_ALLOWED`) are ever messaged, matched by exact chat title and re-checked against the open chat header; phone numbers are never used; at most 6 sends an hour; every send is audit-logged. Unofficial automation of WhatsApp Web can be restricted by WhatsApp, so keep volumes small.

## MCP server

`mcp_server/` lets any MCP client search hospitals, compose the appeal, create a request and get a WhatsApp link. See [`mcp_server/README.md`](mcp_server/README.md).

---

## Run it on GitHub (Codespaces) and automatic testing

**One-click cloud copy.** Open the repository on GitHub, choose **Code → Codespaces → Create codespace on main**. The dev container installs everything, starts the FastAPI backend and the website, seeds the demo accounts and forwards port **5173**. Open that port and sign in as `asha@example.com` or `dr.rao@example.com` (password `Demo@12345`). Inside a Codespace the website reaches the API through its own `/api` proxy, so nothing else needs to be opened or made public.

- AI keys are optional: add `GROQ_API_KEY` and `GEMINI_API_KEY` as **Codespaces secrets** and they are picked up automatically.
- More demo data: `cd backend && python seed_cohort.py`.
- The local WhatsApp bridge needs a desktop Chrome and your phone, so it is for local use only.

**CI on every push.** The workflow in `.github/workflows/ci.yml` runs the backend tests, the language-file check, the TypeScript check and production build, and the full browser suite (real Chromium against a real backend) on GitHub's runners. The badge above shows its status.

---

## Host it for other people (one service, one link)

`backend/app/deploy.py` serves the API under `/api` and the built website from `/`, so the whole app is one service. A `Dockerfile` and a Render blueprint are included.

1. In Render choose **New → Blueprint** and pick this repository (`render.yaml` does the rest).
2. Add `GROQ_API_KEY` and `GEMINI_API_KEY` in the service's environment (optional; the app works without AI).
3. Open the service URL and share it. Demo accounts are created on first start (`asha@example.com`, `dr.rao@example.com`, password `Demo@12345`) along with 320 demo patients.

On a hosted copy the local WhatsApp bridge is switched off (`WHATSAPP_ENABLED=0`), the free plan sleeps when idle, and its SQLite file is reset on restart. Anyone with the link can register, so treat it as a demo and do not enter real health data.

---

## Testing

```powershell
.\run-tests.ps1
```

| Suite | Count | Covers |
|---|---|---|
| Backend (pytest) | 58 | auth, labs, clinical, Rx safety, chat, population, transplant, translation, WhatsApp allowlist, MCP |
| Browser (Playwright) | 30 | real Chromium against the real backend: login, labs, Living Kidney, forecast, Rx with override and PDF, live chat, rooms, community, hub, doctor console, helpers, offline service worker |
| Language check | 749 keys | key, placeholder and care-plan-code parity across all four languages |

---

## Project structure

```
backend/        FastAPI app (modules per domain), tests, seed scripts
frontend/web/   React website, Playwright end-to-end tests
frontend/i18n/  English, Tamil, Bengali, Telugu strings and a parity checker
frontend/api/   exported API client and OpenAPI spec
ml/             data pipeline, models, forecast, kidney state
data/processed/ prepared NHANES adults, simulated follow-up, population tables
bridge/         local WhatsApp bridge
mcp_server/     MCP server
assets/         README diagrams and screenshots
```

Data pipeline (`ml/src`): `nhanes_build.py`, `train_ckd_uci.py`, `survival_cox.py`, `calibrate_vs_kfre.py`, `simulate_followup.py`, `population_build.py`.

---

## Safety and ethics

- **No exact date of death, ever.** Only time-to-kidney-failure ranges and group-level survival.
- **Doctors decide.** Prescriptions are drafts until a doctor signs. Overrides need a written reason and are audit-logged. Doses are removed from AI replies.
- **Organs are never bought or sold.** There are no prices or payments anywhere. Public pages show a scam warning and only a masked phone number. Heart and most organs are deceased-donor pledges, not public appeals.
- **Consent first.** Donor pledges and public offers require explicit consent and can be withdrawn. Doctors must tick patient consent before sharing a patient's summary.
- **Human in the loop.** AI helpers read data and call tools; anything that writes becomes a draft or an approval task.

## Honest limits

- **Not a medical device.** Forecasts are simulation-based (published decline-rate ranges, prior calibrated to the KFRE equation). No free real follow-up dataset exists, so validation checks the uncertainty machinery, not clinical truth.
- **The detector** is trained on the small UCI CKD set, which is almost trivially separable (AUROC about 0.99). Treat it as a demonstration.
- **Survival** is group-level all-cause mortality from US NHANES.
- **Drug rules** (`backend/app/modules/rx/rules.json`) are drafted from public guidance and **must be reviewed by a doctor or pharmacist**. KFRE constants in `ml/src/clinical.py` should be re-checked against the paper.
- **Tamil, Bengali and Telugu texts are first drafts** and need review by a native-speaking clinician before real use. Doctor and admin screens are English only.
- **Population Pulse** is a model, not a census. Anchors in `anchors.json` are marked for verification; state rates currently equal the national rate.
- **Hospital directory** entries are names only, unverified until an admin verifies them. The care hub providers are fictional demo entries.
- **Donor matching** is ABO only. The hospital performs HLA typing and the legal authorisation.
- **WhatsApp bridge** relies on WhatsApp Web's page structure and may need adjustment when it changes.
- **Not built:** video consultations, SMS reminders, a real India map (region tiles are used), multi-server deployment (single local process).

---

<div align="center"><sub>RenalSight · built for learning and demonstration · runs entirely on your own machine</sub></div>
