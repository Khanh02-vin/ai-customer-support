"""Mô hình miền cho AI Customer Support.
Ticket = phiên hội thoại; KBEntry = đoạn tri thức trong knowledge base."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TicketStatus(str, Enum):
    OPEN = "open"              # bot đang xử lý / mới
    WAITING_HUMAN = "waiting_human"  # agent escalate → chờ người thật
    RESOLVED = "resolved"      # giải quyết xong
    CLOSED = "closed"


class Channel(str, Enum):
    WIDGET = "widget"
    API = "api"


class Message(BaseModel):
    """Một lượt trong ticket."""
    role: str            # user | assistant | tool
    content: str
    tool: Optional[str] = None   # tool đã gọi (nếu lượt tool)
    ts: datetime = Field(default_factory=datetime.now)


class Ticket(BaseModel):
    """Phiên hỗ trợ khách hàng."""
    id: str
    session_id: str          # khách giữ, gửi lại mỗi lượt → memory theo phiên
    messages: List[Message] = []
    status: TicketStatus = TicketStatus.OPEN
    channel: Channel = Channel.WIDGET
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


class KBEntry(BaseModel):
    """Một đoạn tri thức trong knowledge base."""
    id: str
    title: str
    content: str             # đã chunk
    doc_name: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class WidgetConfig(BaseModel):
    """Cấu hình widget chat hiển thị cho khách."""
    title: str = "Hỗ trợ khách hàng"
    welcome: str = "Chào bạn! Tôi có thể giúp gì?"
    primary_color: str = "#2563eb"
    bot_name: str = "Trợ lý ảo"


class User(BaseModel):
    """Người quản trị."""
    id: str
    username: str
    password_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserPublic(BaseModel):
    id: str
    username: str
    created_at: datetime = Field(default_factory=datetime.now)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    channel: Channel = Channel.WIDGET


class ChatResponse(BaseModel):
    ticket_id: str
    session_id: str
    reply: str
    status: TicketStatus
    tools_used: List[str] = []
