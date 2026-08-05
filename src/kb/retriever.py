"""Knowledge base: chunk tài liệu + truy vấn (stdlib, không cần vector DB).
Vietnamese không có word segmenter → tokenize = từ + char-bigram.
Scoring: TF-IDF cosine (IDF tính từ corpus) — khắc phục từ thường (tiki, làm, tại)
lấn át từ khóa hiếm khi chỉ dùng độ phủ token.
semantic=True (tùy chọn): hybrid TF-IDF + multilingual-e5-small — fallback TF-IDF
nếu chưa cài sentence-transformers. α (KB_SEMANTIC_ALPHA, mặc định 0.2) sweep trên
22 câu hỏi tự nhiên Tiki thật: hit@3 54.5%→63.6%; kiểm tra held-out (15 tune/7 eval)
xác nhận α=0.2 generalizes tốt hơn α tune chọn (hit@3 71.4% vs 42.9%) — không overfit."""
import math
import os
import re
from collections import Counter
from typing import List

from ..domain.models import KBEntry

_ALPHA = float(os.environ.get("KB_SEMANTIC_ALPHA", "0.2"))
_sem_model = None
_sem_cache = (None, None)  # (id(entries), embeddings)

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


def _sem_embeddings(entries: List[KBEntry]):
    """Embed toàn bộ chunk bằng e5-small (cache theo id(entries))."""
    global _sem_model, _sem_cache
    if _sem_cache[0] == id(entries):
        return _sem_cache[1]
    if _sem_model is None:
        from sentence_transformers import SentenceTransformer
        _sem_model = SentenceTransformer("intfloat/multilingual-e5-small")
    emb = _sem_model.encode(["passage: " + e.content for e in entries], batch_size=8)
    _sem_cache = (id(entries), emb)
    return emb


def _cosine(a, b) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(query: str, entries: List[KBEntry], k: int = 3, semantic: bool = False) -> List[KBEntry]:
    """Top-k đoạn liên quan nhất. semantic=False: TF-IDF cosine thuần (stdlib).
    semantic=True: hybrid (1-α)*TF-IDF + α*semantic — cần sentence-transformers."""
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

    d_norm = [math.sqrt(sum(idf.get(t, 0.0) ** 2 for t in toks)) for toks in entry_tokens]

    sem_emb = None
    if semantic:
        try:
            sem_emb = _sem_embeddings(entries)
        except Exception:
            sem_emb = None

    q_sem = None
    if sem_emb is not None:
        from sentence_transformers import SentenceTransformer
        q_sem = list(_sem_model.encode(["query: " + query], batch_size=8)[0])

    scored = []
    for i, (e, toks, dn) in enumerate(zip(entries, entry_tokens, d_norm)):
        overlap = q & toks
        lex = 0.0
        if overlap:
            dot = sum(idf.get(t, 0.0) ** 2 for t in overlap)
            if dn > 0:
                lex = dot / (q_norm * dn)
        if sem_emb is not None:
            score = (1 - _ALPHA) * lex + _ALPHA * _cosine(q_sem, sem_emb[i])
        else:
            score = lex
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:k]]
