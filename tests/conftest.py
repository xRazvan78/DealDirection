"""Shared fixtures. Task 1 adds `db` and `sample`, and Task 6 adds the auth clients."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
