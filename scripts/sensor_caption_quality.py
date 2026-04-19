#!/usr/bin/env python3
"""
Sensor: caption quality check.

Computational feedback sensor (harness engineering pattern).
Checks length, hook strength, unsafe keywords, emoji balance.
Error output has `remediation` for agent self-correction.

Exit codes:
  0 — passed all checks
  1 — failed (non-fatal, agent should rewrite)
  2 — failed (fatal, content must change)
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Unsafe keywords (extend as needed)
UNSAFE_KEYWORDS = {
    "kill", "suicide", "drugs", "cocaine", "heroin",
    "tự tử", "tự sát", "giết", "ma túy", "cần sa",
    # Political sensitive
    # Medical false claims
    "chữa khỏi", "100% khỏi", "đảm bảo",
}

# Hook weakeners (first 5 words shouldn't contain these)
WEAK_HOOK_STARTERS = [
    "chào các bạn", "hôm nay mình", "hi mọi người",
    "các bạn ơi", "xin chào", "hello everyone",
    "hi guys", "in this video",
]


def check_length(caption: str) -> list[dict]:
    """Return list of issues related to length."""
    issues = []
    char_count = len(caption)

    if char_count < 20:
        issues.append({
            "severity": "fatal",
            "issue": "too_short",
            "detail": f"{char_count} chars < 20",
            "fix": "Thêm context + payoff + CTA. Tối thiểu hook + 1 câu giải thích.",
        })
    elif char_count < 60:
        issues.append({
            "severity": "warning",
            "issue": "under_sweet_spot",
            "detail": f"{char_count} chars < 60 (sweet spot 80-150)",
            "fix": "Thêm 1 câu context hoặc CTA rõ ràng.",
        })

    if char_count > 200:
        issues.append({
            "severity": "fatal",
            "issue": "too_long",
            "detail": f"{char_count} chars > 200 (engagement drops sharply)",
            "fix": "Cắt bỏ [context] hoặc [payoff], giữ hook + CTA. Mục tiêu 80-150.",
        })
    elif char_count > 150:
        issues.append({
            "severity": "warning",
            "issue": "over_sweet_spot",
            "detail": f"{char_count} chars > 150 (sweet spot 80-150)",
            "fix": "Cắt 1 câu thừa. Ưu tiên giữ hook và CTA.",
        })

    return issues


def check_hook(caption: str) -> list[dict]:
    """Check opening 5 words strength."""
    issues = []
    words = caption.strip().split()[:5]
    first_5 = " ".join(words).lower()

    for weakener in WEAK_HOOK_STARTERS:
        if weakener in first_5:
            issues.append({
                "severity": "fatal",
                "issue": "weak_hook",
                "detail": f"Hook starts with '{weakener}' — TikTok down-ranks generic openings",
                "fix": "Invoke skill tiktok-hook-writer. Dùng framework Question/Number/POV. Bỏ hoàn toàn phần greeting.",
            })
            break

    # Hook should not have emoji (save for body)
    if words and any(_is_emoji(c) for c in words[0]):
        issues.append({
            "severity": "warning",
            "issue": "hook_has_emoji",
            "detail": "Word đầu tiên chứa emoji",
            "fix": "Bỏ emoji ở 5 từ đầu. Emoji dùng cuối câu để nhấn mạnh CTA.",
        })

    return issues


def check_safety(caption: str) -> list[dict]:
    """Check unsafe keywords."""
    issues = []
    caption_lower = caption.lower()
    for kw in UNSAFE_KEYWORDS:
        if kw in caption_lower:
            issues.append({
                "severity": "fatal",
                "issue": "unsafe_keyword",
                "detail": f"Chứa từ nhạy cảm: '{kw}'",
                "fix": "Rewrite bỏ từ này. Hoặc nếu context đòi hỏi, hỏi user confirm.",
            })
    return issues


def check_hashtags_in_caption(caption: str) -> list[dict]:
    """Caption should NOT contain hashtags (handled by separate skill)."""
    issues = []
    tags = re.findall(r"#\w+", caption)
    if tags:
        issues.append({
            "severity": "warning",
            "issue": "hashtags_in_caption",
            "detail": f"Tìm thấy {len(tags)} hashtag trong caption: {tags[:3]}",
            "fix": "Bỏ hashtag khỏi caption. Hashtag được append riêng ở bước hashtag-strategy.",
        })
    return issues


def check_emoji_balance(caption: str) -> list[dict]:
    """Too many emojis = spammy."""
    issues = []
    emoji_count = sum(1 for c in caption if _is_emoji(c))
    word_count = len(caption.split())

    if emoji_count > 5:
        issues.append({
            "severity": "warning",
            "issue": "emoji_overload",
            "detail": f"{emoji_count} emoji (recommend ≤4)",
            "fix": "Giảm xuống 2-3 emoji. Giữ emoji có mục đích, bỏ emoji decoration.",
        })
    if word_count > 0 and emoji_count > word_count / 3:
        issues.append({
            "severity": "warning",
            "issue": "emoji_density_high",
            "detail": f"Emoji density {emoji_count}/{word_count} words",
            "fix": "Emoji không nên chiếm > 1/3 số từ.",
        })
    return issues


def _is_emoji(char: str) -> bool:
    """Basic emoji detection."""
    if not char:
        return False
    code = ord(char)
    # Emoji ranges (not exhaustive but covers most)
    return (
        0x1F300 <= code <= 0x1F9FF or  # Symbols & pictographs
        0x2600 <= code <= 0x27BF or    # Misc symbols
        0x1F600 <= code <= 0x1F64F or  # Emoticons
        0x1F680 <= code <= 0x1F6FF     # Transport & map
    )


def main():
    p = argparse.ArgumentParser(description="Caption quality sensor")
    p.add_argument("--caption", help="Caption text (use --caption-file for long text)")
    p.add_argument("--caption-file", help="Read caption from file")
    args = p.parse_args()

    if args.caption_file:
        try:
            caption = Path(args.caption_file).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as e:
            print(json.dumps({
                "success": False,
                "error_type": "caption_file_read_failed",
                "raw_error": str(e),
                "remediation": {
                    "explanation": f"Không đọc được file: {args.caption_file}",
                    "action": "halt",
                    "next_step": "Verify path + file là UTF-8 text",
                    "do_not": "Giả định caption rỗng — skip sensor là lỗi nghiêm trọng",
                    "user_message": f"Không đọc được caption từ {args.caption_file}",
                },
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
    elif args.caption:
        caption = args.caption
    else:
        print(json.dumps({
            "success": False,
            "error_type": "missing_input",
            "remediation": {
                "explanation": "Không có caption để check",
                "next_step": "Pass --caption=\"...\" hoặc --caption-file=<path>",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(2)

    all_issues = []
    all_issues.extend(check_length(caption))
    all_issues.extend(check_hook(caption))
    all_issues.extend(check_safety(caption))
    all_issues.extend(check_hashtags_in_caption(caption))
    all_issues.extend(check_emoji_balance(caption))

    fatal = [i for i in all_issues if i["severity"] == "fatal"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]

    result = {
        "success": len(fatal) == 0,
        "passed": len(all_issues) == 0,
        "char_count": len(caption),
        "word_count": len(caption.split()),
        "issues": all_issues,
        "fatal_count": len(fatal),
        "warning_count": len(warnings),
    }

    if fatal:
        # Build remediation plan from all fatal issues
        result["remediation"] = {
            "explanation": f"{len(fatal)} vấn đề nghiêm trọng phải fix trước khi upload",
            "action": "rewrite_caption",
            "steps": [issue["fix"] for issue in fatal],
            "do_not": "Upload caption này — sẽ ảnh hưởng reach hoặc vi phạm policy",
            "user_message": f"Caption có {len(fatal)} lỗi, đang rewrite...",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if not fatal else 2 if any(i["issue"] == "unsafe_keyword" for i in fatal) else 1)


if __name__ == "__main__":
    main()
