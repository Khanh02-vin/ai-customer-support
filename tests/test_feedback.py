"""Test feedback loop: rating + stats."""
import pytest
from fastapi.testclient import TestClient
from src.store.repository import SupportRepo
from src.store.users import UserRepository
import src.app as app_module


def _register(client):
    r = client.post("/auth/register", json={"username": "demo_fb", "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def client(monkeypatch):
    import os
    os.environ["OPEN_REGISTRATION"] = "1"
    monkeypatch.setattr(app_module, "repo", SupportRepo(":memory:"))
    monkeypatch.setattr(app_module, "users", UserRepository(":memory:"))
    with TestClient(app_module.app) as c:
        yield c


def test_feedback(client):
    h = _register(client)
    chat = client.post("/chat", json={"message": "test", "session_id": "fb-test"}, headers=h)
    ticket_id = chat.json()["ticket_id"]

    fb = client.post(f"/tickets/{ticket_id}/feedback", json={"rating": 4, "text": "Hữu ích"}, headers=h)
    assert fb.status_code == 200
    assert fb.json()["rating"] == 4

    stats = client.get("/stats", headers=h).json()
    assert stats["feedback"].get("4", 0) >= 1


def test_feedback_validation(client):
    h = _register(client)
    chat = client.post("/chat", json={"message": "hi", "session_id": "fb2"}, headers=h)
    tid = chat.json()["ticket_id"]

    assert client.post(f"/tickets/{tid}/feedback", json={"rating": 6}, headers=h).status_code == 400
    assert client.post(f"/tickets/{tid}/feedback", json={"text": "ok"}, headers=h).status_code == 400
    assert client.post(f"/tickets/xxx/feedback", json={"rating": 5}, headers=h).status_code == 404
