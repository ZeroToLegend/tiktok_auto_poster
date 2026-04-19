#!/usr/bin/env python3
"""validate_skills.py — Lint all SKILL.md files for format compliance.

Checks:
  1. YAML frontmatter exists (--- ... ---)
  2. Has `name:` and `description:` keys
  3. description length 50-500 chars
  4. Body length <= 100 lines
  5. No broken tool references (scripts/X.py where X doesn't exist)

Exit 0 = all pass, 1 = issues found.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"


def validate_skill(skill_dir: Path) -> tuple[list[str], list[str], int, int]:
    """Returns (issues, warnings, body_lines, desc_len)."""
    skill_md = skill_dir / "SKILL.md"
    issues: list[str] = []
    warnings: list[str] = []

    if not skill_md.exists():
        return [f"SKILL.md missing"], [], 0, 0

    lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()

    # Check 1: frontmatter
    if not lines or lines[0].strip() != "---":
        issues.append("missing YAML frontmatter (must start with ---)")
        return issues, warnings, len(lines), 0

    # Find closing ---
    frontmatter_end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_end = i
            break

    if frontmatter_end is None:
        issues.append("frontmatter never closed (no second ---)")
        return issues, warnings, len(lines), 0

    frontmatter = "\n".join(lines[1:frontmatter_end])
    body_lines = len(lines) - frontmatter_end - 1

    # Check 2: name + description keys
    if not re.search(r"^name:", frontmatter, re.MULTILINE):
        issues.append("missing 'name:' in frontmatter")
    if not re.search(r"^description:", frontmatter, re.MULTILINE):
        issues.append("missing 'description:' in frontmatter")

    # Check 3: description length
    desc_match = re.search(r"^description:\s*(.+)", frontmatter, re.MULTILINE)
    desc = desc_match.group(1).strip() if desc_match else ""
    desc_len = len(desc)
    if desc_len < 50:
        issues.append(f"description too short ({desc_len} chars, need >=50)")
    elif desc_len > 500:
        issues.append(f"description too long ({desc_len} chars, recommend <=500)")

    # Check 4: body length
    if body_lines > 100:
        warnings.append(f"body too long ({body_lines} lines, recommend <=100 to save context)")

    # Check 5: broken tool references
    content = skill_md.read_text(encoding="utf-8", errors="replace")
    refs = set(re.findall(r"scripts/(?:sensor|tool)_[a-z_]+\.py", content))
    for ref in sorted(refs):
        if not (ROOT / ref).exists():
            issues.append(f"references missing script: {ref}")

    return issues, warnings, body_lines, desc_len


def main() -> int:
    if not SKILLS_DIR.exists():
        print(f"❌ Skills dir not found: {SKILLS_DIR}")
        return 1

    print(f"🔍 Validating skills in {SKILLS_DIR}")
    print()

    passed = failed = warned = 0

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        issues, warnings, body_lines, desc_len = validate_skill(skill_dir)

        if not issues and not warnings:
            print(f"✅ {name} ({body_lines} lines, {desc_len} char desc)")
            passed += 1
        elif not issues and warnings:
            print(f"⚠️  {name}")
            for w in warnings:
                print(f"     • {w}")
            warned += 1
        else:
            print(f"❌ {name}")
            for i in issues:
                print(f"     • {i}")
            for w in warnings:
                print(f"     • {w}")
            failed += 1

    print()
    print("━━━ Summary ━━━")
    print(f"Pass:    {passed}")
    print(f"Warning: {warned}")
    print(f"Fail:    {failed}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
