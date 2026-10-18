import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'translate.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.modules.translate import router as tr  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def hdr(client):
    r = client.post("/auth/register", json={"email": "tr_user@example.com", "password": "password123", "name": "T", "role": "patient"}).json()
    return {"Authorization": "Bearer " + r["access_token"]}


def test_parse_array_handles_fences_and_wrong_length():
    assert tr._parse_array('```json\n["a","b"]\n```', 2) == ["a", "b"]
    assert tr._parse_array('["a"]', 2) is None
    assert tr._parse_array("no json", 1) is None


def test_translate_caches_and_reports_unavailable(client, monkeypatch):
    h = hdr(client)
    calls = []

    def fake(texts, target):
        calls.append(list(texts))
        return [f"[{target}] {t}" for t in texts]

    monkeypatch.setattr(tr, "translate_batch", fake)
    r = client.post("/translate", json={"texts": ["Hello", "How are you?", ""], "target": "ta"}, headers=h).json()
    assert r["available"] and r["translations"][:2] == ["[ta] Hello", "[ta] How are you?"] and r["translations"][2] == ""
    again = client.post("/translate", json={"texts": ["Hello", "Hello"], "target": "ta"}, headers=h).json()
    assert again["translations"] == ["[ta] Hello", "[ta] Hello"] and len(calls) == 1          # served from the cache, no second AI call
    other = client.post("/translate", json={"texts": ["Hello"], "target": "bn"}, headers=h).json()
    assert other["translations"] == ["[bn] Hello"] and len(calls) == 2                        # cache is per language

    monkeypatch.setattr(tr, "translate_batch", lambda t, l: None)                              # no AI provider ready
    off = client.post("/translate", json={"texts": ["Brand new text"], "target": "te"}, headers=h).json()
    assert off["available"] is False and off["translations"] == ["Brand new text"] and off["translated"] == [False]


def test_translate_requires_login_and_valid_language(client):
    assert client.post("/translate", json={"texts": ["x"], "target": "ta"}).status_code == 401
    assert client.post("/translate", json={"texts": ["x"], "target": "fr"}, headers=hdr_existing(client)).status_code == 422


def hdr_existing(client):
    r = client.post("/auth/login", json={"email": "tr_user@example.com", "password": "password123"}).json()
    return {"Authorization": "Bearer " + r["access_token"]}
