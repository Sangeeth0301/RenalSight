import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'buddy.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.modules.buddy import llm_router  # noqa: E402
from app.modules.buddy.llm_router import LLMRouter, ProviderError  # noqa: E402


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def make_router(chain, enabled, clock=None):
    cfgs = {n: {"base_url": "http://x", "api_key": "k", "model": "m", "enabled": n in enabled} for n in ("gemini", "groq", "openai", "xai", "ollama")}
    return LLMRouter(chain=chain, cfgs=cfgs, clock=clock or Clock())


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_router():
    yield
    llm_router.set_router(None)


def patient(client, email, lang="en"):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Pat", "language": lang})
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    client.put("/me/profile", json={"birth_year": 1960, "sex": "female", "diabetes": True}, headers=h)
    client.post("/labs", json={"taken_on": "2026-06-01", "scr": 2.4, "acr": 250, "sbp": 148, "hgb": 11.0, "potassium": 4.9}, headers=h)
    return h


def text_msg(t):
    return {"choices": [{"message": {"role": "assistant", "content": t}}]}


def tool_msg(name, args="{}", cid="c1"):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": cid, "type": "function", "function": {"name": name, "arguments": args}}]}}]}


def test_fallback_between_providers_and_cooldown(client, monkeypatch):
    clock = Clock()
    llm_router.set_router(make_router(["gemini", "groq", "rules"], {"gemini", "groq"}, clock))
    calls = {"gemini": 0, "groq": 0}
    seen_tool_result = {}

    def fake(cfg, payload, timeout):
        n = cfg["name"]
        calls[n] += 1
        if n == "gemini":
            raise ProviderError(429, "quota exceeded")
        last = payload["messages"][-1]
        if last["role"] == "tool":
            seen_tool_result["content"] = last["content"]
            return text_msg("Your kidney stage is shown above. Please talk to your doctor.")
        return tool_msg("my_kidney_state")

    monkeypatch.setattr(llm_router, "call_provider", fake)
    h = patient(client, "b1@example.com")
    r = client.post("/buddy/chat", json={"message": "How are my kidneys?"}, headers=h).json()
    assert r["provider"] == "groq" and r["ai_online"] and r["tools_used"][0]["tool"] == "my_kidney_state"
    assert "visual_stage" in seen_tool_result["content"]                     # the model got REAL tool data
    assert calls["gemini"] == 1
    # gemini is now cooling down: not tried again
    client.post("/buddy/chat", json={"message": "Thanks"}, headers=h)
    assert calls["gemini"] == 1
    status = {p["provider"]: p for p in llm_router.get_router().status()}
    assert status["gemini"]["state"] == "cooldown" and status["gemini"]["failures"] == 1 and status["groq"]["successes"] >= 2
    clock.t += 61                                                            # cooldown over: gemini is tried again
    client.post("/buddy/chat", json={"message": "Again"}, headers=h)
    assert calls["gemini"] == 2
    hist = client.get("/buddy/history", headers=h).json()
    assert hist[0]["role"] == "user" and hist[-1]["role"] == "assistant"


def test_all_providers_fail_uses_rule_fallback_in_tamil(client, monkeypatch):
    llm_router.set_router(make_router(["gemini", "groq", "rules"], {"gemini", "groq"}))

    def fake(cfg, payload, timeout):
        raise ProviderError(None, "network: ConnectError")

    monkeypatch.setattr(llm_router, "call_provider", fake)
    h = patient(client, "b2@example.com", lang="ta")
    r = client.post("/buddy/chat", json={"message": "hello"}, headers=h).json()
    assert r["provider"] == "rules" and r["ai_online"] is False and r["language"] == "ta"
    assert "AI உதவியாளர்" in r["reply"] and "eGFR" in r["reply"]
    assert client.get("/buddy/status", headers=h).json() == {"ai_online": False}


def test_no_keys_configured_still_answers(client):
    llm_router.set_router(make_router(["gemini", "groq", "rules"], set()))
    h = patient(client, "b3@example.com", lang="bn")
    r = client.post("/buddy/chat", json={"message": "hi"}, headers=h).json()
    assert r["provider"] == "rules" and "এআই" in r["reply"]


