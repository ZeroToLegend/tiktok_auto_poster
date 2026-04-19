---
name: tiktok-harness-gardener
description: Meta-skill detecting recurring issues in agent operation, proposing SKILL.md improvements. Trigger weekly via cron, or when user asks "tại sao agent hay sai chỗ X?". Analyzes logs + analytics → writes proposals to memory.md "Learned rules". User reviews + approves before moving rules into SKILL.md files. Never auto-modifies skills.
---

# TikTok Harness Gardener

Meta-skill: improve other skills based on real data. Inspired by OpenAI's doc-gardening agent.

## When to invoke
- Weekly cron (Monday 9am)
- User asks why agent repeats mistake
- After ≥30 posts for statistical signal
- After model update

## 3 observation types worth acting on
1. **Repeated error** — same error_type ≥3× in a week
2. **Pattern drift** — top posts have pattern SKILL.md doesn't capture
3. **Stale rule** — SKILL.md says X but data shows X doesn't work

## Workflow

```bash
# 1. Scan for signals (raw data)
python scripts/tool_gardener.py scan --days=7

# 2. Review + write proposals to memory
python scripts/tool_gardener.py scan --days=7 --write-memory
```

Tool returns JSON with:
- `repeated_errors` — error_type, count, samples
- `post_patterns` — top vs bottom 20% comparison
- `proposals` — prioritized list (HIGH/MEDIUM/LOW)

## Output format for user

```
🌱 HARNESS GARDENER REPORT (Week of <date>)

📋 N proposals, 0 auto-applied (all need review)

1. [HIGH] <title>
   Signal: <one-line evidence>
   File: <target file to update>

2. [MEDIUM] <title>
   ...

📖 Details in .agents/memory.md "Learned rules"
👉 Review, cherry-pick rules to adopt. Run `./validate-skills.sh` after.
```

## Gardener rules

- ❌ **NEVER** auto-modify SKILL.md files
- ❌ No proposals from <5 data points (noise)
- ❌ Don't contradict explicit user preferences in context.md
- ✅ Include evidence (log lines, post IDs) per proposal
- ✅ Prioritize: HIGH (safety/ban) > MEDIUM (performance) > LOW (cleanup)
- ✅ Link proposal to specific file + line when possible

## Blind spots (acknowledge)

Gardener cannot detect:
- Correctness issues (user didn't specify intent)
- Creative quality (subjective)
- Algorithm changes (TikTok-side)

For these → user judgment required.
