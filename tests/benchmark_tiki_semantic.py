"""Test: hybrid lexical TF-IDF + semantic (multilingual-e5-small) trên Tiki FAQ thật.

So sánh với retriever hiện tại (TF-IDF thuần). Sweep α để xem semantic cải thiện bao nhiêu.
e5 cần prefix: query = "query: ...", passage = "passage: ..." (đúng quy ước training).
Chạy: python tests/benchmark_tiki_semantic.py   (encode ~992 chunk, 5-15 phút)
"""
import json
import math
import os
import pickle
import re
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, _tokens
from src.domain.models import KBEntry

RAW = Path(__file__).parent.parent / "data" / "tiki_faq_raw.json"
QUERIES_NATURAL = Path(__file__).parent.parent / "data" / "tiki_queries_natural.jsonl"
CACHE = Path(__file__).parent.parent / "data" / "kb_emb_cache.pkl"


def clean_article(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    title = lines[0] if lines else ""
    content_lines = [l for l in lines[1:] if not re.match(r"^(Cập nhật lần cuối|Lượt xem:)", l)]
    return title, "\n".join(content_lines)


def norm(s):
    return re.sub(r"\s+", " ", s.strip()).lower()


def get_embeddings(texts):
    if CACHE.exists():
        d = pickle.loads(CACHE.read_bytes())
        if len(d["texts"]) == len(texts):
            return d["emb"]
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    emb = model.encode(["passage: " + t for t in texts], batch_size=8).tolist()
    CACHE.write_bytes(pickle.dumps({"texts": texts, "emb": emb}))
    return emb


def build_kb():
    arts = json.load(open(RAW, encoding="utf-8"))
    entries, art_chunks = [], {}
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
        art_chunks[a["url"]] = set(ids)
    return entries, art_chunks


def evaluate(queries, entries, art_chunks, emb, alpha):
    """hybrid: (1-alpha)*TF-IDF + alpha*semantic."""
    entry_tokens = [_tokens(e.content) for e in entries]
    df = Counter()
    for tk in entry_tokens:
        for t in tk:
            df[t] += 1
    n = len(entries)
    idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
    d_norm = [math.sqrt(sum(idf.get(t, 0.0) ** 2 for t in tk)) for tk in entry_tokens]

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    q_embs = model.encode(["query: " + q["question"] for q in queries], batch_size=8).tolist()

    hits = {1: 0, 3: 0, 5: 0}
    mrr = 0.0
    for qi, q in enumerate(queries):
        qt = _tokens(q["question"])
        qn = math.sqrt(sum(idf.get(t, 0.0) ** 2 for t in qt))
        scored = []
        for i, (e, tk, dn) in enumerate(zip(entries, entry_tokens, d_norm)):
            overlap = qt & tk
            lex = 0.0
            if overlap and qn > 0 and dn > 0:
                dot = sum(idf.get(t, 0.0) ** 2 for t in overlap)
                lex = dot / (qn * dn)
            sem = _cosine(q_embs[qi], emb[i])
            score = (1 - alpha) * lex + alpha * sem
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        gt = art_chunks[q["url"]]
        for k in (1, 3, 5):
            if set(rr[1].id for rr in scored[:k]) & gt:
                hits[k] += 1
        rank = next((i for i, (_, r) in enumerate(scored) if r.id in gt), None)
        mrr += 1.0 / (rank + 1) if rank is not None else 0.0
    tot = len(queries)
    return hits[1] / tot, hits[3] / tot, hits[5] / tot, mrr / tot


def _cosine(a, b):
    if not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def main():
    print("=" * 72)
    print("CS HYBRID TEST — lexical TF-IDF + e5-small semantic (Tiki FAQ thật)")
    entries, art_chunks = build_kb()
    queries = [json.loads(l) for l in open(QUERIES_NATURAL, encoding="utf-8")]
    print(f"KB: {len(entries)} chunks | {len(queries)} natural queries\n")

    t0 = time.perf_counter()
    texts = [e.content for e in entries]
    emb = get_embeddings(texts)
    print(f"encode: {time.perf_counter() - t0:.0f}s (cache: {CACHE.name})\n")

    print(f"{'alpha':<8}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}")
    print("(alpha=0.0 tương đương retriever hiện tại)")
    for alpha in [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]:
        h1, h3, h5, m = evaluate(queries, entries, art_chunks, emb, alpha)
        print(f"{alpha:<8.1f}{h1:>8.1%}{h3:>8.1%}{h5:>8.1%}{m:>8.3f}")


if __name__ == "__main__":
    main()
