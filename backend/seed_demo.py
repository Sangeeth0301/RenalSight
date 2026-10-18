"""Creates demo accounts and sample labs through the running API (http://localhost:8000).

    python seed_demo.py            # safe to run again; existing users are reused

All demo accounts use the password  Demo@12345  (demo data only: never use it for real people).
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASSWORD = "Demo@12345"
c = httpx.Client(base_url=BASE, timeout=30)


def signup(email, name, role="patient", language="en"):
    r = c.post("/auth/register", json={"email": email, "password": PASSWORD, "name": name, "role": role, "language": language})
    if r.status_code == 409:
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    d = r.json()
    return {"Authorization": "Bearer " + d["access_token"]}, d["user"]


def labs(h, rows):
    existing = c.get("/labs", headers=h).json()
    if existing:
        return
    for row in rows:
        c.post("/labs", json=row, headers=h).raise_for_status()


doc_h, doc = signup("dr.rao@example.com", "Dr. Rao", "doctor", "en")
print("doctor code:", doc["doctor_code"])

asha_h, _ = signup("asha@example.com", "Asha", "patient", "ta")
c.put("/me/profile", json={"birth_year": 1964, "sex": "female", "diabetes": True, "hypertension": True}, headers=asha_h)
c.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=asha_h)
labs(asha_h, [
    {"taken_on": "2024-06-10", "scr": 1.3, "acr": 120, "sbp": 146, "hba1c": 7.9, "hgb": 12.4, "potassium": 4.6},
    {"taken_on": "2024-12-12", "scr": 1.5, "acr": 180, "sbp": 148, "hba1c": 8.0, "hgb": 12.1, "potassium": 4.7},
    {"taken_on": "2025-06-14", "scr": 1.7, "acr": 240, "sbp": 150, "hba1c": 8.2, "hgb": 11.9, "potassium": 4.8},
    {"taken_on": "2025-12-15", "scr": 1.9, "acr": 300, "sbp": 152, "hba1c": 8.1, "hgb": 11.6, "potassium": 4.9},
    {"taken_on": "2026-06-18", "scr": 2.2, "acr": 340, "sbp": 154, "hba1c": 8.3, "hgb": 11.3, "potassium": 5.1},
])

ravi_h, _ = signup("ravi@example.com", "Ravi", "patient", "te")
c.put("/me/profile", json={"birth_year": 1958, "sex": "male", "diabetes": True, "hypertension": True}, headers=ravi_h)
c.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=ravi_h)
labs(ravi_h, [
    {"taken_on": "2025-10-01", "scr": 3.4, "acr": 650, "sbp": 168, "hba1c": 9.0, "hgb": 9.8, "potassium": 5.4},
    {"taken_on": "2026-04-01", "scr": 4.6, "acr": 900, "sbp": 172, "hba1c": 9.2, "hgb": 9.1, "potassium": 6.1},
])

meena_h, _ = signup("meena@example.com", "Meena", "patient", "bn")
c.put("/me/profile", json={"birth_year": 1990, "sex": "female", "diabetes": False, "hypertension": False}, headers=meena_h)
c.post("/me/doctor", json={"code": doc["doctor_code"]}, headers=meena_h)
labs(meena_h, [{"taken_on": "2026-05-02", "scr": 0.7, "acr": 8, "sbp": 116, "hba1c": 5.3, "hgb": 13.6, "potassium": 4.2}])

signup("brother@example.com", "Kumar (family)", "caregiver", "ta")
print("demo accounts ready:")
for e in ("dr.rao@example.com", "asha@example.com", "ravi@example.com", "meena@example.com", "brother@example.com"):
    print("  ", e, "/", PASSWORD)
print("admin: python create_admin.py admin@example.com", PASSWORD, "Admin")
