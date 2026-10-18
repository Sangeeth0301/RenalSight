"""Fills the local database with a large, realistic demo cohort.

    python seed_cohort.py            # about 320 patients, 8 doctors; safe to run again (skips if already seeded)
    python seed_cohort.py --patients 600

Real part: each patient's most recent lab values (creatinine, urine ACR, BP, HbA1c, haemoglobin, potassium, urea, age, sex, diabetes)
are real adult records sampled from NHANES 2005-2014 (data/processed/nhanes_adults.csv).
Synthetic part: names, cities, earlier visits (back-calculated from a plausible eGFR decline rate), doctors, donor pledges, requests and dialysis logs.
Everything is demo data; phone numbers are fake. Password for every account: Demo@12345
"""
import argparse
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import DialysisSession, DonorOffer, DonorPledge, Hospital, JourneyStep, OrganRequest, User  # noqa: E402
from app.modules.doctor.router import new_doctor_code  # noqa: E402
from app.modules.labs import service as labs_service  # noqa: E402
from app.modules.transplant import data as TD  # noqa: E402
from app.modules.transplant import service as TS  # noqa: E402
from clinical import egfr_ckdepi_2021  # noqa: E402

PASSWORD = "Demo@12345"
REGIONS = [  # (language, cities, first names, last names)
    ("ta", ["Chennai", "Coimbatore", "Madurai", "Vellore", "Salem", "Tiruchirappalli"],
     ["Arun", "Karthik", "Murugan", "Selvi", "Lakshmi", "Priya", "Senthil", "Meenakshi", "Gopal", "Kavitha", "Ramesh", "Vijaya", "Saravanan", "Thenmozhi", "Bala", "Anbu"],
     ["Kumar", "Raman", "Pillai", "Subramanian", "Natarajan", "Iyer", "Devi", "Selvam", "Rajan"]),
    ("bn", ["Kolkata", "Howrah", "Siliguri", "Durgapur", "Asansol"],
     ["Sourav", "Anirban", "Debasish", "Sumita", "Rina", "Tapan", "Mousumi", "Arpita", "Subir", "Nandini", "Partha", "Shyamal", "Ruma", "Biswajit", "Soma", "Ashok"],
     ["Das", "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Sen", "Roy", "Bose", "Dutta"]),
    ("te", ["Hyderabad", "Visakhapatnam", "Vijayawada", "Warangal", "Guntur", "Tirupati"],
     ["Venkat", "Srinivas", "Lakshmi", "Padma", "Ravi", "Sujatha", "Naresh", "Anitha", "Krishna", "Madhavi", "Suresh", "Radha", "Prasad", "Vani", "Ramana", "Swathi"],
     ["Reddy", "Rao", "Naidu", "Chowdary", "Sastry", "Varma", "Goud", "Murthy", "Babu"]),
    ("en", ["New Delhi", "Mumbai", "Bengaluru", "Kochi", "Lucknow", "Chandigarh", "Pune"],
     ["Amit", "Neha", "Rahul", "Pooja", "Vikram", "Sunita", "Manoj", "Anjali", "Rohit", "Deepa", "Sanjay", "Kiran", "Farah", "Imran", "Gurpreet", "Joseph"],
     ["Sharma", "Verma", "Singh", "Gupta", "Khan", "Nair", "Menon", "Kapoor", "Joshi"]),
]
DOCTORS = [("dr.meera.nair", "Dr. Meera Nair", "en"), ("dr.arjun.das", "Dr. Arjun Das", "bn"), ("dr.sunil.reddy", "Dr. Sunil Reddy", "te"), ("dr.kavya.iyer", "Dr. Kavya Iyer", "ta"),
           ("dr.rahul.mehta", "Dr. Rahul Mehta", "en"), ("dr.ananya.sen", "Dr. Ananya Sen", "bn"), ("dr.vamsi.krishna", "Dr. Vamsi Krishna", "te"), ("dr.senthil.vel", "Dr. Senthil Vel", "ta")]
BG = ["O+", "B+", "A+", "AB+", "O-", "B-", "A-", "AB-"]
BG_W = [0.36, 0.31, 0.21, 0.07, 0.02, 0.015, 0.01, 0.005]


