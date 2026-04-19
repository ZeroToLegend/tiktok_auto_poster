"""
Post Scheduler — hàng đợi persistent dùng SQLite.
Hỗ trợ đăng đúng giờ vàng, tránh spam, retry.
"""
from __future__ import annotations

import logging
import pickle
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Giờ vàng TikTok Việt Nam (giờ địa phương, 24h format)
GOLDEN_HOURS = [6, 7, 8, 9, 12, 19, 20, 21, 22]
MIN_GAP_HOURS = 2  # tối thiểu cách 2 giờ giữa 2 post


@dataclass
class ScheduleSlot:
    run_at: float  # unix timestamp
    account_id: str
    payload: Any   # PostRequest


class PostScheduler:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_at REAL NOT NULL,
                    account_id TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    processed_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_run_at ON queue(run_at, status);

                CREATE TABLE IF NOT EXISTS posted (
                    video_hash TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    publish_id TEXT,
                    posted_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_posted_at ON posted(posted_at);
            """)

    # ------------------------------------------------------------------
    def enqueue(self, slot: ScheduleSlot) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO queue (run_at, account_id, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (slot.run_at, slot.account_id, pickle.dumps(slot.payload), time.time()),
            )
            return cur.lastrowid

    def pop_due_jobs(self, now: float) -> list:
        """Lấy các job đã đến hạn, đánh dấu processing."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, payload FROM queue "
                "WHERE run_at <= ? AND status = 'pending' "
                "ORDER BY run_at LIMIT 10",
                (now,),
            ).fetchall()
            if not rows:
                return []
            ids = [r[0] for r in rows]
            conn.execute(
                f"UPDATE queue SET status='processing' "
                f"WHERE id IN ({','.join('?' * len(ids))})",
                ids,
            )
            return [pickle.loads(r[1]) for r in rows]

    def mark_done(self, job_id: int, success: bool = True) -> None:
        status = "done" if success else "failed"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE queue SET status=?, processed_at=? WHERE id=?",
                (status, time.time(), job_id),
            )

    # ------------------------------------------------------------------
    def count_published_today(self, account_id: str) -> int:
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM posted WHERE account_id=? AND posted_at >= ?",
                (account_id, start_of_day),
            ).fetchone()
            return row[0]

    def was_posted_recently(self, video_hash: str, days: int = 7) -> bool:
        cutoff = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM posted WHERE video_hash=? AND posted_at >= ?",
                (video_hash, cutoff),
            ).fetchone()
            return row is not None

    def record_posted(self, video_hash: str, account_id: str, publish_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO posted VALUES (?, ?, ?, ?)",
                (video_hash, account_id, publish_id, time.time()),
            )

    # ------------------------------------------------------------------
    def next_optimal_slot(self, account_id: str, after: float = None) -> float:
        """
        Tính thời điểm tối ưu kế tiếp:
          - Thuộc golden hours
          - Cách post gần nhất ≥ MIN_GAP_HOURS
        """
        after = after or time.time()
        last_post = self._last_post_time(account_id) or 0
        earliest = max(after, last_post + MIN_GAP_HOURS * 3600)

        # Tìm golden hour gần nhất sau `earliest`
        dt = datetime.fromtimestamp(earliest)
        for offset_days in range(7):
            candidate_date = dt.date() + timedelta(days=offset_days)
            for hour in GOLDEN_HOURS:
                candidate = datetime.combine(
                    candidate_date,
                    datetime.min.time().replace(hour=hour, minute=0),
                )
                ts = candidate.timestamp()
                if ts >= earliest:
                    return ts
        return earliest + 3600  # fallback

    def _last_post_time(self, account_id: str) -> Optional[float]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MAX(posted_at) FROM posted WHERE account_id=?",
                (account_id,),
            ).fetchone()
            return row[0] if row and row[0] else None

    def list_pending(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, run_at, account_id, status FROM queue "
                "WHERE status IN ('pending', 'processing') ORDER BY run_at"
            ).fetchall()
            return [dict(r) for r in rows]
