"""Công cụ cho agent. search_knowledge đọc KB qua repo;
escalate là hành động đặc biệt cần ticket → agent loop xử lý inline."""
from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class Tool:
    description: str
    fn: Callable[..., str]


def _search_knowledge(repo, query: str) -> str:
    """Tìm câu trả lời trong knowledge base."""
    hits = repo.search_kb(query, k=3)
    if not hits:
        return "KHÔNG TÌM THẤY trong knowledge base."
    return "\n---\n".join(f"[{h.title}] {h.content}" for h in hits)


def build_tools(repo) -> Dict[str, Tool]:
    """Tool registry gắn với repository. escalate do agent loop xử lý (cần ticket)."""
    return {
        "search_knowledge": Tool(
            description=(
                "Tìm câu trả lời trong knowledge base của công ty. "
                "Dùng khi câu hỏi về sản phẩm, chính sách, hướng dẫn, giá, bảo hành."
            ),
            fn=lambda q: _search_knowledge(repo, q),
        ),
    }
