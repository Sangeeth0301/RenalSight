"""Translate chat messages and posts into the reader's language (English, Tamil, Bengali, Telugu).

Uses the same multi-provider LLM router as the helpers, with a cache so each text is translated once per language.
Names, numbers, units and medicine names are kept as they are. If no AI provider is available the original text is returned
and `available` is false, so the app can say so honestly instead of pretending."""
import hashlib
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...models import TranslationCache, User
from ..buddy.llm_router import AllProvidersFailed, get_router
from ..buddy.router import _rate_limit

router = APIRouter(tags=["translate"])
NAMES = {"en": "English", "ta": "Tamil", "bn": "Bengali", "te": "Telugu"}


class TranslateIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=40)
    target: Literal["en", "ta", "bn", "te"]


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf8")).hexdigest()


def _parse_array(raw: str, n: int) -> list[str] | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < 0:
        return None
    try:
        arr = json.loads(raw[start:end + 1])
    except ValueError:
        return None
    return [str(x) for x in arr] if isinstance(arr, list) and len(arr) == n else None


def translate_batch(texts: list[str], target: str) -> list[str] | None:
    router_ = get_router()
    if not router_.any_ready(target):
        return None
    system = (f"You are a careful medical-chat translator. Translate each string in the JSON array into {NAMES[target]}. "
              "If a string is already in that language, return it unchanged. Keep names, numbers, units (mg, mL/min), medicine names, emoji and line breaks. "
              "Do not add, explain or censor anything. Reply with ONLY a JSON array of strings, same length and order.")
    try:
        _, msg = router_.chat([{"role": "system", "content": system}, {"role": "user", "content": json.dumps(texts, ensure_ascii=False)}], language=target, max_tokens=3000)
    except AllProvidersFailed:
        return None
    return _parse_array(msg.get("content") or "", len(texts))


@router.post("/translate")
def translate(body: TranslateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _rate_limit(user.id)
    texts = [t[:2000] for t in body.texts]
    out: list[str | None] = [None] * len(texts)
    todo: dict[str, list[int]] = {}
    for i, t in enumerate(texts):
        if not t.strip():
            out[i] = t
            continue
        todo.setdefault(_digest(t), []).append(i)
    if todo:
        rows = db.scalars(select(TranslationCache).where(TranslationCache.lang == body.target, TranslationCache.digest.in_(list(todo))))
        for r in rows:
            for i in todo.pop(r.digest, []):
                out[i] = r.translated
    available = True
    if todo:
        firsts = [(d, idx[0]) for d, idx in todo.items()]
        result = translate_batch([texts[i] for _, i in firsts], body.target)
        if result is None:
            available = False
        else:
            for (d, _), tr in zip(firsts, result):
                for i in todo[d]:
                    out[i] = tr
                db.add(TranslationCache(lang=body.target, digest=d, translated=tr))
            db.commit()
    return {"target": body.target, "available": available, "translations": [o if o is not None else texts[i] for i, o in enumerate(out)],
            "translated": [o is not None for o in out]}
