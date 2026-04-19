#!/usr/bin/env python3
"""
Sensor: post-upload verification.

After tool_upload.py returns PUBLISH_COMPLETE, verify the video is ACTUALLY
visible on the user's profile. This catches cases where TikTok accepts the
upload but shadowbans the video silently.

Run 2-5 minutes after upload for best signal.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config
from tools.tiktok_api import TikTokAPI


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--publish-id", required=True)
    p.add_argument("--wait-minutes", type=int, default=3,
                   help="Đợi trước khi check (mặc định 3 phút)")
    p.add_argument("--skip-wait", action="store_true",
                   help="Check ngay không đợi")
    args = p.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error_type": "config_load_failed",
            "raw_error": str(e),
            "remediation": {
                "explanation": "Không load config được",
                "action": "halt",
                "next_step": "Check config/.env",
                "user_message": "Lỗi config khi verify upload.",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    api = TikTokAPI(
        client_key=config["tiktok"]["client_key"],
        client_secret=config["tiktok"]["client_secret"],
        access_token=config["tiktok"]["access_token"],
        refresh_token=config["tiktok"].get("refresh_token"),
    )
    api.ensure_token_valid()

    # Wait if requested (video processing takes ~2 min on TikTok side)
    if not args.skip_wait:
        wait_s = args.wait_minutes * 60
        time.sleep(wait_s)

    # Check 1: publish status = COMPLETE
    try:
        status = api.get_publish_status(args.publish_id)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error_type": "status_fetch_failed",
            "raw_error": str(e),
            "remediation": {
                "explanation": "Không fetch được publish status",
                "action": "retry_later",
                "next_step": "Đợi 2 phút rồi chạy lại sensor này",
                "do_not": "Giả định upload đã fail — TikTok có thể chỉ chậm",
                "user_message": "Không check được status, thử lại sau.",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    if status != "PUBLISH_COMPLETE":
        print(json.dumps({
            "success": False,
            "error_type": "not_completed",
            "status": status,
            "remediation": {
                "explanation": f"Status là {status}, không phải PUBLISH_COMPLETE",
                "action": "wait_more_or_escalate",
                "next_step": "Đợi thêm 5 phút. Nếu vẫn không COMPLETE → báo user check TikTok app thủ công.",
                "do_not": "Ghi analytics — chưa chắc đã publish",
                "user_message": f"Video status: {status}. Đang xử lý...",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Status OK — done.
    # (Thực tế có thể thêm: check video_id có xuất hiện trong /v2/video/list/ không,
    # nhưng scope đó cần scope khác, để nâng cấp sau.)
    print(json.dumps({
        "success": True,
        "publish_id": args.publish_id,
        "status": status,
        "waited_minutes": 0 if args.skip_wait else args.wait_minutes,
        "message": "Upload verified complete. Stats sẽ có sau ~24h.",
    }, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
