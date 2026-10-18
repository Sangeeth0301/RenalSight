import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'connect.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email, role="patient", name=None):
    r = client.post("/auth/register", json={"email": "cn_" + email, "password": "password123", "name": name or email.split("@")[0], "role": role}).json()
    return {"Authorization": "Bearer " + r["access_token"]}, r["user"], r["access_token"]


def with_labs(client, h):
    client.put("/me/profile", json={"birth_year": 1960, "sex": "male", "diabetes": True}, headers=h)
    return client.post("/labs", json={"taken_on": "2026-06-01", "scr": 2.1, "acr": 300, "sbp": 150, "potassium": 5.0}, headers=h).json()


def connect(client, tid, token):
    ws = client.websocket_connect(f"/ws/threads/{tid}")
    s = ws.__enter__()
    s.send_json({"type": "auth", "token": token})
    return ws, s


def test_direct_thread_and_live_chat(client):
    dh, doc, dtok = signup(client, "d1@example.com", "doctor", "Dr Rao")
    ph, pat, ptok = signup(client, "p1@example.com", name="Asha")
    stranger_h, stranger, _ = signup(client, "s1@example.com", name="Stranger")
    # only linked doctor/patient pairs can open a direct thread
    assert client.post("/threads/direct", json={"user_id": doc["id"]}, headers=ph).status_code == 404
    client.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=ph)
    t = client.post("/threads/direct", json={"user_id": doc["id"]}, headers=ph).json()
    again = client.post("/threads/direct", json={"user_id": pat["id"]}, headers=dh).json()
    assert t["id"] == again["id"] and t["kind"] == "direct" and t["title"] == "Dr Rao"
    assert client.get(f"/threads/{t['id']}/messages", headers=stranger_h).status_code == 404
    lab = with_labs(client, ph)

    wa, a = connect(client, t["id"], ptok)
    wb, b = connect(client, t["id"], dtok)
    try:
        assert a.receive_json()["type"] == "ready"
        ready_b = b.receive_json()
        assert ready_b["type"] == "ready" and set(ready_b["online"]) == {pat["id"], doc["id"]}
        assert a.receive_json() == {"type": "presence", "user_id": doc["id"], "online": True}

        a.send_json({"type": "message", "body": "Hello doctor, my feet are swollen", "client_id": "abc"})
        ea, eb = a.receive_json(), b.receive_json()
        assert ea["message"]["body"] == "Hello doctor, my feet are swollen" and ea["message"]["client_id"] == "abc"
        assert eb["message"]["sender_name"] == "Asha"
        mid = eb["message"]["id"]

        b.send_json({"type": "typing"})
        assert a.receive_json() == {"type": "typing", "user_id": doc["id"]}
        b.send_json({"type": "read", "up_to": mid})
        assert a.receive_json()["up_to"] == mid and b.receive_json()["up_to"] == mid

        # patient shares their own kidney; the doctor cannot share a kidney
        a.send_json({"type": "message", "body": "my kidney", "attachment": {"type": "kidney_snapshot"}})
        got = b.receive_json()["message"]
        a.receive_json()
        assert got["kind"] == "attachment" and got["attachment"]["state"]["has_data"] and got["attachment"]["state"]["g_stage"]
        b.send_json({"type": "message", "attachment": {"type": "kidney_snapshot"}})
        assert b.receive_json()["type"] == "error"
        # a lab attachment must be the sender's own
        b.send_json({"type": "message", "attachment": {"type": "lab", "id": lab["id"]}})
        assert b.receive_json()["type"] == "error"
        a.send_json({"type": "message", "body": "lab", "attachment": {"type": "lab", "id": lab["id"]}})
        assert b.receive_json()["message"]["attachment"]["lab"]["scr"] == 2.1
        a.receive_json()
        # REST send also reaches connected members live
        r = client.post(f"/threads/{t['id']}/messages", json={"body": "Sent from REST"}, headers=dh)
        assert r.status_code == 201
        assert a.receive_json()["message"]["body"] == "Sent from REST" and b.receive_json()["message"]["id"] == r.json()["id"]
        a.send_json({"type": "ping"})
        assert a.receive_json() == {"type": "pong"}
        a.send_json({"type": "bogus"})
        assert a.receive_json()["type"] == "error"
    finally:
        wb.__exit__(None, None, None)
        wa.__exit__(None, None, None)

    hist = client.get(f"/threads/{t['id']}/messages", headers=ph).json()
    assert [m["body"] for m in hist][:1] == ["Hello doctor, my feet are swollen"] and len(hist) == 4
    older = client.get(f"/threads/{t['id']}/messages?before_id={hist[-1]['id']}&limit=2", headers=ph).json()
    assert len(older) == 2 and older[-1]["id"] < hist[-1]["id"]
    lst = client.get("/threads", headers=ph).json()
    assert lst[0]["id"] == t["id"] and lst[0]["last_message"]["body"] == "Sent from REST" and lst[0]["unread"] == 1
    client.post(f"/threads/{t['id']}/read", json={"up_to": 10 ** 6}, headers=ph)
    assert client.get("/threads", headers=ph).json()[0]["unread"] == 0


