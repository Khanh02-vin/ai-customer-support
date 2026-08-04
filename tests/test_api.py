"""Test API: auth JWT, KB upload, chat (fallback RAG + LLM), tickets, stats."""
import pytest
from fastapi.testclient import TestClient

import src.app as app_module
from src.store.repository import SupportRepo
from src.store.users import UserRepository
from tests.test_agent import MockSeq


@pytest.fixture()
def client(monkeypatch):
    """Mỗi test một DB rỗng — không đụng support.db thật. Đăng ký mở cho test."""
    monkeypatch.setenv("OPEN_REGISTRATION", "1")
    monkeypatch.setattr(app_module, "repo", SupportRepo(":memory:"))
    monkeypatch.setattr(app_module, "users", UserRepository(":memory:"))
    with TestClient(app_module.app) as c:
        yield c


def _register(client, username="demo"):
    r = client.post("/auth/register", json={"username": username, "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_auth_flow(client):
    h = _register(client)
    me = client.get("/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["username"] == "demo"
    # sai mật khẩu (hợp lệ format nhưng khác password)
    assert client.post("/auth/login", json={"username": "demo", "password": "demoxxx"}).status_code == 401
    # trùng username
    assert client.post("/auth/register", json={"username": "demo", "password": "demo1234"}).status_code == 400


def test_tickets_can_401(client):
    assert client.get("/tickets").status_code == 401
    assert client.get("/stats").status_code == 401
    assert client.get("/kb/docs").status_code == 401


def test_kb_upload_list_delete(client):
    h = _register(client)
    r = client.post("/kb/upload", headers=h,
                    files={"file": ("kb.txt", b"Bao hanh 24 thang. Giao hang mien phi tren 500k.", "text/plain")})
    assert r.status_code == 200
    docs = client.get("/kb/docs", headers=h).json()
    assert docs["total_chunks"] >= 1
    doc_id = docs["docs"][0]["id"]
    assert client.delete(f"/kb/docs/{doc_id}", headers=h).status_code == 200
    assert client.get("/kb/docs", headers=h).json()["total_chunks"] == 0


def test_kb_upload_file_ngan(client):
    h = _register(client)
    r = client.post("/kb/upload", headers=h, files={"file": ("ngan.txt", b"abc", "text/plain")})
    assert r.status_code == 400


def test_chat_fallback_rag_khong_llm(client, monkeypatch):
    """Không có LLM → fallback RAG thuần, không 500."""
    monkeypatch.setattr(app_module, "get_llm_provider", lambda: None)
    h = _register(client)
    client.post("/kb/upload", headers=h,
                files={"file": ("kb.txt", b"Bao hanh 24 thang, can giu hoa don.", "text/plain")})
    r = client.post("/chat", json={"session_id": "s-rag", "message": "bao hanh the nao?"})
    assert r.status_code == 200
    assert "bao hanh" in r.json()["reply"].lower()
    assert r.json()["tools_used"] == []


def test_chat_agent_llm(client, monkeypatch):
    """Có LLM → agent loop chạy, tools_used trả về."""
    monkeypatch.setattr(app_module, "get_llm_provider", lambda: MockSeq([
        '{"tool": "search_knowledge", "args": {"query": "bao hanh"}}',
        "San pham bao hanh 24 thang.",
    ]))
    r = client.post("/chat", json={"session_id": "s-agent", "message": "bao hanh?"})
    assert r.status_code == 200
    assert r.json()["tools_used"] == ["search_knowledge"]
    assert "24 thang" in r.json()["reply"]


def test_chat_cung_session_cung_ticket(client, monkeypatch):
    """Memory: 2 lượt cùng session → cùng ticket_id."""
    monkeypatch.setattr(app_module, "get_llm_provider", lambda: MockSeq([
        '{"tool": "escalate", "args": {}}',   # lượt 1: escalate
        "Trả lời cuối.",                       # lượt 2
    ]))
    r1 = client.post("/chat", json={"session_id": "s-mem", "message": "gap nhan vien"})
    r2 = client.post("/chat", json={"session_id": "s-mem", "message": "xin chao"})
    assert r1.json()["ticket_id"] == r2.json()["ticket_id"]
    assert r1.json()["status"] == "waiting_human"


def test_ticket_404(client):
    h = _register(client)
    assert client.get("/tickets/khong-ton-tai", headers=h).status_code == 404


def test_human_reply(client, monkeypatch):
    """Nhân viên trả lời → ticket chuyển open, nội dung có tiền tố tên."""
    monkeypatch.setattr(app_module, "get_llm_provider", lambda: None)
    h = _register(client)
    client.post("/chat", json={"session_id": "s-hr", "message": "ho tro"})
    ticket_id = client.get("/tickets", headers=h).json()[0]["id"]
    r = client.post(f"/tickets/{ticket_id}/reply", headers=h, json={"message": "Chúng tôi đã xử lý xong"})
    assert r.status_code == 200
    t = client.get(f"/tickets/{ticket_id}", headers=h).json()
    assert t["status"] == "open"
    assert "demo" in t["messages"][-1]["content"]


def test_set_status_invalid(client):
    h = _register(client)
    client.post("/chat", json={"session_id": "s-st", "message": "ho tro"})
    ticket_id = client.get("/tickets", headers=h).json()[0]["id"]
    r = client.patch(f"/tickets/{ticket_id}", headers=h, json={"status": "hack"})
    assert r.status_code == 400


def test_stats(client):
    h = _register(client)
    s = client.get("/stats", headers=h).json()
    assert "total" in s and "resolved_rate" in s


def test_widget_config(client):
    h = _register(client)
    r = client.put("/config", headers=h, json={"title": "Hỗ trợ nhanh", "welcome": "Chào!",
                                               "primary_color": "#00ff00", "bot_name": "BotX"})
    assert r.status_code == 200
    # widget công khai đọc được config đã lưu
    assert client.get("/widget/config").json()["bot_name"] == "BotX"
