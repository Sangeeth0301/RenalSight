# RenalSight: complete setup guide

This file is written so a person, or an AI coding assistant working for them, can take a fresh machine from `git clone` to a running app. Follow the steps in order and run the checks at the end of each section.

**What you get:** a React website (port 5173) and a FastAPI backend (port 8000), with demo accounts and demo patients. Everything runs on your own computer.

---

## 0. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Git | any recent | `git --version` |
| Python | 3.11 or newer (3.12 recommended) | `python --version` (on macOS/Linux you may need `python3`) |
| Node.js | 20 or newer | `node --version` |
| Google Chrome | optional, only for the WhatsApp bridge | |

Windows users: use PowerShell or Git Bash. Commands below show both Windows and macOS/Linux forms where they differ.

---

## 1. Get the code

```bash
git clone https://github.com/Sangeeth0301/RenalSight.git
cd RenalSight
```

The repository is private. The person cloning must be added as a collaborator by the owner and signed in to GitHub (`gh auth login`, or a personal access token over HTTPS).

---

## 2. Backend

### 2.1 Create a virtual environment and install packages

```bash
cd backend
python -m venv .venv
# Windows PowerShell:   .\.venv\Scripts\Activate.ps1
# macOS / Linux / Git Bash:   source .venv/bin/activate        (Git Bash on Windows: source .venv/Scripts/activate)
pip install --upgrade pip
pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, XGBoost, SHAP, lifelines, PyMuPDF, ReportLab and the rest. It takes a few minutes the first time.

### 2.2 Create `backend/.env`

The `.env` file holds secrets and is **never** committed. Create it from the example:

```bash
# macOS / Linux / Git Bash
cp .env.example .env
# Windows PowerShell
Copy-Item .env.example .env
```

Then set a real `SECRET_KEY` and (optionally) the AI keys. Generate a secret like this and paste it after `SECRET_KEY=`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

A working minimal file:

```ini
SECRET_KEY=<paste the generated value>
LLM_CHAIN=groq,gemini,openai,xai,ollama,rules
GROQ_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
XAI_API_KEY=
OLLAMA_ENABLED=false
BUDDY_MESSAGES_PER_MINUTE=30
```

**The app works with every API key left blank.** The helpers then answer in "basic mode" from the patient's saved data. Keys only switch on the AI chat answers, AI message polishing and the chat translation toggle (see section 6).

### 2.3 Start the backend

Run this from the `backend` folder with the virtual environment active:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check: open http://127.0.0.1:8000/health. It should return `{"status":"ok","tools":31}`. API docs are at http://127.0.0.1:8000/docs. Leave this terminal running.

### 2.4 Create the demo accounts

In a **second** terminal (same `backend` folder, virtual environment active):

```bash
python seed_demo.py
python create_admin.py admin@example.com "Demo@12345" "Admin"
python seed_cohort.py        # optional: adds 320 demo patients and 8 more doctors (about 20 seconds)
```

`seed_demo.py` talks to the running backend. It is safe to run again; existing users are reused. `seed_cohort.py` writes straight into the database and skips itself if it has already run.

---

## 3. Website

In a **third** terminal:

```bash
cd frontend/web
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The first visit shows a language popup; choose English.

If the page loads but sign-in fails with a network error, the backend is not running on port 8000. The website expects the API at `http://localhost:8000`.

---

## 4. Sign in (demo credentials)

All demo accounts use the same password: **`Demo@12345`** (local demo data only).

| Role | Email | Language | What to look at |
|---|---|---|---|
| **Patient 1** | `asha@example.com` | Tamil | Stage 4 kidney disease: Living Kidney, forecast, care plan, transplant hub |
| **Patient 2** | `ravi@example.com` | Telugu | Urgent values (stage 5): urgent banner, high-risk forecast |
| **Doctor** | `dr.rao@example.com` | English | Dashboard, ranked patient table (68 patients with the cohort seed), patient quick view, review queue, schedule, Copilot |
| Admin | `admin@example.com` | English | AI provider status, moderation |
| Extra patient | `meena@example.com` | Bengali | Healthy kidney |
| Cohort patients | `patient001@example.com` to `patient320@example.com` | mixed | Only after `seed_cohort.py` |
| Cohort doctors | `dr.meera.nair@example.com`, `dr.arjun.das@example.com`, `dr.sunil.reddy@example.com`, `dr.kavya.iyer@example.com`, `dr.rahul.mehta@example.com`, `dr.ananya.sen@example.com`, `dr.vamsi.krishna@example.com`, `dr.senthil.vel@example.com` | mixed | Only after `seed_cohort.py` |

On the login page, the "Patient: Asha" and "Doctor: Dr. Rao" buttons fill in these credentials when the site is opened on localhost.

Tip for a two-person demo: open the doctor in one browser window and a patient in a private window. Message each other from "Direct line" (patient) and "Messages" (doctor); the chat is live.

---

## 5. Run the tests (optional but recommended)

```bash
# backend (from backend/, venv active)
python -m pytest tests -q                 # 58 tests

# browser tests (backend on 8000 and website on 5173 must be running; seed_demo.py and create_admin.py done)
cd frontend/web
npx playwright install chromium
npx playwright test                       # 30 tests
```

The same checks run automatically on GitHub (Actions tab).

---

## 6. Optional: AI keys

AI is optional. To switch it on, put free keys into `backend/.env` and restart the backend:

