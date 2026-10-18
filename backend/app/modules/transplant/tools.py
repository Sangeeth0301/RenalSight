"""Transplant tools: the same functions power the REST buttons, the AI helpers and the MCP server."""
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from ...models import OrganRequest
from ...tools import Ctx, tool
from . import service as S
from .router import ComposeIn, RequestIn, compose_payload, create_request


class SearchIn(BaseModel):
    query: str = Field(default="", description="hospital name, short name (AIIMS, KMCH) or city")
    transplant_only: bool = False


@tool("search_hospitals", "Search the hospital directory by name, short name (AIIMS, KMCH) or city. Names only, not verified unless marked.", SearchIn, module="transplant")
def search_hospitals(ctx: Ctx, a: SearchIn):
    return {"hospitals": S.search_hospitals(ctx.db, a.query, "", True if a.transplant_only else None, 10)}


@tool("compose_request_message", "Write a polished appeal message (English, Tamil, Bengali or Telugu) asking friends and family to help find a kidney donor, with ready WhatsApp/Telegram/SMS/email links. Does NOT send anything.",
      ComposeIn, module="transplant")
def compose_request_message(ctx: Ctx, a: ComposeIn):
    return compose_payload(a)


class WaIn(BaseModel):
    text: str = Field(min_length=3, max_length=3000)
    phone: str = Field(default="", description="optional recipient number; empty lets the user pick a contact or group inside WhatsApp")


@tool("whatsapp_link", "Build a one-click WhatsApp link for a message. The person opens it and taps send, so nothing is sent automatically.", WaIn, module="transplant")
def whatsapp_link(ctx: Ctx, a: WaIn):
    return {"url": S.share_links(a.text, a.phone)["whatsapp"]}


@tool("create_kidney_request", "Save a kidney-donor request for a patient (draft appeal page with a share link). Needs patient name, blood group, hospital and a contact number. Never involves payment.",
      RequestIn, roles=("patient", "caregiver"), writes=True, module="transplant")
def create_kidney_request(ctx: Ctx, a: RequestIn):
    r = create_request(ctx.db, ctx.user, a)
    return {"request": S.request_out(r, offers=0), "public_path": f"/r/{r.token}"}


class MatchIn(BaseModel):
    request_id: int


@tool("find_compatible_donors", "List registered living-donor pledges whose ABO blood group is compatible with a request (phones masked).", MatchIn, roles=("patient", "caregiver", "doctor", "admin"), module="transplant")
def find_compatible_donors(ctx: Ctx, a: MatchIn):
    r = ctx.db.get(OrganRequest, a.request_id)
    if r is None or (r.user_id != ctx.user.id and ctx.user.role not in ("doctor", "admin")):
        return {"error": "Request not found"}
    return {"request_id": r.id, "matches": S.find_matches(ctx.db, r, reveal_phone=ctx.user.role in ("doctor", "admin"))}


class NoneIn(BaseModel):
    status: Literal["open", "matched", "fulfilled", "closed", "any"] = "any"


@tool("list_my_requests", "List the signed-in person's donor requests with status and number of offers.", NoneIn, roles=("patient", "caregiver"), module="transplant")
def list_my_requests(ctx: Ctx, a: NoneIn):
    q = select(OrganRequest).where(OrganRequest.user_id == ctx.user.id)
    if a.status != "any":
        q = q.where(OrganRequest.status == a.status)
    return {"requests": [S.request_out(r) for r in ctx.db.scalars(q.order_by(OrganRequest.id.desc()).limit(20))]}
