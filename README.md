# AI Customer Support

Chatbot hỗ trợ khách hàng có agent: RAG trên knowledge base + tool-use + memory theo phiên + bàn giao người thật (escalation). Widget chat nhúng vào website, dashboard quản trị cho nhân viên.

## Tính năng

- **Agent loop tự viết** (không framework): LLM quyết định gọi công cụ, hệ thống thực thi, lặp tối đa 3 vòng rồi bàn giao an toàn.
- **RAG không cần vector DB**: chunk tài liệu + retrieval bằng token-overlap, xử lý tiếng Việt (từ + char-bigram).
- **Hard-guard chống hallucination**: câu hỏi chạm chủ đề công ty (giá, bảo hành, giao hàng...) mà LLM trả lời thẳng → hệ thống ép tra knowledge base trước, không cho trả lời từ kiến thức riêng.
- **Memory theo phiên**: cùng `session_id` → cùng ticket; lịch sử 10 lượt gần nhất đưa vào context mỗi lần hỏi.
- **Escalation**: agent tự bàn giao khi thiếu thông tin hoặc khách yêu cầu người thật; nhân viên trả lời qua dashboard → ticket quay lại quy trình.
- **Widget chat nhúng**: 1 file JS thuần, không dependency, cấu hình màu/tên qua API công khai.
- **Dashboard admin**: thống kê, quản lý ticket + trả lời, upload/duyệt knowledge base, cấu hình widget.
- **Fallback RAG thuần**: không có LLM key vẫn trả lời được từ knowledge base (không 500).

## Demo

![Demo widget chat — agent tra KB + bàn giao nhân viên](mockup/demo.gif)

| Đăng nhập | Dashboard | Ticket |
|---|---|---|
| ![Đăng nhập](mockup/ui-login.png) | ![Dashboard](mockup/ui-overview.png) | ![Ticket](mockup/ui-tickets.png) |

| Kiến thức | Cài đặt | Widget |
|---|---|---|
| ![Kiến thức](mockup/ui-kb.png) | ![Cài đặt](mockup/ui-settings.png) | ![Widget mở](mockup/widget-open.png) |

## Kiến trúc

```
src/
  agent/     agent loop + tool registry (search_knowledge, escalate)
  kb/        chunk tài liệu + retrieval (stdlib)
  llm/       provider OpenAI-compatible (qwencoder mặc định), mock cho test
  domain/    pydantic models: Ticket, KBEntry, WidgetConfig...
  store/     SQLite: tickets (messages = memory), kb, kb_docs, widget_config
  auth/      pbkdf2 hash + JWT (HS256)
  app.py     FastAPI: /chat (public), /kb /tickets /stats /config (admin JWT)
widget/      widget.js nhúng + trang demo
frontend/    React admin (Vite), build ra dist — server tự phục vụ
tests/       pytest: retriever, agent loop, API
```

### Agent loop

1. LLM nhận system prompt mô tả công cụ + lịch sử hội thoại.
2. Trả JSON `{"tool": "...", "args": {...}}` → hệ thống thực thi, kết quả đưa lại context.
3. Trả văn bản thường → kết thúc. Escalate hoặc hết vòng lặp → chuyển `waiting_human`.

## Chạy

```bash
pip install -r requirements.txt
python -m uvicorn src.app:app --host 0.0.0.0 --port 8005
```

- UI admin: http://localhost:8005/ — tạo tài khoản mới hoặc demo/demo1234
- Widget demo: http://localhost:8005/widget/
- API health: http://localhost:8005/health

Frontend build lại: `cd frontend && npm install && npm run build` (server tự phục vụ `frontend/dist`).

## Cấu hình (.env)

| Biến | Mặc định | Mô tả |
|---|---|---|
| `LLM_BASE_URL` | https://api.qwencoder.cloud/api/v1 | OpenAI-compatible endpoint |
| `LLM_API_KEY` | (trống) | Không có key → fallback RAG thuần |
| `LLM_MODEL` | qwen3.7-max | Model agent |
| `JWT_SECRET` | dev-secret... | Đổi khi deploy |

## Demo

```bash
python main.py
```

Đăng ký admin → upload `kb-demo.txt` → chat 3 lượt (tra cứu KB → escalate → hỏi tiếp, memory giữ ngữ cảnh) → nhân viên trả lời → thống kê.

## Test

```bash
python -m pytest tests/ -q
```

27 test: retrieval tiếng Việt, agent loop (guard KB, escalate, tool lỗi), API (auth JWT, KB, chat, ticket 404/400), regression enterprise FAQ.

## Benchmark — Real-world Retrieval on Vietnamese FAQs

### 1. Tiki Help Center (hotro.tiki.vn) — 107 bài viết thật

