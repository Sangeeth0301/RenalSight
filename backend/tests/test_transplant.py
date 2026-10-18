import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'transplant.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.modules.transplant import service as S  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email, role="patient", lang="en"):
    r = client.post("/auth/register", json={"email": "tx_" + email, "password": "password123", "name": email.split("@")[0].title(), "role": role, "language": lang}).json()
    return {"Authorization": "Bearer " + r["access_token"]}, r["user"]


def make_admin(client):
    with SessionLocal() as db:
        db.add(User(email="tx_admin@example.com", password_hash=hash_password("password123"), name="Admin", role="admin"))
        db.commit()
    r = client.post("/auth/login", json={"email": "tx_admin@example.com", "password": "password123"}).json()
    return {"Authorization": "Bearer " + r["access_token"]}


REQ = {"hospital_name": "KMCH", "patient_name": "Ravi Kumar", "blood_group": "B+", "contact_phone": "9876543210", "contact_name": "Anita", "city": "Coimbatore", "age": 41, "relation": "father"}


def test_abo_rules():
    assert S.donor_groups_for("O+") == ["O"]
    assert set(S.donor_groups_for("AB-")) == {"AB", "A", "B", "O"}
    assert S.is_compatible("B+", "O-") and not S.is_compatible("B+", "A+")
    assert S.clean_bg("ab positive") == "AB+"
    with pytest.raises(Exception):
        S.clean_bg("Z+")


def test_hospital_search_aliases(client):
    assert any(h["short_name"] == "KMCH" for h in client.get("/hospitals", params={"q": "kmch"}).json())
    kol = client.get("/hospitals", params={"city": "kolkata"}).json()
    assert len(kol) >= 5 and all(not h["verified"] for h in kol) and kol[0]["note"]


def test_compose_all_languages_and_links(client):
    h, _ = signup(client, "composer@example.com")
    for lang in ("en", "ta", "bn", "te"):
        body = {"hospital": "AIIMS", "patient_name": "Ravi Kumar", "blood_group": "B+", "contact_name": "Anita", "contact_phone": "+91 98765 43210", "language": lang, "city": "Delhi"}
        out = client.post("/share/compose", json=body, headers=h).json()
        assert "Ravi Kumar" in out["text"] and "B+" in out["text"] and "98765 43210" in out["text"]
        assert out["links"]["whatsapp"].startswith("https://wa.me/?text=")
    en = client.post("/share/compose", json={**body, "language": "en", "tone": "urgent", "relation": "myself", "send_to": "98765 11111"}, headers=h).json()
    assert en["text"].startswith("🚨 URGENT") and "I am admitted" in en["text"]
    assert en["links"]["whatsapp"].startswith("https://wa.me/919876511111?text=") and en["links"]["sms"].startswith("sms:+919876511111")
    assert "never paid" in en["text"] and "₹" not in en["text"]
    no_phone = client.post("/share/compose", json={**body, "language": "en", "include_phone": False}, headers=h).json()
    assert "98765" not in no_phone["text"]


def test_compose_polish_falls_back_without_ai(client):
    h, _ = signup(client, "polish@example.com")
    out = client.post("/share/compose", json={"hospital": "KMCH", "patient_name": "Sita", "blood_group": "O+", "contact_phone": "9000000001", "polish": True}, headers=h).json()
    assert out["written_by"] == "template"


def test_polish_rejects_lost_facts():
    assert not S.facts_preserved("x", "Please help with a donor.", patient_name="Ravi", blood_group="B+", contact_phone="9876543210")
    assert S.facts_preserved("x", "Ravi needs a kidney, group B+, call 9876543210", patient_name="Ravi", blood_group="B+", contact_phone="9876543210")


