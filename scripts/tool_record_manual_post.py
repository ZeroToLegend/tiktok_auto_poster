#!/usr/bin/env python3
"""
Record a manually-posted TikTok video into analytics.db.

User posts via advisory-mode package, then runs this to track stats later.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config


def extract_video_id(url: str) -> str | None:
    """Parse TikTok URL to extract video ID."""
    import re
    match = re.search(r"/video/(\d+)", url)
    return match.group(1) if match else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="TikTok video URL")
    p.add_argument("--caption-file", help="Path to caption.txt from advisory package")
    p.add_argument("--hashtags", default="", help="Comma-separated hashtags")
    p.add_argument("--package-dir", help="Path to advisory package folder")
    p.add_argument("--account", default="default")
    args = p.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(json.dumps({
            "success": False,
            "error_type": "invalid_url",
            "remediation": {
                "explanation": "URL không chứa video ID (format: tiktok.com/@user/video/NNN)",
                "next_step": "Copy URL đúng format từ app TikTok (share → copy link)",
                "user_message": "URL không đúng format TikTok.",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Load caption
    caption = ""
    if args.caption_file and Path(args.caption_file).exists():
        caption = Path(args.caption_file).read_text(encoding="utf-8").strip()
    elif args.package_dir:
        cap_path = Path(args.package_dir) / "caption.txt"
        if cap_path.exists():
            caption = cap_path.read_text(encoding="utf-8").strip()

    # Parse hashtags
    hashtags = [h.strip().lstrip("#") for h in args.hashtags.split(",") if h.strip()]
    if not hashtags and args.package_dir:
        tags_path = Path(args.package_dir) / "hashtags.txt"
        if tags_path.exists():
            raw = tags_path.read_text(encoding="utf-8").strip()
            hashtags = [t.lstrip("#") for t in raw.split() if t.strip()]

    # Fake publish_id for manual post (TikTok API assigns to API posts only)
    publish_id = f"manual_{hashlib.sha256(video_id.encode()).hexdigest()[:16]}"

    try:
        config = load_config()
    except Exception as e:
        # Allow recording even without full config (just need DB path)
        config = {"analytics_db": str(ROOT / "data" / "analytics.db")}

    db_path = Path(config["analytics_db"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                publish_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                caption TEXT,
                hashtags TEXT,
                posted_at REAL NOT NULL,
                video_hash TEXT,
                video_id TEXT
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO posts
            (publish_id, account_id, caption, hashtags, posted_at, video_hash, video_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            publish_id, args.account, caption,
            json.dumps(hashtags), time.time(),
            None, video_id,
        ))

    print(json.dumps({
        "success": True,
        "publish_id": publish_id,
        "video_id": video_id,
        "url": args.url,
        "caption_preview": caption[:80] if caption else "(no caption recorded)",
        "hashtags": hashtags,
        "message": "Manual post recorded. Analytics worker sẽ fetch stats mỗi 24h.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
