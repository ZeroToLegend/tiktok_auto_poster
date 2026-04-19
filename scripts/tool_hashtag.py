#!/usr/bin/env python3
"""
CLI wrapper cho Hashtag — self-correcting error output.

Wraps HashtagGenerator (rule-based). No AI call needed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def error(error_type: str, raw_error: str, remediation: dict, exit_code: int = 1) -> None:
    print(json.dumps({
        "success": False,
        "error_type": error_type,
        "raw_error": raw_error,
        "remediation": remediation,
    }, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=True)
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--strategy", default="balanced",
                   choices=["trending", "niche", "balanced"])
    p.add_argument("--brand-tags", default="", help="Comma-separated")
    p.add_argument("--custom-pool", default="",
                   help="Path to data/custom_hashtags.json (optional)")
    args = p.parse_args()

    # Validate count
    if args.count < 1 or args.count > 10:
        error(
            "invalid_count",
            f"count={args.count}",
            {
                "explanation": "Count phải từ 1 đến 10",
                "action": "halt",
                "next_step": "Dùng --count=5 (default) hoặc 3-7 tuỳ niche",
                "do_not": "Dùng count >10 — TikTok 2026 penalty stuffing signal",
                "user_message": f"Số hashtag không hợp lệ: {args.count}. Dùng 3-7.",
            },
            exit_code=1,
        )

    # Validate topic not empty after strip
    topic = args.topic.strip()
    if not topic:
        error(
            "empty_topic",
            "topic is empty",
            {
                "explanation": "Topic rỗng → không detect được niche category",
                "action": "halt",
                "next_step": "Pass --topic=\"<chủ đề video>\" rõ ràng",
                "do_not": "Gọi với topic rỗng — sẽ fallback sang lifestyle generic",
                "user_message": "Cần topic cụ thể để suggest hashtag phù hợp.",
            },
            exit_code=1,
        )

    # Validate custom pool if provided
    if args.custom_pool:
        pool_path = Path(args.custom_pool)
        if not pool_path.exists():
            error(
                "custom_pool_missing",
                f"Path: {args.custom_pool}",
                {
                    "explanation": "File custom hashtag pool không tồn tại",
                    "action": "halt_or_default",
                    "next_step": "Verify path, hoặc bỏ --custom-pool để dùng pool mặc định",
                    "do_not": "Assume tool đã load pool — không fallback silent",
                    "user_message": f"Không tìm thấy file: {args.custom_pool}",
                },
                exit_code=1,
            )
        try:
            import json as _json
            with open(pool_path) as f:
                _json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            error(
                "custom_pool_invalid",
                f"{e}",
                {
                    "explanation": "File custom pool có JSON invalid",
                    "action": "halt",
                    "next_step": f"Fix syntax lỗi trong {args.custom_pool}. "
                                 f"Check template tại templates/coding-creator/hashtag-pool.json",
                    "do_not": "Proceed với pool corrupt",
                    "user_message": "Custom hashtag pool JSON lỗi syntax.",
                },
                exit_code=1,
            )

    # Main work
    try:
        from tools.hashtag_generator import HashtagGenerator
    except ImportError as e:
        error(
            "import_failed",
            f"{e}",
            {
                "explanation": "Không import được HashtagGenerator",
                "action": "halt",
                "next_step": "Check `tools/hashtag_generator.py` tồn tại. Chạy `pip install -r requirements.txt`",
                "do_not": "Retry — structural issue",
                "user_message": "Module thiếu, check setup.",
            },
            exit_code=2,
        )

    brand = [t.strip() for t in args.brand_tags.split(",") if t.strip()]

    try:
        hg = HashtagGenerator(
            brand_tags=brand,
            custom_pool=args.custom_pool or None,
        )
        tags = hg.suggest(topic, count=args.count, strategy=args.strategy)
    except Exception as e:
        error(
            "generation_failed",
            f"{type(e).__name__}: {e}",
            {
                "explanation": "HashtagGenerator raised exception khi suggest",
                "action": "halt_and_log",
                "next_step": "Log raw error. Thử với strategy=balanced nếu đang dùng strategy khác.",
                "do_not": "Return empty hashtag list — pipeline sau sẽ fail",
                "user_message": "Lỗi khi generate hashtag.",
            },
            exit_code=2,
        )

    # Validate output
    if not tags:
        error(
            "no_hashtags_generated",
            f"empty list for topic={topic}",
            {
                "explanation": "HashtagGenerator returned empty — topic không match category nào",
                "action": "use_defaults_or_retry",
                "next_step": "Dùng strategy=trending để fallback sang #fyp + evergreen tags",
                "do_not": "Post without hashtags — giảm reach nặng",
                "user_message": f"Không gợi ý được hashtag cho topic '{topic}'. Thử topic khác hoặc strategy=trending.",
            },
            exit_code=1,
        )

    # Sanity check: total length
    total_len = sum(len(t) + 1 for t in tags)  # +1 for '#' prefix
    warnings = []
    if total_len > 100:
        warnings.append(f"Total length {total_len} chars > 100 recommended — consider reducing count")

    print(json.dumps({
        "success": True,
        "hashtags": tags,
        "count": len(tags),
        "total_chars": total_len,
        "strategy": args.strategy,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
