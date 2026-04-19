"""
Analytics Tracker — theo dõi hiệu suất post để học và tối ưu.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS posts (
                    publish_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    caption TEXT,
                    hashtags TEXT,       -- JSON array
                    posted_at REAL NOT NULL,
                    video_hash TEXT,
                    video_id TEXT        -- ID TikTok trả về khi publish xong
                );

                CREATE TABLE IF NOT EXISTS stats_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    publish_id TEXT NOT NULL,
                    checked_at REAL NOT NULL,
                    views INTEGER,
                    likes INTEGER,
                    comments INTEGER,
                    shares INTEGER,
                    FOREIGN KEY (publish_id) REFERENCES posts(publish_id)
                );
                CREATE INDEX IF NOT EXISTS idx_snap_pid ON stats_snapshots(publish_id);
            """)

    def record_post(
        self,
        publish_id: str,
        account_id: str,
        caption: str,
        hashtags: list[str],
        posted_at: float,
        video_hash: str,
        video_id: Optional[str] = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO posts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (publish_id, account_id, caption, json.dumps(hashtags),
                 posted_at, video_hash, video_id),
            )

    def record_stats(self, publish_id: str, stats: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO stats_snapshots "
                "(publish_id, checked_at, views, likes, comments, shares) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (publish_id, time.time(),
                 stats.get("view_count", 0),
                 stats.get("like_count", 0),
                 stats.get("comment_count", 0),
                 stats.get("share_count", 0)),
            )

    def last_24h(self) -> dict:
        cutoff = time.time() - 86400
        with sqlite3.connect(self.db_path) as conn:
            posts = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE posted_at >= ?", (cutoff,)
            ).fetchone()[0]

            totals = conn.execute("""
                SELECT COALESCE(SUM(views),0), COALESCE(SUM(likes),0),
                       COALESCE(SUM(comments),0), COALESCE(SUM(shares),0)
                FROM stats_snapshots s
                WHERE s.checked_at >= ?
                  AND s.id IN (
                      SELECT MAX(id) FROM stats_snapshots GROUP BY publish_id
                  )
            """, (cutoff,)).fetchone()

        return {
            "posts": posts,
            "views": totals[0],
            "likes": totals[1],
            "comments": totals[2],
            "shares": totals[3],
            "top_hashtag": self._top_hashtag(cutoff),
        }

    def _top_hashtag(self, since: float) -> str:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT hashtags FROM posts WHERE posted_at >= ?", (since,)
            ).fetchall()
        counts = {}
        for (hashtags_json,) in rows:
            for tag in json.loads(hashtags_json or "[]"):
                counts[tag] = counts.get(tag, 0) + 1
        if not counts:
            return "N/A"
        return max(counts.items(), key=lambda x: x[1])[0]

    def best_posting_hours(self, days: int = 30) -> list[tuple[int, float]]:
        """Phân tích giờ nào post có avg views cao nhất. Dùng để tối ưu scheduler."""
        cutoff = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT p.posted_at, MAX(s.views) as max_views
                FROM posts p
                LEFT JOIN stats_snapshots s USING(publish_id)
                WHERE p.posted_at >= ?
                GROUP BY p.publish_id
            """, (cutoff,)).fetchall()

        from collections import defaultdict
        hour_stats = defaultdict(list)
        for posted_at, views in rows:
            import datetime as dt
            hour = dt.datetime.fromtimestamp(posted_at).hour
            hour_stats[hour].append(views or 0)

        avg_by_hour = [
            (h, sum(vs) / len(vs)) for h, vs in hour_stats.items() if vs
        ]
        return sorted(avg_by_hour, key=lambda x: x[1], reverse=True)
