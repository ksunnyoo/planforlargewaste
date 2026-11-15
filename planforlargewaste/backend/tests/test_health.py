from fastapi.testclient import TestClient

from app.main import app


def test_health_항상_200():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] in ("ok", "down")
    assert body["status"] == ("ok" if body["db"] == "ok" else "degraded")
    assert "llm" in body