def test_offline_notification_and_validation(client):
    dh, doc, _ = signup(client, "d2@example.com", "doctor")
    ph, pat, _ = signup(client, "p2@example.com")
    client.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=ph)
    t = client.post("/threads/direct", json={"user_id": doc["id"]}, headers=ph).json()
    for i in range(3):
        assert client.post(f"/threads/{t['id']}/messages", json={"body": f"m{i}"}, headers=ph).status_code == 201
    notes = [n for n in client.get("/notifications", headers=dh).json() if n["kind"] == "message"]
    assert len(notes) == 1 and notes[0]["payload"]["thread_id"] == t["id"]           # one nudge until they read it
    assert client.post(f"/threads/{t['id']}/messages", json={"body": "x" * 2001}, headers=ph).status_code == 422
    assert client.post(f"/threads/{t['id']}/messages", json={"body": "   "}, headers=ph).status_code == 422


def test_websocket_auth_failures(client):
    dh, doc, dtok = signup(client, "d3@example.com", "doctor")
    ph, pat, ptok = signup(client, "p3@example.com")
    client.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=ph)
    t = client.post("/threads/direct", json={"user_id": doc["id"]}, headers=ph).json()
    _, _, other_tok = signup(client, "o3@example.com")
    for token, code in (("garbage", 4401), (other_tok, 4403)):
        with client.websocket_connect(f"/ws/threads/{t['id']}") as ws:
            ws.send_json({"type": "auth", "token": token})
            with pytest.raises(WebSocketDisconnect) as e:
                ws.receive_json()
            assert e.value.code == code
    with client.websocket_connect(f"/ws/threads/{t['id']}") as ws:             # first frame must be auth
        ws.send_json({"type": "message", "body": "hi"})
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4401


def test_consult_room_join_code_tasks_and_limits(client):
    oh, owner, otok = signup(client, "o4@example.com", name="Asha")
    fh, fam, ftok = signup(client, "f4@example.com", "caregiver", "Brother")
    dh, doc, _ = signup(client, "d4@example.com", "doctor", "Dr Rao")
    room = client.post("/rooms", json={"title": "Amma's kidney care"}, headers=oh).json()
    assert len(room["code"]) == 6 and room["code"].isdigit()
    # non-owners never see the code in listings
    j = client.post("/rooms/join", json={"code": room["code"]}, headers=fh).json()
    assert "code" not in j and {m["name"] for m in j["members"]} == {"Asha", "Brother"}
    assert client.post("/rooms/join", json={"code": room["code"]}, headers=dh).status_code == 200
    assert client.post("/rooms/join", json={"code": "12ab56"}, headers=dh).status_code == 422

    wa, a = connect(client, room["id"], otok)
    try:
        assert a.receive_json()["type"] == "ready"
        client.post(f"/rooms/{room['id']}/tasks", json={"text": "Buy low-salt groceries"}, headers=fh)
        assert a.receive_json()["task"]["text"] == "Buy low-salt groceries"
        tid = client.get(f"/rooms/{room['id']}/tasks", headers=oh).json()[0]["id"]
        client.patch(f"/rooms/{room['id']}/tasks/{tid}", json={"done": True}, headers=dh)
        assert a.receive_json()["task"]["done"] is True
    finally:
        wa.__exit__(None, None, None)
    hist = client.get(f"/threads/{room['id']}/messages", headers=fh).json()
    assert [m["kind"] for m in hist] == ["system", "system"]                  # two joins

    # leaving, owner rules, new code
    assert client.post(f"/rooms/{room['id']}/leave", headers=fh).status_code == 204
    assert client.get(f"/threads/{room['id']}/messages", headers=fh).status_code == 404
    assert client.post(f"/rooms/{room['id']}/leave", headers=oh).status_code == 409
    assert client.post(f"/rooms/{room['id']}/code", headers=dh).status_code == 403
    newc = client.post(f"/rooms/{room['id']}/code", headers=oh).json()["code"]
    assert client.post("/rooms/join", json={"code": newc}, headers=fh).status_code == 200
    assert client.delete(f"/rooms/{room['id']}", headers=dh).status_code == 403
    assert client.delete(f"/rooms/{room['id']}", headers=oh).status_code == 204
    assert client.post("/rooms/join", json={"code": newc}, headers=fh).status_code == 404          # closed rooms cannot be joined
    assert client.get("/threads", headers=oh).json() == []


def test_wrong_codes_are_rate_limited_and_rooms_have_a_member_cap(client):
    oh, owner, _ = signup(client, "o5@example.com")
    room = client.post("/rooms", json={"title": "Cap test"}, headers=oh).json()
    for i in range(7):
        h, _, _ = signup(client, f"m5{i}@example.com")
        r = client.post("/rooms/join", json={"code": room["code"]}, headers=h)
        assert r.status_code == (200 if i < 7 else 409)
    h, _, _ = signup(client, "late5@example.com")
    assert client.post("/rooms/join", json={"code": room["code"]}, headers=h).status_code == 409    # owner + 7 = 8 members
    bad = "000000" if room["code"] != "000000" else "000001"
    codes = [client.post("/rooms/join", json={"code": bad}, headers=h).status_code for _ in range(7)]
    assert codes[:5] == [404] * 5 and codes[5] == 429
