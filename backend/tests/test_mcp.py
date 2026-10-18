import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'mcp.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "mcp_server"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

pytest.importorskip("mcp")
from app.main import app  # noqa: E402
from server import RenalSightClient, build_server  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_mcp_tools_end_to_end():
    with TestClient(app) as http:
        http.post("/auth/register", json={"email": "mcp_family@example.com", "password": "password123", "name": "Family", "role": "caregiver"})
        server = build_server(RenalSightClient(http=http, email="mcp_family@example.com", password="password123"))
        names = {t.name for t in run(server.list_tools())}
        assert {"search_hospitals", "compose_request_message", "whatsapp_link", "create_kidney_request", "find_compatible_donors", "list_my_requests"} <= names
        assert "send_whatsapp_cloud" not in names                       # real sending stays off unless configured

        def call(name, args):
            res = run(server.call_tool(name, args))
            assert not res.is_error, res.content
            return json.loads(res.content[0].text)

        hosp = call("search_hospitals", {"query": "kmch"})
        assert any(h["short_name"] == "KMCH" for h in hosp["hospitals"])
        msg = call("compose_request_message", {"hospital": "KMCH", "patient_name": "Ravi Kumar", "blood_group": "B+", "contact_phone": "9876543210", "language": "en"})
        assert "Ravi Kumar" in msg["text"] and msg["links"]["whatsapp"].startswith("https://wa.me/?text=")
        link = call("whatsapp_link", {"text": "Hello"})
        assert link["url"] == "https://wa.me/?text=Hello"
        created = call("create_kidney_request", {"hospital_name": "KMCH", "patient_name": "Ravi Kumar", "blood_group": "B+", "contact_phone": "9876543210"})
        assert created["public_path"].startswith("/r/")
        mine = call("list_my_requests", {})
        assert len(mine["requests"]) == 1
