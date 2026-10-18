import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'wa.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.modules.whatsapp import router as wa  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def hdr(client, email="wa_user@example.com", role="patient"):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Wa", "role": role})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_allowlist_is_exactly_the_four_chats_and_blocks_everyone_else(client, monkeypatch):
    h = hdr(client)
    assert client.get("/whatsapp/allowed", headers=h).json()["allowed"] == ["Sem 5 Project", "Sandeep", "Sangeeth (You)", "Jagan"]
    launched = []
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(wa, "_state", lambda: {"linked": True})
    bad = client.post("/whatsapp/send", json={"text": "hello there", "recipients": [{"name": "Sandeep"}, {"name": "Mom"}]}, headers=h)
    assert bad.status_code == 403 and "Mom" in bad.text and launched == []             # one stranger blocks the whole send: nothing launched
    ok = client.post("/whatsapp/send", json={"text": "hello there", "recipients": [{"name": "sandeep"}, {"name": "Jagan", "phone": "9999999999"}]}, headers=h)
    assert ok.status_code == 200 and ok.json()["recipients"] == ["Sandeep", "Jagan"] and len(launched) == 1      # canonical names; phone numbers are ignored
    import json as _j
    job = _j.loads(Path(wa.JOBS, f"{ok.json()['job_id']}.job.json").read_text())
    assert job["recipients"] == [{"name": "Sandeep"}, {"name": "Jagan"}]


def test_requires_link_login_and_rate_limit(client, monkeypatch):
    h = hdr(client, "wa_user2@example.com")
    monkeypatch.setattr(wa.subprocess, "Popen", lambda *a, **k: None)
    monkeypatch.setattr(wa, "_state", lambda: {"linked": False})
    assert client.post("/whatsapp/send", json={"text": "hello there", "recipients": [{"name": "Jagan"}]}, headers=h).status_code == 409
    assert client.post("/whatsapp/send", json={"text": "hello there", "recipients": [{"name": "Jagan"}]}).status_code == 401
    monkeypatch.setattr(wa, "_state", lambda: {"linked": True})
    codes = [client.post("/whatsapp/send", json={"text": "hello there", "recipients": [{"name": "Jagan"}]}, headers=h).status_code for _ in range(8)]
    assert codes.count(200) == 6 and 429 in codes
    admin_like = hdr(client, "wa_admin_try@example.com", role="doctor")
    assert client.get("/whatsapp/status", headers=admin_like).status_code == 200
