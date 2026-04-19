#!/usr/bin/env python3
"""
run_agent.py — Entry point chạy TikTok Auto Poster.

Ví dụ:
  # Đăng ngay 1 video
  python scripts/run_agent.py --mode=once --video=/path/video.mp4 --topic="học python"

  # Lên lịch đăng vào giờ vàng kế tiếp
  python scripts/run_agent.py --mode=once --video=/path/video.mp4 --schedule=auto

  # Chạy worker xử lý queue (gọi từ cron mỗi 5 phút)
  python scripts/run_agent.py --mode=worker

  # Đăng hàng loạt từ thư mục
  python scripts/run_agent.py --mode=batch --dir=/path/videos
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Thêm project root vào path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from dotenv import load_dotenv

from agent.orchestrator import TikTokAgent, PostRequest


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "logs" / "agent.log"),
        ],
    )


def load_config() -> dict:
    load_dotenv(ROOT / "config" / ".env")
    with open(ROOT / "config" / "config.yaml") as f:
        cfg = yaml.safe_load(f)

    # Inject secrets từ env
    cfg["tiktok"]["client_key"] = os.environ["TIKTOK_CLIENT_KEY"]
    cfg["tiktok"]["client_secret"] = os.environ["TIKTOK_CLIENT_SECRET"]
    cfg["tiktok"]["access_token"] = os.environ["TIKTOK_ACCESS_TOKEN"]
    cfg["tiktok"]["refresh_token"] = os.environ.get("TIKTOK_REFRESH_TOKEN", "")
    # Claude CLI không cần API key — dùng `claude login` trước

    # Resolve paths
    cfg["queue_db"] = str(ROOT / cfg.get("queue_db", "data/queue.db"))
    cfg["analytics_db"] = str(ROOT / cfg.get("analytics_db", "data/analytics.db"))
    return cfg


# ----------------------------------------------------------------------
def cmd_once(agent: TikTokAgent, args) -> int:
    video_path = Path(args.video)
    schedule_at = None

    if args.schedule == "auto":
        schedule_at = agent.scheduler.next_optimal_slot(account_id="default")
    elif args.schedule and args.schedule != "now":
        import dateutil.parser
        schedule_at = dateutil.parser.parse(args.schedule).timestamp()

    req = PostRequest(
        video_path=video_path,
        topic=args.topic or "",
        description=args.description or "",
        schedule_at=schedule_at,
        style=args.style,
        privacy=args.privacy,
    )
    result = agent.post(req)

    if result.status.value == "published":
        print(f"✅ OK — publish_id={result.publish_id}")
        return 0
    elif result.status.value == "scheduled":
        import datetime as dt
        when = dt.datetime.fromtimestamp(result.schedule_at)
        print(f"⏰ Đã lên lịch lúc {when.strftime('%Y-%m-%d %H:%M')}")
        return 0
    else:
        print(f"❌ Thất bại: {result.error}")
        return 1


def cmd_worker(agent: TikTokAgent, args) -> int:
    """Chạy 1 lần, xử lý các job đã đến hạn. Cron gọi mỗi 5 phút."""
    results = agent.run_scheduled_jobs()
    print(f"Worker xử lý {len(results)} job(s).")
    for r in results:
        print(f"  • {r.video_path.name}: {r.status.value}")
    return 0


def cmd_batch(agent: TikTokAgent, args) -> int:
    """Đăng hàng loạt, mỗi video vào 1 golden slot kế tiếp."""
    video_dir = Path(args.dir)
    videos = sorted(video_dir.glob("*.mp4")) + sorted(video_dir.glob("*.mov"))
    print(f"Tìm thấy {len(videos)} video trong {video_dir}")

    import time
    next_slot = time.time()
    for v in videos:
        slot = agent.scheduler.next_optimal_slot(
            account_id="default", after=next_slot,
        )
        req = PostRequest(
            video_path=v,
            schedule_at=slot,
            style=args.style,
        )
        agent.post(req)
        next_slot = slot + 1  # đảm bảo slot kế tiếp sau slot này

    return 0


# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="TikTok Auto Poster Agent")
    p.add_argument("--mode", choices=["once", "worker", "batch"], default="once")
    p.add_argument("--video", help="Đường dẫn file video")
    p.add_argument("--dir", help="Thư mục chứa videos (mode=batch)")
    p.add_argument("--topic", default="", help="Chủ đề video")
    p.add_argument("--description", default="", help="Mô tả chi tiết")
    p.add_argument("--style", default="gen_z_engaging",
                   choices=["gen_z_engaging", "professional", "storytelling", "educational"])
    p.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                   choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"])
    p.add_argument("--schedule", default="now",
                   help="'now' / 'auto' / '2026-04-20 20:00'")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    setup_logging(args.log_level)
    config = load_config()
    agent = TikTokAgent(config)

    if args.mode == "once":
        if not args.video:
            p.error("--video là bắt buộc với mode=once")
        sys.exit(cmd_once(agent, args))
    elif args.mode == "worker":
        sys.exit(cmd_worker(agent, args))
    elif args.mode == "batch":
        if not args.dir:
            p.error("--dir là bắt buộc với mode=batch")
        sys.exit(cmd_batch(agent, args))


if __name__ == "__main__":
    main()