def test_doses_are_stripped_and_disallowed_tools_refused(client, monkeypatch):
    llm_router.set_router(make_router(["groq", "rules"], {"groq"}))
    state = {"n": 0}
    captured = {}

    def fake(cfg, payload, timeout):
        state["n"] += 1
        last = payload["messages"][-1]
        if last["role"] == "tool":
            captured["tool_out"] = last["content"]
            return text_msg("You could take losartan 50 mg every day.")
        return tool_msg("whatif", json.dumps({"base": {}}))                  # exists in the registry but the Buddy may not use it

    monkeypatch.setattr(llm_router, "call_provider", fake)
    h = patient(client, "b4@example.com")
    r = client.post("/buddy/chat", json={"message": "what dose?"}, headers=h).json()
    assert "not available" in captured["tool_out"]
    assert "50 mg" not in r["reply"] and "[ask your doctor for the dose]" in r["reply"] and r["dose_removed"]
    assert r["tools_used"][0]["ok"] is False


def test_language_ordering_and_status_schema():
    r = make_router(["groq", "gemini", "openai", "ollama", "rules"], {"groq", "gemini", "openai", "ollama"})
    assert r.ordered("en") == ["groq", "gemini", "openai", "ollama"]
    assert r.ordered("te") == ["gemini", "openai", "groq", "ollama"]          # strong multilingual models first, local model last
    names = [x["provider"] for x in r.status()]
    assert names == ["groq", "gemini", "openai", "ollama", "rules"]


def test_roles_and_rate_limit(client, monkeypatch):
    llm_router.set_router(make_router(["rules"], set()))
    r = client.post("/auth/register", json={"email": "bd@example.com", "password": "password123", "name": "Dr", "role": "doctor"})
    dh = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.post("/buddy/chat", json={"message": "hi"}, headers=dh).status_code == 403
    assert client.get("/admin/llm-status", headers=dh).status_code == 403
    # admin can read provider status
    with SessionLocal() as db:
        db.add(User(email="admin@example.com", password_hash=hash_password("password123"), name="Admin", role="admin"))
        db.commit()
    ah = {"Authorization": "Bearer " + client.post("/auth/login", json={"email": "admin@example.com", "password": "password123"}).json()["access_token"]}
    assert client.get("/admin/llm-status", headers=ah).json()[0]["provider"] == "rules"
    # per-user rate limit protects free-tier quotas
    monkeypatch.setattr(get_settings(), "buddy_messages_per_minute", 3)
    h = patient(client, "b5@example.com")
    codes = [client.post("/buddy/chat", json={"message": f"m{i}"}, headers=h).status_code for i in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    assert client.post("/buddy/chat", json={"message": ""}, headers=h).status_code in (422, 429)
    assert client.post("/buddy/chat", json={"message": "hi", "language": "xx"}, headers=h).status_code in (422, 429)


def test_http_client_format_and_error_mapping(monkeypatch):
    import httpx

    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers.get("authorization"), json.loads(request.content)
        code = int(request.headers.get("x-test-status", "200"))
        return httpx.Response(code, json={"choices": [{"message": {"content": "hi"}}]} if code == 200 else {"error": "quota"})

    transport = httpx.MockTransport(handler)

    def fake_post(url, json=None, headers=None, timeout=None):
        with httpx.Client(transport=transport) as c:
            return c.post(url, json=json, headers=headers)

    monkeypatch.setattr(httpx, "post", fake_post)
    cfg = {"base_url": "https://api.example.com/v1/", "api_key": "secret", "model": "m1"}
    out = llm_router.call_provider(cfg, {"messages": []}, 5)
    assert out["choices"][0]["message"]["content"] == "hi"
    assert seen["url"] == "https://api.example.com/v1/chat/completions" and seen["auth"] == "Bearer secret" and seen["body"]["model"] == "m1"

    def fake_429(url, json=None, headers=None, timeout=None):
        return httpx.Response(429, text="quota")

    monkeypatch.setattr(httpx, "post", fake_429)
    with pytest.raises(ProviderError) as e:
        llm_router.call_provider(cfg, {"messages": []}, 5)
    assert e.value.status == 429

    def fake_timeout(url, json=None, headers=None, timeout=None):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", fake_timeout)
    with pytest.raises(ProviderError) as e:
        llm_router.call_provider(cfg, {"messages": []}, 5)
    assert e.value.status is None
