"""Transplant hub API: hospital directory, organ requests (with one-click share), donor registry, journey, dialysis, emergency card, exports."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.events import audit, notify
from ...core.security import get_current_user, require_roles
from ...models import DialysisSession, DonorOffer, DonorPledge, EmergencyCard, Hospital, JourneyStep, OrganRequest, User
from ..labs import service as labs_service
from . import data as D
from . import service as S

router = APIRouter(tags=["transplant"])
Staff = ("doctor", "admin")


def _owner_or_staff(r: OrganRequest | None, user: User) -> OrganRequest:
    if r is None or (r.user_id != user.id and user.role not in Staff):
        raise HTTPException(404, "Request not found")
    return r


@router.get("/transplant/meta")
def meta():
    return {"blood_groups": D.BLOOD_GROUPS, "tones": D.TONES, "relations": D.RELATIONS, "languages": list(D.T),
            "organs_living": sorted(D.ORGANS_LIVING), "organs_deceased": sorted(D.ORGANS_DECEASED),
            "journey": [{"key": k, "title": t, "body": b} for k, t, b in D.JOURNEY],
            "safety": ["Organs are never bought or sold. Anyone asking for money is a scam: report it to the hospital and the police.",
                       "Only the hospital's transplant team and authorisation committee can approve a donor.",
                       "Hearts and most organs are donated after death through the hospital waitlist, not through public appeals."]}


# ---------------------------------------------------------------- hospitals
@router.get("/hospitals")
def hospitals(q: str = "", city: str = "", transplant: bool | None = None, limit: int = 12, db: Session = Depends(get_db)):
    return S.search_hospitals(db, q, city, transplant, limit)


class HospitalIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    short_name: str = Field(default="", max_length=40)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=80)
    country: str = Field(default="India", max_length=60)
    transplant: bool = False
    phone: str = Field(default="", max_length=40)


@router.post("/hospitals")
def add_hospital(body: HospitalIn, user: User = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)):
    h = Hospital(**body.model_dump(), verified=user.role == "admin")
    db.add(h)
    db.flush()
    audit(db, user, "hospital.add", "hospital", h.id, name=h.name)
    db.commit()
    return S.hospital_out(h)


@router.post("/hospitals/{hid}/verify")
def verify_hospital(hid: int, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    h = db.get(Hospital, hid)
    if h is None:
        raise HTTPException(404, "Hospital not found")
    h.verified = True
    audit(db, user, "hospital.verify", "hospital", h.id)
    db.commit()
    return S.hospital_out(h)


class SeatsIn(BaseModel):
    shift: Literal["morning", "afternoon", "evening", "night"]
    total: int = Field(ge=0, le=500)
    free: int = Field(ge=0, le=500)


@router.get("/dialysis/seats")
def seat_board(city: str = "", db: Session = Depends(get_db)):
    S.seed_hospitals(db)
    out = []
    for h in db.scalars(select(Hospital).where(Hospital.seats != {})):
        if city and city.lower() not in h.city.lower():
            continue
        free = sum(v.get("free", 0) for v in h.seats.values())
        out.append({**S.hospital_out(h), "seats": h.seats, "free_total": free})
    out.sort(key=lambda x: -x["free_total"])
    return {"hospitals": out, "note": "Seat numbers are entered by hospital staff and may be out of date. Always phone the centre."}


@router.put("/hospitals/{hid}/seats")
def set_seats(hid: int, body: SeatsIn, user: User = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)):
    h = db.get(Hospital, hid)
    if h is None:
        raise HTTPException(404, "Hospital not found")
    if body.free > body.total:
        raise HTTPException(422, "Free seats cannot be more than total seats")
    h.seats = {**(h.seats or {}), body.shift: {"total": body.total, "free": body.free}}
    audit(db, user, "hospital.seats", "hospital", h.id, shift=body.shift, free=body.free)
    db.commit()
    return S.hospital_out(h) | {"seats": h.seats}


# ---------------------------------------------------------------- share composer
class ComposeIn(BaseModel):
    hospital: str = Field(min_length=2, max_length=200)
    patient_name: str = Field(min_length=1, max_length=120)
    blood_group: str
    contact_name: str = Field(default="", max_length=120)
    contact_phone: str = Field(default="", max_length=30)
    city: str = Field(default="", max_length=80)
    age: int | None = Field(default=None, ge=0, le=120)
    relation: str = "family"
    tone: Literal["warm", "formal", "urgent"] = "warm"
    language: Literal["en", "ta", "bn", "te"] = "en"
    include_phone: bool = True
    extra: str = Field(default="", max_length=300)
    link: str = Field(default="", max_length=300)
    polish: bool = False
    send_to: str = Field(default="", max_length=30)


def compose_payload(body: ComposeIn) -> dict:
    kw = dict(hospital=body.hospital, patient_name=body.patient_name, blood_group=body.blood_group, contact_name=body.contact_name, contact_phone=body.contact_phone,
              city=body.city, age=body.age, relation=body.relation, tone=body.tone, language=body.language, include_phone=body.include_phone, link=body.link, extra=body.extra)
    text, by = S.compose_message(**kw), "template"
    if body.polish:
        text, by = S.polish_message(text, body.language, body.tone, patient_name=body.patient_name, blood_group=body.blood_group, contact_phone=body.contact_phone if body.include_phone else "")
    return {"text": text, "written_by": by, "language": body.language, "tone": body.tone, "links": S.share_links(text, body.send_to),
            "compatible_groups": S.donor_groups_for(body.blood_group),
            "tips": ["Send it to groups and people you know. Ask them to forward it.", "Never share bank details; no one should pay for an organ.", "Check the hospital's name and your phone number before sending."]}


@router.post("/share/compose")
def compose(body: ComposeIn, user: User = Depends(get_current_user)):
    return compose_payload(body)


# ---------------------------------------------------------------- organ requests
class RequestIn(BaseModel):
    hospital_name: str = Field(min_length=2, max_length=200)
    hospital_id: int | None = None
    patient_name: str = Field(min_length=1, max_length=120)
    blood_group: str
    organ: Literal["kidney", "liver"] = "kidney"
    age: int | None = Field(default=None, ge=0, le=120)
    city: str = Field(default="", max_length=80)
    contact_name: str = Field(default="", max_length=120)
    contact_phone: str = Field(min_length=7, max_length=30)
    relation: str = "family"
    story: str = Field(default="", max_length=1200)
    urgency: Literal["routine", "soon", "urgent"] = "routine"


def create_request(db: Session, user: User, body: RequestIn) -> OrganRequest:
    h = S.resolve_hospital(db, body.hospital_name, body.hospital_id)
    r = OrganRequest(token=S.new_token(), user_id=user.id, hospital_id=h.id if h else None, hospital_name=h.name if h else body.hospital_name.strip(),
                     patient_name=body.patient_name.strip(), blood_group=S.clean_bg(body.blood_group), organ=body.organ, age=body.age, city=body.city.strip() or (h.city if h else ""),
                     contact_name=body.contact_name.strip() or user.name, contact_phone=body.contact_phone.strip(), relation=body.relation, story=body.story.strip(), urgency=body.urgency)
    db.add(r)
    db.flush()
    audit(db, user, "request.create", "organ_request", r.id, organ=r.organ)
    db.commit()
    return r


@router.post("/requests")
def post_request(body: RequestIn, user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    r = create_request(db, user, body)
    return S.request_out(r, offers=0)


@router.get("/requests")
def my_requests(all: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(OrganRequest).order_by(OrganRequest.id.desc())
    if not (all and user.role in Staff):
        q = q.where(OrganRequest.user_id == user.id)
    out = []
    for r in db.scalars(q.limit(100)):
        n = db.scalar(select(func.count()).select_from(DonorOffer).where(DonorOffer.request_id == r.id)) or 0
        out.append(S.request_out(r, offers=n))
    return out


@router.get("/requests/{rid}")
def get_request(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _owner_or_staff(db.get(OrganRequest, rid), user)
    offers = [{"id": o.id, "name": o.name, "blood_group": o.blood_group, "phone": o.phone, "note": o.note, "compatible": o.compatible, "status": o.status, "created_at": o.created_at.isoformat()}
              for o in db.scalars(select(DonorOffer).where(DonorOffer.request_id == r.id).order_by(DonorOffer.id.desc()))]
    return S.request_out(r, offers=len(offers)) | {"offer_list": offers, "matches": S.find_matches(db, r, reveal_phone=user.role in Staff)}


class StatusIn(BaseModel):
    status: Literal["open", "matched", "fulfilled", "closed"]


@router.patch("/requests/{rid}/status")
def set_status(rid: int, body: StatusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _owner_or_staff(db.get(OrganRequest, rid), user)
    r.status = body.status
    audit(db, user, "request.status", "organ_request", r.id, status=body.status)
    db.commit()
    return S.request_out(r)


@router.post("/requests/{rid}/verify")
def verify_request(rid: int, user: User = Depends(require_roles("doctor", "admin")), db: Session = Depends(get_db)):
    r = db.get(OrganRequest, rid)
    if r is None:
        raise HTTPException(404, "Request not found")
    r.verified = True
    notify(db, r.user_id, "request_verified", "Your request was verified", f"{user.name} confirmed your request for {r.patient_name}.", request_id=r.id)
    audit(db, user, "request.verify", "organ_request", r.id)
    db.commit()
    return S.request_out(r)


@router.post("/requests/{rid}/compose")
def compose_for_request(rid: int, body: dict | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ready-made share message for a saved request (public link included)."""
    r = _owner_or_staff(db.get(OrganRequest, rid), user)
    b = body or {}
    c = ComposeIn(hospital=r.hospital_name, patient_name=r.patient_name, blood_group=r.blood_group, contact_name=r.contact_name, contact_phone=r.contact_phone, city=r.city, age=r.age,
                  relation=r.relation, tone=b.get("tone", "urgent" if r.urgency == "urgent" else "warm"), language=b.get("language", user.language if user.language in D.T else "en"),
                  include_phone=b.get("include_phone", True), polish=bool(b.get("polish", False)), send_to=b.get("send_to", ""), link=b.get("link", ""))
    return compose_payload(c)


