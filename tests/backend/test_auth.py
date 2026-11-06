"""Task 6: register, login, demo login and current_user."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models import User, UserStore

EMAIL = "new-user@example.com"
PASSWORD = "parola1!"


@pytest.fixture
def me_client(db: Session) -> TestClient:
    """A small app with one protected route, because no real route uses current_user yet."""
    protected = FastAPI()
    protected.dependency_overrides[get_db] = lambda: db

    @protected.get("/me")
    def me(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
        return {"email": user.email}

    return TestClient(protected)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_register_then_log_in(client: TestClient, me_client: TestClient) -> None:
    assert register(client).status_code == 201

    response = client.post("/api/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD})

    assert response.status_code == 200
    assert me_client.get("/me", headers=bearer(response.json()["token"])).json() == {"email": EMAIL}


def test_new_users_have_all_stores_selected(client: TestClient, db: Session, sample) -> None:
    register(client)

    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    selected = set(db.scalars(select(UserStore.store_id).where(UserStore.user_id == user.id)))
    assert {store.id for store in sample.stores} <= selected


def test_a_six_character_password_with_a_digit_and_a_special_character_works(
    client: TestClient,
) -> None:
    assert register(client, password="abc12!").status_code == 201


def test_a_duplicate_email_gives_409(client: TestClient) -> None:
    register(client)

    assert register(client, EMAIL.upper()).status_code == 409


@pytest.mark.parametrize(
    ("email", "password"),
    [
        (EMAIL, "abc1!"),
        (EMAIL, "abcdef!"),
        (EMAIL, "abcde1"),
        (EMAIL, "1!" + "x" * 71),
        ("not-an-email", PASSWORD),
    ],
)
def test_invalid_details_give_422(client: TestClient, email: str, password: str) -> None:
    assert register(client, email, password).status_code == 422


@pytest.mark.parametrize(
    ("email", "password"),
    [(EMAIL, "parola-gresita"), (EMAIL, "x" * 100), ("nobody@example.com", PASSWORD)],
)
def test_wrong_details_give_the_same_401(client: TestClient, email: str, password: str) -> None:
    register(client)

    response = client.post("/api/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong email or password"


def test_demo_login_needs_no_details(
    client: TestClient, me_client: TestClient, demo_user: User
) -> None:
    response = client.post("/api/auth/demo")

    assert response.status_code == 200
    assert me_client.get("/me", headers=bearer(response.json()["token"])).json() == {
        "email": demo_user.email
    }


def test_auth_client_sends_a_valid_token(auth_client: TestClient, me_client: TestClient) -> None:
    response = me_client.get("/me", headers=auth_client.headers)

    assert response.json() == {"email": "auth-client@example.com"}


def test_a_missing_token_gives_401(me_client: TestClient) -> None:
    assert me_client.get("/me").status_code == 401


def test_a_bad_token_gives_401(me_client: TestClient) -> None:
    assert me_client.get("/me", headers=bearer("bad")).status_code == 401


def test_an_expired_token_gives_401(me_client: TestClient) -> None:
    claims = {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}
    token = jwt.encode(claims, get_settings().JWT_SECRET, algorithm="HS256")

    assert me_client.get("/me", headers=bearer(token)).status_code == 401
