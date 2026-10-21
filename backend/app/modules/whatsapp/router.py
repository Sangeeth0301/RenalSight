"""WhatsApp bridge API (local only).

The website's "Send on WhatsApp" button posts the selected recipients and the message here. A small Node script (bridge/wa_bridge.mjs)
then drives YOUR OWN WhatsApp Web session (linked once by scanning a QR code) and sends to exactly those people, without any
"who do you want to send to" step. Safeguards: signed-in patients and doctors only, at most 8 recipients and 6 sends an hour,
text length limit, every send is written to the audit log, and nothing is sent unless the button is clicked."""
import json
import os
import shutil
import subprocess
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ...core.db import get_db
from ...core.events import audit
from ...core.security import require_roles
from ...models import User

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
BRIDGE = Path(__file__).resolve().parents[4] / "bridge"
JOBS = BRIDGE / "jobs"
_sends: dict[int, deque] = defaultdict(deque)
_login_proc: subprocess.Popen | None = None


ENABLED = os.getenv("WHATSAPP_ENABLED", "1") != "0"      # off in a hosted copy: the bridge needs your own computer, Chrome and phone


def _node() -> str:
    if not ENABLED:
        raise HTTPException(403, "The WhatsApp bridge is turned off on this server. Use the local app for one-click sending.")
    n = shutil.which("node")
    if not n:
        raise HTTPException(503, "Node.js is needed for the WhatsApp bridge. Install Node 18+ and try again.")
    return n


def _state() -> dict:
    try:
        return json.loads((BRIDGE / "state.json").read_text())
    except (OSError, ValueError):
        return {}


# Strictly these chats and nobody else. Names must match the WhatsApp chat title exactly. Override with WHATSAPP_ALLOWED="Name one;Name two".
ALLOWED = [x.strip() for x in (os.getenv("WHATSAPP_ALLOWED") or "Sem 5 Project;Sandeep;Sangeeth (You);Jagan").split(";") if x.strip()]


class Recipient(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(default="", max_length=30)


class SendIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    recipients: list[Recipient] = Field(min_length=1, max_length=8)


@router.get("/allowed")
def allowed_list(user: User = Depends(require_roles("patient", "caregiver", "doctor"))):
    return {"allowed": ALLOWED}


@router.get("/status")
def status(user: User = Depends(require_roles("patient", "caregiver", "doctor"))):
    st = _state()
    try:
        import httpx

        chrome = httpx.get("http://127.0.0.1:9222/json/version", timeout=1.5).status_code == 200
    except Exception:
        chrome = False
    login_running = _login_proc is not None and _login_proc.poll() is None
    return {"linked": bool(st.get("linked")) and chrome, "chrome_open": chrome, "checked_at": st.get("at"), "login_window_open": login_running, "node": ENABLED and bool(shutil.which("node")),
            "note": "Link once: a Chrome window opens on this computer with WhatsApp Web. Scan its QR code with your phone (WhatsApp > Linked devices), then keep that Chrome window open (you can minimise it)."}


@router.post("/login")
def login(user: User = Depends(require_roles("patient", "caregiver", "doctor"))):
    global _login_proc
    if _login_proc is not None and _login_proc.poll() is None:
        return {"started": False, "message": "The WhatsApp window is already open on your computer."}
    _login_proc = subprocess.Popen([_node(), str(BRIDGE / "wa_bridge.mjs"), "login"], cwd=str(BRIDGE))
    return {"started": True, "message": "A Chrome window with WhatsApp Web opened on your computer. Scan its QR code with your phone and keep that window open."}


@router.post("/send")
def send(body: SendIn, user: User = Depends(require_roles("patient", "caregiver", "doctor")), db=Depends(get_db)):
    allowed = {a.lower(): a for a in ALLOWED}
    names = []
    for r in body.recipients:
        canon = allowed.get(r.name.strip().lower())
        if canon is None:
            raise HTTPException(403, f'"{r.name}" is not on the allowed list ({", ".join(ALLOWED)}). Nothing was sent.')
        if canon not in names:
            names.append(canon)
    q, now = _sends[user.id], time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= 6:
        raise HTTPException(429, "Limit reached: 6 sends per hour, to keep your WhatsApp account safe.")
    if not _state().get("linked"):
        raise HTTPException(409, "WhatsApp is not linked yet. Click 'Link WhatsApp' first.")
    q.append(now)
    JOBS.mkdir(exist_ok=True)
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "text": body.text, "recipients": [{"name": n} for n in names], "out": str(JOBS / f"{jid}.result.json")}
    (JOBS / f"{jid}.job.json").write_text(json.dumps(job, ensure_ascii=False))
    subprocess.Popen([_node(), str(BRIDGE / "wa_bridge.mjs"), "send", str(JOBS / f"{jid}.job.json")], cwd=str(BRIDGE))
    audit(db, user, "whatsapp.send", "whatsapp", None, recipients=names, chars=len(body.text))
    db.commit()
    return {"job_id": jid, "recipients": names}


@router.get("/jobs/{jid}")
def job(jid: str, user: User = Depends(require_roles("patient", "caregiver", "doctor"))):
    if not jid.isalnum() or len(jid) > 20:
        raise HTTPException(404, "Unknown job")
    f = JOBS / f"{jid}.result.json"
    if not f.exists():
        return {"id": jid, "done": False, "results": []}
    try:
        return json.loads(f.read_text())
    except ValueError:
        return {"id": jid, "done": False, "results": []}


@router.get("/qr")
def qr(user: User = Depends(require_roles("patient", "caregiver", "doctor"))):
    """The live WhatsApp link QR (refreshed every few seconds while the link window is waiting)."""
    f = BRIDGE / "qr.png"
    if not f.exists() or time.time() - f.stat().st_mtime > 20:
        raise HTTPException(404, "No QR yet")
    return Response(content=f.read_bytes(), media_type="image/png", headers={"Cache-Control": "no-store"})
