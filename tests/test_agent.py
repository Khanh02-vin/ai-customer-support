"""Test agent loop: tool-use, hard-guard chống hallucination, escalate, memory."""
from src.agent.agent import run_agent, _needs_kb
from src.domain.models import KBEntry, Ticket, TicketStatus
from src.llm.base import LLMProvider
from src.store.repository import SupportRepo


class MockSeq(LLMProvider):
    """Trả từng response trong queue theo thứ tự — mô phỏng LLM qua nhiều vòng."""

    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, system, user):
        return self.responses.pop(0)


def _repo_with_kb():
    repo = SupportRepo(":memory:")
    repo.add_doc("kb-demo.txt", [
        "Sản phẩm được bảo hành 24 tháng kể từ ngày mua, cần giữ hóa đơn.",
        "Giao hàng miễn phí cho đơn từ 500.000 đồng, giao 2-3 ngày.",
    ])
    return repo


def _ticket(repo):
    return repo.create_ticket("sess-test", "widget")


def test_guard_bat_buoc_tra_kb():
    """LLM trả lời thẳng câu hỏi về chính sách → guard ép search_knowledge trước."""
    repo = _repo_with_kb()
    llm = MockSeq([
        "Trả lời thẳng không gọi tool.",          # vòng 1: bị guard chặn
        "Theo chính sách, sản phẩm bảo hành 24 tháng.",  # vòng 2: có KB trong context
    ])
    reply, tools_used, status = run_agent(repo, llm, _ticket(repo), "chính sách bảo hành thế nào?")
    assert "search_knowledge" in tools_used
    assert "24 tháng" in reply
    assert status == TicketStatus.OPEN


def test_khong_guard_cau_ngoai_domain():
    """Câu chào không chạm KB → không ép tra cứu."""
    repo = _repo_with_kb()
    llm = MockSeq(["Chào bạn! Tôi là trợ lý ảo."])
    reply, tools_used, _ = run_agent(repo, llm, _ticket(repo), "Chào bạn")
    assert tools_used == []
    assert "trợ lý" in reply


def test_tool_call_tra_kb():
    """LLM chủ động gọi search_knowledge → kết quả đưa vào context."""
    repo = _repo_with_kb()
    llm = MockSeq([
        '{"tool": "search_knowledge", "args": {"query": "giao hàng"}}',
        "Giao hàng miễn phí từ 500.000 đồng.",
    ])
    reply, tools_used, _ = run_agent(repo, llm, _ticket(repo), "giao hàng mất bao lâu?")
    assert tools_used == ["search_knowledge"]
    assert "500.000" in reply


def test_escalate():
    repo = _repo_with_kb()
    llm = MockSeq(['{"tool": "escalate", "args": {}}'])
    reply, tools_used, status = run_agent(repo, llm, _ticket(repo), "tôi muốn gặp nhân viên")
    assert tools_used == ["escalate"]
    assert status == TicketStatus.WAITING_HUMAN


def test_tool_khong_ton_tai_ep_escalate():
    repo = _repo_with_kb()
    llm = MockSeq(['{"tool": "khong_co_tool_nay", "args": {}}'])
    _, tools_used, status = run_agent(repo, llm, _ticket(repo), "có vấn đề")
    assert tools_used == ["escalate"]
    assert status == TicketStatus.WAITING_HUMAN


def test_memory_theo_ticket():
    """Lịch sử lượt trước nằm trong context lượt sau (memory)."""
    repo = _repo_with_kb()
    ticket = _ticket(repo)
    llm1 = MockSeq(['{"tool": "escalate", "args": {}}'])
    run_agent(repo, llm1, ticket, "tôi muốn gặp nhân viên")
    llm2 = MockSeq(["Trả lời cuối.", "Giao 2-3 ngày theo chính sách."])
    reply, tools_used, _ = run_agent(repo, llm2, ticket, "còn giao hàng thì sao?")
    # Guard bắt buộc tra KB trước khi trả lời
    assert "search_knowledge" in tools_used
    assert len(repo.get_ticket(ticket.id).messages) >= 4  # user+bot x2 lượt


def test_needs_kb():
    assert _needs_kb("giá sản phẩm này bao nhiêu?")
    assert _needs_kb("chính sách bảo hành")
    assert not _needs_kb("bạn khỏe không?")
