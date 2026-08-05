# Dataset sources — dữ liệu thật dùng cho benchmark

## 1. Tiki Help Center — 107 bài viết thật (committed)

- Nguồn: `https://hotro.tiki.vn/` (Help Center chính thức của Tiki)
- Thu thập: browser automation (playwright domSnapshot + locator innerText) — 107 bài FAQ, mỗi bài gồm title + content
- Local: `data/tiki_faq_raw.json` (committed) → dùng cho 2 benchmark:
  - `tests/benchmark_tiki.py` — query = tiêu đề bài (107 câu)
  - `tests/benchmark_tiki_natural.py` — 22 câu hỏi tự nhiên paraphrase
- License: nội dung công khai của Tiki — dùng cho benchmark cá nhân

## 2. Tiki natural queries — 22 câu hỏi tự viết (committed)

- `data/tiki_queries_natural.jsonl`: 22 câu hỏi kiểu người dùng thật (paraphrase tiêu đề, không dùng nguyên văn), GT = bài gốc theo URL
- Đóng lỗ hổng benchmark "query = tiêu đề quá dễ"

## 3. Enterprise FAQ — controlled (committed)

- `kb/enterprise_faq.jsonl` (21 bài chính sách TMĐT) + `data/qa_pairs.jsonl` (31 QA paraphrase)
- **Controlled data, không phải thật** — dùng để kiểm tra regression cơ bản (hit@3 90.3%), không phải claim "real data"

## Verify

```bash
sha256sum -c data/checksums.sha256
python tests/benchmark_tiki.py          # 107 title queries
python tests/benchmark_tiki_natural.py  # 22 natural queries
pytest tests/test_retrieval_regression.py
```
