from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import add_frontend_routes


@pytest.fixture
def site(tmp_path: Path) -> TestClient:
    dist = tmp_path / "browser"
    dist.mkdir()
    (dist / "index.html").write_text("<app-root></app-root>")
    (dist / "main.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("private")

    app = FastAPI()
    add_frontend_routes(app, dist)
    return TestClient(app)


def test_root_serves_index(site: TestClient) -> None:
    assert "app-root" in site.get("/").text


def test_real_files_are_served(site: TestClient) -> None:
    assert "console.log" in site.get("/main.js").text


def test_unknown_paths_serve_index(site: TestClient) -> None:
    response = site.get("/cart/12")

    assert response.status_code == 200
    assert "app-root" in response.text


def test_unknown_api_paths_stay_404(site: TestClient) -> None:
    assert site.get("/api/nothing").status_code == 404


def test_unknown_api_writes_stay_404(site: TestClient) -> None:
    assert site.post("/api/nothing").status_code == 404


def test_files_outside_the_build_are_not_served(site: TestClient) -> None:
    response = site.get("/..%2Fsecret.txt")

    assert "private" not in response.text


def test_real_app_keeps_health_route(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
