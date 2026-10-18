# RenalSight MCP server

Lets an AI assistant (Claude Desktop, Cursor, any MCP client) write and share the kidney-donor appeal with your family, using the same rules as the website.

## Tools
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

## Run
Start the RenalSight backend first (port 8000), then:
```
pip install -r mcp_server/requirements.txt
python mcp_server/server.py
```
Environment: `RENALSIGHT_URL` (default http://127.0.0.1:8000) and either `RENALSIGHT_TOKEN` or `RENALSIGHT_EMAIL` + `RENALSIGHT_PASSWORD` of a patient or caregiver account.

## Claude Desktop config (`claude_desktop_config.json`)
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
