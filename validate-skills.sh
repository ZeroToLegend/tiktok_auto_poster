#!/usr/bin/env bash
# validate-skills.sh — Lint all SKILL.md files for format compliance.
#
# Checks:
#   1. YAML frontmatter exists (--- ... ---)
#   2. Has `name:` and `description:` keys
#   3. description length 50-500 chars (too short = ambiguous; too long = verbose)
#   4. Body length ≤ 100 lines (skill bloat → context waste)
#   5. No broken tool references (python scripts/X.py where X doesn't exist)
#
# Exit 0 = all pass, 1 = issues found.

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$ROOT/.claude/skills"

if [ ! -d "$SKILLS_DIR" ]; then
    echo "❌ Skills dir not found: $SKILLS_DIR"
    exit 1
fi

PASS=0
FAIL=0
WARN=0

echo "🔍 Validating skills in $SKILLS_DIR"
echo ""

for skill_dir in "$SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"

    if [ ! -f "$skill_md" ]; then
        echo "❌ $skill_name: SKILL.md missing"
        FAIL=$((FAIL + 1))
        continue
    fi

    issues=()

    # Check 1: frontmatter present
    if ! head -n 1 "$skill_md" | grep -q "^---$"; then
        issues+=("missing YAML frontmatter (must start with ---)")
    fi

    # Check 2: name + description
    if ! grep -q "^name:" "$skill_md"; then
        issues+=("missing 'name:' in frontmatter")
    fi

    if ! grep -q "^description:" "$skill_md"; then
        issues+=("missing 'description:' in frontmatter")
    fi

    # Check 3: description length (extract value, count chars)
    desc=$(awk '/^description:/{flag=1; sub(/^description:[ \t]*/,""); printf "%s",$0; next} /^---$/{flag=0} flag && /^[a-zA-Z]+:/{flag=0} flag{printf " %s",$0}' "$skill_md")
    desc_len=${#desc}
    if [ "$desc_len" -lt 50 ]; then
        issues+=("description too short ($desc_len chars, need ≥50)")
    elif [ "$desc_len" -gt 500 ]; then
        issues+=("description too long ($desc_len chars, recommend ≤500)")
    fi

    # Check 4: body line count (excl frontmatter)
    total_lines=$(wc -l < "$skill_md")
    frontmatter_end=$(awk '/^---$/{count++; if(count==2){print NR; exit}}' "$skill_md")
    body_lines=$((total_lines - ${frontmatter_end:-0}))
    if [ "$body_lines" -gt 100 ]; then
        issues+=("body too long ($body_lines lines, recommend ≤100 to save context)")
    fi

    # Check 5: broken tool refs (python scripts/X.py — check X exists)
    while IFS= read -r script_ref; do
        if [ -n "$script_ref" ] && [ ! -f "$ROOT/$script_ref" ]; then
            issues+=("references missing script: $script_ref")
        fi
    done < <(grep -oE 'scripts/(sensor|tool)_[a-z_]+\.py' "$skill_md" | sort -u)

    # Report
    if [ ${#issues[@]} -eq 0 ]; then
        echo "✅ $skill_name ($body_lines lines, $desc_len char desc)"
        PASS=$((PASS + 1))
    else
        if [ "$body_lines" -gt 100 ] && [ ${#issues[@]} -eq 1 ]; then
            echo "⚠️  $skill_name"
            WARN=$((WARN + 1))
        else
            echo "❌ $skill_name"
            FAIL=$((FAIL + 1))
        fi
        for issue in "${issues[@]}"; do
            echo "     • $issue"
        done
    fi
done

echo ""
echo "━━━ Summary ━━━"
echo "Pass:    $PASS"
echo "Warning: $WARN"
echo "Fail:    $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
