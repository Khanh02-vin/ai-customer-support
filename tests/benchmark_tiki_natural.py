"""Benchmark retrieval với CÂU HỎI TỰ NHIÊN trên FAQ THẬT Tiki.

Đóng lỗ hổng của benchmark cũ (query = tiêu đề bài viết — quá dễ):
- KB: 107 bài FAQ thật từ hotro.tiki.vn (content-only chunks, không index title)
- Queries: 22 câu hỏi tự nhiên kiểu người dùng (paraphrase, có cả cách viết
  tự nhiên không khớp từng từ tiêu đề) — data/tiki_queries_natural.jsonl
- GT: bài viết gốc mà câu hỏi được viết ra (theo url)
Metric: hit@1, hit@3, hit@5, MRR.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry

RAW = Path(__file__).parent.parent / "data" / "tiki_faq_raw.json"
QUERIES = Path(__file__).parent.parent / "data" / "tiki_queries_natural.jsonl"


def clean_article(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    title = lines[0] if lines else ""
    content_lines = []
    for l in lines[1:]:
        if re.match(r"^(Cập nhật lần cuối|Lượt xem:)", l):
            continue
        content_lines.append(l)
    return title, "\n".join(content_lines)


def main():
    print("=" * 72)
    print("CUSTOMER SUPPORT — TIKI FAQ THẬT + CÂU HỎI TỰ NHIÊN")
    print("=" * 72)

    arts = json.load(open(RAW, encoding="utf-8"))
    entries = []
    art_chunk_ids = {}
    idx = 0
    for a in arts:
        title, content = clean_article(a["text"])
        if not title or len(content) < 300:
            continue
        parts = chunk_text(content, size=300, overlap=40)
        ids = []
        for p in parts:
            cid = f"{title[:20]}_{idx}"
            ids.append(cid)
            entries.append(KBEntry(id=cid, title=title, content=p))
            idx += 1
        art_chunk_ids[a["url"]] = set(ids)
    print(f"KB: {len(entries)} chunks từ {len(art_chunk_ids)} articles (content-only)\n")

    queries = []
    for line in open(QUERIES, encoding="utf-8"):
        q = json.loads(line)
        if q["url"] in art_chunk_ids:
            queries.append(q)
    print(f"Queries: {len(queries)} câu hỏi tự nhiên (viết tay, paraphrase tiêu đề)\n")

    ks = [1, 3, 5]
    counts = {k: 0 for k in ks}
    mrrs = []
    fails = []

    for q in queries:
        result = retrieve(q["question"], entries, k=max(ks), semantic=True)
        gt = art_chunk_ids[q["url"]]
        for k in ks:
            if set(r.id for r in result[:k]) & gt:
                counts[k] += 1
        found = False
        for i, r in enumerate(result, 1):
            if r.id in gt:
                mrrs.append(1.0 / i)
                found = True
                break
        if not found:
            mrrs.append(0.0)
        if not any(r.id in gt for r in result):
            fails.append(q["question"])

    total = len(queries)
    print(f"{'Metric':<12}{'value':>10}")
    print("-" * 24)
    avg_mrr = sum(mrrs) / total
    for k in ks:
        print(f"{'hit@' + str(k):<12}{counts[k] / total * 100:>9.1f}%")
    print(f"{'MRR':<12}{avg_mrr:>10.3f}")
    print(f"\nFails (không tìm thấy bài đúng trong top-5): {len(fails)}/{total}")
    for f in fails:
        print(f"  - {f[:90]}")


if __name__ == "__main__":
    main()
