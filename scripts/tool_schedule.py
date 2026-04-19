#!/usr/bin/env python3
"""CLI wrapper cho Scheduler — với self-correcting error messages."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config
from tools.scheduler import PostScheduler, ScheduleSlot
from agent.orchestrator import PostRequest


def error(error_type: str, raw_error: str, remediation: dict) -> None:
    """Print self-correcting error and exit non-zero."""
    print(json.dumps({
        "success": False,
        "error_type": error_type,
        "raw_error": raw_error,
        "remediation": remediation,
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enqueue")
    e.add_argument("--video", required=True)
    e.add_argument("--caption", required=True)
    e.add_argument("--hashtags", default="")
    e.add_argument("--when", default="auto")
    e.add_argument("--account", default="default")

    n = sub.add_parser("next-slot")
    n.add_argument("--account", default="default")

    sub.add_parser("list")

    q = sub.add_parser("check-quota")
    q.add_argument("--account", default="default")

    d = sub.add_parser("check-duplicate")
    d.add_argument("--hash", required=True)
    d.add_argument("--days", type=int, default=7)

    args = p.parse_args()

    try:
        config = load_config()
    except Exception as ex:
        error("config_error", str(ex), {
            "explanation": "Không load được config",
            "action": "halt",
            "next_step": "Check config/config.yaml + config/.env",
            "user_message": "Thiếu config. Chạy scripts/setup.sh.",
        })

    sch = PostScheduler(db_path=config["queue_db"])

    if args.cmd == "enqueue":
        # Pre-enqueue validation
        quota = sch.count_published_today(args.account)
        if quota >= 6:
            error("quota_exceeded", f"posted {quota}/6 today", {
                "explanation": f"Account {args.account} đã đăng {quota}/6 hôm nay",
                "action": "halt_or_defer",
                "next_step": "Đợi sang ngày mới, hoặc schedule với --when=<tomorrow 8am>",
                "do_not": "force enqueue — worker sẽ reject",
                "user_message": f"Quota full ({quota}/6). Schedule cho mai?",
            })

        try:
            if args.when == "auto":
                run_at = sch.next_optimal_slot(args.account)
            else:
                run_at = dt.datetime.fromisoformat(args.when).timestamp()
        except ValueError as ex:
            error("invalid_datetime", str(ex), {
                "explanation": f"'--when={args.when}' không parse được",
                "action": "halt",
                "next_step": "Dùng 'auto' hoặc ISO format '2026-04-20T20:00:00'",
                "do_not": "guess format — ISO only",
                "user_message": f"Ngày giờ không hợp lệ: {args.when}",
            })

        # Validate not in past, not in 2h blackout
        import time as _t
        now = _t.time()
        if run_at < now - 60:
            error("time_in_past", f"run_at={run_at} < now={now}", {
                "explanation": "Thời điểm schedule đã qua",
                "action": "halt",
                "next_step": "Dùng --when=auto hoặc ISO future time",
                "user_message": "Không thể schedule vào quá khứ.",
            })

        req = PostRequest(
            video_path=Path(args.video),
            caption=args.caption,
            hashtags=[h.strip() for h in args.hashtags.split(",") if h.strip()],
            schedule_at=run_at,
            account_id=args.account,
        )
        job_id = sch.enqueue(ScheduleSlot(run_at, args.account, req))

        print(json.dumps({
            "success": True,
            "job_id": job_id,
            "scheduled_for_iso": dt.datetime.fromtimestamp(run_at).isoformat(),
            "scheduled_for_human": dt.datetime.fromtimestamp(run_at).strftime("%Y-%m-%d %H:%M"),
            "account": args.account,
            "quota_used": quota + 1,
            "quota_remaining": 5 - quota,
        }, ensure_ascii=False, indent=2))

    elif args.cmd == "next-slot":
        ts = sch.next_optimal_slot(args.account)
        print(json.dumps({
            "success": True,
            "timestamp": ts,
            "iso": dt.datetime.fromtimestamp(ts).isoformat(),
            "human": dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
        }, ensure_ascii=False, indent=2))

    elif args.cmd == "list":
        pending = sch.list_pending()
        print(json.dumps({
            "success": True,
            "pending_count": len(pending),
            "jobs": pending,
        }, ensure_ascii=False, indent=2, default=str))

    elif args.cmd == "check-quota":
        count = sch.count_published_today(args.account)
        can_post = count < 6
        result = {
            "success": True,
            "posted_today": count,
            "daily_limit": 6,
            "remaining": max(0, 6 - count),
            "can_post": can_post,
        }
        if not can_post:
            result["remediation"] = {
                "explanation": "Quota today đã hết",
                "action": "schedule_tomorrow",
                "next_step": "Defer to next golden slot (tomorrow morning)",
                "user_message": "Đã đủ quota. Muốn schedule mai?",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "check-duplicate":
        exists = sch.was_posted_recently(args.hash, days=args.days)
        result = {
            "success": True,
            "is_duplicate": exists,
            "window_days": args.days,
        }
        if exists:
            result["remediation"] = {
                "explanation": f"Video này đã đăng trong {args.days} ngày qua",
                "action": "halt",
                "next_step": "Dừng, không upload. Nếu user thực sự muốn đăng lại → đổi video hoặc đổi content đáng kể.",
                "do_not": "upload duplicate — TikTok penalize account",
                "user_message": "Video đã đăng gần đây. Đổi video khác?",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