> ⚠️ **Dữ liệu đã gỡ vì lý do pháp lý.** `data/tiki_faq_raw.json` + `data/tiki_queries_natural.jsonl` (nội dung scrape từ Tiki Help Center) đã bị xóa khỏi git history 08/2026 — tái phân phối nội dung có bản quyền của Tiki. Số liệu dưới đây là **lịch sử, không tái hiện được**; script `benchmark_tiki*.py` giữ lại làm tài liệu phương pháp. Thay thế cho dữ liệu thật không-phạm: mục 3 (Wikipedia).

Data scrape qua browser automation từ Tiki Help Center. KB = chunk nội dung không index title → retriever phải khớp query→content tự nhiên. Query = tiêu đề bài (câu hỏi thật của khách VN):

| Metric | Token-overlap (baseline) | TF-IDF + stopwords | **Hybrid + e5-small** |
|---|---|---|---|
| hit@1 | 37.4% | 46.7% | **49.5%** |
| hit@3 | 55.1% | 65.4% | **68.2%** |
| hit@5 | 67.3% | 76.6% | **75.7%** |
| MRR | 0.478 | 0.569 | **0.591** |

TF-IDF khắc phục từ thường (tiki, tôi, làm, tại) lấn át token hiếm (bảo hành, đổi trả). Lần 2: thêm VN stopwords + lọc char-bigram chứa space/punct (noise như `"h "`, `"y?"`) — quan trọng với câu hỏi tự nhiên (xem mục 2). Lần 3: hybrid TF-IDF + `intfloat/multilingual-e5-small` (α=0.2, sweep trên 22 câu tự nhiên; semantic layer tùy chọn `retrieve(semantic=True)`, fallback TF-IDF nếu chưa cài sentence-transformers).

### 1b. Câu hỏi tự nhiên — 22 câu paraphrase kiểu người dùng thật

`data/tiki_queries_natural.jsonl`: 22 câu hỏi viết tay kiểu khách hàng thật (không dùng tiêu đề), GT = bài gốc theo URL. Đóng lỗ hổng benchmark cũ "query = tiêu đề quá dễ":

| Metric | TF-IDF thuần | Hybrid + e5-small | **+ LLM re-rank top-5** |
|---|---|---|---|
| hit@1 | 36.4% | 45.5% | **50.0%** |
| hit@3 | 54.5% | 63.6% | **72.7%** |
| hit@5 | 68.2% | 72.7% | 72.7% |
| MRR | 0.486 | 0.548 | **0.591** |

Lần 4 — **LLM re-rank top-5** (qwen3.7-max, `BENCH_LLM=1`): LLM chọn chunk trả lời đúng trong top-5 → đẩy lên rank 1. hit@1 45.5→**50.0%**, hit@3 63.6→**72.7%**, MRR 0.548→**0.591**. Trần: hit@5 72.7% không đổi — re-rank chỉ đổi thứ tự trong top-5, không thêm mới (giới hạn retrieval thật). Quyết định re-rank (chỉ số chunk, không hallucinate được) cache trong `data/llm_rerank_cache.jsonl` → chạy lại không cần API key.

**RAG answer generation** (`tests/benchmark_answer_gen.py`, grounding check tự động — không phải đo độ đúng ngữ nghĩa): 13/22 câu hỏi trả lời được từ top-3 context, **12/13** câu trả lời có mọi số nằm trong context (chống hallucinate), 7/13 có từ khóa chính của bài GT. 9 câu còn lại LLM từ chối đúng ("không tìm thấy") — top-3 không chứa context (khớp với hit@3 72.7%).

**Kiểm tra overfit (held-out 15/7, seed=42):** α=0.2 đang deploy đạt held-out hit@3 **71.4%**, MRR 0.588 — TỐT HƠN α=0.8 mà sweep trên 15 câu tune chọn (hit@3 42.9%, MRR 0.527) → xác nhận α=0.2 không phải do tune trên eval set, giá trị chọn ổn định ngoài mẫu (`python tests/tune_tiki_alpha.py`). Lưu ý: 7 câu held-out là mẫu nhỏ, nên dùng như kiểm tra chiều hướng, không phải con số chính.

```bash
python tests/benchmark_tiki_natural.py   # chạy lại (22 câu hỏi tự nhiên, semantic=True)
BENCH_LLM=1 python tests/benchmark_tiki_natural.py   # + LLM re-rank (cache sẵn, không cần key)
BENCH_LLM=1 python tests/benchmark_answer_gen.py     # RAG answer generation + grounding check
python tests/benchmark_tiki_semantic.py  # sweep α để kiểm tra lại tuning
```

### 2. Controlled Enterprise FAQ — 21 bài chính sách TMĐT tự tổng hợp, 31 QA paraphrase

