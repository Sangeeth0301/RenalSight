"""Transplant hub logic: blood-group compatibility, share-message composer, donor matching, FHIR export, referral letter.

Safety rules baked in: no payments or prices anywhere, organ appeals are kidney/liver only (hearts and other organs are
deceased-donor pledges handled through hospital waitlists), public pages never show a full phone number."""
from __future__ import annotations

import re
import secrets
import time
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from io import BytesIO
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...models import DonorPledge, Hospital, OrganRequest, User
from . import data as D

# ---------------------------------------------------------------- small helpers
BG_RE = re.compile(r"^(O|A|B|AB)[+-]$")


def clean_bg(bg: str) -> str:
    v = (bg or "").strip().upper().replace(" ", "")
    v = v.replace("POSITIVE", "+").replace("NEGATIVE", "-").replace("POS", "+").replace("NEG", "-")
    if v in ("O", "A", "B", "AB"):
        return v          # Rh not given: fine for kidney matching
    if not BG_RE.match(v):
        raise HTTPException(422, "Blood group must look like A+, O-, AB+ ...")
    return v


def abo(bg: str) -> str:
    return bg.rstrip("+-")


def donor_groups_for(recipient_bg: str) -> list[str]:
    """ABO groups that can donate a kidney to this recipient (Rh does not matter for kidneys)."""
    return D.ABO_DONORS[abo(clean_bg(recipient_bg))]


def is_compatible(recipient_bg: str, donor_bg: str) -> bool:
    if not donor_bg:
        return False
    return abo(clean_bg(donor_bg)) in donor_groups_for(recipient_bg)


def normalize_phone(p: str, default_cc: str = "91") -> str:
    """Digits only, international style, for wa.me links (10-digit numbers get the default country code)."""
    d = re.sub(r"\D", "", p or "")
    d = d.lstrip("0") if len(d) > 10 and d.startswith("00") else d
    if len(d) == 10:
        d = default_cc + d
    return d


def mask_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    return "" if not d else "•" * max(len(d) - 2, 0) + d[-2:]


def new_token() -> str:
    return secrets.token_urlsafe(9)


# simple in-memory limiter for public (unauthenticated) endpoints
_hits: dict[str, deque] = defaultdict(deque)


def public_rate_limit(key: str, limit: int = 6, window: int = 3600):
    q, now = _hits[key], time.monotonic()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many submissions from this address. Please try again later.")
    q.append(now)


# ---------------------------------------------------------------- hospitals
def seed_hospitals(db: Session):
    if db.scalar(select(func.count()).select_from(Hospital)):
        return
    for name, short, city, state, country, kind, tx in D.HOSPITALS:
        seats = {}
        if country == "India" and tx:
            seats = {"morning": {"total": 12, "free": 0}, "afternoon": {"total": 12, "free": 0}, "evening": {"total": 8, "free": 0}}
        db.add(Hospital(name=name, short_name=short, city=city, state=state, country=country, kind=kind, transplant=tx, verified=False, seats=seats))
    db.commit()


def hospital_out(h: Hospital) -> dict:
    return {"id": h.id, "name": h.name, "short_name": h.short_name, "city": h.city, "state": h.state, "country": h.country, "kind": h.kind,
            "transplant": h.transplant, "phone": h.phone, "verified": h.verified,
            "note": "" if h.verified else "Directory name only. Check the hospital's official website or phone before travelling."}


def search_hospitals(db: Session, q: str = "", city: str = "", transplant: bool | None = None, limit: int = 12) -> list[dict]:
    seed_hospitals(db)
    stmt = select(Hospital)
    q = (q or "").strip()
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Hospital.name).like(like), func.lower(Hospital.short_name).like(like), func.lower(Hospital.city).like(like)))
    if city:
        stmt = stmt.where(func.lower(Hospital.city).like(f"%{city.lower()}%"))
    if transplant is not None:
        stmt = stmt.where(Hospital.transplant == transplant)
    rows = list(db.scalars(stmt.order_by(Hospital.verified.desc(), Hospital.name).limit(min(limit, 50))))
    return [hospital_out(h) for h in rows]


