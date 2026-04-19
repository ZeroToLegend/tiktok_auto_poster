#!/usr/bin/env python3
"""
CLI wrapper cho TikTok upload — với self-correcting error messages.

Every error output has a `remediation` field that tells the agent
EXACTLY what to do next. This is a harness engineering pattern:
error messages are a prompt injection opportunity.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_agent import load_config
from tools.tiktok_api import TikTokAPI, TikTokUploadError


# ============================================================
# Remediation map: error_type → {explanation, action, steps}
# ============================================================
REMEDIATION_MAP = {
    "spam_risk_too_many_posts": {
        "explanation": "Account đã đăng 6+ posts trong 24h, TikTok hard-cap",
        "action": "halt",
        "retry": False,
        "next_step": "Invoke tiktok-scheduler enqueue với --when=<24h_from_now>",
        "do_not": "retry ngay — sẽ làm TikTok flag account nặng hơn",
        "user_message": "Quota hôm nay đã hết. Auto-schedule cho 24h sau.",
    },
    "spam_risk_user_banned_from_posting": {
        "explanation": "Account bị TikTok tạm khóa quyền đăng bài",
        "action": "halt",
        "retry": False,
        "next_step": "Dừng hoàn toàn. Báo user check email TikTok gửi.",
        "do_not": "retry hoặc thử account khác từ cùng IP",
        "user_message": "Account bị TikTok khóa đăng. Kiểm tra email + đợi 24-48h.",
    },
    "reached_active_user_cap": {
        "explanation": "App unaudited đạt cap 5 active user/24h",
        "action": "halt_or_fallback",
        "retry": False,
        "next_step": "Chuyển sang tiktok-advisory-mode hoặc đợi 24h reset",
        "do_not": "tạo thêm user để bypass — TikTok detect được",
        "user_message": "App chưa audit hết quota user. Chuyển sang advisory-mode?",
    },
    "unaudited_client_can_only_post_to_private_accounts": {
        "explanation": "App chưa audit, chỉ post được lên private account",
        "action": "halt_or_fallback",
        "retry": False,
        "next_step": "Chuyển account sang private TRƯỚC, hoặc dùng tiktok-advisory-mode",
        "do_not": "force PUBLIC privacy — TikTok override về SELF_ONLY",
        "user_message": "App chưa audit. Cần chuyển account sang private hoặc đăng thủ công.",
    },
    "rate_limit_exceeded": {
        "explanation": "Gọi API quá nhanh, hit rate limit tạm thời",
        "action": "wait_and_retry",
        "retry": True,
        "wait_seconds": 900,
        "next_step": "sleep 900s rồi tự động retry. Không báo user trừ khi fail lần 2.",
        "do_not": "retry ngay, sẽ nhân đôi penalty",
        "user_message": None,  # silent unless fails again
    },
    "publish_rate_exceeded": {
        "explanation": "Publish quá nhanh giữa các video",
        "action": "wait_and_retry",
        "retry": True,
        "wait_seconds": 1800,
        "next_step": "sleep 1800s (30 phút) rồi retry",
        "do_not": "thử publish video khác cùng lúc",
        "user_message": None,
    },
    "video_pull_failed": {
        "explanation": "TikTok server không đọc được file video",
        "action": "retry_with_backoff",
        "retry": True,
        "max_retries": 3,
        "next_step": "Retry 3 lần với exponential backoff (1s, 2s, 4s)",
        "do_not": "resize/re-process video — thường là lỗi transient",
        "user_message": None,
    },
    "invalid_file_upload": {
        "explanation": "File video không hợp lệ (codec, size, duration)",
        "action": "reprocess",
        "retry": False,
        "next_step": "Chạy lại skill tiktok-video-prep với input gốc",
        "do_not": "upload lại cùng file — sẽ fail tương tự",
        "user_message": "File video không hợp lệ. Đang chuẩn hóa lại.",
    },
    "authentication_failed": {
        "explanation": "Access token hết hạn hoặc invalid",
        "action": "refresh_and_retry",
        "retry": True,
        "next_step": "Gọi api.ensure_token_valid() rồi retry. Nếu vẫn fail → user cần re-login",
        "do_not": "giả định token vẫn valid",
        "user_message": "Token hết hạn, đang refresh...",
    },
    "file_too_large": {
        "explanation": "Video >287.6 MB, vượt limit TikTok",
        "action": "reprocess_compress",
        "retry": False,
        "next_step": "Chạy tiktok-video-prep với CRF cao hơn (28 thay vì 23) để giảm size",
        "do_not": "upload — sẽ fail",
        "user_message": "Video quá lớn, đang nén lại.",
    },
    "unknown": {
        "explanation": "Lỗi không xác định từ TikTok API",
        "action": "halt_and_log",
        "retry": False,
        "next_step": "Log full error, báo user. Không retry blind.",
        "do_not": "retry without reading error message",
        "user_message": "Gặp lỗi lạ. Kiểm tra logs/agent.log.",
    },
}


def classify_error(error_msg: str) -> str:
    """Map raw error string → remediation key."""
    msg = error_msg.lower()
    if "spam_risk" in msg and ("too_many" in msg or "too many" in msg):
        return "spam_risk_too_many_posts"
    if "spam_risk" in msg and "banned" in msg:
        return "spam_risk_user_banned_from_posting"
    if "active_user_cap" in msg or "user cap" in msg:
        return "reached_active_user_cap"
    if "unaudited" in msg and "private" in msg:
        return "unaudited_client_can_only_post_to_private_accounts"
    if "rate_limit" in msg or "rate limit" in msg:
        return "rate_limit_exceeded"
    if "publish_rate" in msg:
        return "publish_rate_exceeded"
    if "video_pull" in msg or "pull failed" in msg:
        return "video_pull_failed"
    if "invalid" in msg and ("file" in msg or "upload" in msg):
        return "invalid_file_upload"
    if "auth" in msg or "token" in msg or "401" in msg:
        return "authentication_failed"
    if "too large" in msg or "287" in msg:
        return "file_too_large"
    return "unknown"


def build_error_output(raw_error: str) -> dict:
    """Build self-correcting error output with remediation."""
    error_type = classify_error(raw_error)
    remediation = REMEDIATION_MAP[error_type].copy()
    return {
        "success": False,
        "error_type": error_type,
        "raw_error": raw_error,
        "remediation": remediation,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--caption", required=True)
    p.add_argument("--hashtags", default="")
    p.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                   choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"])
    p.add_argument("--disable-duet", action="store_true")
    p.add_argument("--disable-stitch", action="store_true")
    p.add_argument("--disable-comment", action="store_true")
    args = p.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error_type": "config_load_failed",
            "raw_error": str(e),
            "remediation": {
                "explanation": "Không load được config/env",
                "action": "halt",
                "next_step": "Check config/.env có đủ TIKTOK_CLIENT_KEY, TIKTOK_ACCESS_TOKEN",
                "do_not": "proceed với credential rỗng",
                "user_message": "Thiếu credential. Chạy oauth_setup.py.",
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

    tags = " ".join(f"#{t.strip().lstrip('#')}"
                    for t in args.hashtags.split(",") if t.strip())
    full_caption = f"{args.caption}\n\n{tags}".strip()

    try:
        publish_id = api.upload_video(
            video_path=Path(args.video),
            caption=full_caption,
            privacy=args.privacy,
            disable_duet=args.disable_duet,
            disable_stitch=args.disable_stitch,
            disable_comment=args.disable_comment,
        )
        final_status = api.wait_for_publish(publish_id, timeout=300)

        if final_status == "PUBLISH_COMPLETE":
            print(json.dumps({
                "success": True,
                "publish_id": publish_id,
                "status": final_status,
                "caption_preview": full_caption[:100],
            }, ensure_ascii=False, indent=2))
            sys.exit(0)
        else:
            print(json.dumps(build_error_output(f"Final status: {final_status}"),
                             ensure_ascii=False, indent=2))
            sys.exit(2)

    except TikTokUploadError as e:
        print(json.dumps(build_error_output(str(e)),
                         ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps(build_error_output(f"Unexpected: {e}"),
                         ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
