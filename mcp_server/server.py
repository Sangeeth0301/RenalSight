"""RenalSight MCP server.

Lets an AI assistant (Claude Desktop, Cursor, any MCP client) help a family with the donor appeal: find a hospital, write the message,
create a request and hand back a one-click WhatsApp link. It talks to the local RenalSight backend over HTTP using the same
tools as the website, so every rule (blood-group checks, no payments, consent) applies here too.

Nothing is sent automatically: `whatsapp_link` returns a wa.me link that the person opens and sends themselves.
The optional `send_whatsapp_cloud` tool (off unless configured) uses Meta's WhatsApp Cloud API; it has NOT been tested without real credentials.

Run (stdio):   python mcp_server/server.py
Config (env):  RENALSIGHT_URL=http://127.0.0.1:8000  and either RENALSIGHT_TOKEN=<jwt> or RENALSIGHT_EMAIL + RENALSIGHT_PASSWORD
"""
from __future__ import annotations

import os
import re
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = (
    "You help patients' families ask for a kidney donor safely. Always get: hospital name, patient name, blood group and a contact phone before composing. "
    "Never suggest payment for an organ. Compose the message, show it to the person, then give them the WhatsApp link to tap. Never claim a message was sent."
)


class RenalSightClient:
    def __init__(self, http: httpx.Client | None = None, base_url: str | None = None, token: str | None = None, email: str | None = None, password: str | None = None):
        self.http = http or httpx.Client(base_url=base_url or os.getenv("RENALSIGHT_URL", "http://127.0.0.1:8000"), timeout=30)
        self.token = token or os.getenv("RENALSIGHT_TOKEN")
        self.email = email or os.getenv("RENALSIGHT_EMAIL")
        self.password = password or os.getenv("RENALSIGHT_PASSWORD")

    def _auth(self) -> dict:
        if not self.token:
            if not (self.email and self.password):
                raise RuntimeError("Set RENALSIGHT_TOKEN, or RENALSIGHT_EMAIL and RENALSIGHT_PASSWORD, for the RenalSight account to act as.")
            r = self.http.post("/auth/login", json={"email": self.email, "password": self.password})
            r.raise_for_status()
            self.token = r.json()["access_token"]
        return {"Authorization": f"Bearer {self.token}"}

    def tool(self, name: str, payload: dict) -> dict:
        r = self.http.post(f"/tools/{name}", json=payload, headers=self._auth())
        if r.status_code == 401:                                  # token expired: log in again once
            self.token = None
            r = self.http.post(f"/tools/{name}", json=payload, headers=self._auth())
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise RuntimeError(f"RenalSight said {r.status_code}: {detail}")
        return r.json()


def build_server(client: RenalSightClient | None = None) -> MCPServer:
    c = client or RenalSightClient()
    mcp = MCPServer("RenalSight", instructions=INSTRUCTIONS)

    @mcp.tool()
    def search_hospitals(query: str = "", transplant_only: bool = False) -> dict:
        """Search the hospital directory by name, short name (AIIMS, KMCH) or city. Names only; they are not verified unless marked."""
        return c.tool("search_hospitals", {"query": query, "transplant_only": transplant_only})

    @mcp.tool()
    def compose_request_message(hospital: str, patient_name: str, blood_group: str, contact_phone: str = "", contact_name: str = "", city: str = "", age: int | None = None,
                                relation: str = "family", tone: Literal["warm", "formal", "urgent"] = "warm", language: Literal["en", "ta", "bn", "te"] = "en",
                                include_phone: bool = True, polish: bool = False) -> dict:
        """Write a polished appeal asking friends and family to help find a kidney donor (English, Tamil, Bengali or Telugu). Returns the text plus ready share links. Sends nothing."""
        return c.tool("compose_request_message", {"hospital": hospital, "patient_name": patient_name, "blood_group": blood_group, "contact_phone": contact_phone,
                                                  "contact_name": contact_name, "city": city, "age": age, "relation": relation, "tone": tone, "language": language,
                                                  "include_phone": include_phone, "polish": polish})

    @mcp.tool()
    def whatsapp_link(text: str, phone: str = "") -> dict:
        """One-click WhatsApp link for a message. With no phone the person picks a contact or group inside WhatsApp. They must tap send themselves."""
        return c.tool("whatsapp_link", {"text": text, "phone": phone})

    @mcp.tool()
    def create_kidney_request(hospital_name: str, patient_name: str, blood_group: str, contact_phone: str, contact_name: str = "", city: str = "", age: int | None = None,
                              relation: str = "family", urgency: Literal["routine", "soon", "urgent"] = "routine", story: str = "") -> dict:
        """Save a kidney-donor request and get its public page path (/r/<token>) to share. Needs a patient or caregiver account."""
        return c.tool("create_kidney_request", {"hospital_name": hospital_name, "patient_name": patient_name, "blood_group": blood_group, "contact_phone": contact_phone,
                                                "contact_name": contact_name, "city": city, "age": age, "relation": relation, "urgency": urgency, "story": story})

    @mcp.tool()
    def find_compatible_donors(request_id: int) -> dict:
        """Registered living-donor pledges whose ABO blood group is compatible with a request (phones are masked)."""
        return c.tool("find_compatible_donors", {"request_id": request_id})

    @mcp.tool()
    def list_my_requests(status: Literal["open", "matched", "fulfilled", "closed", "any"] = "any") -> dict:
        """List this account's donor requests."""
        return c.tool("list_my_requests", {"status": status})

    # ---- optional: real sending through Meta's WhatsApp Cloud API (not tested without credentials) ----
    if os.getenv("WHATSAPP_CLOUD_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID"):
        @mcp.tool()
        def send_whatsapp_cloud(to_phone: str, text: str, confirm: bool = False) -> dict:
            """Send a WhatsApp message through the WhatsApp Cloud API. Only works to people who messaged your business number in the last 24 hours (Meta rule), and only after the person says yes (confirm=true)."""
            if not confirm:
                return {"sent": False, "reason": "Ask the person to confirm the recipient and the text, then call again with confirm=true."}
            digits = re.sub(r"\D", "", to_phone)
            r = httpx.post(f"https://graph.facebook.com/v20.0/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages", timeout=20,
                           headers={"Authorization": f"Bearer {os.environ['WHATSAPP_CLOUD_TOKEN']}"},
                           json={"messaging_product": "whatsapp", "to": digits, "type": "text", "text": {"body": text[:4000]}})
            return {"sent": r.status_code < 300, "status": r.status_code, "response": r.text[:300]}

    return mcp


if __name__ == "__main__":
    build_server().run()
