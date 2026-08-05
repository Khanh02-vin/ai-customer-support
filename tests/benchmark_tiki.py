"""Benchmark retrieval trên FAQ THẬT của Tiki Help Center.

Data: data/tiki_faq_raw.json — 107 bài viết (title + content) scrape từ hotro.tiki.vn
Queries: tiêu đề bài viết (câu hỏi tự nhiên tiếng Việt của khách hàng Tiki)
KB: chunk content bài viết (KHÔNG index tiêu đề — retriever phải khớp query→content)
Metric: hit@k (k=1,3,5), MRR

Chạy: python tests/benchmark_tiki.py > tests/tiki_baseline.txt
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry

RAW = Path(__file__).parent.parent / "data" / "tiki_faq_raw.json"


def clean_article(raw_text: str) -> tuple:
    """Tách (title, content). Bỏ dòng metadata 'Cập nhật lần cuối'/'Lượt xem'."""
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
    print("CUSTOMER SUPPORT RETRIEVAL BENCHMARK — TIKI FAQ THẬT (hotro.tiki.vn)")
    print("=" * 72)

    arts = json.load(open(RAW, encoding="utf-8"))
    print(f"\n{len(arts)} bài viết thật từ Tiki Help Center\n")

    # Build KB: chunks per article (content only, không có title)
    entries = []
    art_chunk_ids = {}
    idx = 0
    usable = 0
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
        art_chunk_ids[title] = set(ids)
        usable += 1
    print(f"KB: {len(entries)} chunks từ {usable} articles (content-only)\n")

    # Queries = article titles (câu hỏi thật của khách)
    queries = [(a["text"].splitlines()[0].strip(), a["text"].splitlines()[0].strip())
               for a in arts]
    queries = [(t, t) for t, _ in queries if t in art_chunk_ids]
    total = len(queries)
    print(f"Queries: {total} câu hỏi (tiêu đề bài viết Tiki)\n")

    ks = [1, 3, 5]
    counts = {k: 0 for k in ks}
    mrrs = []
    fails = []

    for title, _ in queries:
        result = retrieve(title, entries, k=max(ks), semantic=True)
        gt = art_chunk_ids[title]
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
            fails.append(title)

    print(f"{'Metric':<12}{'value':>10}")
    print("-" * 24)
    avg_mrr = sum(mrrs) / total
    for k in ks:
        print(f"{'hit@' + str(k):<12}{counts[k] / total * 100:>9.1f}%")
    print(f"{'MRR':<12}{avg_mrr:>10.3f}")
    print(f"\nFails (query không tìm thấy article của mình trong top-5): {len(fails)}/{total}")
    for f in fails[:15]:
        print(f"  - {f[:80]}")

    print(f"\nMethod: token-overlap coverage (stdlib, không vector DB)")
    print(f"KB không index title — retriever phải khớp query→content thật")


if __name__ == "__main__":
    main()