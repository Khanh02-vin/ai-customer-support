"""Benchmark retrieval trên BÀI VIẾT CHỌN LỌC Wikipedia tiếng Việt.

Data: Thể loại:Bài viết chọn lọc trên vi.wikipedia.org (480 bài, chất lượng
      cao, license CC-BY-SA). Nội dung bài TẢI LÚC CHẠY qua API + cache vào
      data/wiki_cache/ (gitignored) — KHÔNG commit nội dung bài vào repo
      (chỉ commit câu hỏi tự viết + số liệu benchmark).
Queries: 25 câu hỏi tiếng Việt tự nhiên tự viết (data/wiki_queries.jsonl),
         GT = bài chứa đáp án (key theo title).
KB: chunk nội dung bài (không index title — retriever phải khớp query→content),
    giống setup benchmark Tiki.
Metric: hit@k (k=1,3,5), MRR. Không dùng semantic (không thêm dep).

Chạy: python tests/benchmark_wiki.py > tests/wiki_result.txt
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from hashlib import sha1
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb.retriever import chunk_text, retrieve
from src.domain.models import KBEntry

DATA = Path(__file__).parent.parent / "data"
CACHE = DATA / "wiki_cache"
API = "https://vi.wikipedia.org/w/api.php"
UA = "RetrievalBenchmark/1.0 (research; contact: takaokaginji@gmail.com)"
N_ARTICLES = 120
MIN_CHARS = 2000  # bỏ bài quá ngắn (stub/redirect)
CAT = "Thể loại:Bài viết chọn lọc"
QUERIES = DATA / "wiki_queries.jsonl"


def api(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def article_titles(n: int) -> list:
    """Danh sách bài chọn lọc — deterministic: sort theo title, lấy đều khắp."""
    d = api({"action": "query", "list": "categorymembers",
             "cmtitle": CAT, "cmtype": "page", "cmlimit": "500", "format": "json"})
    titles = sorted(x["title"] for x in d["query"]["categorymembers"])
    return titles[:: len(titles) // n][:n]


def fetch_articles(titles: list) -> dict:
    """Tải extract từng bài (API trả extract 1 trang/lần), cache data/wiki_cache/."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in titles:
        key = sha1(t.encode()).hexdigest()[:12]
        p = CACHE / f"{key}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
        else:
            r = api({"action": "query", "prop": "extracts", "explaintext": "1",
                     "titles": t, "format": "json"})
            d = next(iter(r["query"]["pages"].values()))
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            time.sleep(0.5)
        text = d.get("extract", "")
        if len(text) >= MIN_CHARS:
            out[d.get("title", t)] = text
    return out


def build_kb(articles: dict):
    """Chunk nội dung bài (không index title) → List[KBEntry] + map title→chunk ids."""
    entries, art_chunk_ids = [], {}
    for title, text in articles.items():
        chunks = [c for c in chunk_text(text, size=300, overlap=40) if len(c) >= 20]
        if not chunks:
            continue
        ids = set()
        for idx, chunk in enumerate(chunks):
            cid = f"{title[:20]}_{idx}"
            ids.add(cid)
            entries.append(KBEntry(id=cid, title=title, content=chunk, doc_name="wikipedia-vi"))
        art_chunk_ids[title] = ids
    return entries, art_chunk_ids


def load_queries():
    return [json.loads(l) for l in QUERIES.open(encoding="utf-8") if l.strip()]


def main():
    print("=" * 60)
    print("RETRIEVAL — BÀI VIẾT CHỌN LỌC WIKIPEDIA TIẾNG VIỆT (CC-BY-SA)")
    t0 = time.perf_counter()
    titles = article_titles(N_ARTICLES)
    articles = fetch_articles(titles)
    print(f"Bài tải: {len(articles)}/{len(titles)} (>= {MIN_CHARS} chars)")
    entries, art_chunk_ids = build_kb(articles)
    print(f"Chunks: {len(entries)}, bài có KB: {len(art_chunk_ids)}")

    queries = load_queries()
    queries = [q for q in queries if q["title"] in art_chunk_ids]
    ks = [1, 3, 5]
    hits = {k: 0 for k in ks}
    mrr_sum = 0.0
    fails = []
    for q in queries:
        result = retrieve(q["question"], entries, k=max(ks), semantic=False)
        gt = art_chunk_ids[q["title"]]
        for k in ks:
            if set(r.id for r in result[:k]) & gt:
                hits[k] += 1
        for i, r in enumerate(result):
            if r.id in gt:
                mrr_sum += 1.0 / (i + 1)
                break
        else:
            fails.append((q["question"], q["title"]))
    n = len(queries)
    dt = time.perf_counter() - t0
    print(f"Queries: {n} (tự viết, GT = bài chứa đáp án)\n")
    print(f"{'Metric':<12}{'value':>10}")
    print("-" * 24)
    for k in ks:
        print(f"{('hit@' + str(k)):<12}{hits[k] / n * 100:>9.1f}%")
    print(f"{'MRR':<12}{mrr_sum / n:>10.3f}")
    print(f"\nFails (query không tìm thấy bài trong top-{max(ks)}): {len(fails)}/{n}")
    for question, title in fails[:15]:
        print(f"  - {question[:80]}")
    print(f"\nTime: {dt:.0f}s (cache nếu đã tải)")


if __name__ == "__main__":
    main()
