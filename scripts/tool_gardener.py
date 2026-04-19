#!/usr/bin/env python3
"""
Harness gardener tool — self-correcting error output.

Scans logs + analytics for patterns worth proposing as harness updates.
Never modifies SKILL.md — only emits proposals to .agents/memory.md.
"""
import argparse
import datetime as dt
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
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


def scan_repeated_errors(days: int = 7, min_count: int = 3) -> list[dict]:
    """Find error types occurring ≥min_count in last N days."""
    log = ROOT / "logs" / "agent.log"
    if not log.exists():
        return []  # no log yet is not an error

    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    error_types = Counter()
    error_samples = defaultdict(list)

    patterns = [
        re.compile(r'error_type["\':\s]+(\w+)'),
        re.compile(r'spam_risk_(\w+)'),
        re.compile(r'unaudited_client_(\w+)'),
        re.compile(r'rate_limit_(\w+)'),
    ]

    try:
        with open(log, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "[ERROR]" not in line and "❌" not in line:
                    continue
                match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if not match:
                    continue
                try:
                    ts = dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if ts < cutoff:
                    continue
                for pat in patterns:
                    m = pat.search(line)
                    if m:
                        etype = m.group(1)
                        error_types[etype] += 1
                        if len(error_samples[etype]) < 3:
                            error_samples[etype].append({
                                "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                                "line": line.strip()[:200],
                            })
                        break
    except (PermissionError, OSError) as e:
        raise RuntimeError(f"Cannot read log file: {e}")

    return [
        {
            "error_type": etype,
            "count": count,
            "samples": error_samples[etype],
            "proposal_priority": "HIGH" if "spam" in etype or "ban" in etype else "MEDIUM",
        }
        for etype, count in error_types.most_common()
        if count >= min_count
    ]


def scan_post_patterns(days: int = 30) -> dict:
    """Compare top-20% vs bottom-20% posts to find patterns."""
    db = ROOT / "data" / "analytics.db"
    if not db.exists():
        return {"error": "analytics.db missing — no posts tracked yet"}

    cutoff = time.time() - days * 86400
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT p.publish_id, p.caption, p.hashtags, p.posted_at,
                       COALESCE(s.views, 0) as views
                FROM posts p
                LEFT JOIN stats_snapshots s ON s.id = (
                    SELECT MAX(id) FROM stats_snapshots WHERE publish_id = p.publish_id
                )
                WHERE p.posted_at >= ?
                ORDER BY views DESC
            """, (cutoff,)).fetchall()
    except sqlite3.Error as e:
        return {"error": f"SQLite error: {e}"}

    posts = [dict(r) for r in rows]
    if len(posts) < 10:
        return {"error": f"only {len(posts)} posts, need ≥10 for pattern analysis"}

    n = len(posts)
    top_n = max(2, n // 5)
    top = posts[:top_n]
    bottom = posts[-top_n:]

    def stats(group):
        lengths = [len(p["caption"] or "") for p in group]
        hours = [dt.datetime.fromtimestamp(p["posted_at"]).hour for p in group]
        first_tags = []
        for p in group:
            try:
                tags = json.loads(p["hashtags"] or "[]")
                if tags:
                    first_tags.append(tags[0])
            except json.JSONDecodeError:
                pass
        avg_views = sum(p["views"] for p in group) / len(group) if group else 0
        return {
            "avg_views": avg_views,
            "avg_caption_length": sum(lengths) / len(lengths) if lengths else 0,
            "most_common_hour": Counter(hours).most_common(1)[0] if hours else None,
            "most_common_first_tag": Counter(first_tags).most_common(1)[0] if first_tags else None,
        }

    top_stats = stats(top)
    bot_stats = stats(bottom)

    return {
        "sample_size": n,
        "top_group": top_stats,
        "bottom_group": bot_stats,
        "view_ratio": top_stats["avg_views"] / bot_stats["avg_views"]
                      if bot_stats["avg_views"] else None,
        "length_diff": top_stats["avg_caption_length"] - bot_stats["avg_caption_length"],
    }


def generate_proposals(errors: list[dict], patterns: dict) -> list[dict]:
    """Turn signals into actionable proposals."""
    proposals = []

    for err in errors:
        etype = err["error_type"]
        if "spam" in etype or "ban" in etype:
            proposals.append({
                "priority": "HIGH",
                "title": f"Repeated error: {etype} ({err['count']}×)",
                "target_file": ".claude/skills/tiktok-scheduler/SKILL.md or relevant skill",
                "signal": f"Error '{etype}' occurred {err['count']} times in window",
                "proposed_action": (
                    f"Add preemptive check in skill to avoid triggering {etype}. "
                    f"Review samples and tighten pre-upload validation."
                ),
                "evidence": err["samples"],
            })
        elif "unsafe_keyword" in etype or "safety" in etype:
            proposals.append({
                "priority": "HIGH",
                "title": "Expand safety blacklist",
                "target_file": "scripts/sensor_caption_quality.py + tiktok-caption-writer SKILL.md",
                "signal": f"{err['count']} safety violations caught this window",
                "proposed_action": (
                    "Review blocked captions. Extract common unsafe keyword patterns. "
                    "Add to UNSAFE_KEYWORDS set in sensor_caption_quality.py."
                ),
                "evidence": err["samples"],
            })
        else:
            proposals.append({
                "priority": "MEDIUM",
                "title": f"Investigate repeated: {etype}",
                "target_file": "Check logs for root cause",
                "signal": f"{err['count']}× in window",
                "proposed_action": "Trace to source tool, add earlier detection.",
                "evidence": err["samples"],
            })

    if "error" not in patterns and patterns.get("view_ratio") and patterns["view_ratio"] >= 3:
        top = patterns["top_group"]
        bot = patterns["bottom_group"]

        if top["most_common_hour"] and bot["most_common_hour"]:
            if top["most_common_hour"][0] != bot["most_common_hour"][0]:
                proposals.append({
                    "priority": "MEDIUM",
                    "title": f"Update golden_hours — top posts cluster at {top['most_common_hour'][0]}h",
                    "target_file": "config/config.yaml",
                    "signal": f"Top 20% at {top['most_common_hour'][0]}h "
                             f"(avg {top['avg_views']:.0f} views), "
                             f"bottom 20% at {bot['most_common_hour'][0]}h "
                             f"(avg {bot['avg_views']:.0f} views).",
                    "proposed_action": (
                        f"Elevate {top['most_common_hour'][0]}h in golden_hours list. "
                        f"Consider deprioritizing {bot['most_common_hour'][0]}h."
                    ),
                })

        if abs(patterns.get("length_diff", 0)) > 50:
            direction = "shorter" if patterns["length_diff"] < 0 else "longer"
            proposals.append({
                "priority": "LOW",
                "title": f"Caption length signal: top posts are {direction}",
                "target_file": ".claude/skills/tiktok-caption-writer/SKILL.md",
                "signal": f"Top posts avg {top['avg_caption_length']:.0f} chars vs "
                         f"bottom {bot['avg_caption_length']:.0f} chars.",
                "proposed_action": (
                    f"Adjust sweet spot in caption-writer. Current is 80-150; "
                    f"data suggests {'60-120' if direction == 'shorter' else '120-180'}."
                ),
            })

    return proposals


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--write-memory", action="store_true",
                   help="Append proposals to .agents/memory.md")

    args = p.parse_args()

    # Validate days
    if args.days < 1 or args.days > 365:
        error(
            "invalid_days",
            f"days={args.days}",
            {
                "explanation": "Days phải từ 1 đến 365",
                "action": "halt",
                "next_step": "Dùng --days=7 (weekly) hoặc --days=30 (monthly)",
                "do_not": "Scan quá rộng — noise cao, quá hẹp — không đủ data",
                "user_message": f"Days không hợp lệ: {args.days}. Dùng 1-365.",
            },
            exit_code=1,
        )

    if args.cmd == "scan":
        # Collect signals
        try:
            errors = scan_repeated_errors(days=args.days)
        except RuntimeError as e:
            error(
                "log_read_failed",
                str(e),
                {
                    "explanation": "Không đọc được logs/agent.log",
                    "action": "check_permissions",
                    "next_step": "Check `ls -la logs/agent.log` — file readable không?",
                    "do_not": "Skip log — error signal quan trọng nhất cho gardener",
                    "user_message": "Không đọc được log file.",
                },
                exit_code=2,
            )

        patterns = scan_post_patterns(days=max(args.days, 30))

        # Generate proposals
        try:
            proposals = generate_proposals(errors, patterns)
        except Exception as e:
            error(
                "proposal_generation_failed",
                f"{type(e).__name__}: {e}",
                {
                    "explanation": "Lỗi khi generate proposals từ signals",
                    "action": "halt_and_log",
                    "next_step": "Report bug. Signals vẫn dùng được — xem repeated_errors/post_patterns trực tiếp.",
                    "do_not": "Pretend proposals list empty — user mất signal",
                    "user_message": "Lỗi internal khi generate proposals.",
                },
                exit_code=2,
            )

        result = {
            "success": True,
            "scanned_days": args.days,
            "repeated_errors_count": len(errors),
            "repeated_errors": errors,
            "post_patterns": patterns,
            "proposals_count": len(proposals),
            "proposals": proposals,
        }

        # Optionally append to memory
        if args.write_memory and proposals:
            try:
                summary = (
                    f"Scan {dt.datetime.now():%Y-%m-%d}: {len(proposals)} proposals "
                    f"({sum(1 for p in proposals if p['priority']=='HIGH')} HIGH). See full scan output."
                )
                memory_tool = ROOT / "scripts" / "tool_memory.py"
                ret = subprocess.run(
                    ["python", str(memory_tool),
                     "append", "--section=learned-rules", f"--text={summary}"],
                    capture_output=True, text=True, timeout=10,
                )
                if ret.returncode == 0:
                    result["memory_updated"] = True
                else:
                    result["memory_update_warning"] = {
                        "stderr": ret.stderr[:200],
                        "remediation": {
                            "explanation": "Không append được vào memory.md",
                            "action": "retry_manually",
                            "next_step": (
                                f"Chạy thủ công: python scripts/tool_memory.py "
                                f"append --section=learned-rules --text=\"{summary}\""
                            ),
                            "do_not": "Bỏ qua — proposals sẽ bị mất nếu không lưu",
                            "user_message": "Proposals generated nhưng chưa lưu vào memory.",
                        },
                    }
            except subprocess.TimeoutExpired:
                result["memory_update_warning"] = {
                    "error": "timeout calling tool_memory.py",
                    "remediation": {
                        "explanation": "tool_memory.py timeout sau 10s",
                        "action": "retry_manually",
                        "next_step": "Append thủ công như trên",
                    },
                }
            except Exception as e:
                result["memory_update_warning"] = {
                    "error": str(e),
                    "remediation": {
                        "explanation": "Lỗi không xác định khi append memory",
                        "action": "retry_manually",
                        "next_step": "Check .agents/memory.md tồn tại + writable",
                    },
                }

        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
