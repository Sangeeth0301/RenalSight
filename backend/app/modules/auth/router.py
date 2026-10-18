from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import create_token, get_current_user, hash_password, verify_password
from ...models import User

router = APIRouter(tags=["auth"])

Language = Literal["en", "ta", "bn", "te"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["patient", "doctor", "caregiver"] = "patient"   # admin accounts are never self-registered
    language: Language = "en"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    language: Language | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2026)
    sex: Literal["male", "female"] | None = None
    diabetes: bool | None = None
    hypertension: bool | None = None


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "language": u.language,
            "birth_year": u.birth_year, "age": u.age(), "sex": u.sex, "diabetes": u.diabetes,
            "hypertension": u.hypertension, "doctor_code": u.doctor_code, "doctor_id": u.doctor_id}


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    u = User(email=email, password_hash=hash_password(body.password), name=body.name, role=body.role, language=body.language)
    if body.role == "doctor":
        from ..doctor.router import new_doctor_code

        u.doctor_code = new_doctor_code(db)
    db.add(u)
    db.commit()
    return {"access_token": create_token(u.id, u.role), "token_type": "bearer", "user": user_out(u)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return {"access_token": create_token(u.id, u.role), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/me/profile")
def update_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    db.add(user)
    db.commit()
    from ..labs.service import recompute_egfr

    recompute_egfr(db, user)
    return user_out(user)
