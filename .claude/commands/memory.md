---
description: View or update .agents/memory.md (recent posts, errors, experiments, todos)
argument-hint: [show | refresh | add-todo "text" | add-experiment "text"]
---

Manage agent memory file.

**Args:** $ARGUMENTS

## Actions

### show (default)
```bash
python scripts/tool_memory.py show
```
Pipe through less if long. Highlight sections with content.

### refresh
Sync auto sections (recent posts, errors) with DB/logs:
```bash
python scripts/tool_memory.py refresh
```

### add-todo "<text>"
```bash
python scripts/tool_memory.py append --section=todos --text="<text>"
```

### add-experiment "<text>"
```bash
python scripts/tool_memory.py append --section=experiments --text="<text>"
```

## When to use

- **Start of session**: run `refresh` then read to get context on recent state
- **After user mentions a recurring pattern**: add as experiment or todo
- **Weekly**: review with user to see what's accumulated

## Philosophy

Memory is for:
- Recent **state** (what happened last week)
- **Open questions** (todos for human decision)
- **Hypotheses being tested** (experiments)
- **Candidate rules** (from gardener, awaiting approval)

Memory is NOT for:
- Full post history (use analytics.db)
- Skill content (use SKILL.md)
- Configuration (use config.yaml)
