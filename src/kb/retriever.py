"""Knowledge base: chunk tài liệu + truy vấn (stdlib, không cần vector DB).
Vietnamese không có word segmenter → tokenize = từ + char-bigram.
Scoring: TF-IDF cosine (IDF tính từ corpus) — khắc phục từ thường (tiki, làm, tại)
lấn át từ khóa hiếm khi chỉ dùng độ phủ token."""
import math
import re
from collections import Counter
from typing import List

from ..domain.models import KBEntry

_VIET = r"a-zA-Z0-9_àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
_WORD = re.compile(rf"[{_VIET}]+")
_ALNUM = re.compile(r"[0-9a-zà-ỹ]")
_BREAK = re.compile(r"(?<=[.\n!?;])\s*")

# Từ chức năng tiếng Việt thường gặp trong câu hỏi FAQ — không mang nghĩa truy vấn.
# Chỉ là bộ stopword cơ bản, không tune theo bộ query nào.
_STOPWORDS = frozenset(
    "tôi em mình anh chị bạn quý khách khách hàng của và là với thì như vậy nên cần phải "
    "được bị có không cũng đang sẽ đã đang rất hơn nhất mà vì nếu hay hoặc tại ở vào từ "
    "cho lại sau trước bao lâu bao nhiêu thế nào làm sao làm thế nào khi nào đâu gì "
    "nào ạ à nhé đó này đây kia rồi hết đã từng vẫn chứ hỏi ai mấy".split()
)


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
    """Từ (lower) + char-bigram — bắt compounds tiếng Việt.
    Lọc: stopword, bigram không thuần alnum (bỏ noise từ space/punct)."""
    s = s.lower()
    words = set(_WORD.findall(s)) - _STOPWORDS
    bigrams = {s[i:i + 2] for i in range(len(s) - 1)
               if _ALNUM.fullmatch(s[i:i + 2])}
    return words | bigrams


def retrieve(query: str, entries: List[KBEntry], k: int = 3) -> List[KBEntry]:
    """Top-k đoạn liên quan nhất theo TF-IDF cosine similarity (query boolean-TF)."""
    q = _tokens(query)
    if not q:
        return []

    # IDF từ corpus (entry-level document frequency)
    entry_tokens = [_tokens(e.content) for e in entries]
    df = Counter()
    for toks in entry_tokens:
        for t in toks:
            df[t] += 1
    n = len(entries)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}

    q_norm = math.sqrt(sum(idf.get(t, 0.0) ** 2 for t in q))
    if q_norm == 0:
        return []

    scored = []
    for e, toks in zip(entries, entry_tokens):
        overlap = q & toks
        if not overlap:
            continue
        dot = sum(idf.get(t, 0.0) ** 2 for t in overlap)
        d_norm = math.sqrt(sum(idf.get(t, 0.0) ** 2 for t in toks))
        score = dot / (q_norm * d_norm)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:k]]