def resolve_hospital(db: Session, name: str, hospital_id: int | None) -> Hospital | None:
    seed_hospitals(db)
    if hospital_id:
        return db.get(Hospital, hospital_id)
    n = (name or "").strip().lower()
    if not n:
        return None
    return db.scalar(select(Hospital).where(or_(func.lower(Hospital.name) == n, func.lower(Hospital.short_name) == n)))


# ---------------------------------------------------------------- the share composer
def _compat_text(bg: str) -> str:
    g = donor_groups_for(bg)
    return ", ".join(g[:-1]) + " or " + g[-1] if len(g) > 1 else g[0]


def compose_message(*, hospital: str, patient_name: str, blood_group: str, contact_name: str = "", contact_phone: str = "", city: str = "",
                    age: int | None = None, relation: str = "family", tone: str = "warm", language: str = "en", include_phone: bool = True,
                    link: str = "", extra: str = "") -> str:
    lang = language if language in D.T else "en"
    tpl = D.T[lang]
    tone = tone if tone in D.TONES else "warm"
    bg = clean_bg(blood_group)
    mine = relation == "myself"
    who = tpl["self"] if mine else patient_name.strip()
    if lang == "en" and not mine and relation not in ("family", "friend"):
        who = f"{who} (my {relation})"
    body = tpl["body"].format(
        who=who, hospital=hospital.strip(), city_part=f", {city.strip()}" if city.strip() else "", bg=bg, compat=_compat_text(bg) if lang == "en" else "/".join(donor_groups_for(bg)),
        age_part=f" (age {age})" if age and lang == "en" else (f" ({age})" if age else ""),
        is_=tpl["self_is"] if mine else tpl["other_is"], needs=tpl["self_needs"] if mine else tpl["other_needs"],
    )
    body = re.sub(r"\s+", " ", body).replace(" ,", ",").strip()
    parts = [tpl["greet"][tone], body]
    if extra.strip():
        parts.append(extra.strip())
    parts.append(tpl["ask"])
    if include_phone and contact_phone.strip():
        parts.append(tpl["contact"].format(name=contact_name.strip() or patient_name.strip(), phone=contact_phone.strip()))
    parts.append(tpl["safe"])
    if link:
        parts.append(link)
    return "\n\n".join(parts)


def facts_preserved(original: str, polished: str, *, patient_name: str, blood_group: str, contact_phone: str) -> bool:
    """A polished rewrite is accepted only if it kept the facts that matter."""
    low = polished.lower()
    digits = re.sub(r"\D", "", polished)
    ok = patient_name.strip().split(" ")[0].lower() in low if patient_name.strip() else True
    ok = ok and clean_bg(blood_group).lower() in low.replace(" ", "")
    ok = ok and (not re.sub(r"\D", "", contact_phone) or re.sub(r"\D", "", contact_phone)[-10:] in digits)
    return ok and len(polished) < 2500


def polish_message(text: str, language: str, tone: str, **facts) -> tuple[str, str]:
    """Ask the LLM router to improve the wording. Falls back to the template text if no provider is ready or facts get lost."""
    from ..buddy.llm_router import AllProvidersFailed, get_router

    router = get_router()
    if not router.any_ready(language):
        return text, "template"
    lang_name = {"en": "English", "ta": "Tamil", "bn": "Bengali", "te": "Telugu"}.get(language, "English")
    sys = (f"You edit appeal messages for organ donation that people forward on WhatsApp. Rewrite the message in clear, warm, respectful {lang_name} "
           f"with a {tone} tone. Keep EVERY fact exactly: patient name, hospital, blood group, phone number, and the sentence that donation is voluntary and never paid. "
           "Do not add facts, prices, promises or medical claims. Keep it under 130 words. Output only the message.")
    try:
        _, msg = router.chat([{"role": "system", "content": sys}, {"role": "user", "content": text}], language=language, max_tokens=500)
        out = (msg.get("content") or "").strip()
    except AllProvidersFailed:
        return text, "template"
    if out and facts_preserved(text, out, **facts):
        return out, "ai"
    return text, "template"


