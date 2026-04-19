---
name: tiktok-scheduler
description: Plan when a TikTok post goes live — calculate golden-hour slots, manage SQLite queue, check quota, detect duplicates. Trigger when user says "lên lịch", "schedule", "khi nào đăng". Does NOT upload — cron_worker picks up scheduled jobs.
---

# TikTok Scheduler

## Core rules
- Max 6 posts/day/account (recommend 2-3)
- ≥2h gap between posts (algorithm cooldown)
- Post in golden hours only

## Golden hours (VN default)
- Morning: 6-9h
- Noon: 12-13h
- Evening: 19-22h ⭐ peak (80% traffic)
- Avoid: 2-5h, 14-17h

## Commands

```bash
# Next optimal slot
python scripts/tool_schedule.py next-slot --account=default

# Check quota (ALWAYS before enqueue)
python scripts/tool_schedule.py check-quota --account=default

# Check duplicate
python scripts/tool_schedule.py check-duplicate --hash=<sha256> --days=7

# Enqueue
python scripts/tool_schedule.py enqueue \
  --video=<path> --caption="..." --hashtags="tag1,tag2" \
  --when=auto --account=default

# List pending
python scripts/tool_schedule.py list
```

## Decision flow

```
User specifies time? → validate (not past, not in 2h blackout) → enqueue
User says "now"? → in golden hour? → upload now : ask "now or wait <next>?"
Default → next-slot → enqueue
```

## Batch scheduling

5 videos/week → distribute, don't dump:
```
Mon 20:00 | Tue 08:00 | Wed 20:00 | skip Thu | Fri 12:00 | Sat 21:00
```
Enforce ≥12h gap for batch, not just 2h.

## Worker required

Scheduler only enqueues. Worker runs jobs:
```bash
# Once (cron):
python scripts/cron_worker.py --once

# Daemon:
python scripts/cron_worker.py --interval=300
```
**ALWAYS remind user to start worker after enqueue.**

## Learning loop (after 30 days data)

```python
from tools.analytics import AnalyticsTracker
best = AnalyticsTracker('data/analytics.db').best_posting_hours(days=30)
# Update config.yaml golden_hours with results
```

## Output format

```
⏰ SCHEDULED
├─ Job: #42
├─ When: 2026-04-18 20:00 (golden hour, in 3h 15m)
├─ Video: tt_*.mp4 (24 MB, 28s)
├─ Quota: 3/6 used today
└─ Worker: ✅ running (PID 12345)  // or ⚠️ NOT RUNNING
```

If worker not running → show start commands.