Định lượng mức baseline trên dataset kiểm soát, từ vựng query-content trùng khớp cao hơn thực tế:

| Metric | Kết quả |
|---|---|
| hit@1 | 64.5% |
| hit@3 | 90.3% |
| hit@5 | 93.5% |
| MRR | 0.772 |

```bash
# Tiki FAQ thật (107 queries)
python tests/benchmark_tiki.py                  # chạy lại benchmark
pytest tests/test_retrieval_regression.py       # regression: 8 câu hỏi tìm đúng article top-5
```

```bash
# Enterprise FAQ (31 queries, dataset kiểm soát)
python tests/benchmark_retrieval.py             # chạy lại benchmark
pytest tests/test_retrieval_regression.py       # regression
```

Data: `data/tiki_faq_raw.json` (KB thật từ hotro.tiki.vn — **đã gỡ, xem note mục 1**), `kb/enterprise_faq.jsonl` (KB kiểm soát), `data/qa_pairs.jsonl` (QA pairs). Không sửa test data cũ.

### 3. Bài viết chọn lọc Wikipedia tiếng Việt — 120 bài, 25 câu hỏi tự nhiên

Data: **Thể loại:Bài viết chọn lọc** trên vi.wikipedia.org (120 bài, license **CC-BY-SA** — nội dung thuộc Wikipedia, **tải lúc chạy** qua API + cache `data/wiki_cache/` gitignored, KHÔNG commit nội dung bài; chỉ commit câu hỏi tự viết + số liệu). KB = chunk nội dung không index title, giống setup Tiki. Test generalization của retriever ra ngoài FAQ công ty — corpus đa chủ đề (lịch sử, văn hóa, khoa học, game...):

| Metric | TF-IDF thuần (không semantic) |
|---|---|
| hit@1 | **93.3%** |
| hit@3 | **97.8%** |
| hit@5 | **97.8%** |
| MRR | **0.956** |

45 câu theo 3 mức khó (đo riêng từng nhóm — số thật, không suy đoán): **24 câu entity-rich** (chứa tên riêng hiếm: Saturn V, HCl, Clamp, PopCap) → hit@1 **100%**; **15 câu paraphrase không nhắc title nhưng chứa từ đặc trưng nội dung** (chaebol, Los Alamos, Manhattan, cân bằng thuỷ tĩnh) → hit@1 **100%**; **6 câu paraphrase thuần từ chung** (mức khó thật) → hit@1 **50%** (3/6). Fail duy nhất toàn benchmark thuộc nhóm cuối: "nghệ sĩ qua bộ ria và cây gậy chống" (Charlie Chaplin) — toàn từ chung, không từ đặc trưng để TF-IDF bám vào giữa 25k chunks (bài 80k chars, "bộ ria" chỉ xuất hiện 1-2 lần).

**Phát hiện trung thực:** retriever đạt 100% khi câu hỏi có bất kỳ từ đặc trưng nào; **tụt còn 50% khi paraphrase thuần không từ đặc trưng** — đây chính là nơi cần semantic layer (chưa bật, không thêm dep) hoặc LLM re-rank. Giới hạn khác: corpus là bài dài một-chủ-đề (mỗi chunk chứa nhiều token chủ đề) nên số cao hơn FAQ Tiki (bài ngắn trùng chủ đề) — không so sánh ngang được.

```bash
python tests/benchmark_wiki.py   # chạy lại (tự tải bài qua API nếu cache thiếu)
```

Data: `data/wiki_queries.jsonl` (25 câu hỏi tự viết, GT = bài chứa đáp án theo title).

## API tóm tắt

| Method | Path | Quyền | Mô tả |
|---|---|---|---|
| POST | `/chat` | công khai | 1 lượt hỏi-đáp, `session_id` giữ memory |
| GET | `/widget/config` | công khai | Cấu hình widget |
| POST | `/auth/register` `/auth/login` | — | Admin |
| POST | `/kb/upload` | admin | Upload txt/pdf → chunk → KB |
| GET/DELETE | `/kb/docs` `/kb/docs/{id}` | admin | Quản lý tài liệu |
| GET | `/tickets` `/tickets/{id}` | admin | Danh sách / chi tiết |
| POST | `/tickets/{id}/reply` | admin | Nhân viên trả lời |
| PATCH | `/tickets/{id}` | admin | Đổi trạng thái |
| GET | `/stats` | admin | Tổng ticket, tỷ lệ giải quyết |
| GET/PUT | `/config` | admin | Cấu hình widget |

## Nhúng widget

```html
<script src="http://localhost:8005/widget/widget.js" data-api="http://localhost:8005"></script>
```

Widget tự lấy cấu hình từ `/widget/config` (màu, tên bot, lời chào).
