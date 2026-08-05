"""Benchmark câu trả lời sinh ra từ retrieval (RAG answer generation).

Pipeline: query → retrieve top-3 (hybrid, như benchmark_tiki_natural) → LLM trả lời
từ context → kiểm tra grounding (chống hallucinate):
  - mọi SỐ trong câu trả lời phải xuất hiện trong context (so chuỗi số thô)
  - câu trả lời phải có ít nhất 1 từ khóa quan trọng của bài GT (title keywords)
Ghi rõ: đây là sanity-check tự động, không phải đo độ đúng ngữ nghĩa.
Chạy: BENCH_LLM=1 python tests/benchmark_answer_gen.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry
from tests.benchmark_tiki_natural import clean_article, RAW, QUERIES
from src.llm.base import OpenAIProvider

CACHE = Path(__file__).parent.parent / "data" / "answer_gen_cache.jsonl"

_SYSTEM = ("Bạn là trợ lý hỗ trợ khách hàng. Trả lời bằng tiếng Việt, CHỈ dùng thông tin "
           "trong đoạn văn bản được cung cấp. Nếu context không có câu trả lời, nói rõ "
           "'Tôi không tìm thấy thông tin này'. Không bịa số liệu. Tối đa 3 câu.")


def _h(q, ctx):
    import hashlib
    return hashlib.sha1((q + "\x00" + ctx).encode()).hexdigest()


def load_cache():
    c = {}
    if CACHE.exists():
        for line in CACHE.open(encoding="utf-8"):
            d = json.loads(line)
            c[d["h"]] = d["answer"]
    return c


loaded_cache = load_cache()


def main():
    arts = json.load(open(RAW, encoding="utf-8"))
    entries = []
    art_chunks = {}
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
        art_chunks[a["url"]] = (title, ids, content)

    queries = [json.loads(l) for l in open(QUERIES, encoding="utf-8") if l.strip()]
    queries = [q for q in queries if q["url"] in art_chunks]
    llm = OpenAIProvider()
    total = len(queries)

    ctx_by_q = {}
    for q in queries:
        result = retrieve(q["question"], entries, k=3, semantic=True)
        ctx_by_q[q["question"]] = "\n---\n".join(r.content for r in result)

    # preload song song
    from concurrent.futures import ThreadPoolExecutor
    todo = {q["question"]: q for q in queries if _h(q["question"], ctx_by_q[q["question"]]) not in loaded_cache}
    new_ans = {}
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(llm.complete, _SYSTEM,
                              f"Context:\n{ctx_by_q[q]}\n\nCâu hỏi: {q}"): q
                    for q in todo}
            for fut in futs:
                q = futs[fut]
                try:
                    new_ans[q] = fut.result()
                except Exception as e:
                    new_ans[q] = f"<!-- ERROR {e} -->"
        with CACHE.open("a", encoding="utf-8") as f:
            for q, ans in new_ans.items():
                h = _h(q, ctx_by_q[q])
                loaded_cache[h] = ans
                f.write(json.dumps({"h": h, "answer": ans}, ensure_ascii=False) + "\n")

    stats = {"answered": 0, "grounded_all_numbers": 0, "has_gt_keyword": 0}
    samples = []
    for q in queries:
        ans = loaded_cache.get(_h(q["question"], ctx_by_q[q["question"]]), "")
        if not ans or "không tìm thấy" in ans:
            continue
        stats["answered"] += 1
        ctx = ctx_by_q[q["question"]]
        ctx_nums = set(re.findall(r"\d[\d.,%]*", ctx))
        ans_nums = set(re.findall(r"\d[\d.,%]*", ans))
        odd = ans_nums - ctx_nums
        if not odd:
            stats["grounded_all_numbers"] += 1
        title, _, _ = art_chunks[q["url"]]
        kw = [w for w in re.split(r"\s+", title.lower()) if len(w) > 4]
        if kw and any(w in ans.lower() for w in kw):
            stats["has_gt_keyword"] += 1
        if len(samples) < 6:
            samples.append((q["question"], title, ans[:200]))

    print("=" * 72)
    print("CUSTOMER SUPPORT — RAG ANSWER GENERATION (tiki FAQ thật, 22 câu hỏi tự nhiên)")
    print("Metric: grounding tự động (số trong câu trả lời phải có trong context) — "
          "không phải đo độ đúng ngữ nghĩa")
    print("=" * 72)
    print(f"Trả lời được (không từ chối):      {stats['answered']}/{total}")
    print(f"Grounding: mọi số đều nằm trong context: {stats['grounded_all_numbers']}/{stats['answered']}")
    print(f"Có từ khóa chính của bài GT:       {stats['has_gt_keyword']}/{stats['answered']}")
    print("\n--- 6 mẫu (câu hỏi | bài GT | trả lời) ---")
    for q, t, a in samples:
        print(f"Q: {q}\n  GT: {t}\n  A: {a}\n")


if __name__ == "__main__":
    main()