def test_request_lifecycle_and_public_page(client):
    h, owner = signup(client, "owner@example.com")
    r = client.post("/requests", json=REQ, headers=h)
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["hospital_name"].startswith("Kovai") and req["blood_group"] == "B+" and not req["verified"]
    pub = client.get(f"/public/requests/{req['token']}").json()
    assert "id" not in pub and "9876543210" not in str(pub) and pub["contact_phone"].endswith("10") and pub["scam_warning"]
    # a stranger offering to be tested, with consent required
    offer = {"name": "Meena", "blood_group": "O-", "phone": "9123456789", "note": "Happy to be tested", "consent": True}
    assert client.post(f"/public/requests/{req['token']}/offers", json={**offer, "consent": False}).status_code == 422
    ok = client.post(f"/public/requests/{req['token']}/offers", json=offer).json()
    assert ok["ok"] and ok["compatible_hint"] is True
    detail = client.get(f"/requests/{req['id']}", headers=h).json()
    assert len(detail["offer_list"]) == 1 and detail["offer_list"][0]["phone"] == "9123456789"
    # privacy: another patient cannot open it
    h2, _ = signup(client, "other@example.com")
    assert client.get(f"/requests/{req['id']}", headers=h2).status_code == 404
    # doctor verifies
    d, _ = signup(client, "drv@example.com", role="doctor")
    assert client.post(f"/requests/{req['id']}/verify", headers=d).json()["verified"] is True
    assert client.post(f"/requests/{req['id']}/verify", headers=h2).status_code == 403
    msg = client.post(f"/requests/{req['id']}/compose", json={"language": "ta"}, headers=h).json()
    assert "Ravi Kumar" in msg["text"] and msg["links"]["whatsapp"].startswith("https://wa.me/")
    client.patch(f"/requests/{req['id']}/status", json={"status": "closed"}, headers=h)
    assert client.get(f"/public/requests/{req['token']}").status_code == 404


def test_public_offer_rate_limit(client):
    h, _ = signup(client, "rl@example.com")
    tok = client.post("/requests", json=REQ, headers=h).json()["token"]
    codes = [client.post(f"/public/requests/{tok}/offers", json={"name": "Xx", "phone": "9999999999", "consent": True}).status_code for _ in range(8)]
    assert 429 in codes


def test_donor_registry_and_matching(client):
    don, _ = signup(client, "donor@example.com")
    bad = client.post("/donors/pledge", json={"name": "Donor", "blood_group": "O+", "kind": "living", "organs": ["heart"], "consent": True}, headers=don)
    assert bad.status_code == 422 and "after death" in bad.text
    assert client.post("/donors/pledge", json={"name": "Donor", "blood_group": "O+", "kind": "living", "organs": ["kidney"], "consent": False}, headers=don).status_code == 422
    ok = client.post("/donors/pledge", json={"name": "Donor One", "blood_group": "O+", "city": "Coimbatore", "phone": "9000011111", "kind": "both", "organs": ["kidney"], "consent": True}, headers=don)
    assert ok.status_code == 200, ok.text
    h, _ = signup(client, "needer@example.com")
    req = client.post("/requests", json=REQ, headers=h).json()
    detail = client.get(f"/requests/{req['id']}", headers=h).json()
    m = detail["matches"]
    assert m and m[0]["name"] == "Donor One" and "9000011111" not in m[0]["phone"] and m[0]["can_message"]
    assert client.post(f"/requests/{req['id']}/contact-donor/{m[0]['pledge_id']}", headers=h).json()["ok"]
    stats = client.get("/donors/stats").json()
    assert stats["pledges"] >= 1 and stats["by_organ"]["kidney"] >= 1
    deceased = client.post("/donors/pledge", json={"name": "Donor One", "blood_group": "O+", "kind": "deceased", "organs": ["heart", "kidney", "cornea"], "consent": True}, headers=don)
    assert deceased.status_code == 200 and "heart" in deceased.json()["organs"]
    assert client.get("/donors/mine", headers=don).json()["kind"] == "deceased"
    assert client.get(f"/requests/{req['id']}", headers=h).json()["matches"] == []        # deceased-only pledges are not offered as living matches
    assert client.delete("/donors/mine", headers=don).json()["ok"]
    assert client.get("/donors/mine", headers=don).json() is None
    assert "O" in client.get("/donors/compat", params={"blood_group": "A+"}).json()["donor_groups"]


