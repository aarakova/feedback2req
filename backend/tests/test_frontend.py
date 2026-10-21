from fastapi.testclient import TestClient

from feedback2req.main import create_app

from .conftest import ORIGIN


def test_frontend_static_does_not_expose_api_or_private_paths(app, tmp_path):
    """F1a: serve only the public build; API auth and Origin/CSRF remain in force."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>frontend build</html>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("private", encoding="utf-8")
    settings = app.state.settings.model_copy(update={"frontend_dist": dist})
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        response = client.get("/")
        assert response.status_code == 200 and "frontend build" in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/api/v1/missing").status_code == 404
        assert client.get("/private.txt").status_code == 404
        assert client.get("/%2e%2e/private.txt").status_code == 404
        assert client.post("/api/v1/auth/session", json={}).status_code == 403
