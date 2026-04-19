#!/usr/bin/env python3
"""
cron_worker.py — Daemon chạy ngầm, xử lý queue + cập nhật analytics.

Deploy:
  # Cách 1: systemd (production)
  sudo cp scripts/tiktok-worker.service /etc/systemd/system/
  sudo systemctl enable --now tiktok-worker

  # Cách 2: cron đơn giản
  */5 * * * * cd /path/to/tiktok_auto_poster && python scripts/cron_worker.py --once
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config, setup_logging
from agent.orchestrator import TikTokAgent

logger = logging.getLogger("cron_worker")


def tick(agent: TikTokAgent) -> None:
    """Một vòng công việc: xử lý queue + refresh analytics."""
    # 1. Xử lý các job đến hạn
    try:
        results = agent.run_scheduled_jobs()
        if results:
            logger.info(f"📮 Xử lý {len(results)} job đến hạn.")
    except Exception as e:
        logger.exception(f"Lỗi khi chạy scheduled jobs: {e}")

    # 2. Refresh analytics cho các post trong 24h qua
    try:
        refresh_analytics(agent)
    except Exception as e:
        logger.exception(f"Lỗi khi refresh analytics: {e}")


def refresh_analytics(agent: TikTokAgent) -> None:
    """Gọi TikTok API lấy stats cho các post gần đây."""
    import sqlite3
    cutoff = time.time() - 7 * 86400  # 7 ngày
    with sqlite3.connect(agent.analytics.db_path) as conn:
        rows = conn.execute(
            "SELECT publish_id, video_id FROM posts "
            "WHERE posted_at >= ? AND video_id IS NOT NULL",
            (cutoff,),
        ).fetchall()

    for publish_id, video_id in rows:
        try:
            stats = agent.api.get_video_stats(video_id)
            if stats:
                agent.analytics.record_stats(publish_id, stats)
                logger.debug(f"  {publish_id}: {stats.get('view_count', 0)} views")
        except Exception as e:
            logger.warning(f"Không lấy được stats cho {publish_id}: {e}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="Chạy 1 tick rồi thoát (cho cron)")
    p.add_argument("--interval", type=int, default=300, help="Giây giữa các tick (daemon mode)")
    args = p.parse_args()

    setup_logging("INFO")
    config = load_config()
    agent = TikTokAgent(config)

    if args.once:
        tick(agent)
        return

    logger.info(f"🔄 Worker daemon bắt đầu, interval={args.interval}s")
    while True:
        try:
            tick(agent)
        except KeyboardInterrupt:
            logger.info("Nhận Ctrl+C, dừng worker.")
            break
        except Exception as e:
            logger.exception(f"Lỗi ngoài dự kiến: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
