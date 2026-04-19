---
description: Scan logs + analytics for harness improvement proposals
argument-hint: [days: 7]
---

Invoke skill `tiktok-harness-gardener` to detect recurring issues and propose SKILL.md updates.

**Days to scan:** $ARGUMENTS (default 7)

## Steps

1. Read the skill: `.claude/skills/tiktok-harness-gardener/SKILL.md`
2. Run scan:
   ```bash
   DAYS=${1:-7}
   python scripts/tool_gardener.py scan --days=$DAYS --write-memory
   ```
3. Parse JSON output:
   - `repeated_errors` — errors ≥3× in window
   - `post_patterns` — top vs bottom 20% comparison
   - `proposals` — HIGH/MEDIUM/LOW prioritized

4. Present report to user per gardener SKILL.md format:
   ```
   🌱 HARNESS GARDENER REPORT (Week of <date>)
   📋 N proposals
   1. [HIGH] ...
   2. [MEDIUM] ...
   📖 Details in .agents/memory.md "Learned rules"
   ```

5. Ask user: "Want to apply any proposals now?"
   - If yes → for each chosen proposal, show specific diff and wait for user confirmation before edit
   - NEVER auto-edit SKILL.md files

## Follow-up

After user applies changes → run `/audit-harness` to verify score improved.
