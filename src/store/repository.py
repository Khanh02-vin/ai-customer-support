"""Lưu trữ SQLite: tickets (memory hội thoại), knowledge base, cấu hình widget."""
import hashlib
import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from ..domain.models import KBEntry, Message, Ticket, TicketStatus, WidgetConfig
from ..kb.retriever import retrieve
from .db import SQLiteRepo


class SupportRepo(SQLiteRepo):
    """Ticket + KB + config trên một DB."""

    def _ensure_schema(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                messages TEXT DEFAULT '[]',
                status TEXT,
                channel TEXT,
                created_at TEXT,
                updated_at TEXT,
                resolved_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kb (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                doc_name TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kb_docs (
                id TEXT PRIMARY KEY,
                name TEXT,
                chunk_count INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS widget_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                title TEXT,
                welcome TEXT,
                primary_color TEXT,
                bot_name TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_session ON tickets(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_doc ON kb(doc_name)")

    # ---------- Ticket ----------

    def create_ticket(self, session_id: str, channel: str) -> Ticket:
        ticket = Ticket(
            id=hashlib.md5(f"{session_id}|{datetime.now().isoformat()}".encode()).hexdigest()[:12],
            session_id=session_id,
            channel=channel,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tickets (id, session_id, messages, status, channel, created_at, updated_at, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ticket.id, ticket.session_id, "[]", ticket.status.value, channel,
                 ticket.created_at.isoformat(), ticket.updated_at.isoformat(), None),
            )
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._row_to_ticket(row) if row else None

    def get_ticket_by_session(self, session_id: str) -> Optional[Ticket]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                               (session_id,)).fetchone()
        return self._row_to_ticket(row) if row else None

    def list_tickets(self, status: Optional[str] = None, limit: int = 100) -> List[Ticket]:
        query = "SELECT * FROM tickets"
        params = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params += (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_ticket(r) for r in rows]

    def append_message(self, ticket_id: str, role: str, content: str, tool: Optional[str] = None) -> Message:
        """Thêm lượt vào ticket, cập nhật updated_at. Trả Message để đồng bộ object."""
        msg = Message(role=role, content=content, tool=tool)
        with self._connect() as conn:
            row = conn.execute("SELECT messages FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if not row:
                raise KeyError(f"ticket {ticket_id} không tồn tại")
            msgs = json.loads(row["messages"])
            msgs.append(msg.model_dump(mode="json"))
            conn.execute(
                "UPDATE tickets SET messages = ?, updated_at = ? WHERE id = ?",
                (json.dumps(msgs, ensure_ascii=False), datetime.now().isoformat(), ticket_id),
            )
        return msg

    def set_status(self, ticket_id: str, status: str) -> None:
        resolved_at = datetime.now().isoformat() if status == "resolved" else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ?, resolved_at = COALESCE(?, resolved_at) WHERE id = ?",
                (status, datetime.now().isoformat(), resolved_at, ticket_id),
            )

    def stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) c FROM tickets GROUP BY status").fetchall()
        by_status = {r["status"]: r["c"] for r in rows}
        total = sum(by_status.values())
        resolved = by_status.get("resolved", 0)
        return {
            "total": total,
            "by_status": by_status,
            "resolved_rate": round(resolved / total, 2) if total else 0.0,
        }

    def _row_to_ticket(self, row: sqlite3.Row) -> Ticket:
        msgs = [Message(**m) for m in json.loads(row["messages"])]
        return Ticket(
            id=row["id"],
            session_id=row["session_id"],
            messages=msgs,
            status=TicketStatus(row["status"]),
            channel=row["channel"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )

    # ---------- Knowledge base ----------

    def add_doc(self, name: str, chunks: List[str], title: str = "") -> int:
        """Lưu doc + các đoạn. Trả số chunk."""
        doc_id = hashlib.md5(name.encode()).hexdigest()[:12]
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO kb_docs (id, name, chunk_count, created_at) VALUES (?, ?, ?, ?)",
                         (doc_id, name, len(chunks), now))
            conn.execute("DELETE FROM kb WHERE doc_name = ?", (name,))
            for i, chunk in enumerate(chunks):
                eid = hashlib.md5(f"{doc_id}|{i}".encode()).hexdigest()[:12]
                conn.execute("INSERT INTO kb (id, title, content, doc_name, created_at) VALUES (?, ?, ?, ?, ?)",
                             (eid, title or name, chunk, name, now))
        return len(chunks)

    def list_docs(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name, chunk_count, created_at FROM kb_docs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_doc(self, doc_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT name FROM kb_docs WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM kb_docs WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM kb WHERE doc_name = ?", (row["name"],))
        return True

    def all_entries(self) -> List[KBEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM kb ORDER BY doc_name, id").fetchall()
        return [KBEntry(id=r["id"], title=r["title"], content=r["content"], doc_name=r["doc_name"],
                        created_at=datetime.fromisoformat(r["created_at"])) for r in rows]

    def search_kb(self, query: str, k: int = 3) -> List[KBEntry]:
        """Retrieval: token-overlap trên toàn bộ KB."""
        return retrieve(query, self.all_entries(), k=k)

    def kb_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) c FROM kb").fetchone()["c"]

    # ---------- Widget config ----------

    def get_config(self) -> WidgetConfig:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM widget_config WHERE id = 1").fetchone()
        if row is None:
            cfg = WidgetConfig()
            self.set_config(cfg)
            return cfg
        return WidgetConfig(title=row["title"], welcome=row["welcome"],
                            primary_color=row["primary_color"], bot_name=row["bot_name"])

    def set_config(self, cfg: WidgetConfig) -> WidgetConfig:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO widget_config (id, title, welcome, primary_color, bot_name) VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, welcome=excluded.welcome, "
                "primary_color=excluded.primary_color, bot_name=excluded.bot_name",
                (cfg.title, cfg.welcome, cfg.primary_color, cfg.bot_name),
            )
        return cfg
