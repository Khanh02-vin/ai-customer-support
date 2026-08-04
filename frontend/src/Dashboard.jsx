import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import LineSidebar from "./components/react-bits/LineSidebar.jsx";
import { CountUp, Sparkline } from "./components/mini.jsx";

const NAV = ["Tổng quan", "Ticket", "Kiến thức", "Cài đặt"];
const VIEWS = ["overview", "ticket", "kb", "settings"];

const STATUS = {
  open: { label: "Mở", cls: "open" },
  waiting_human: { label: "Chờ người", cls: "waiting" },
  resolved: { label: "Đã giải quyết", cls: "resolved" },
  closed: { label: "Đóng", cls: "closed" },
};

function fmtDate(s) {
  const d = new Date(s);
  return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" }) +
    " " + d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export default function Dashboard({ user, onLogout }) {
  const [view, setView] = useState(0);
  const [tickets, setTickets] = useState([]);
  const [docs, setDocs] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [sel, setSel] = useState(null);   // ticket đang mở chi tiết
  const [msg, setMsg] = useState(null);   // thông báo nhanh

  async function load() {
    try {
      const [t, d, c, s] = await Promise.all([
        api("/tickets?limit=100"), api("/kb/docs"), api("/config"), api("/stats"),
      ]);
      setTickets(t); setDocs(d.docs); setCfg(c); setStats(s);
      setSel((cur) => cur && t.find((x) => x.id === cur.id) || null);
    } catch { /* token hết hạn → App chuyển login */ }
  }

  useEffect(() => { load(); }, []);

  // Sparkline: số ticket mới mỗi ngày trong 7 ngày qua
  const series = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(); d.setDate(d.getDate() - (6 - i));
      return d.toISOString().slice(0, 10);
    });
    return days.map((day) => tickets.filter((t) => t.created_at.startsWith(day)).length);
  }, [tickets]);

  const flash = (text, ok = true) => { setMsg({ text, ok }); setTimeout(() => setMsg(null), 3500); };

  async function humanReply(text) {
    await api(`/tickets/${sel.id}/reply`, { method: "POST", body: JSON.stringify({ message: text }) });
    flash("Đã gửi trả lời, ticket chuyển sang chờ xử lý");
    load();
  }

  async function setStatus(id, status) {
    await api(`/tickets/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
    flash("Đã cập nhật trạng thái");
    load();
  }

  async function uploadKB(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await api("/kb/upload", { method: "POST", body: fd });
    flash(`Đã thêm "${r.doc}" — ${r.chunks} đoạn vào knowledge base`);
    load();
  }

  async function deleteDoc(id) {
    await api(`/kb/docs/${id}`, { method: "DELETE" });
    flash("Đã xóa tài liệu");
    load();
  }

  async function saveCfg(e) {
    e.preventDefault();
    const saved = await api("/config", { method: "PUT", body: JSON.stringify(cfg) });
    setCfg(saved);
    flash("Đã lưu cấu hình widget");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand"><span className="brand-dot" /><strong>AI Support</strong></div>
        <LineSidebar items={NAV} accentColor="var(--accent)" fontSize={1} itemGap={14}
          defaultActive={view} onItemClick={(i) => setView(i)} />
        <div className="sidebar-user">
          <span className="avatar">{user.username[0].toUpperCase()}</span>
          <div>
            <div className="sidebar-user-name">{user.username}</div>
            <div className="sidebar-user-role">Quản trị viên</div>
          </div>
          <button className="logout-btn" title="Đăng xuất" onClick={onLogout}>⏻</button>
        </div>
      </aside>

      <main className="content">
        <div className="content-header">
          <h1>{NAV[view]}</h1>
          {msg && <div className={"msg " + (msg.ok ? "ok" : "err")}>{msg.text}</div>}
        </div>

        {view === 0 && stats && (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-top"><span className="stat-label">Tổng ticket</span><Sparkline data={series} /></div>
                <div className="stat-num"><CountUp to={stats.total} /></div>
                <div className="stat-sub">7 ngày gần nhất</div>
              </div>
              <div className="stat-card">
                <div className="stat-top"><span className="stat-label">Chờ người thật</span></div>
                <div className="stat-num"><CountUp to={stats.by_status.waiting_human || 0} /></div>
                <div className="stat-sub">Agent đã escalate</div>
              </div>
              <div className="stat-card">
                <div className="stat-top"><span className="stat-label">Đã giải quyết</span></div>
                <div className="stat-num"><CountUp to={stats.by_status.resolved || 0} /></div>
                <div className="stat-sub">Tự động + thủ công</div>
              </div>
              <div className="stat-card">
                <div className="stat-top"><span className="stat-label">Tỷ lệ giải quyết</span></div>
                <div className="stat-num"><CountUp to={Math.round((stats.resolved_rate || 0) * 100)} format={(v) => v.toFixed(0) + "%"} /></div>
                <div className="stat-sub">Không cần người thật</div>
              </div>
            </div>

            <div className="card">
              <div className="card-head"><h2>Ticket gần đây</h2><span className="stat-sub">{tickets.length} ticket</span></div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Mã</th><th>Kênh</th><th>Trạng thái</th><th>Lượt</th><th>Cập nhật</th><th></th></tr></thead>
                  <tbody>
                    {tickets.length === 0 && <tr><td className="empty" colSpan="6">Chưa có ticket nào</td></tr>}
                    {tickets.slice(0, 6).map((t) => (
                      <tr key={t.id} onClick={() => { setView(1); setSel(t); }} style={{ cursor: "pointer" }}>
                        <td className="mono">{t.id}</td>
                        <td>{t.channel}</td>
                        <td><span className={"badge " + STATUS[t.status].cls}>{STATUS[t.status].label}</span></td>
                        <td className="num">{t.messages.length}</td>
                        <td>{fmtDate(t.updated_at)}</td>
                        <td className="actions"><span className="stat-sub">mở →</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {view === 1 && (
          <div className="ticket-layout">
            <div className="card ticket-list">
              <div className="card-head">
                <h2>Ticket</h2>
                <select value="" onChange={(e) => { if (e.target.value) { const t = tickets.find((x) => x.id === e.target.value); setSel(t); } }}>
                  <option value="">Chọn ticket...</option>
                  {tickets.map((t) => (
                    <option key={t.id} value={t.id}>{t.id} — {STATUS[t.status].label} ({t.messages.length} lượt)</option>
                  ))}
                </select>
              </div>
              {tickets.map((t) => (
                <div key={t.id} className={"ticket-row" + (sel && sel.id === t.id ? " active" : "")} onClick={() => setSel(t)}>
                  <div>
                    <span className="mono">{t.id}</span>{" "}
                    <span className={"badge " + STATUS[t.status].cls}>{STATUS[t.status].label}</span>
                  </div>
                  <div className="stat-sub">
                    {t.channel} · {t.messages.length} lượt · {fmtDate(t.updated_at)}
                  </div>
                </div>
              ))}
              {tickets.length === 0 && <p className="empty-note">Chưa có ticket</p>}
            </div>

            {sel && (
              <div className="card ticket-detail">
                <div className="card-head">
                  <h2>Ticket {sel.id}</h2>
                  <div className="row">
                    <select value={sel.status} onChange={(e) => setStatus(sel.id, e.target.value)}>
                      {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>
                    <span className="stat-sub">{fmtDate(sel.updated_at)}</span>
                  </div>
                </div>
                <div className="chat-log">
                  {sel.messages.map((m, i) => (
                    <div key={i} className={"chat-msg " + (m.role === "user" ? "user" : m.role === "tool" ? "tool" : "bot")}>
                      <div className="chat-role">
                        {m.role === "user" ? "Khách" : m.role === "tool" ? `Công cụ: ${m.tool}` : "Bot"}
                      </div>
                      <div className="chat-text">{m.content}</div>
                    </div>
                  ))}
                </div>
                <form className="reply-row" onSubmit={(e) => { e.preventDefault(); const t = e.target.reply.value.trim(); if (t) humanReply(t); e.target.reset(); }}>
                  <input name="reply" placeholder="Trả lời với tư cách nhân viên..." required />
                  <button className="btn-primary" type="submit">Gửi</button>
                </form>
              </div>
            )}
            {!sel && <p className="empty-note">Chọn một ticket để xem hội thoại</p>}
          </div>
        )}

        {view === 2 && (
          <div className="card">
            <div className="card-head">
              <h2>Knowledge base</h2>
              <span className="stat-sub">{docs.length} tài liệu · tổng {docs.reduce((s, d) => s + d.chunk_count, 0)} đoạn</span>
            </div>
            <form className="row" onSubmit={(e) => { e.preventDefault(); const f = e.target.file.files[0]; if (f) uploadKB(f); e.target.reset(); }}>
              <label className="btn-primary">
                Chọn file (txt/pdf)
                <input type="file" name="file" accept=".txt,.pdf" required />
              </label>
              <button className="btn-primary" type="submit">Tải lên → KB</button>
              <span className="stat-sub">Agent tự tìm trong KB khi khách hỏi chính sách, giá, bảo hành...</span>
            </form>
            <div className="table-wrap" style={{ marginTop: 14 }}>
              <table>
                <thead><tr><th>Tài liệu</th><th>Đoạn</th><th>Ngày thêm</th><th></th></tr></thead>
                <tbody>
                  {docs.length === 0 && <tr><td className="empty" colSpan="4">Chưa có tài liệu — tải lên để agent có nguồn trả lời</td></tr>}
                  {docs.map((d) => (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td className="num">{d.chunk_count}</td>
                      <td>{fmtDate(d.created_at)}</td>
                      <td className="actions"><button className="btn-small danger" onClick={() => deleteDoc(d.id)}>Xóa</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {view === 3 && cfg && (
          <div className="card settings">
            <h2>Widget chat</h2>
            <form onSubmit={saveCfg}>
              <div className="settings-row">
                <div><div className="settings-name">Tiêu đề</div><div className="settings-meta">Hiện trên đầu widget</div></div>
                <input value={cfg.title} onChange={(e) => setCfg({ ...cfg, title: e.target.value })} />
              </div>
              <div className="settings-row">
                <div><div className="settings-name">Tên bot</div><div className="settings-meta">Tên trợ lý ảo</div></div>
                <input value={cfg.bot_name} onChange={(e) => setCfg({ ...cfg, bot_name: e.target.value })} />
              </div>
              <div className="settings-row">
                <div><div className="settings-name">Lời chào</div><div className="settings-meta">Câu chào khi mở widget</div></div>
                <input value={cfg.welcome} onChange={(e) => setCfg({ ...cfg, welcome: e.target.value })} />
              </div>
              <div className="settings-row">
                <div><div className="settings-name">Màu chủ đạo</div><div className="settings-meta">Nút + tin nhắn bot</div></div>
                <input type="color" value={cfg.primary_color} onChange={(e) => setCfg({ ...cfg, primary_color: e.target.value })} />
                <code>{cfg.primary_color}</code>
              </div>
              <button className="btn-primary" type="submit">Lưu cấu hình</button>
              <p className="stat-sub" style={{ marginTop: 14 }}>
                Nhúng widget vào website: <code>&lt;script src="/widget/widget.js" data-api="http://localhost:8005"&gt;&lt;/script&gt;</code>
              </p>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
