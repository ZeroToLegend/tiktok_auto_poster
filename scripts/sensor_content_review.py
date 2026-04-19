#!/usr/bin/env python3
"""
Sensor: inferential content review (LLM-as-judge).

Uses Claude CLI to evaluate caption + hook quality semantically.
More expensive than computational sensors — run ONLY for:
  - High-stakes posts (user flag --critical)
  - After 2+ failed computational sensor iterations
  - Weekly sampling for quality baseline

Not part of default pipeline (too slow for every post).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


REVIEW_PROMPT_TEMPLATE = """Bạn là expert reviewer TikTok, đánh giá nghiêm khắc.

Context creator:
{context}

Hook đề xuất: "{hook}"
Caption đầy đủ: "{caption}"
Hashtags: {hashtags}

Đánh giá 5 tiêu chí, mỗi cái 1-10 (10 = xuất sắc):

1. HOOK_STRENGTH — 5 từ đầu có tension/specific/stop-the-scroll không?
2. CONTEXT_FIT — match với niche/pillar/voice trong context không?
3. RETENTION_POTENTIAL — đọc hết không? có payoff đủ motivate không?
4. SAFETY — có risk vi phạm policy (medical/legal/politic/copyright) không? (10=an toàn)
5. HASHTAG_RELEVANCE — tag có match content và audience không?

Trả về DUY NHẤT JSON (không markdown fence, không giải thích):
{{
  "scores": {{
    "hook_strength": <1-10>,
    "context_fit": <1-10>,
    "retention_potential": <1-10>,
    "safety": <1-10>,
    "hashtag_relevance": <1-10>
  }},
  "overall": <average of 5 scores, 1 decimal>,
  "verdict": "approve" | "revise" | "reject",
  "top_issue": "<câu ngắn mô tả vấn đề chính, hoặc null nếu approve>",
  "suggested_rewrite": "<nếu revise: hook/caption đề xuất, else null>"
}}

Threshold:
- overall ≥ 7.5 → approve
- overall 5.5-7.4 → revise (return suggested_rewrite)
- overall < 5.5 OR safety ≤ 5 → reject"""


def call_claude_cli(prompt: str, timeout: int = 120) -> str:
    """Call claude CLI, return stdout."""
    if not shutil.which("claude"):
        raise RuntimeError(
            "`claude` CLI không tìm thấy. "
            "Cài: https://docs.claude.com/en/docs/claude-code/setup"
        )

    result = subprocess.run(
        ["claude", "-p", prompt,
         "--append-system-prompt",
         "Bạn trả về DUY NHẤT JSON hợp lệ, không markdown, không preamble."],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr[:300]}")

    return result.stdout.strip()


def parse_judge_response(raw: str) -> dict:
    """Strip fences and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude trả về JSON invalid: {e}\nRaw: {cleaned[:300]}")


def load_context() -> str:
    """Load .agents/tiktok-context.md if present."""
    ctx_path = ROOT / ".agents" / "tiktok-context.md"
    if ctx_path.exists():
        return ctx_path.read_text(encoding="utf-8")
    return "(no context file found)"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hook", required=True)
    p.add_argument("--caption", required=True,
                   help="Full caption (including hook at start)")
    p.add_argument("--hashtags", default="",
                   help="Comma-separated hashtags without '#'")
    p.add_argument("--critical", action="store_true",
                   help="User marked this post as critical — full review")
    args = p.parse_args()

    context = load_context()
    tags_display = ", ".join(f"#{t.strip().lstrip('#')}"
                             for t in args.hashtags.split(",") if t.strip())

    prompt = REVIEW_PROMPT_TEMPLATE.format(
        context=context[:2000],  # limit context size
        hook=args.hook,
        caption=args.caption,
        hashtags=tags_display or "(none)",
    )

    try:
        raw = call_claude_cli(prompt)
        review = parse_judge_response(raw)
    except RuntimeError as e:
        print(json.dumps({
            "success": False,
            "error_type": "claude_cli_failed",
            "raw_error": str(e),
            "remediation": {
                "explanation": "Không gọi được Claude CLI",
                "action": "skip_or_install",
                "next_step": "Bỏ qua inferential sensor (pipeline vẫn chạy với computational sensors), "
                             "hoặc cài claude CLI và login",
                "do_not": "Block pipeline chỉ vì inferential sensor — nó là advisory only",
                "user_message": "Skip quality review (Claude CLI không available).",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    except ValueError as e:
        print(json.dumps({
            "success": False,
            "error_type": "parse_failed",
            "raw_error": str(e),
            "remediation": {
                "explanation": "Claude response không phải JSON valid",
                "action": "retry_once",
                "next_step": "Retry 1 lần. Nếu vẫn fail → skip sensor.",
                "user_message": "Quality review glitch, skipping.",
            },
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Normalize verdict
    verdict = review.get("verdict", "revise")
    safety = review.get("scores", {}).get("safety", 10)
    overall = review.get("overall", 0)

    # Override verdict if safety too low
    if safety <= 5 and verdict != "reject":
        verdict = "reject"
        review["verdict"] = "reject"
        review["top_issue"] = f"Safety score {safety}/10 — {review.get('top_issue', 'safety concern')}"

    result = {
        "success": True,
        "verdict": verdict,
        "overall_score": overall,
        "scores": review.get("scores", {}),
        "top_issue": review.get("top_issue"),
        "suggested_rewrite": review.get("suggested_rewrite"),
    }

    if verdict == "reject":
        result["remediation"] = {
            "explanation": f"Content rejected by LLM judge (overall {overall}, safety {safety})",
            "action": "rewrite_from_scratch",
            "next_step": "Invoke tiktok-hook-writer + tiktok-caption-writer again với feedback từ top_issue",
            "do_not": "Force upload bỏ qua judge — có thể là safety violation",
            "user_message": f"Review từ chối: {review.get('top_issue', 'unknown')}. Rewrite?",
        }
    elif verdict == "revise":
        result["remediation"] = {
            "explanation": f"Content cần revise (overall {overall}/10)",
            "action": "apply_suggested_rewrite",
            "next_step": "Dùng suggested_rewrite từ response, hoặc invoke caption-writer lại",
            "user_message": f"Score {overall}/10, có thể improve. Apply suggestion?",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Exit code: 0 approve, 1 revise (non-fatal), 2 reject (fatal)
    sys.exit(0 if verdict == "approve" else 2 if verdict == "reject" else 1)


if __name__ == "__main__":
    main()