| Provider | Where to get a key | `.env` line |
|---|---|---|
| Groq (fast, main provider) | https://console.groq.com/keys | `GROQ_API_KEY=` |
| Google Gemini (best for Tamil, Bengali, Telugu) | https://aistudio.google.com/apikey | `GEMINI_API_KEY=` |
| OpenAI (optional) | https://platform.openai.com/api-keys | `OPENAI_API_KEY=` |
| xAI Grok (optional) | https://console.x.ai | `XAI_API_KEY=` |

Recommended models if you need to set them (provider model lists change, so check the provider's site if a request fails with 404):

```ini
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_MODEL=gemini-3.5-flash
```

The router tries providers in the order of `LLM_CHAIN`, backs off a provider that hits a quota, and finally answers from built-in rules. Check which providers are ready by signing in as `admin@example.com` and opening the Admin page.

**Where the owner's keys are:** API keys are deliberately **not** stored in this repository (GitHub scans repositories for leaked keys and providers revoke them, and anyone with repository access could use them). If you want to use the owner's keys, ask the owner to send them privately (not by committing them), then paste them into your own `backend/.env`. Otherwise create your own free keys with the links above.

---

## 7. Optional: WhatsApp one-click sending

There are two ways to share a message from the app:

1. **Links (works for everyone, nothing to set up).** The "Send on WhatsApp" and donor-appeal buttons open WhatsApp (app or web) with the message ready; you pick the chat and tap send.
2. **Local bridge (one-click send to chosen chats).** It drives **your own** WhatsApp Web through a normal Chrome window and needs Chrome, Node.js and your phone.
   1. Sign in, click the green **Send on WhatsApp** button, then **Link WhatsApp (one time)**.
   2. A Chrome window opens on WhatsApp Web. On your phone: WhatsApp, Linked devices, Link a device, scan the QR code.
   3. Keep that Chrome window open (minimising is fine), tick people and click **Send now**.
   - The allowed chats are listed in `backend/app/modules/whatsapp/router.py` (`ALLOWED`) and can be changed with the environment variable `WHATSAPP_ALLOWED="Name one;Name two"`. The bridge only messages chats whose title matches exactly.
   - At most 6 sends per hour; every send is audit-logged.

**The owner's WhatsApp is not included and cannot be shared.** A linked WhatsApp session gives full access to that person's account, so it stays on the owner's own computer (it lives in an ignored folder, `bridge/chrome-profile`). Each person links their own WhatsApp on their own machine, or just uses the links in option 1.

---

## 8. Optional: MCP server

Lets an MCP-compatible AI assistant search hospitals, write a donor appeal and create a request through the same backend.

```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py        # needs the backend running; set RENALSIGHT_EMAIL and RENALSIGHT_PASSWORD (a patient or caregiver account)
```

See `mcp_server/README.md` for a client configuration example.

---

## 9. Run it in the cloud instead (GitHub Codespaces)

On the repository page choose **Code, Codespaces, Create codespace on main**. The dev container installs everything, starts both servers, seeds the demo accounts and forwards port 5173. Add `GROQ_API_KEY` and `GEMINI_API_KEY` as Codespaces secrets if you want AI.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` when starting the backend | The virtual environment is not active, or `pip install -r requirements.txt` did not finish. |
| Port 8000 or 5173 already in use | Stop the other program, or change the port (backend `--port`, and set `VITE_API_URL` for the website if you move the backend). |
| Sign-in says network error | The backend is not running. Check http://127.0.0.1:8000/health. |
| Wrong password for a demo account | Run `python seed_demo.py` again, or delete `backend/renalsight.db` and redo section 2.4 to start fresh. |
| AI answers say "basic mode" | No API key is set, or the provider is out of quota. Add a key (section 6). |
| Translate toggle does nothing | It needs an AI key; without one the original text is shown. |
| Browser tests fail at the very start | The language popup appears on first visit; the tests set a stored language, so make sure `seed_demo.py` and `create_admin.py` ran and both servers are up. |
| Windows: `Activate.ps1 cannot be loaded` | Run PowerShell as your user and execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| `npm install` fails | Check `node --version` is 20 or newer; delete `frontend/web/node_modules` and retry. |

To start completely fresh: stop both servers, delete `backend/renalsight.db`, start the backend, and run the seed commands again.

---

## 11. Checklist for an AI assistant doing this setup

1. Confirm Git, Python 3.11+ and Node 20+ are installed; report anything missing instead of guessing.
2. Clone the repository and `cd RenalSight`.
3. Create and activate `backend/.venv`; `pip install -r backend/requirements.txt`.
4. Create `backend/.env` from `.env.example` with a freshly generated `SECRET_KEY`. Leave AI keys blank unless the user supplies them. Never print, log or commit keys.
5. Start the backend on port 8000 in a background process and confirm `/health` returns `ok`.
6. Run `seed_demo.py`, `create_admin.py admin@example.com "Demo@12345" "Admin"` and (optionally) `seed_cohort.py`.
7. In `frontend/web` run `npm install`, then start `npm run dev` on port 5173.
8. Open http://127.0.0.1:5173 and sign in as `asha@example.com` / `Demo@12345` to confirm the Living Kidney page loads; then sign in as `dr.rao@example.com` to confirm the dashboard lists patients.
9. Report the result, and tell the user which optional parts (AI keys, WhatsApp bridge) are not configured.

Do not ask for, store or commit another person's API keys or WhatsApp session.
