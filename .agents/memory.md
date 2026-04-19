# TikTok Agent Memory

This file is progressive context the agent reads BEFORE taking action.
Auto-updated by `scripts/tool_memory.py`. Agent should also append learnings manually.

Last updated: 2026-04-18 14:31

---

## Recent posts (last 7 days)

<!-- AUTO-GENERATED — do not edit between markers -->
(no posts in last 7 days)

## Recent errors (last 7 days)

<!-- AUTO-GENERATED — do not edit between markers -->
(no errors in last 7 days)

## Active experiments

<!-- MANUAL: agent + user add hypotheses here -->
<!-- Format: - [YYYY-MM-DD] Hypothesis X. Status: testing/done. Result: ... -->

- [2026-04-18] Testing Number-hook vs POV-hook (10 posts each)
(none)

---

## Open todos

<!-- MANUAL: agent adds items that need human decision -->

- [ ] Run `python scripts/tool_memory.py refresh` daily via cron
- [ ] Review `tiktok-harness-gardener` output weekly

---

## Learned rules (from harness-gardener)

<!-- AUTO: tiktok-harness-gardener writes recommendations here -->
<!-- User reviews and moves accepted rules into relevant SKILL.md files -->

(none yet)

---

## How to use this file

- Agent reads this FIRST at start of any TikTok pipeline
- Skip sections marked `(empty)` or `(none)` — no content to act on
- "Recent posts" helps detect patterns without querying DB
- "Open todos" = backlog of things user has deferred
- "Learned rules" = candidate updates to SKILL.md files
