"""FastAPI app — AI Customer Support.
Public: POST /chat (widget), GET /widget/config. Admin (JWT): KB, tickets, stats, config."""
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from .agent.agent import run_agent
from .domain.models import (
    ChatRequest, ChatResponse, Ticket, TicketStatus, Token, User, UserCreate, UserPublic,
    WidgetConfig,
)
from .kb.retriever import chunk_text
from .llm.base import get_llm_provider
from .store.repository import SupportRepo
from .store.users import UserRepository
from .auth.security import hash_password, verify_password, create_token, decode_token

app = FastAPI(title="AI Customer Support", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

repo = SupportRepo()
users = UserRepository()
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> User:
    """Admin từ JWT. 401 nếu thiếu/sai token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    user_id = decode_token(credentials.credentials)
    user = users.get(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return user


def _read_text(path: str) -> str:
    """Đọc file text/PDF thành text."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            pass
    return Path(path).read_text(encoding="utf-8", errors="ignore")


# ---------- Chat công khai ----------

@app.post("/chat", response_model=ChatResponse)
async def chat(data: ChatRequest):
    """1 lượt hỏi-đáp. Cùng session_id → cùng ticket (memory)."""
    llm = get_llm_provider()
    session = data.session_id or uuid.uuid4().hex[:12]

    ticket = repo.get_ticket_by_session(session)
    if ticket is None:
        ticket = repo.create_ticket(session, data.channel.value)
    elif ticket.status == TicketStatus.RESOLVED.value:
        # Khách mở lại ticket đã đóng → ticket mới cùng phiên
        ticket = repo.create_ticket(session, data.channel.value)

    if llm is None:
        # Không có LLM key → fallback RAG thuần (không agent)
        hits = repo.search_kb(data.message, k=2)
        reply = ("KHÔNG TÌM THẤY trong knowledge base." if not hits
                 else "\n".join(f"- {h.content[:200]}" for h in hits))
        return ChatResponse(ticket_id=ticket.id, session_id=session, reply=reply,
                            status=ticket.status, tools_used=[])

    reply, tools_used, status = run_agent(repo, llm, ticket, data.message)
    return ChatResponse(ticket_id=ticket.id, session_id=session, reply=reply,
                        status=status, tools_used=tools_used)


@app.get("/widget/config", response_model=WidgetConfig)
async def widget_config():
    """Cấu hình widget (public — widget khách đọc)."""
    return repo.get_config()


# ---------- Auth admin ----------
# Đăng ký mặc định TẮT khi deploy (ai có link public đều gọi được API).
# Mở bằng env OPEN_REGISTRATION=1 khi cần tạo tài khoản mới.

@app.post("/auth/register", response_model=Token)
async def register(data: UserCreate):
    import os
    if not os.getenv("OPEN_REGISTRATION"):
        raise HTTPException(status_code=403, detail="Đăng ký đã tắt — liên hệ quản trị viên")
    if users.get_by_username(data.username):
        raise HTTPException(status_code=400, detail="Tên người dùng đã tồn tại")
    user = users.create(data.username, hash_password(data.password))
    return Token(access_token=create_token(user.id))


@app.post("/auth/login", response_model=Token)
async def login(data: UserCreate):
    user = users.get_by_username(data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    return Token(access_token=create_token(user.id))


@app.get("/auth/me", response_model=UserPublic)
async def me(user: User = Depends(current_user)):
    return UserPublic(id=user.id, username=user.username, created_at=user.created_at)


# ---------- Knowledge base (admin) ----------

@app.post("/kb/upload")
async def kb_upload(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Upload tài liệu (txt/pdf) → chunk → vào KB."""
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await file.read())
        path = f.name
    try:
        text = _read_text(path)
        if len(text.strip()) < 30:
            raise HTTPException(status_code=400, detail="File quá ngắn hoặc không đọc được text")
        chunks = chunk_text(text)
        count = repo.add_doc(file.filename, chunks, title=Path(file.filename).stem)
        return {"doc": file.filename, "chunks": count, "total_chunks": repo.kb_count()}
    finally:
        Path(path).unlink()


@app.get("/kb/docs")
async def kb_docs(user: User = Depends(current_user)):
    return {"docs": repo.list_docs(), "total_chunks": repo.kb_count()}


@app.delete("/kb/docs/{doc_id}")
async def kb_delete(doc_id: str, user: User = Depends(current_user)):
    if not repo.delete_doc(doc_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return {"deleted": doc_id}


# ---------- Tickets (admin) ----------

@app.get("/tickets", response_model=List[Ticket])
async def list_tickets(status: Optional[str] = None, limit: int = 100, user: User = Depends(current_user)):
    return repo.list_tickets(status=status, limit=limit)


@app.get("/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str, user: User = Depends(current_user)):
    ticket = repo.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket")
    return ticket


@app.post("/tickets/{ticket_id}/reply")
async def human_reply(ticket_id: str, body: dict, user: User = Depends(current_user)):
    """Nhân viên người trả lời → ticket về trạng thái xử lý."""
    text = (body or {}).get("message", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Thiếu nội dung trả lời")
    if not repo.get_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket")
    repo.append_message(ticket_id, "assistant", f"[Nhân viên {user.username}] {text}")
    if repo.get_ticket(ticket_id).status != TicketStatus.RESOLVED.value:
        repo.set_status(ticket_id, "open")
    return {"ok": True}

@app.post("/tickets/{ticket_id}/feedback")
async def submit_feedback(ticket_id: str, body: dict, user: User = Depends(current_user)):
    """Ghi nhận feedback → hệ thống học từ đánh giá."""
    rating = body.get("rating")
    text = (body or {}).get("text", "").strip()
    if rating is None or not (1 <= rating <= 5):
        raise HTTPException(status_code=400, detail="rating 1-5 bắt buộc")
    if not repo.get_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket")
    repo.add_feedback(ticket_id, rating, text)
    return {"ok": True, "rating": rating}


@app.patch("/tickets/{ticket_id}")
async def set_ticket_status(ticket_id: str, body: dict, user: User = Depends(current_user)):
    status = (body or {}).get("status")
    if status not in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, TicketStatus.OPEN.value):
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")
    if not repo.get_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy ticket")
    repo.set_status(ticket_id, status)
    return {"ok": True}


@app.get("/stats")
async def stats(user: User = Depends(current_user)):
    s = repo.stats()
    s["feedback"] = repo.feedback_stats()
    return s


# ---------- Cấu hình widget (admin) ----------

@app.get("/config", response_model=WidgetConfig)
async def get_config(user: User = Depends(current_user)):
    return repo.get_config()


@app.put("/config", response_model=WidgetConfig)
async def set_config(cfg: WidgetConfig, user: User = Depends(current_user)):
    return repo.set_config(cfg)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0", "llm": bool(get_llm_provider())}


# ---------- Static: widget + frontend (mount SAU routes) ----------
_widget_dir = Path(__file__).parent.parent / "widget"
_dist = Path(__file__).parent.parent / "frontend" / "dist"

if _widget_dir.exists():
    app.mount("/widget", StaticFiles(directory=str(_widget_dir), html=True), name="widget")

ui_dir = _dist if _dist.exists() else None
if ui_dir:
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