def share_links(text: str, phone: str = "") -> dict:
    enc = quote(text, safe="")
    wa = f"https://wa.me/{normalize_phone(phone)}?text={enc}" if phone else f"https://wa.me/?text={enc}"
    ph = normalize_phone(phone)
    sms = f"sms:+{ph}?body={enc}" if ph else f"sms:?body={enc}"
    return {"whatsapp": wa, "telegram": f"https://t.me/share/url?url=%20&text={enc}", "sms": sms,
            "email": f"mailto:?subject={quote('Kind request: kidney donor needed')}&body={enc}", "chars": len(text)}


# ---------------------------------------------------------------- requests and donor matching
def request_out(r: OrganRequest, public: bool = False, offers: int | None = None) -> dict:
    out = {"id": r.id, "token": r.token, "hospital_id": r.hospital_id, "hospital_name": r.hospital_name, "patient_name": r.patient_name, "blood_group": r.blood_group,
           "organ": r.organ, "age": r.age, "city": r.city, "relation": r.relation, "story": r.story, "urgency": r.urgency, "status": r.status,
           "verified": r.verified, "created_at": r.created_at.isoformat(), "compatible_groups": donor_groups_for(r.blood_group),
           "contact_name": r.contact_name, "contact_phone": mask_phone(r.contact_phone) if public else r.contact_phone}
    if offers is not None:
        out["offers"] = offers
    if public:
        out.pop("id", None)
    return out


def find_matches(db: Session, r: OrganRequest, reveal_phone: bool = False, limit: int = 30) -> list[dict]:
    groups = set(donor_groups_for(r.blood_group))
    rows = db.scalars(select(DonorPledge).where(DonorPledge.consent.is_(True), DonorPledge.kind.in_(("living", "both"))))
    out = []
    for p in rows:
        if "kidney" not in (p.organs or []) or abo(p.blood_group) not in groups:
            continue
        if p.user_id == r.user_id:
            continue
        score = 2 if p.blood_group.rstrip("+-") == abo(r.blood_group) else 1
        if p.city and r.city and p.city.strip().lower() == r.city.strip().lower():
            score += 2
        out.append({"pledge_id": p.id, "name": p.name, "blood_group": p.blood_group, "city": p.city, "score": score, "can_message": p.user_id is not None,
                    "phone": p.phone if reveal_phone else mask_phone(p.phone), "identical_abo": p.blood_group.rstrip("+-") == abo(r.blood_group)})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def pledge_out(p: DonorPledge) -> dict:
    return {"id": p.id, "name": p.name, "blood_group": p.blood_group, "city": p.city, "phone": p.phone, "kind": p.kind, "organs": p.organs,
            "family_informed": p.family_informed, "consent": p.consent, "created_at": p.created_at.isoformat()}


def validate_pledge(kind: str, organs: list[str]):
    organs = [o.lower() for o in organs]
    allowed = D.ORGANS_LIVING if kind == "living" else D.ORGANS_DECEASED
    bad = [o for o in organs if o not in allowed]
    if bad:
        raise HTTPException(422, f"These cannot be pledged as '{kind}' donation: {', '.join(bad)}. Hearts and most organs are donated after death only.")
    if not organs:
        raise HTTPException(422, "Choose at least one organ or tissue")
    return organs


