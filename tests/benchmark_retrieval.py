"""Benchmark retrieval tren enterprise FAQ tieng Viet that.

KB: kb/enterprise_faq.jsonl - 21 articles chinh sach BH/Giao hang/Doi tra/Tien bao
QA: data/qa_pairs.jsonl - 31 cau hoi paraphrase tu nhien tu KB content
Metric: hit@k (k=1,3,5), MRR (Mean Reciprocal Rank)

Chay: python tests/benchmark_retrieval.py > tests/cs_baseline.txt (baseline)
      sau do sua retriever roi chay lai > tests/cs_improved.txt
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry

KB_PATH = Path(__file__).parent.parent / "kb" / "enterprise_faq.jsonl"
QA_PATH = Path(__file__).parent.parent / "data" / "qa_pairs.jsonl"


def build_kb():
    """Xay dung DB chua chunks + mapping article_id -> list of chunk_ids."""
    arts = []
    for line in open(KB_PATH, encoding="utf-8"):
        arts.append(json.loads(line.strip()))

    all_entries = []
    art_to_chunk_ids = {}
    idx = 0
    for art in arts:
        ids = []
        parts = chunk_text(art["content"], size=300, overlap=40)
        if not parts:
            # Article too short -> treat as single chunk or skip
            cid = "%s_%d" % (art["id"], idx)
            all_entries.append(KBEntry(id=cid, title=art["title"], content=art["content"]))
            ids.append(cid)
            art_to_chunk_ids[art["id"]] = set(ids)
            idx += 1
            continue
        for part in parts:
            cid = "%s_%d" % (art["id"], idx)
            ids.append(cid)
            all_entries.append(KBEntry(id=cid, title=art["title"], content=part))
            idx += 1
        art_to_chunk_ids[art["id"]] = set(ids)

    print("KB loaded: %d chunks from %d articles" % (len(all_entries), len(arts)))
    return all_entries, art_to_chunk_ids, len(arts)


def main():
    print("=" * 72)
    print("CUSTOMER SUPPORT RETRIEVAL BENCHMARK -- Enterprise FAQ VN")
    print("KB: %s | QA: %s" % (KB_PATH, QA_PATH))
    print("=" * 72)

    n_arts = len([l for l in open(KB_PATH, encoding="utf-8")])
    print("\n%d articles (%s)" % (n_arts, KB_PATH.name))

    entries, art_to_cid, n = build_kb()

    qas = []
    for line in open(QA_PATH, encoding="utf-8"):
        stripped = line.strip()
        if stripped:
            qas.append(json.loads(stripped))
    total = len(qas)
    print("QA pairs: %d queries\n" % total)

    ks = [1, 3, 5]
    counts = {k: 0 for k in ks}
    mrrs = []
    fails = []

    for qa in qas:
        result = retrieve(qa["query"], entries, k=max(ks))
        gt_ids = art_to_cid.get(qa["answer_id"], set())

        for k in ks:
            top_k = set(r.id for r in result[:k])
            if top_k & gt_ids:
                counts[k] += 1

        found = False
        for i, r in enumerate(result, 1):
            if r.id in gt_ids:
                mrrs.append(1.0 / i)
                found = True
                break
        if not found:
            mrrs.append(0.0)

        if not any(r.id in gt_ids for r in result):
            fails.append((qa["query"], qa["answer_id"]))

    # Print results
    header = "%-25s" % "Metric"
    for k in ks:
        header += "%6s" % ("hit@" + str(k))
    header += "   MRR"
    print(header)
    print("-" * 50)

    avg_mrr = sum(mrrs) / total if total else 0
    for k in ks:
        rate = counts[k] / total * 100
        row = "%-25s" % ("hit@" + str(k))
        row += "%6.1f%%" % rate
        if k == ks[-1]:
            row += "   %.3f" % avg_mrr
        print(row)

    if fails:
        print("\n--- %d fail ---" % len(fails))
        for q, aid in fails[:20]:
            print("  %s -> %s" % (q[:70], aid))

    print("\nMethod: token-overlap coverage (stdlib, khong vector DB)")
    print("Tokenization: lowercase + word + char-bigram")


if __name__ == "__main__":
    main()