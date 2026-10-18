from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.db import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="patient")        # patient | doctor | caregiver | admin
    language: Mapped[str] = mapped_column(String(5), default="en")          # en | ta | bn | te
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)      # male | female
    diabetes: Mapped[bool] = mapped_column(Boolean, default=False)
    hypertension: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    doctor_code: Mapped[str | None] = mapped_column(String(8), unique=True, nullable=True)   # doctors share this so patients can link
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)      # a patient's linked doctor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    labs: Mapped[list["LabRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def age(self, on: date | None = None):
        if self.birth_year is None:
            return None
        return (on or date.today()).year - self.birth_year


class LabRecord(Base):
    __tablename__ = "lab_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    taken_on: Mapped[date] = mapped_column(Date)
    scr: Mapped[float | None] = mapped_column(Float, nullable=True)         # serum creatinine mg/dL
    acr: Mapped[float | None] = mapped_column(Float, nullable=True)         # urine albumin/creatinine mg/g
    sbp: Mapped[float | None] = mapped_column(Float, nullable=True)
    dbp: Mapped[float | None] = mapped_column(Float, nullable=True)
    hba1c: Mapped[float | None] = mapped_column(Float, nullable=True)
    hgb: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)
    bun: Mapped[float | None] = mapped_column(Float, nullable=True)
    egfr: Mapped[float | None] = mapped_column(Float, nullable=True)        # computed on save
    g_stage: Mapped[str | None] = mapped_column(String(4), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")       # manual | upload | assisted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped[User] = relationship(back_populates="labs")


class Prescription(Base):
    __tablename__ = "prescriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(12), default="draft")       # draft | submitted | signed | rejected
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)             # labs / profile at creation
    care_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    safety: Mapped[dict] = mapped_column(JSON, default=dict)               # latest safety-check result
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.id")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    drug_key: Mapped[str] = mapped_column(String(40))
    drug_name: Mapped[str] = mapped_column(String(80))
    dose_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    times_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_by_system: Mapped[bool] = mapped_column(Boolean, default=False)
    prescription: Mapped[Prescription] = relationship(back_populates="items")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    agent: Mapped[str] = mapped_column(String(20), default="buddy")
    role: Mapped[str] = mapped_column(String(12))                          # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)                 # provider, tool calls
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Thread(Base):
    """A conversation: 'direct' (patient-doctor) or 'room' (Consult Room joined with a 6-digit code)."""
    __tablename__ = "threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(120), default="")
    code: Mapped[str | None] = mapped_column(String(6), nullable=True, index=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    members: Mapped[list["ThreadMember"]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class ThreadMember(Base):
    __tablename__ = "thread_members"
    __table_args__ = (UniqueConstraint("thread_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    last_read_id: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    thread: Mapped[Thread] = relationship(back_populates="members")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(12), default="text")          # text | attachment | system
    body: Mapped[str] = mapped_column(Text, default="")
    attachment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RoomTask(Base):
    __tablename__ = "room_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RegionCapacity(Base):
    """Real capacity numbers (entered by an admin from a verified source) used to compute the care gap."""
    __tablename__ = "region_capacity"
    __table_args__ = (UniqueConstraint("region", "year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(10), index=True)
    year: Mapped[int] = mapped_column(Integer)
    dialysis_stations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nephrologists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(300), default="")
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RitualLog(Base):
    """Daily habit entries: medicines taken, water, low-salt meal, BP reading, symptoms."""
    __tablename__ = "ritual_logs"
    __table_args__ = (UniqueConstraint("user_id", "day", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(30))          # med_morning | med_noon | med_night | water | low_salt | bp | symptoms
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    reports: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PostReport(Base):
    __tablename__ = "post_reports"
    __table_args__ = (UniqueConstraint("post_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("channel_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(200), default="")


class CareProvider(Base):
    """Specialists, dialysis centres, labs, pharmacies. Entries marked is_demo are clearly fictional samples."""
    __tablename__ = "care_providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))          # nephrologist | dialysis | lab | pharmacy
    name: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(10), default="IND")
    city: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    languages: Mapped[str] = mapped_column(String(40), default="en")     # comma separated codes
    services: Mapped[str] = mapped_column(String(200), default="")
    min_stage: Mapped[int] = mapped_column(Integer, default=1)           # most useful from this CKD stage up
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("care_providers.id"), nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(12), default="requested")   # requested | confirmed | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentTask(Base):
    """Something an AI helper did or suggests. Medical or outward-facing actions need a human to approve."""
    __tablename__ = "agent_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)       # who sees it / approves it
    agent: Mapped[str] = mapped_column(String(20))                                  # scheduler | buddy | copilot | outreach
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="pending")              # pending | approved | rejected | done
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ------------------------------------------------------------------ transplant hub (hospitals, requests, donors, journey, dialysis)
class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    short_name: Mapped[str] = mapped_column(String(40), default="")         # e.g. AIIMS, KMCH
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(60), default="India")
    kind: Mapped[str] = mapped_column(String(20), default="hospital")       # hospital | transplant_centre | dialysis_centre
    transplant: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str] = mapped_column(String(40), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)          # directory names are NOT verified until an admin confirms
    seats: Mapped[dict] = mapped_column(JSON, default=dict)                 # dialysis seats: {"morning": {"total": 10, "free": 2}, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OrganRequest(Base):
    __tablename__ = "organ_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    hospital_name: Mapped[str] = mapped_column(String(200))
    patient_name: Mapped[str] = mapped_column(String(120))
    blood_group: Mapped[str] = mapped_column(String(4))
    organ: Mapped[str] = mapped_column(String(20), default="kidney")        # kidney | liver (appeal); hearts etc. only via hospital waitlist
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(80), default="")
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    contact_phone: Mapped[str] = mapped_column(String(30), default="")
    relation: Mapped[str] = mapped_column(String(40), default="family")
    story: Mapped[str] = mapped_column(Text, default="")
    urgency: Mapped[str] = mapped_column(String(10), default="routine")     # routine | soon | urgent
    status: Mapped[str] = mapped_column(String(12), default="open")         # open | matched | fulfilled | closed
    verified: Mapped[bool] = mapped_column(Boolean, default=False)          # confirmed by a doctor or admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DonorPledge(Base):
    __tablename__ = "donor_pledges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    blood_group: Mapped[str] = mapped_column(String(4))
    city: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    kind: Mapped[str] = mapped_column(String(12), default="deceased")       # living | deceased | both
    organs: Mapped[list] = mapped_column(JSON, default=list)               # kidney, heart, liver, cornea, ...
    family_informed: Mapped[bool] = mapped_column(Boolean, default=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DonorOffer(Base):
    __tablename__ = "donor_offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("organ_requests.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    blood_group: Mapped[str] = mapped_column(String(4), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    compatible: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="new")          # new | contacted | declined | accepted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class JourneyStep(Base):
    __tablename__ = "journey_steps"
    __table_args__ = (UniqueConstraint("user_id", "step_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    step_key: Mapped[str] = mapped_column(String(40))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(300), default="")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DialysisSession(Base):
    __tablename__ = "dialysis_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    on_date: Mapped[date] = mapped_column(Date)
    centre: Mapped[str] = mapped_column(String(160), default="")
    pre_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_bp: Mapped[str] = mapped_column(String(12), default="")
    post_bp: Mapped[str] = mapped_column(String(12), default="")
    hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(String(400), default="")


class EmergencyCard(Base):
    __tablename__ = "emergency_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    token: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    blood_group: Mapped[str] = mapped_column(String(4), default="")
    allergies: Mapped[str] = mapped_column(String(300), default="")
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    contact_phone: Mapped[str] = mapped_column(String(30), default="")
    public: Mapped[bool] = mapped_column(Boolean, default=True)


class TranslationCache(Base):
    __tablename__ = "translation_cache"
    __table_args__ = (UniqueConstraint("lang", "digest"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(5))
    digest: Mapped[str] = mapped_column(String(64), index=True)
    translated: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