def scr_for_egfr(target, age, female):
    lo, hi = 0.3, 15.0
    for _ in range(40):                                    # eGFR falls as creatinine rises: bisect
        mid = (lo + hi) / 2
        if float(egfr_ckdepi_2021(mid, age, female)) > target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)


def sample_patients(n, rng):
    df = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    need = ["age", "male", "scr", "egfr", "acr", "sbp", "hba1c", "hgb", "potassium", "bun", "diabetes"]
    df = df.dropna(subset=need)
    df = df[(df.age >= 25) & (df.age <= 88)]
    advanced = df[df.egfr < 30]
    mid = df[(df.egfr >= 30) & (df.egfr < 60)]
    early = df[(df.egfr >= 60) & ((df.acr >= 30) | (df.diabetes == 1))]
    risk = df[df.egfr >= 60]
    parts = [(advanced, 0.10), (mid, 0.35), (early, 0.30), (risk, 0.25)]
    out = []
    for pool, share in parts:
        k = min(len(pool), max(1, round(n * share)))
        out.append(pool.sample(k, random_state=int(rng.integers(1e9))))
    return pd.concat(out).sample(frac=1, random_state=5).reset_index(drop=True).head(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=320)
    n = ap.parse_args().patients
    rng = np.random.default_rng(2026)
    rnd = random.Random(2026)
    Base.metadata.create_all(engine)
    pw = hash_password(PASSWORD)
    today = date.today()
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == "patient001@example.com")):
            print("Cohort already present; nothing to do.")
            return
        rao = db.scalar(select(User).where(User.email == "dr.rao@example.com"))
        docs = [rao] if rao else []
        for slug, name, lang in DOCTORS:
            d = User(email=f"{slug}@example.com", password_hash=pw, name=name, role="doctor", language=lang)
            d.doctor_code = new_doctor_code(db)
            db.add(d)
            db.commit()
            docs.append(d)
        TS.seed_hospitals(db)

        people = sample_patients(n, rng)
        users: list[tuple[User, float]] = []
        for i, row in people.iterrows():
            lang, cities, firsts, lasts = REGIONS[i % len(REGIONS)]
            female = int(row.male) == 0
            name = f"{rnd.choice(firsts)} {rnd.choice(lasts)}"
            age = int(row.age)
            u = User(email=f"patient{i + 1:03d}@example.com", password_hash=pw, name=name, role="patient", language=lang, birth_year=today.year - age,
                     sex="female" if female else "male", diabetes=bool(row.diabetes) or bool(row.hba1c >= 6.5), hypertension=bool(row.sbp >= 140),
                     doctor_id=docs[0].id if i % 11 == 0 else rnd.choice(docs).id)
            db.add(u)
            db.flush()
            # visits: the real record is the latest; earlier ones are back-calculated from a plausible decline rate
            visits = int(rng.integers(3, 7))
            slope = -float(rng.gamma(2.0, 1.1 if row.egfr < 60 else 0.5)) * (1.4 if u.diabetes else 1.0)      # mL/min/yr
            last_date = today - timedelta(days=int(rng.integers(3, 70)))
            for v in range(visits):
                back_years = (visits - 1 - v) * 0.5
                d = last_date - timedelta(days=int(back_years * 365))
                e = float(row.egfr) - slope * back_years * (1 + rng.normal(0, 0.06))
                e = min(max(e, 8), 125)
                is_last = v == visits - 1
                scr = float(row.scr) if is_last else scr_for_egfr(e, u.age(d) or age, female)
                f = 1.0 if is_last else max(0.4, 1 + slope * back_years * 0.03 * -1)
                rec = {"taken_on": d, "scr": round(scr, 2), "acr": round(float(row.acr) * (1.0 if is_last else rng.uniform(0.55, 0.95)), 1),
                       "sbp": round(float(row.sbp) + (0 if is_last else rng.normal(-3, 5))), "dbp": round(float(row.dbp) if not math.isnan(row.dbp) else 80),
                       "hba1c": round(float(row.hba1c) + (0 if is_last else rng.normal(0, 0.3)), 1), "hgb": round(float(row.hgb) + (0 if is_last else rng.uniform(0.1, 0.7)), 1),
                       "potassium": round(float(row.potassium) + (0 if is_last else rng.normal(-0.1, 0.2)), 1), "bun": round(float(row.bun) * (1.0 if is_last else rng.uniform(0.7, 1.0)))}
                labs_service.add_lab(db, u, rec, source="cohort")
            users.append((u, float(row.egfr)))
        print(f"patients: {len(users)}")

        # donor pledges: ~half of the cohort's healthy-ish members and some family
        pledges = 0
        for u, e in users:
            if rnd.random() < 0.4:
                kind = rnd.choices(["deceased", "both", "living"], [0.6, 0.25, 0.15])[0]
                organs = ["kidney", "liver"] if kind == "living" else rnd.sample(sorted(TD.ORGANS_DECEASED), rnd.randint(3, 7))
                if kind == "both":
                    organs = sorted(set(organs) | {"kidney"})
                db.add(DonorPledge(user_id=None, name=u.name, blood_group=rnd.choices(BG, BG_W)[0], city=rnd.choice(REGIONS[users.index((u, e)) % 4][1]),
                                   phone=f"+91 90000 {rnd.randint(10000, 99999)}", kind=kind, organs=organs, family_informed=rnd.random() < 0.6, consent=True))
                pledges += 1
        db.commit()
        print(f"donor pledges: {pledges}")

        # requests for the sickest, dialysis logs for stage 5
        hospitals = list(db.scalars(select(Hospital).where(Hospital.transplant.is_(True))))
        sick = [(u, e) for u, e in users if e < 20]
        reqs = 0
        for u, e in sick:
            if rnd.random() < 0.55:
                h = rnd.choice(hospitals)
                r = OrganRequest(token=TS.new_token(), user_id=u.id, hospital_id=h.id, hospital_name=h.name, patient_name=u.name, blood_group=rnd.choices(BG, BG_W)[0],
                                 age=u.age(), city=h.city, contact_name=f"{u.name.split()[0]}'s family", contact_phone=f"+91 98000 {rnd.randint(10000, 99999)}",
                                 relation="family", urgency=rnd.choice(["routine", "soon", "urgent"]), status=rnd.choice(["open", "open", "open", "matched", "fulfilled"]),
                                 verified=rnd.random() < 0.5)
                db.add(r)
                db.flush()
                for _ in range(rnd.randint(0, 3)):
                    bg = rnd.choices(BG, BG_W)[0]
                    db.add(DonorOffer(request_id=r.id, name=f"{rnd.choice(REGIONS[0][2])} {rnd.choice(REGIONS[1][3])}", blood_group=bg, phone=f"+91 91000 {rnd.randint(10000, 99999)}",
                                      note="Happy to be tested", compatible=TS.is_compatible(r.blood_group, bg)))
                reqs += 1
        dial = 0
        for u, e in users:
            if e < 15:
                w = rnd.uniform(48, 82)
                for k in range(rnd.randint(6, 10)):
                    pre = round(w + rnd.uniform(1.0, 4.2), 1)
                    db.add(DialysisSession(user_id=u.id, on_date=today - timedelta(days=2 * (10 - k)), centre=rnd.choice(hospitals).short_name, pre_weight=pre,
                                           post_weight=round(pre - rnd.uniform(1.5, 3.5), 1), pre_bp=f"{rnd.randint(130, 170)}/{rnd.randint(75, 100)}",
                                           post_bp=f"{rnd.randint(110, 145)}/{rnd.randint(65, 90)}", hours=4.0))
                    dial += 1
            if e < 30 and rnd.random() < 0.6:
                for key in TD.JOURNEY_KEYS[: rnd.randint(1, 6)]:
                    db.add(JourneyStep(user_id=u.id, step_key=key, done=True))
        db.commit()
        print(f"requests: {reqs}, dialysis sessions: {dial}")
        print("Doctors: dr.rao + 8 more (e.g. dr.meera.nair@example.com). Patients: patient001@example.com ... Password: " + PASSWORD)


if __name__ == "__main__":
    main()
