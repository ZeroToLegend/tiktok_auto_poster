#!/usr/bin/env bash
# audit-harness.sh — Score harness quality 0-100, identify gaps.
#
# Computes 5 dimensions:
#   1. Skill format compliance (20 pts)
#   2. Guide-to-sensor ratio (20 pts)
#   3. Error remediation coverage (20 pts)
#   4. Memory + context files present (15 pts)
#   5. Tool error handling quality (25 pts)

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCORE=0
MAX=100

echo "🔬 HARNESS AUDIT"
echo "================"
echo ""

# --------------------------------------------------------------
# 1. Skill format (20 pts)
# --------------------------------------------------------------
echo "1️⃣  Skill format compliance"
if bash "$ROOT/validate-skills.sh" > /tmp/validate.log 2>&1; then
    pts=20
    echo "   ✅ All skills pass validation (+$pts)"
else
    fails=$(grep -c "^❌" /tmp/validate.log || true)
    warns=$(grep -c "^⚠️" /tmp/validate.log || true)
    pts=$((20 - fails * 4 - warns * 1))
    [ $pts -lt 0 ] && pts=0
    echo "   ⚠️  $fails fails, $warns warnings (+$pts)"
fi
SCORE=$((SCORE + pts))
echo ""

# --------------------------------------------------------------
# 2. Guide-to-sensor ratio (20 pts)
# Principle: every critical guide should have ≥1 sensor
# --------------------------------------------------------------
echo "2️⃣  Guide-to-sensor ratio"
guides=$(find "$ROOT/.claude/skills" -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
sensors=$(find "$ROOT/scripts" -name "sensor_*.py" 2>/dev/null | wc -l | tr -d ' ')
if [ "$guides" -eq 0 ]; then
    pts=0
    echo "   ❌ No skills found"
elif [ "$sensors" -eq 0 ]; then
    pts=0
    echo "   ❌ No sensors — only feedforward (agents will repeat mistakes)"
else
    ratio=$(awk "BEGIN {printf \"%.2f\", $sensors / $guides}")
    # Ideal ratio: 1 sensor per 2-3 critical guides (0.3-0.5)
    if (( $(awk "BEGIN {print ($ratio >= 0.3)}") )); then
        pts=20
        echo "   ✅ $guides guides, $sensors sensors (ratio $ratio, +$pts)"
    else
        pts=10
        echo "   ⚠️  $guides guides, $sensors sensors (ratio $ratio, recommend ≥0.3, +$pts)"
    fi
fi
SCORE=$((SCORE + pts))
echo ""

# --------------------------------------------------------------
# 3. Error remediation coverage (20 pts)
# Each tool_*.py/sensor_*.py should emit {"remediation": ...} on error
# --------------------------------------------------------------
echo "3️⃣  Error remediation coverage"
total_tools=0
with_remediation=0
for f in "$ROOT/scripts/tool_"*.py "$ROOT/scripts/sensor_"*.py; do
    [ ! -f "$f" ] && continue
    total_tools=$((total_tools + 1))
    if grep -q '"remediation"' "$f" || grep -q "'remediation'" "$f"; then
        with_remediation=$((with_remediation + 1))
    fi
done

if [ "$total_tools" -eq 0 ]; then
    pts=0
    echo "   ❌ No tools found"
else
    pct=$((with_remediation * 100 / total_tools))
    pts=$((pct * 20 / 100))
    icon="✅"
    [ $pct -lt 70 ] && icon="⚠️"
    [ $pct -lt 40 ] && icon="❌"
    echo "   $icon $with_remediation/$total_tools tools have remediation ($pct%, +$pts)"
fi
SCORE=$((SCORE + pts))
echo ""

# --------------------------------------------------------------
# 4. Memory + context files (15 pts)
# --------------------------------------------------------------
echo "4️⃣  Memory + context infrastructure"
pts=0
if [ -f "$ROOT/.agents/memory.md" ]; then
    pts=$((pts + 8))
    echo "   ✅ .agents/memory.md exists (+8)"
else
    echo "   ❌ .agents/memory.md missing"
fi
if [ -f "$ROOT/.agents/tiktok-context.md" ]; then
    pts=$((pts + 7))
    echo "   ✅ .agents/tiktok-context.md exists (+7)"
else
    echo "   ⚠️  .agents/tiktok-context.md missing (user hasn't set up context)"
fi
SCORE=$((SCORE + pts))
echo ""

# --------------------------------------------------------------
# 5. Tool error handling quality (25 pts)
# Look for try/except + structured error output in tools
# --------------------------------------------------------------
echo "5️⃣  Tool error handling quality"
total=0
with_try=0
with_exit_code=0
for f in "$ROOT/scripts/tool_"*.py "$ROOT/scripts/sensor_"*.py; do
    [ ! -f "$f" ] && continue
    total=$((total + 1))
    grep -q "try:" "$f" && with_try=$((with_try + 1))
    # Accept: sys.exit(1), sys.exit(2), sys.exit(exit_code), sys.exit(0 if ... else 1)
    grep -qE "sys\.exit\(([12]|exit_code|[01] if .* else [12]|0 if .* else [12])\)" "$f" && with_exit_code=$((with_exit_code + 1))
done

if [ "$total" -eq 0 ]; then
    pts=0
    echo "   ❌ No tools"
else
    try_pct=$((with_try * 100 / total))
    exit_pct=$((with_exit_code * 100 / total))
    pts=$((try_pct * 12 / 100 + exit_pct * 13 / 100))
    icon="✅"
    [ $try_pct -lt 70 ] || [ $exit_pct -lt 70 ] && icon="⚠️"
    echo "   $icon try/except: $with_try/$total ($try_pct%), exit codes: $with_exit_code/$total ($exit_pct%), +$pts"
fi
SCORE=$((SCORE + pts))
echo ""

# --------------------------------------------------------------
# Summary
# --------------------------------------------------------------
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HARNESS SCORE: $SCORE / $MAX"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$SCORE" -ge 85 ]; then
    echo "🏆 Production-ready harness"
elif [ "$SCORE" -ge 70 ]; then
    echo "✅ Solid harness, some gaps"
elif [ "$SCORE" -ge 50 ]; then
    echo "⚠️  Functional but fragile — add sensors + remediation"
else
    echo "❌ Prototype level — significant harness work needed"
fi

echo ""
echo "💡 Run individual sections for details:"
echo "   ./validate-skills.sh"
echo "   grep -L remediation scripts/tool_*.py scripts/sensor_*.py"