@router.post("/requests/{rid}/contact-donor/{pid}")
def contact_donor(rid: int, pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _owner_or_staff(db.get(OrganRequest, rid), user)
    p = db.get(DonorPledge, pid)
    if p is None or p.user_id is None:
        raise HTTPException(404, "This donor cannot be messaged in the app. Ask a coordinator.")
    notify(db, p.user_id, "donor_contact", "A patient's family asked about donating", f"{r.patient_name} ({r.blood_group}) at {r.hospital_name}. Contact {r.contact_name}: {r.contact_phone}. You are free to say no.", request_id=r.id)
    audit(db, user, "request.contact_donor", "organ_request", r.id, pledge=p.id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- public pages
@router.get("/public/requests/{token}")
def public_request(token: str, db: Session = Depends(get_db)):
    r = db.scalar(select(OrganRequest).where(OrganRequest.token == token))
    if r is None or r.status in ("closed",):
        raise HTTPException(404, "This request is no longer active")
    return S.request_out(r, public=True) | {"scam_warning": "Never send money. Organ donation is voluntary and is arranged only through the hospital's transplant team."}


class OfferIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    blood_group: str = ""
    phone: str = Field(min_length=7, max_length=30)
    note: str = Field(default="", max_length=400)
    consent: bool


@router.post("/public/requests/{token}/offers")
def public_offer(token: str, body: OfferIn, request: Request, db: Session = Depends(get_db)):
    S.public_rate_limit(f"offer:{request.client.host if request.client else 'x'}")
    r = db.scalar(select(OrganRequest).where(OrganRequest.token == token))
    if r is None or r.status != "open":
        raise HTTPException(404, "This request is no longer open")
    if not body.consent:
        raise HTTPException(422, "Please confirm that you offer this freely, without payment")
    bg = S.clean_bg(body.blood_group) if body.blood_group.strip() else ""
    o = DonorOffer(request_id=r.id, name=body.name.strip(), blood_group=bg, phone=body.phone.strip(), note=body.note.strip(), compatible=bool(bg and S.is_compatible(r.blood_group, bg)))
    db.add(o)
    notify(db, r.user_id, "donor_offer", "Someone offered to be tested as a donor", f"{o.name} ({bg or 'blood group unknown'}). Open the request to see the contact. The hospital must still evaluate every donor.", request_id=r.id)
    db.commit()
    return {"ok": True, "message": "Thank you. The family has been told. The hospital will check your health and blood group before anything else happens.", "compatible_hint": o.compatible}


@router.patch("/offers/{oid}")
def update_offer(oid: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(DonorOffer, oid)
    if o is None:
        raise HTTPException(404, "Offer not found")
    _owner_or_staff(db.get(OrganRequest, o.request_id), user)
    if body.get("status") not in ("new", "contacted", "declined", "accepted"):
        raise HTTPException(422, "Bad status")
    o.status = body["status"]
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- donor registry
class PledgeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    blood_group: str
    city: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=30)
    kind: Literal["living", "deceased", "both"] = "deceased"
    organs: list[str] = Field(default_factory=list)
    family_informed: bool = False
    consent: bool


@router.post("/donors/pledge")
def pledge(body: PledgeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(422, "Consent is required. You can withdraw it at any time.")
    organs = S.validate_pledge("living" if body.kind == "living" else "deceased", body.organs)
    if body.kind == "both":
        S.validate_pledge("living", [o for o in organs if o in D.ORGANS_LIVING] or ["kidney"])
    p = db.scalar(select(DonorPledge).where(DonorPledge.user_id == user.id)) or DonorPledge(user_id=user.id, name=body.name, blood_group="", consent=True)
    p.name, p.blood_group, p.city, p.phone, p.kind, p.organs = body.name.strip(), S.clean_bg(body.blood_group), body.city.strip(), body.phone.strip(), body.kind, organs
    p.family_informed, p.consent = body.family_informed, True
    db.add(p)
    audit(db, user, "donor.pledge", "donor_pledge", p.id, kind=p.kind, organs=organs)
    db.commit()
    return S.pledge_out(p) | {"note": "Thank you. Tell your family about your wish: they are asked at the time. Keep a donor card with you."}


@router.get("/donors/mine")
def my_pledge(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(DonorPledge).where(DonorPledge.user_id == user.id))
    return None if p is None else S.pledge_out(p)


@router.delete("/donors/mine")
def withdraw(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(DonorPledge).where(DonorPledge.user_id == user.id))
    audit(db, user, "donor.withdraw", "donor_pledge")
    db.commit()
    return {"ok": True}


@router.get("/donors/stats")
def donor_stats(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(DonorPledge).where(DonorPledge.consent.is_(True))))
    by_organ: dict[str, int] = {}
    by_bg: dict[str, int] = {}
    for p in rows:
        by_bg[p.blood_group] = by_bg.get(p.blood_group, 0) + 1
        for o in p.organs or []:
            by_organ[o] = by_organ.get(o, 0) + 1
    open_n = db.scalar(select(func.count()).select_from(OrganRequest).where(OrganRequest.status == "open")) or 0
    return {"pledges": len(rows), "by_organ": by_organ, "by_blood_group": by_bg, "open_requests": open_n}


@router.get("/donors/compat")
def compat(blood_group: str):
    return {"recipient": S.clean_bg(blood_group), "donor_groups": S.donor_groups_for(blood_group),
            "note": "Kidney matching needs a compatible ABO group; Rh (+/-) does not matter. The hospital still does tissue (HLA) typing and a crossmatch."}


# ---------------------------------------------------------------- transplant journey
@router.get("/journey")
def journey(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    done = {j.step_key: j for j in db.scalars(select(JourneyStep).where(JourneyStep.user_id == user.id))}
    steps = [{"key": k, "title": t, "body": b, "done": bool(done.get(k) and done[k].done), "note": done[k].note if k in done else "",
              "done_at": done[k].done_at.isoformat() if k in done and done[k].done_at else None} for k, t, b in D.JOURNEY]
    n = sum(1 for s in steps if s["done"])
    nxt = next((s["key"] for s in steps if not s["done"]), None)
    return {"steps": steps, "progress": round(100 * n / len(steps)), "next": nxt}


class StepIn(BaseModel):
    done: bool
    note: str = Field(default="", max_length=300)


@router.put("/journey/{key}")
def set_step(key: str, body: StepIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    if key not in D.JOURNEY_KEYS:
        raise HTTPException(404, "Unknown step")
    j = db.scalar(select(JourneyStep).where(JourneyStep.user_id == user.id, JourneyStep.step_key == key)) or JourneyStep(user_id=user.id, step_key=key)
    j.done, j.note = body.done, body.note
    j.done_at = datetime.now(timezone.utc) if body.done else None
    db.add(j)
    db.commit()
    return journey(user, db)


# ---------------------------------------------------------------- dialysis log
class SessionIn(BaseModel):
    on_date: date
    centre: str = Field(default="", max_length=160)
    pre_weight: float | None = Field(default=None, ge=10, le=300)
    post_weight: float | None = Field(default=None, ge=10, le=300)
    pre_bp: str = Field(default="", max_length=12)
    post_bp: str = Field(default="", max_length=12)
    hours: float | None = Field(default=None, ge=0, le=12)
    notes: str = Field(default="", max_length=400)


def _session_out(s: DialysisSession) -> dict:
    return {"id": s.id, "on_date": s.on_date.isoformat(), "centre": s.centre, "pre_weight": s.pre_weight, "post_weight": s.post_weight, "pre_bp": s.pre_bp, "post_bp": s.post_bp,
            "hours": s.hours, "notes": s.notes, "removed_kg": None if s.pre_weight is None or s.post_weight is None else round(s.pre_weight - s.post_weight, 1)}


@router.post("/dialysis/sessions")
def add_session(body: SessionIn, user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    s = DialysisSession(user_id=user.id, **body.model_dump())
    db.add(s)
    db.commit()
    return _session_out(s)


@router.get("/dialysis/sessions")
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(DialysisSession).where(DialysisSession.user_id == user.id).order_by(DialysisSession.on_date.desc()).limit(60)))
    out = [_session_out(r) for r in rows]
    gains = []
    for newer, older in zip(rows, rows[1:]):                       # weight gained between sessions = pre-weight now minus post-weight last time
        if newer.pre_weight is not None and older.post_weight is not None:
            gains.append(round(newer.pre_weight - older.post_weight, 1))
    warn = bool(gains and gains[0] >= 3)
    return {"sessions": out, "interdialytic_gain_kg": gains[:10], "warning": "Weight gain between sessions is high (3 kg or more). Reduce fluids and salt and tell your dialysis team." if warn else None}


@router.delete("/dialysis/sessions/{sid}")
def del_session(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(DialysisSession, sid)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- emergency card
class CardIn(BaseModel):
    blood_group: str = ""
    allergies: str = Field(default="", max_length=300)
    contact_name: str = Field(default="", max_length=120)
    contact_phone: str = Field(default="", max_length=30)
    public: bool = True


WARNINGS = ["Kidney disease: avoid NSAID pain-killers (ibuprofen, diclofenac) and check every drug dose for kidney function.",
            "Avoid IV contrast, potassium supplements and magnesium/phosphate enemas unless a doctor decides.",
            "Do not take blood pressure on or put cannulas in a dialysis-fistula arm."]


def _card_out(c: EmergencyCard, user: User, db: Session, public: bool = False) -> dict:
    snap = labs_service.snapshot(db, user)
    out = {"token": c.token, "name": user.name, "age": snap["age"], "blood_group": c.blood_group, "allergies": c.allergies, "stage": snap["g_stage"], "egfr": snap["egfr"],
           "as_of": snap["as_of"], "diabetes": user.diabetes, "hypertension": user.hypertension, "contact_name": c.contact_name,
           "contact_phone": c.contact_phone, "public": c.public, "warnings": WARNINGS}
    return out


@router.get("/emergency-card")
def get_card(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.scalar(select(EmergencyCard).where(EmergencyCard.user_id == user.id))
    if c is None:
        c = EmergencyCard(user_id=user.id, token=S.new_token())
        db.add(c)
        db.commit()
    return _card_out(c, user, db)


@router.put("/emergency-card")
def put_card(body: CardIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.scalar(select(EmergencyCard).where(EmergencyCard.user_id == user.id)) or EmergencyCard(user_id=user.id, token=S.new_token())
    c.blood_group = S.clean_bg(body.blood_group) if body.blood_group.strip() else ""
    c.allergies, c.contact_name, c.contact_phone, c.public = body.allergies.strip(), body.contact_name.strip(), body.contact_phone.strip(), body.public
    db.add(c)
    db.commit()
    return _card_out(c, user, db)


@router.get("/public/emergency/{token}")
def public_card(token: str, db: Session = Depends(get_db)):
    c = db.scalar(select(EmergencyCard).where(EmergencyCard.token == token))
    if c is None or not c.public:
        raise HTTPException(404, "Card not found")
    return _card_out(c, db.get(User, c.user_id), db, public=True)


# ---------------------------------------------------------------- exports
def _target(user: User, patient_id: int | None, db: Session) -> User:
    if patient_id is None or patient_id == user.id:
        return user
    p = db.get(User, patient_id)
    if user.role == "doctor" and p is not None and p.doctor_id == user.id:
        return p
    raise HTTPException(403, "You can only export your own record or your linked patients")


@router.get("/export/fhir")
def export_fhir(patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _target(user, patient_id, db)
    audit(db, user, "export.fhir", "user", target.id)
    db.commit()
    return Response(content=__import__("json").dumps(S.fhir_bundle(db, target), indent=1), media_type="application/fhir+json",
                    headers={"Content-Disposition": 'attachment; filename="renalsight-fhir.json"'})


@router.get("/export/referral.pdf")
def referral(to: str = "", reason: str = "", patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _target(user, patient_id, db)
    audit(db, user, "export.referral", "user", target.id)
    db.commit()
    return Response(content=S.referral_pdf(db, target, to[:200], reason[:300]), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="referral.pdf"'})
