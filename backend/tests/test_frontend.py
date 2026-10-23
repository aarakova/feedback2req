from fastapi.testclient import TestClient

from feedback2req.main import create_app

from .conftest import ORIGIN


def test_frontend_static_does_not_expose_api_or_private_paths(app, tmp_path, monkeypatch):
    """DEC-011: FastAPI serves only API, even with a local frontend build."""
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>frontend build</html>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("private", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(app.state.settings), base_url=ORIGIN) as client:
        response = client.get("/")
        assert response.status_code == 404 and "frontend build" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/api/v1/missing").status_code == 404
        assert client.get("/private.txt").status_code == 404
        assert client.get("/%2e%2e/private.txt").status_code == 404
        assert client.post("/api/v1/auth/session", json={}).status_code == 403
