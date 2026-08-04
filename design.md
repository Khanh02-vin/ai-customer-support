# Thiết kế giao diện — AI Customer Support

Dashboard admin dark SaaS: sidebar điều hướng + thẻ thống kê + quản lý ticket dạng hội thoại.

## Design tokens (nguồn chuẩn — đổi màu toàn app tại `frontend/src/styles.css`)

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--bg` | `#0f1117` | Nền app |
| `--surface` | `#161a22` | Card |
| `--surface-2` | `#1d222d` | Input, hover |
| `--border` | `#262c38` | Viền |
| `--text` | `#e2e8f0` | Chữ chính |
| `--text-dim` | `#94a3b8` | Phụ đề |
| `--accent` | `#2563eb` | Nút, active |
| `--accent-hover` | `#1d4ed8` | Hover nút |
| `--success` | `#22c55e` | Đã giải quyết |
| `--warning` | `#eab308` | Chờ người |
| `--danger` | `#ef4444` | Xóa |
| `--sidebar-bg` | `#0b0e13` | Thanh bên |

## Typography

| Biến | Cỡ | Vai trò |
|---|---|---|
| `--fs-xs` | 12px | Nhãn, badge |
| `--fs-md` | 15px | Nội dung (body) |
| `--fs-lg` | 24px | Tiêu đề trang |
| `--fs-xl` | 28px | Số thống kê |

Ratio giữa các bước ≥ 1.25 (WCAG AA + rule flat-type-hierarchy). Không có font 16px orphan (body khai báo `font-size` tường minh).

## Bố cục

- **Sidebar** 220px: brand + LineSidebar (4 mục: Tổng quan, Ticket, Kiến thức, Cài đặt) + user card.
- **Tổng quan**: 4 stat card (CountUp + sparkline 7 ngày) + bảng ticket gần đây.
- **Ticket**: 2 cột — danh sách trái, hội thoại phải (bubble user/bot, badge tool, khung trả lời nhân viên, select trạng thái).
- **Kiến thức**: upload txt/pdf → chunk, bảng tài liệu + xóa.
- **Cài đặt**: tiêu đề, tên bot, lời chào, màu chủ đạo (color picker).
- Mobile (< 760px): sidebar thành top bar.

## Badge trạng thái

`open` = xanh accent · `waiting_human` = vàng · `resolved` = xanh lá · `closed` = xám.

## React bits

- `LineSidebar` — sidebar hiệu ứng (zero-dep)
- `Aurora` + `SpotlightCard` — màn đăng nhập (ogl)
- `CountUp` + `Sparkline` — thẻ thống kê (tự viết, không dep)
