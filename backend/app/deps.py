"""Shared FastAPI dependencies, such as current_user. Owner: Member 2, Task 6."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(days=7)

bearer = HTTPBearer(auto_error=False)


def create_token(user: User) -> str:
    claims = {"sub": str(user.id), "exp": datetime.now(UTC) + TOKEN_LIFETIME}
    return jwt.encode(claims, get_settings().JWT_SECRET, algorithm=ALGORITHM)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            get_settings().JWT_SECRET,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user = db.get(User, int(claims["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    if user is None:
        raise unauthorized
    return user
