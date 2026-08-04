"""Knowledge base: chunk tài liệu + truy vấn bằng token-overlap (stdlib, không cần
vector DB). Vietnamese không có word segmenter → tokenize = từ + char-bigram."""
import re
from typing import List

from ..domain.models import KBEntry

_VIET = r"a-zA-Z0-9_àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
_WORD = re.compile(rf"[{_VIET}]+")
_BREAK = re.compile(r"(?<=[.\n!?;])\s*")


def chunk_text(text: str, size: int = 300, overlap: int = 40) -> List[str]:
    """Tách text thành đoạn ~size ký tự, chồng lấp overlap để không mất ngữ cảnh câu.
    Chỉ tách khi đoạn đang gom đủ dài — không sinh mẩu ngắn lẻ giữa chừng."""
    chunks, cur = [], ""
    for part in _BREAK.split(text):
        part = part.strip()
        if not part:
            continue
        if cur and len(cur) + len(part) + 1 > size and len(cur) >= 20:
            chunks.append(cur.strip())
            cur = cur[-overlap:]
        cur += " " + part
    if cur.strip() and len(cur.strip()) > 20:
        chunks.append(cur.strip())
    return chunks


def _tokens(s: str) -> set:
    """Từ (không dấu hóa nhẹ bằng lower) + char-bigram — bắt compounds tiếng Việt."""
    s = s.lower()
    words = set(_WORD.findall(s))
    bigrams = {s[i:i + 2] for i in range(len(s) - 1) if not s[i].isspace()}
    return words | bigrams


def retrieve(query: str, entries: List[KBEntry], k: int = 3) -> List[KBEntry]:
    """Top-k đoạn liên quan nhất theo độ phủ token của câu hỏi."""
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for e in entries:
        c = _tokens(e.content)
        cov = len(q & c) / len(q)   # độ phủ query, không phạt độ dài
        if cov > 0:
            scored.append((cov, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:k]]
