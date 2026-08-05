"""Tune hybrid α trên 15 câu tune, eval trên 7 câu held-out (seed=42).

Trước: α sweep trên CHÍNH 22 câu benchmark → nghi overfit (số lạc quan).
Tách 7 câu làm held-out không tham gia sweep để xác nhận α generalizable,
theo đúng quy trình đã dùng cho RAG (tune_rag_alpha.py).
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.benchmark_tiki_semantic import build_kb, get_embeddings, evaluate

QUERIES = Path(__file__).parent.parent / "data" / "tiki_queries_natural.jsonl"
SEED = 42


def main():
    entries, art_chunks = build_kb()
    queries = [json.loads(l) for l in open(QUERIES, encoding="utf-8")]
    emb = get_embeddings([e.content for e in entries])

    ids = list(range(len(queries)))
    random.Random(SEED).shuffle(ids)
    held, tune_ids = ids[:7], ids[7:]
    tune = [queries[i] for i in tune_ids]
    held_q = [queries[i] for i in held]
    print("=" * 72)
    print("CS HYBRID α TUNING — held-out split (15 tune / 7 eval)")
    print("Split: seed=42, held-out = 7/22 câu tự nhiên (không tham gia sweep)")
    print(f"held-out ids: {sorted(held)}")
    print(f"tune: {len(tune)} câu | held-out: {len(held_q)} câu\n")

    best_a, best_m = None, -1.0
    print("Sweep α trên tune set (metric: MRR):")
    for alpha in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
        h1, h3, h5, m = evaluate(tune, entries, art_chunks, emb, alpha)
        print(f"  α={alpha:.1f}: hit@1 {h1:.1%}  hit@3 {h3:.1%}  hit@5 {h5:.1%}  MRR {m:.3f}")
        if m > best_m:
            best_a, best_m = alpha, m
    print(f"\nBest α trên tune: {best_a} (MRR {best_m:.3f})\n")

    h1, h3, h5, m = evaluate(held_q, entries, art_chunks, emb, best_a)
    print(f"Eval trên 7 câu HELD-OUT (α={best_a} — best trên tune):")
    print(f"  hit@1 {h1:.1%}  hit@3 {h3:.1%}  hit@5 {h5:.1%}  MRR {m:.3f}")
    h1, h3, h5, m = evaluate(held_q, entries, art_chunks, emb, 0.2)
    print(f"Eval trên 7 câu HELD-OUT (α=0.2 — giá trị đang deploy):")
    print(f"  hit@1 {h1:.1%}  hit@3 {h3:.1%}  hit@5 {h5:.1%}  MRR {m:.3f}")
    h1, h3, h5, m = evaluate(queries, entries, art_chunks, emb, best_a)
    print(f"Eval trên TOÀN BỘ 22 câu (cùng α={best_a}): hit@1 {h1:.1%}  hit@3 {h3:.1%}  hit@5 {h5:.1%}  MRR {m:.3f}")


if __name__ == "__main__":
    main()
