"""Test retrieval + chunking tiếng Việt (stdlib, không vector DB)."""
from src.domain.models import KBEntry
from src.kb.retriever import chunk_text, retrieve


def _entry(content, title="t"):
    return KBEntry(id=title, title=title, content=content)


def test_chunk_text_ghep_duoi_nguong():
    text = "Câu đầu tiên. " * 8  # 8 câu, ~104 ký tự
    chunks = chunk_text(text, size=60, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) > 20 for c in chunks)  # không sinh mẩu ngắn lẻ


def test_chunk_text_bo_chunk_nho():
    chunks = chunk_text("Ngắn.", size=300)
    assert chunks == []  # dưới 20 ký tự → không lưu


def test_retrieve_top_k_tieng_viet():
    entries = [
        _entry("Sản phẩm được bảo hành 24 tháng kể từ ngày mua."),
        _entry("Giao hàng miễn phí cho đơn từ 500.000 đồng."),
        _entry("Khách cần giữ hóa đơn để được bảo hành."),
    ]
    hits = retrieve("chính sách bảo hành như thế nào?", entries, k=2)
    assert len(hits) == 2
    assert "bảo hành" in hits[0].content  # liên quan nhất lên đầu


def test_retrieve_khong_khop():
    assert retrieve("xyz", [_entry("nội dung a b c d")], k=3) == []
