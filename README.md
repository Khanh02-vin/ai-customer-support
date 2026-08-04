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

23 test: retrieval tiếng Việt, agent loop (guard KB, escalate, tool lỗi), API (auth JWT, KB, chat, ticket 404/400).

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
