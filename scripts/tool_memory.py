#!/usr/bin/env python3
"""
Memory file refresher.

Keeps .agents/memory.md in sync with actual state:
  - Recent posts from analytics.db
  - Recent errors from logs/agent.log
  - Leaves manual sections (experiments, todos, learned rules) untouched

Run via cron daily, or agent calls this at pipeline start.
"""
import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MEMORY_PATH = ROOT / ".agents" / "memory.md"

# Section markers in memory.md
AUTO_POSTS_MARKER = ("## Recent posts (last 7 days)", "## Recent errors")
AUTO_ERRORS_MARKER = ("## Recent errors (last 7 days)", "## Active experiments")


def fetch_recent_posts(days: int = 7, limit: int = 10) -> list[dict]:
    """Get recent posts from analytics.db."""
    db = ROOT / "data" / "analytics.db"
    if not db.exists():
        return []

    cutoff = time.time() - days * 86400
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT p.publish_id, p.caption, p.hashtags, p.posted_at,
                   COALESCE(s.views, 0) as views,
                   COALESCE(s.likes, 0) as likes
            FROM posts p
            LEFT JOIN stats_snapshots s ON s.id = (
                SELECT MAX(id) FROM stats_snapshots WHERE publish_id = p.publish_id
            )
            WHERE p.posted_at >= ?
            ORDER BY p.posted_at DESC
            LIMIT ?
        """, (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]


def fetch_recent_errors(days: int = 7, limit: int = 10) -> list[dict]:
    """Extract errors from agent.log (simple grep)."""
    log = ROOT / "logs" / "agent.log"
    if not log.exists():
        return []

    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    errors = []

    with open(log, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "[ERROR]" not in line and "❌" not in line:
                continue
            # Parse timestamp (format: "2026-04-18 13:55:00,xxx [ERROR] ...")
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if not match:
                continue
            try:
                ts = dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if ts < cutoff:
                continue
            errors.append({
                "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                "message": line.strip()[:200],
            })

    return errors[-limit:]


def format_posts_section(posts: list[dict]) -> str:
    if not posts:
        return "(no posts in last 7 days)"

    lines = ["| Date | First tag | Views | Likes |", "|---|---|---|---|"]
    for p in posts:
        date_str = dt.datetime.fromtimestamp(p["posted_at"]).strftime("%Y-%m-%d %H:%M")
        tags = json.loads(p["hashtags"] or "[]")
        first_tag = f"#{tags[0]}" if tags else "-"
        views = f"{p['views']:,}" if p['views'] else "(pending)"
        likes = f"{p['likes']:,}" if p['likes'] else "-"
        lines.append(f"| {date_str} | {first_tag} | {views} | {likes} |")
    return "\n".join(lines)


def format_errors_section(errors: list[dict]) -> str:
    if not errors:
        return "(no errors in last 7 days)"

    lines = []
    for e in errors:
        lines.append(f"- **{e['timestamp']}** — {e['message']}")
    return "\n".join(lines)


def update_memory_section(content: str, section_start: str, section_end: str,
                          new_content: str) -> str:
    """Replace content between two markers while preserving the markers."""
    pattern = re.compile(
        re.escape(section_start) + r"(.*?)" + re.escape(section_end),
        re.DOTALL,
    )
    replacement = (
        f"{section_start}\n\n"
        f"<!-- AUTO-GENERATED — do not edit between markers -->\n"
        f"{new_content}\n\n"
        f"{section_end}"
    )
    updated, count = pattern.subn(replacement, content)
    if count == 0:
        # Section missing entirely, append before end of file
        updated = content + f"\n{replacement}\n"
    return updated


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="Sync auto sections with DB/logs")
    show = sub.add_parser("show", help="Print current memory.md")

    append = sub.add_parser("append", help="Add to a manual section")
    append.add_argument("--section", required=True,
                        choices=["todos", "experiments", "learned-rules"])
    append.add_argument("--text", required=True)

    args = p.parse_args()

    if args.cmd == "show":
        print(MEMORY_PATH.read_text(encoding="utf-8"))
        return

    if args.cmd == "refresh":
        if not MEMORY_PATH.exists():
            print(json.dumps({
                "success": False,
                "error_type": "memory_missing",
                "remediation": {
                    "explanation": ".agents/memory.md không tồn tại",
                    "next_step": "Copy từ template, hoặc chạy scripts/setup.sh",
                },
            }))
            sys.exit(1)

        content = MEMORY_PATH.read_text(encoding="utf-8")
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Update Last updated line
        content = re.sub(
            r"Last updated: .*",
            f"Last updated: {now}",
            content, count=1,
        )

        # Update posts section
        posts = fetch_recent_posts()
        posts_md = format_posts_section(posts)
        content = update_memory_section(content, *AUTO_POSTS_MARKER, posts_md)

        # Update errors section
        errors = fetch_recent_errors()
        errors_md = format_errors_section(errors)
        content = update_memory_section(content, *AUTO_ERRORS_MARKER, errors_md)

        MEMORY_PATH.write_text(content, encoding="utf-8")

        print(json.dumps({
            "success": True,
            "refreshed_at": now,
            "posts_count": len(posts),
            "errors_count": len(errors),
            "memory_path": str(MEMORY_PATH),
        }, ensure_ascii=False, indent=2))

    elif args.cmd == "append":
        # Simple append to a manual section
        content = MEMORY_PATH.read_text(encoding="utf-8")
        timestamp = dt.datetime.now().strftime("%Y-%m-%d")

        section_map = {
            "todos": ("## Open todos", f"- [ ] [{timestamp}] {args.text}"),
            "experiments": ("## Active experiments", f"- [{timestamp}] {args.text}"),
            "learned-rules": ("## Learned rules (from harness-gardener)",
                              f"- [{timestamp}] {args.text}"),
        }
        section_header, entry = section_map[args.section]

        # Find section and insert entry right after header
        lines = content.split("\n")
        new_lines = []
        inserted = False
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.startswith(section_header) and not inserted:
                # Skip any HTML comments immediately after header
                j = i + 1
                while j < len(lines) and (
                    lines[j].strip() == ""
                    or lines[j].strip().startswith("<!--")
                ):
                    j += 1
                # Insert after comments
                if j < len(lines):
                    # Remove lines we already copied, reinsert with entry
                    new_lines.extend(lines[i+1:j])
                    new_lines.append(entry)
                    new_lines.extend(lines[j:])
                    inserted = True
                    break

        if inserted:
            MEMORY_PATH.write_text("\n".join(new_lines), encoding="utf-8")
            print(json.dumps({
                "success": True,
                "section": args.section,
                "entry": entry,
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                "success": False,
                "error_type": "section_not_found",
                "remediation": {
                    "explanation": f"Section '{section_header}' không tìm thấy trong memory.md",
                    "next_step": "Verify .agents/memory.md còn template markers",
                },
            }))
            sys.exit(1)


if __name__ == "__main__":
    main()
