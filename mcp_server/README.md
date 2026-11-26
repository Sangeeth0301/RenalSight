# RenalSight MCP servers

Two servers live here:

| Server | File | Needs |
|---|---|---|
| **Forecast** (research engine) | `forecast_server.py` | nothing else: runs the SALT-FG forecaster locally, no backend, no account, no internet |
| Donor appeal | `server.py` | the RenalSight backend on port 8000 and an account |

## Forecast server

Lets an AI assistant run the SALT-FG kidney-function forecaster on a person's lab history. Research prototype: not medical advice.

| Tool | What it does |
|---|---|
| `egfr_from_creatinine` | CKD-EPI 2021 (race-free) eGFR and CKD stage from serum creatinine |
| `forecast_kidney` | median and 50/80% ranges at 0.5-5 years (80% band calibrated on real MIMIC-IV patients up to 2 years), chance and timing of eGFR < 45 / 30 / 15, kidney failure versus death before it, probabilities of slow / middle / rapid decline. The guard layer abstains with reasons on implausible or insufficient input |
| `forecast_chart` | the same forecast as a PNG fan chart with CKD stage bands |
| `compare_actions` | paired what-if: blood pressure, sugar, ACE inhibitor/ARB, SGLT2 inhibitor; eGFR gain and kidney-failure risk change (scenarios, not promises) |
| `model_evidence` | validation results, failed criteria, real-patient league table and limits, read from `ml/forecast/results` |
| `population_projection` | India 2024-2044 stage projection and programme results (population face) |

Also a resource `renalsight://model-card` and a prompt "Explain my kidney forecast".

Inputs: `history` is a list of `{date: "YYYY-MM-DD" | years: float, egfr | creatinine}` (at least two); `patient` is `{age, sex, diabetes, systolic_bp?, hba1c?, acr?}`.
Missing blood pressure, HbA1c or ACR are defaulted and the answer says so.

Run: `python mcp_server/forecast_server.py` (stdio). Tests: `cd ml && python -m pytest forecast/tests/test_mcp_forecast.py`.
Example output chart: `example_forecast_chart.png`.

Claude Desktop (`claude_desktop_config.json`) or Claude Code (`.mcp.json`):
```json
{
  "mcpServers": {
    "renalsight-forecast": {
      "command": "python",
      "args": ["C:/Users/sange/KCD/mcp_server/forecast_server.py"]
    }
  }
}
```
Then ask: "My eGFR was 48 in Jan 2023, 44 in Jul 2023, 41 in Jan 2024 and 37 in Aug 2024. I'm a 62-year-old woman with diabetes, BP 150, HbA1c 8.2,
ACR 340. Forecast my kidney function and show what blood-pressure control and an SGLT2 inhibitor would change."

## Donor appeal server

Lets an AI assistant write and share the kidney-donor appeal with your family, using the same rules as the website.

### Tools
| Tool | What it does |
|---|---|
| `search_hospitals` | find AIIMS, KMCH, a Kolkata hospital... (names only, unverified unless marked) |
| `compose_request_message` | polished appeal in English / Tamil / Bengali / Telugu (warm, formal, urgent) with share links |
| `whatsapp_link` | a one-click `wa.me` link; the person taps send themselves |
| `create_kidney_request` | saves the request and returns its public page `/r/<token>` |
| `find_compatible_donors` | ABO-compatible living-donor pledges (phones masked) |
| `list_my_requests` | the account's requests |
| `send_whatsapp_cloud` | OFF by default. Only appears if `WHATSAPP_CLOUD_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are set. Needs confirm=true. **Untested without real Meta credentials.** |

Nothing is sent automatically. Organs are never priced or traded; the tools refuse nothing silently, the backend enforces consent and blood-group rules.

### Run
Start the RenalSight backend first (port 8000), then:
```
pip install -r mcp_server/requirements.txt
python mcp_server/server.py
```
Environment: `RENALSIGHT_URL` (default http://127.0.0.1:8000) and either `RENALSIGHT_TOKEN` or `RENALSIGHT_EMAIL` + `RENALSIGHT_PASSWORD` of a patient or caregiver account.

### Claude Desktop config (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "renalsight": {
      "command": "python",
      "args": ["C:/Users/sange/KCD/mcp_server/server.py"],
      "env": { "RENALSIGHT_EMAIL": "asha@example.com", "RENALSIGHT_PASSWORD": "Demo@12345" }
    }
  }
}
```
Then say: "Ask KMCH Coimbatore for a kidney donor for Ravi Kumar, blood group B+, contact 98765 43210, in Tamil."
