"""Register, login and demo login. Owner: Member 2, Task 6."""

import re
import string
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import create_token
from app.models import Store, User, UserStore

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_BYTES = 72  # bcrypt's limit
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[Session, Depends(get_db)]


class Credentials(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class Registration(Credentials):
    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        if len(value) > 320 or not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Use at least {MIN_PASSWORD_LENGTH} characters")
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Use at most {MAX_PASSWORD_BYTES} bytes")
        if not any(char in string.digits for char in value):
            raise ValueError("Use at least one digit")
        if not any(not char.isalnum() and not char.isspace() for char in value):
            raise ValueError("Use at least one special character")
        return value


class AuthResponse(BaseModel):
    token: str


def password_matches(password: str, password_hash: str) -> bool:
    encoded = password.encode()
    return len(encoded) <= MAX_PASSWORD_BYTES and bcrypt.checkpw(encoded, password_hash.encode())


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(details: Registration, db: Db) -> AuthResponse:
    hashed = bcrypt.hashpw(details.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=details.email, password_hash=hashed)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from None

    db.add_all(
        UserStore(user_id=user.id, store_id=store_id) for store_id in db.scalars(select(Store.id))
    )
    db.commit()
    return AuthResponse(token=create_token(user))


@router.post("/login")
def login(details: Credentials, db: Db) -> AuthResponse:
    user = db.scalars(select(User).where(User.email == details.email)).first()
    if user is None or not password_matches(details.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password")
    return AuthResponse(token=create_token(user))


@router.post("/demo")
def demo(db: Db) -> AuthResponse:
    user = db.scalars(select(User).where(User.is_demo)).first()
    if user is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo user not loaded")
    return AuthResponse(token=create_token(user))