# ---------------------------------------------------------------- FHIR export
def fhir_bundle(db: Session, user: User) -> dict:
    from ..labs import service as labs_service

    labs = labs_service.list_labs(db, user.id)
    pid = f"renalsight-{user.id}"
    entries = [{"fullUrl": f"urn:uuid:{pid}", "resource": {"resourceType": "Patient", "id": pid, "name": [{"text": user.name}],
                                                           "gender": user.sex or "unknown", **({"birthDate": f"{user.birth_year}-01-01"} if user.birth_year else {})}}]
    for r in labs:
        for field, (code, display, unit) in D.LOINC.items():
            v = getattr(r, field)
            if v is None:
                continue
            entries.append({"fullUrl": f"urn:uuid:obs-{r.id}-{field}", "resource": {
                "resourceType": "Observation", "status": "final", "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
                "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]}, "subject": {"reference": f"urn:uuid:{pid}"},
                "effectiveDateTime": r.taken_on.isoformat(), "valueQuantity": {"value": v, "unit": unit, "system": "http://unitsofmeasure.org"}}})
    if user.diabetes:
        entries.append({"resource": {"resourceType": "Condition", "code": {"coding": [{"system": "http://snomed.info/sct", "code": "73211009", "display": "Diabetes mellitus"}]}, "subject": {"reference": f"urn:uuid:{pid}"}}})
    if user.hypertension:
        entries.append({"resource": {"resourceType": "Condition", "code": {"coding": [{"system": "http://snomed.info/sct", "code": "38341003", "display": "Hypertensive disorder"}]}, "subject": {"reference": f"urn:uuid:{pid}"}}})
    return {"resourceType": "Bundle", "type": "collection", "timestamp": datetime.now(timezone.utc).isoformat(), "entry": entries,
            "meta": {"tag": [{"display": "Exported from RenalSight (learning project). Values are patient-entered and unverified."}]}}


# ---------------------------------------------------------------- referral letter
def referral_pdf(db: Session, user: User, to_hospital: str, reason: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from html import escape
    from ..labs import service as labs_service

    snap = labs_service.snapshot(db, user)
    ss = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm, title="Referral summary")
    el = [Paragraph("Patient referral summary", ss["Title"]), Paragraph(f"Date: {date.today().isoformat()}", ss["Normal"]), Spacer(1, 8)]
    el.append(Paragraph(f"To: {escape(to_hospital or 'Treating transplant / nephrology team')}", ss["Normal"]))
    el.append(Paragraph(f"Patient: {escape(user.name)} &nbsp; Age: {snap['age'] or '-'} &nbsp; Sex: {escape(snap['sex'] or '-')}", ss["Normal"]))
    el.append(Paragraph(f"Reason for referral: {escape(reason or 'Opinion on CKD care / transplant evaluation')}", ss["Normal"]))
    el.append(Spacer(1, 10))
    rows = [["Measure", "Latest value"], ["eGFR (CKD-EPI 2021)", snap["egfr"]], ["KDIGO stage", snap["g_stage"]], ["Albuminuria category", snap["a_category"]],
            ["Creatinine (mg/dL)", snap["scr"]], ["Urine ACR (mg/g)", snap["acr"]], ["Potassium (mmol/L)", snap["potassium"]], ["Haemoglobin (g/dL)", snap["hgb"]],
            ["HbA1c (%)", snap["hba1c"]], ["Blood pressure", f"{snap['sbp']}/{snap['dbp']}" if snap["sbp"] else None],
            ["Diabetes / Hypertension", f"{'yes' if snap['diabetes'] else 'no'} / {'yes' if snap['hypertension'] else 'no'}"], ["As of", snap["as_of"]]]
    t = Table([[str(a), "-" if b is None else str(b)] for a, b in rows], colWidths=[7 * cm, 8 * cm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0"))]))
    el += [t, Spacer(1, 14), Paragraph("Generated by RenalSight from patient-entered data. It is decision support, not a diagnosis; the receiving clinician should confirm all values.", ss["Italic"])]
    doc.build(el)
    return buf.getvalue()
