from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model" in body
    assert "api_key_configured" in body
    # The key must never be echoed back, only a boolean flag.
    assert body["api_key_configured"] in (True, False)
