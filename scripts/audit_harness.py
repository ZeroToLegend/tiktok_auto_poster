#!/usr/bin/env python3
"""audit_harness.py — Score harness quality 0-100, identify gaps.

Dimensions:
  1. Skill format compliance     (20 pts)
  2. Guide-to-sensor ratio       (20 pts)
  3. Error remediation coverage  (20 pts)
  4. Memory + context files      (15 pts)
  5. Tool error handling quality (25 pts)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run_validate() -> tuple[int, int, str]:
    """Returns (fails, warns, log)."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_skills.py")],
        capture_output=True,
        text=True,
    )
    log = result.stdout + result.stderr
    fails = len(re.findall(r"^❌", log, re.MULTILINE))
    warns = len(re.findall(r"^⚠️", log, re.MULTILINE))
    return fails, warns, log


def dim1_skill_format() -> int:
    print("1️⃣  Skill format compliance")
    fails, warns, _ = run_validate()
    if fails == 0 and warns == 0:
        pts = 20
        print(f"   ✅ All skills pass validation (+{pts})")
    else:
        pts = max(0, 20 - fails * 4 - warns * 1)
        print(f"   ⚠️  {fails} fails, {warns} warnings (+{pts})")
    print()
    return pts


def dim2_guide_sensor_ratio() -> int:
    print("2️⃣  Guide-to-sensor ratio")
    skills_dir = ROOT / ".claude" / "skills"
    guides = len(list(skills_dir.glob("*/SKILL.md"))) if skills_dir.exists() else 0
    sensors = len(list((ROOT / "scripts").glob("sensor_*.py")))

    if guides == 0:
        pts = 0
        print("   ❌ No skills found")
    elif sensors == 0:
        pts = 0
        print("   ❌ No sensors — only feedforward (agents will repeat mistakes)")
    else:
        ratio = sensors / guides
        if ratio >= 0.3:
            pts = 20
            print(f"   ✅ {guides} guides, {sensors} sensors (ratio {ratio:.2f}, +{pts})")
        else:
            pts = 10
            print(f"   ⚠️  {guides} guides, {sensors} sensors (ratio {ratio:.2f}, recommend >=0.3, +{pts})")
    print()
    return pts


def dim3_remediation_coverage() -> int:
    print("3️⃣  Error remediation coverage")
    scripts_dir = ROOT / "scripts"
    tool_files = list(scripts_dir.glob("tool_*.py")) + list(scripts_dir.glob("sensor_*.py"))
    tool_files = [f for f in tool_files if f.name != "validate_skills.py" and f.name != "audit_harness.py"]

    total = len(tool_files)
    if total == 0:
        print("   ❌ No tools found")
        print()
        return 0

    with_remediation = sum(
        1 for f in tool_files
        if '"remediation"' in f.read_text(encoding="utf-8", errors="replace")
        or "'remediation'" in f.read_text(encoding="utf-8", errors="replace")
    )
    pct = with_remediation * 100 // total
    pts = pct * 20 // 100
    icon = "✅" if pct >= 70 else ("⚠️" if pct >= 40 else "❌")
    print(f"   {icon} {with_remediation}/{total} tools have remediation ({pct}%, +{pts})")
    print()
    return pts


def dim4_memory_context() -> int:
    print("4️⃣  Memory + context infrastructure")
    pts = 0
    if (ROOT / ".agents" / "memory.md").exists():
        pts += 8
        print("   ✅ .agents/memory.md exists (+8)")
    else:
        print("   ❌ .agents/memory.md missing")
    if (ROOT / ".agents" / "tiktok-context.md").exists():
        pts += 7
        print("   ✅ .agents/tiktok-context.md exists (+7)")
    else:
        print("   ⚠️  .agents/tiktok-context.md missing (user hasn't set up context)")
    print()
    return pts


def dim5_error_handling() -> int:
    print("5️⃣  Tool error handling quality")
    scripts_dir = ROOT / "scripts"
    tool_files = list(scripts_dir.glob("tool_*.py")) + list(scripts_dir.glob("sensor_*.py"))
    tool_files = [f for f in tool_files if f.name not in ("validate_skills.py", "audit_harness.py")]

    total = len(tool_files)
    if total == 0:
        print("   ❌ No tools")
        print()
        return 0

    exit_pattern = re.compile(
        r"sys\.exit\(([12]|exit_code|[01]\s+if\s+.*?\s+else\s+[12])\)"
    )
    with_try = with_exit = 0
    for f in tool_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "try:" in text:
            with_try += 1
        if exit_pattern.search(text):
            with_exit += 1

    try_pct = with_try * 100 // total
    exit_pct = with_exit * 100 // total
    pts = try_pct * 12 // 100 + exit_pct * 13 // 100
    ok = try_pct >= 70 and exit_pct >= 70
    icon = "✅" if ok else "⚠️"
    print(f"   {icon} try/except: {with_try}/{total} ({try_pct}%), exit codes: {with_exit}/{total} ({exit_pct}%), +{pts}")
    print()
    return pts


def main() -> int:
    print("🔬 HARNESS AUDIT")
    print("================")
    print()

    score = 0
    score += dim1_skill_format()
    score += dim2_guide_sensor_ratio()
    score += dim3_remediation_coverage()
    score += dim4_memory_context()
    score += dim5_error_handling()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"HARNESS SCORE: {score} / 100")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if score >= 85:
        print("🏆 Production-ready harness")
    elif score >= 70:
        print("✅ Solid harness, some gaps")
    elif score >= 50:
        print("⚠️  Functional but fragile — add sensors + remediation")
    else:
        print("❌ Prototype level — significant harness work needed")

    print()
    print("💡 Run individual sections for details:")
    print("   python scripts/validate_skills.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
