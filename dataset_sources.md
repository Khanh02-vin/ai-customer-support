# Dataset sources — dữ liệu thật dùng cho benchmark

## 1. ~~Tiki Help Center~~ — ĐÃ GỠ vì lý do pháp lý

- `data/tiki_faq_raw.json` + `data/tiki_queries_natural.jsonl` (nội dung scrape từ `hotro.tiki.vn`) **đã bị xóa khỏi git history 08/2026** — tái phân phối nội dung có bản quyền của Tiki (rủi ro DMCA + vi phạm ToS).
- Số liệu benchmark Tiki trong README là **lịch sử, không tái hiện được**. Script `benchmark_tiki*.py` giữ làm tài liệu phương pháp.
- Bài học áp dụng: repo public chỉ chứa code + metrics + link, không commit dữ liệu scrape từ bên thứ ba.

## 2. Enterprise FAQ — controlled (committed)

- `kb/enterprise_faq.jsonl` (21 bài chính sách TMĐT) + `data/qa_pairs.jsonl` (31 QA paraphrase)
- **Controlled data, không phải thật** — dùng để kiểm tra regression cơ bản (hit@3 90.3%), không phải claim "real data"

## 3. Bài viết chọn lọc Wikipedia tiếng Việt (tải lúc chạy, không commit nội dung)

- Nguồn: `vi.wikipedia.org` API — Thể loại:Bài viết chọn lọc, 120 bài (deterministic: sort theo title, lấy đều `titles[::4][:120]`)
- Thu thập: `prop=extracts&explaintext=1`, từng bài (API trả extract 1 trang/lần), cache `data/wiki_cache/` (gitignored) → rerun không gọi lại API
- Queries: `data/wiki_queries.jsonl` (30 câu tự viết, 25 có entity đặc trưng + 5 paraphrase khó), GT = bài chứa đáp án theo title
- Dùng cho: `tests/benchmark_wiki.py` — TF-IDF thuần, hit@1 90.0%, MRR 0.933
- License: **CC-BY-SA** — nội dung thuộc Wikipedia; repo chỉ giữ metrics + câu hỏi tự viết, KHÔNG giữ nội dung bài

## Verify

```bash
sha256sum -c data/checksums.sha256
python tests/benchmark_wiki.py          # 30 queries, tự tải bài nếu cache thiếu
pytest tests/test_retrieval_regression.py
```