def test_journey_and_dialysis(client):
    h, _ = signup(client, "journey@example.com")
    j = client.get("/journey", headers=h).json()
    assert j["progress"] == 0 and j["next"] == "nephrologist" and len(j["steps"]) == 10
    j = client.put("/journey/nephrologist", json={"done": True, "note": "Dr Rao"}, headers=h).json()
    assert j["progress"] == 10 and j["next"] == "blood_hla"
    assert client.put("/journey/nope", json={"done": True}, headers=h).status_code == 404
    client.post("/dialysis/sessions", json={"on_date": "2026-10-01", "pre_weight": 70, "post_weight": 67.5, "hours": 4}, headers=h)
    client.post("/dialysis/sessions", json={"on_date": "2026-10-03", "pre_weight": 71, "post_weight": 68, "hours": 4}, headers=h)
    out = client.get("/dialysis/sessions", headers=h).json()
    assert out["sessions"][0]["on_date"] == "2026-10-03" and out["interdialytic_gain_kg"][0] == 3.5 and out["warning"]


def test_seat_board_staff_only_updates(client):
    p, _ = signup(client, "seatp@example.com")
    d, _ = signup(client, "seatd@example.com", role="doctor")
    hid = client.get("/hospitals", params={"q": "kmch"}).json()[0]["id"]
    assert client.put(f"/hospitals/{hid}/seats", json={"shift": "morning", "total": 10, "free": 2}, headers=p).status_code == 403
    assert client.put(f"/hospitals/{hid}/seats", json={"shift": "morning", "total": 10, "free": 11}, headers=d).status_code == 422
    assert client.put(f"/hospitals/{hid}/seats", json={"shift": "morning", "total": 10, "free": 4}, headers=d).status_code == 200
    board = client.get("/dialysis/seats").json()
    assert board["hospitals"][0]["free_total"] >= 4 and board["note"]


def test_emergency_card_and_exports(client):
    h, u = signup(client, "card@example.com")
    client.put("/me/profile", json={"birth_year": 1970, "sex": "male"}, headers=h)
    client.post("/labs", json={"taken_on": "2026-10-01", "scr": 2.4, "acr": 300, "sbp": 140, "dbp": 90, "potassium": 4.8}, headers=h)
    card = client.put("/emergency-card", json={"blood_group": "A+", "allergies": "Penicillin", "contact_name": "Mom", "contact_phone": "9000000009"}, headers=h).json()
    pub = client.get(f"/public/emergency/{card['token']}").json()
    assert pub["blood_group"] == "A+" and pub["stage"] and any("NSAID" in w for w in pub["warnings"])
    client.put("/emergency-card", json={"blood_group": "A+", "public": False}, headers=h)
    assert client.get(f"/public/emergency/{card['token']}").status_code == 404
    fhir = client.get("/export/fhir", headers=h)
    assert fhir.headers["content-type"].startswith("application/fhir+json")
    b = fhir.json()
    codes = {e["resource"]["code"]["coding"][0]["code"] for e in b["entry"] if e["resource"]["resourceType"] == "Observation"}
    assert {"2160-0", "98979-8", "9318-7"} <= codes
    pdf = client.get("/export/referral.pdf", params={"to": "KMCH", "reason": "Transplant evaluation"}, headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    other, o = signup(client, "card2@example.com")
    assert client.get("/export/fhir", params={"patient_id": u["id"]}, headers=other).status_code == 403


def test_tools_registered(client):
    h, _ = signup(client, "tooluser@example.com")
    names = {t["name"] for t in client.get("/tools", headers=h).json()}
    assert {"search_hospitals", "compose_request_message", "whatsapp_link", "create_kidney_request", "find_compatible_donors", "list_my_requests"} <= names
    r = client.post("/tools/create_kidney_request", json=REQ, headers=h).json()
    assert r["public_path"].startswith("/r/")
    link = client.post("/tools/whatsapp_link", json={"text": "Hello team"}, headers=h).json()
    assert link["url"] == "https://wa.me/?text=Hello%20team"
