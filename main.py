"""Demo end-to-end: admin + KB + khách chat 3 lượt (tool-use, escalate, memory).

Chạy: python demo.py  (cần LLM key trong .env — tự tải, không cần server đang chạy)
"""
import uuid

from fastapi.testclient import TestClient

from src.app import app

SESSION = "demo-" + uuid.uuid4().hex[:8]

with TestClient(app) as client:
    print("=" * 64)
    print("AI CUSTOMER SUPPORT - DEMO")
    print("=" * 64)

    # 1. Admin: đăng ký + upload knowledge base
    print("\n[1] Đăng ký admin + tải lên knowledge base:")
    r = client.post("/auth/register", json={"username": "demo", "password": "demo1234"})
    if r.status_code == 200:
        print("  - Admin 'demo' đã tạo (token JWT 7 ngày)")
    else:
        print("  - Admin 'demo' đã tồn tại")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else \
        {"Authorization": f"Bearer {client.post('/auth/login', json={'username': 'demo', 'password': 'demo1234'}).json()['access_token']}"}

    r = client.post("/kb/upload", headers=h, files={"file": ("kb-demo.txt", open("kb-demo.txt", "rb"), "text/plain")})
    if r.status_code == 200:
        print(f"  - {r.json()['doc']}: {r.json()['chunks']} đoạn (tổng {r.json()['total_chunks']})")
    else:
        print(f"  - KB đã có sẵn ({client.get('/kb/docs', headers=h).json()['total_chunks']} đoạn)")

    # 2. Khách chat qua /chat (widget gọi API này)
    def chat(message):
        r = client.post("/chat", json={"session_id": SESSION, "message": message, "channel": "widget"})
        d = r.json()
        print(f"\n  Khách: {message}")
        print(f"  Bot   : {d['reply'][:180]}")
        print(f"  -> ticket {d['ticket_id'][:8]} | trạng thái {d['status']} | "
              f"công cụ: {d['tools_used'] or 'không'}")
        return d

    print("\n[2] Khách chat (cùng session = cùng ticket = memory):")
    d1 = chat("Chính sách bảo hành của sản phẩm như thế nào?")
    d2 = chat("Tôi muốn nói chuyện với nhân viên thật về vấn đề của tôi")
    d3 = chat("Mà quên, cho hỏi giao hàng mất bao lâu vậy?")

    # 3. Nhân viên tiếp nhận ticket chờ
    print("\n[3] Nhân viên xử lý ticket:")
    tickets = client.get("/tickets?status=waiting_human", headers=h).json()
    waiting = [t for t in tickets if t["session_id"] == SESSION]
    if waiting:
        t = waiting[0]
        client.post(f"/tickets/{t['id']}/reply", headers=h,
                    json={"message": "Đơn của bạn đang giao, mã đơn 8KX123, dự kiến 2 ngày nữa."})
        print(f"  - Ticket {t['id'][:8]}: đã trả lời → chuyển về 'open'")

    # 4. Thống kê
    print("\n[4] Thống kê:")
    s = client.get("/stats", headers=h).json()
    print(f"  - Tổng ticket: {s['total']} | chờ người: {s['by_status'].get('waiting_human', 0)}"
          f" | đã giải quyết: {s['by_status'].get('resolved', 0)}")

print("\n" + "=" * 64)
print("DEMO HOÀN TẤT — UI admin: http://localhost:8005/ (demo/demo1234)")
print("Widget demo: http://localhost:8005/widget/")
