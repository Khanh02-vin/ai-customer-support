"""Agent loop: LLM quyết gọi tool (JSON protocol) → thực thi → lặp → trả lời.
Memory theo ticket: lịch sử hội thoại lưu DB, đưa lại LLM mỗi lượt.
Orchestration tự viết — không dùng framework."""
import json
import re
from typing import List, Tuple

from ..domain.models import Ticket, TicketStatus
from ..llm.base import LLMProvider
from .tools import build_tools

MAX_ITERS = 3
_MAX_HISTORY = 10

_SYSTEM = """Bạn là trợ lý chăm sóc khách hàng {bot_name} của công ty. Trả lời tiếng Việt, ngắn gọn, thân thiện.

Bạn có công cụ:
{tools}

Quy tắc:
1. Câu hỏi về sản phẩm, giá, chính sách, hướng dẫn, bảo hành, thanh toán, giao hàng, đổi trả:
   BẮT BUỘC gọi search_knowledge trước — KHÔNG trả lời từ kiến thức riêng.
   Trả về ĐÚNG MỘT JSON: {{"tool": "tên_công_cụ", "args": {{...}} }}
2. Sau khi nhận kết quả công cụ, dùng nó để trả lời.
3. Nếu kết quả không đủ hoặc khách yêu cầu gặp người: trả về {{"tool": "escalate", "args": {{}} }}
4. Đủ thông tin: trả lời bình thường bằng tiếng Việt.
5. Chỉ trả JSON khi cần gọi công cụ. Không bịa thông tin — không có trong kết quả thì nói không biết và escalate.
6. KHÔNG dùng markdown (**, *, `, #) — trả lời thuần văn bản."""


# Chủ đề thuộc domain công ty — phải tra KB, cấm trả lời từ kiến thức riêng.
_KB_KEYWORDS = (
    "bảo hành", "giao", "vận chuyển", "ship", "giá", "chính sách", "thanh toán",
    "đổi trả", "hoàn tiền", "sản phẩm", "mua", "đơn hàng", "phí", "khuyến mãi", "giảm giá",
    "hóa đơn", "trả", "mã", "size", "kích thước", "màu", "hàng", "kho", "hết hàng",
)


def _needs_kb(message: str) -> bool:
    """Câu hỏi có chạm chủ đề công ty không (heuristic để ép tra cứu)."""
    m = message.lower()
    return any(k in m for k in _KB_KEYWORDS)


def _parse_tool_call(text: str) -> Tuple[str, dict] | None:
    """Nhận diện JSON {tool, args} trong câu trả lời LLM."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        data = json.loads(t)
    except Exception:
        return None
    if isinstance(data, dict) and isinstance(data.get("tool"), str):
        return data["tool"], data.get("args") or {}
    return None


def _format_tools(tools) -> str:
    return "\n".join(f"- {name}: {tool.description}" for name, tool in tools.items())


def _history(ticket: Ticket) -> str:
    """10 lượt gần nhất dạng 'Người dùng: ...' / 'Bot: ...'."""
    lines = []
    for m in ticket.messages[-_MAX_HISTORY:]:
        role = "Người dùng" if m.role == "user" else "Bot"
        lines.append(f"{role}: {m.content[:400]}")
    return "\n".join(lines)


def run_agent(repo, llm: LLMProvider, ticket: Ticket, user_message: str) -> Tuple[str, List[str], TicketStatus]:
    """Chạy vòng lặp agent cho 1 lượt. Trả (reply, tools_used, status cuối)."""
    tools = build_tools(repo)
    system = _SYSTEM.format(bot_name=repo.get_config().bot_name, tools=_format_tools(tools))
    tools_used: List[str] = []
    status = ticket.status

    # Thêm tin nhắn user vào ticket (memory)
    user_msg = repo.append_message(ticket.id, "user", user_message)
    ticket.messages.append(user_msg)

    conversation = _history(ticket)

    for _ in range(MAX_ITERS):
        prompt = conversation + "\n\nBây giờ bạn trả lời lượt vừa rồi."
        raw = llm.complete(system, prompt)
        call = _parse_tool_call(raw)
        if call is None:
            # LLM trả lời thẳng mà không tra KB dù câu hỏi thuộc domain công ty
            # → cưỡng chế tra cứu (chống hallucination), ép LLM trả lời lại
            if _needs_kb(user_message) and "search_knowledge" not in tools_used:
                result = tools["search_knowledge"].fn(user_message)
                tools_used.append("search_knowledge")
                conversation += f"\n[Kết quả search_knowledge]: {result[:600]}"
                continue
            # Câu trả lời cuối
            repo.append_message(ticket.id, "assistant", raw)
            return raw.strip(), tools_used, status

        name, args = call
        if name == "escalate":
            repo.set_status(ticket.id, TicketStatus.WAITING_HUMAN.value)
            reply = ("Tôi chưa chắc về vấn đề này — đã chuyển bạn tới nhân viên hỗ trợ. "
                     "Vui lòng đợi chút nhé!")
            repo.append_message(ticket.id, "assistant", reply)
            return reply, tools_used + ["escalate"], TicketStatus.WAITING_HUMAN

        tool = tools.get(name)
        if tool is None:
            # LLM gọi tool không tồn tại → ép escalate thay vì lặp vô hạn
            repo.set_status(ticket.id, TicketStatus.WAITING_HUMAN.value)
            reply = ("Tôi gặp sự cố xử lý — đã chuyển bạn tới nhân viên hỗ trợ. Xin lỗi vì bất tiện!")
            repo.append_message(ticket.id, "assistant", reply)
            return reply, tools_used + ["escalate"], TicketStatus.WAITING_HUMAN

        try:
            if name == "search_knowledge":
                # LLM có thể trả args dạng khác nhau → lấy query linh hoạt
                q = args.get("query") or args.get("q") or args.get("text") or ""
                result = tool.fn(q) if q else "LỖI: thiếu query trong args"
            else:
                result = tool.fn(**args) if args else tool.fn()
        except TypeError:
            result = tool.fn()
        tools_used.append(name)
        tool_msg = repo.append_message(ticket.id, "tool", f"{name}: {result[:600]}", tool=name)
        ticket.messages.append(tool_msg)
        conversation += f"\n[Kết quả {name}]: {result[:600]}"

    # Hết vòng lặp chưa kết thúc → escalate an toàn
    repo.set_status(ticket.id, TicketStatus.WAITING_HUMAN.value)
    reply = "Tôi vẫn đang tìm câu trả lời — đã chuyển bạn tới nhân viên hỗ trợ nhé!"
    repo.append_message(ticket.id, "assistant", reply)
    return reply, tools_used + ["escalate"], TicketStatus.WAITING_HUMAN
