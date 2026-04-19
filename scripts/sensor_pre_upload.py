#!/usr/bin/env python3
"""
Sensor: pre-upload validation.

Run RIGHT BEFORE tool_upload.py. Validates entire precondition chain:
  - Video file exists + processed
  - Hash not duplicate
  - Quota available
  - Token valid
  - Audit status matches requested privacy
  - Video meets TikTok spec

Exit 0 → safe to upload
Exit 1 → blocker found, check remediation
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config
from tools.video_processor import VideoProcessor
from tools.scheduler import PostScheduler


def check(name: str, passed: bool, detail: str, fix: str) -> dict:
    return {"check": name, "passed": passed, "detail": detail, "fix": fix}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--account", default="default")
    p.add_argument("--privacy", default="PUBLIC_TO_EVERYONE")
    args = p.parse_args()

    results = []
    blockers = []

    # --------------------------------------------------------
    # 1. Video file exists + is processed
    # --------------------------------------------------------
    video_path = Path(args.video)
    if not video_path.exists():
        results.append(check(
            "file_exists", False,
            f"Path không tồn tại: {args.video}",
            "Verify path. Nếu video chưa qua process, gọi tool_process_video.py --action=prepare trước.",
        ))
        blockers.append("file_exists")
    else:
        results.append(check("file_exists", True, f"{video_path.stat().st_size//1024} KB", ""))

        # Processed file should be in data/processed/
        if "processed" not in str(video_path) and not video_path.name.startswith("tt_"):
            results.append(check(
                "is_processed", False,
                "File chưa qua video-prep (không có prefix 'tt_' hoặc không ở data/processed/)",
                "Chạy `python scripts/tool_process_video.py --input=<path> --action=prepare` trước khi upload.",
            ))
            blockers.append("is_processed")
        else:
            results.append(check("is_processed", True, "Prefix tt_ detected", ""))

    # --------------------------------------------------------
    # 2. Video meets TikTok spec
    # --------------------------------------------------------
    if video_path.exists():
        try:
            vp = VideoProcessor()
            info = vp.probe(video_path)
            size_mb = video_path.stat().st_size / 1e6

            # Size check
            if size_mb > 287.6:
                results.append(check(
                    "size_limit", False,
                    f"{size_mb:.1f} MB > 287.6 MB",
                    "Chạy lại video-prep với CRF cao hơn (28 thay vì 23) hoặc trim.",
                ))
                blockers.append("size_limit")
            else:
                results.append(check("size_limit", True, f"{size_mb:.1f} MB / 287.6 MB", ""))

            # Duration check
            if info["duration"] < 3:
                results.append(check(
                    "duration", False,
                    f"{info['duration']:.1f}s < 3s (TikTok min)",
                    "Video quá ngắn, TikTok sẽ reject. Dùng video dài hơn.",
                ))
                blockers.append("duration")
            elif info["duration"] > 180:
                results.append(check(
                    "duration", False,
                    f"{info['duration']:.1f}s > 180s",
                    "Chạy video-prep với --trim=<seconds> để cắt ngắn.",
                ))
                blockers.append("duration")
            else:
                results.append(check("duration", True, f"{info['duration']:.1f}s", ""))

            # Dimensions check (flexible — not strict 1080×1920 but 9:16 ratio)
            if info["width"] == 0 or info["height"] == 0:
                results.append(check(
                    "dimensions", False,
                    "No video stream",
                    "File corrupt hoặc không có video stream. Re-export từ source.",
                ))
                blockers.append("dimensions")
            else:
                ratio = info["width"] / info["height"]
                if abs(ratio - 0.5625) > 0.05:  # Not 9:16
                    results.append(check(
                        "dimensions", False,
                        f"{info['width']}×{info['height']} (ratio {ratio:.3f}, not 9:16=0.5625)",
                        "Chạy video-prep để resize 9:16 (1080×1920).",
                    ))
                    blockers.append("dimensions")
                else:
                    results.append(check(
                        "dimensions", True,
                        f"{info['width']}×{info['height']} ✓ 9:16", "",
                    ))
        except Exception as e:
            results.append(check(
                "video_probe", False,
                f"Probe failed: {e}",
                "File có thể corrupt. Thử re-export hoặc convert MP4 H.264.",
            ))
            blockers.append("video_probe")

    # --------------------------------------------------------
    # 3. Load config + check token
    # --------------------------------------------------------
    try:
        config = load_config()
    except Exception as e:
        results.append(check(
            "config_load", False,
            f"Config error: {e}",
            "Check config/.env có TIKTOK_CLIENT_KEY, TIKTOK_ACCESS_TOKEN. Chạy oauth_setup.py nếu chưa có token.",
        ))
        blockers.append("config_load")
        # Can't continue without config
        _emit(results, blockers)
        return

    token = config["tiktok"].get("access_token", "")
    if not token:
        results.append(check(
            "token_present", False,
            "TIKTOK_ACCESS_TOKEN empty",
            "Chạy `python scripts/oauth_setup.py` để lấy token, hoặc chuyển sang advisory-mode.",
        ))
        blockers.append("token_present")
    else:
        results.append(check("token_present", True, "token found", ""))

    # --------------------------------------------------------
    # 4. Quota check
    # --------------------------------------------------------
    try:
        sch = PostScheduler(db_path=config["queue_db"])
        today_count = sch.count_published_today(args.account)
        if today_count >= 6:
            results.append(check(
                "quota", False,
                f"{today_count}/6 posts today",
                "Đã hết quota ngày. Schedule cho mai bằng tool_schedule.py enqueue --when=<tomorrow>.",
            ))
            blockers.append("quota")
        else:
            results.append(check(
                "quota", True,
                f"{today_count}/6 used, {6-today_count} remaining", "",
            ))

        # Duplicate check
        if video_path.exists():
            vp = VideoProcessor()
            video_hash = vp.compute_hash(video_path)
            is_dup = sch.was_posted_recently(video_hash, days=7)
            if is_dup:
                results.append(check(
                    "not_duplicate", False,
                    f"Hash {video_hash[:12]}... đã đăng trong 7 ngày",
                    "KHÔNG upload. Đổi video khác hoặc edit đáng kể rồi re-hash.",
                ))
                blockers.append("not_duplicate")
            else:
                results.append(check(
                    "not_duplicate", True,
                    f"Hash {video_hash[:12]}... unique", "",
                ))
    except Exception as e:
        results.append(check(
            "scheduler_db", False,
            f"Scheduler DB error: {e}",
            "Check data/queue.db tồn tại và writable. Chạy scripts/setup.sh nếu cần.",
        ))
        blockers.append("scheduler_db")

    # --------------------------------------------------------
    # 5. Audit status vs privacy
    # --------------------------------------------------------
    # Detect audit status from env
    is_audited = os.environ.get("TIKTOK_APP_AUDITED", "false").lower() == "true"
    if not is_audited and args.privacy == "PUBLIC_TO_EVERYONE":
        results.append(check(
            "audit_privacy_match", False,
            "App chưa audit nhưng request PUBLIC_TO_EVERYONE",
            "TikTok sẽ force SELF_ONLY. Để đúng expectation, dùng --privacy=SELF_ONLY, hoặc chuyển sang tiktok-advisory-mode, hoặc submit audit app.",
        ))
        # Not a blocker — TikTok will handle it, but warn agent
    else:
        results.append(check("audit_privacy_match", True, f"privacy={args.privacy}", ""))

    _emit(results, blockers)


def _emit(results: list, blockers: list) -> None:
    output = {
        "success": len(blockers) == 0,
        "checks_total": len(results),
        "checks_passed": sum(1 for r in results if r["passed"]),
        "blockers": blockers,
        "results": results,
    }

    if blockers:
        # Aggregate remediation
        fixes = [r["fix"] for r in results if not r["passed"] and r["fix"]]
        output["remediation"] = {
            "explanation": f"{len(blockers)} blocker(s): {', '.join(blockers)}",
            "action": "halt_upload",
            "steps": fixes,
            "do_not": "Upload khi có blocker — sẽ fail hoặc vi phạm policy",
            "user_message": f"Pre-upload check failed: {len(blockers)} issues. Đang fix...",
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if not blockers else 1)


if __name__ == "__main__":
    main()
