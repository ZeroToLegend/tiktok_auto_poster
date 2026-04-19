---
name: tiktok-analyzer
description: Analyze past post performance, find patterns (which hooks/tags/times work), recommend specific optimizations. Trigger when user asks "báo cáo", "posts nào hiệu quả", "vì sao X flop". Needs ≥7-10 posts with stats. Does NOT fetch stats (cron_worker's job) — analyzes existing data.
---

# TikTok Analyzer

Data-driven insights. No vibes.

## Prereq
- `data/analytics.db` has ≥7-10 posts with stats
- `cron_worker.py` has run recently

If <7 posts → tell user, offer limited analysis anyway.

## Queries

```python
from tools.analytics import AnalyticsTracker
t = AnalyticsTracker('data/analytics.db')

t.last_24h()              # summary
t.best_posting_hours(30)  # [(hour, avg_views), ...]
```

Or direct SQL on `data/analytics.db`:
```sql
SELECT p.caption, s.views, s.likes * 100.0/NULLIF(s.views,0) as engagement_rate
FROM posts p JOIN stats_snapshots s USING(publish_id)
WHERE s.id IN (SELECT MAX(id) FROM stats_snapshots GROUP BY publish_id)
ORDER BY s.views DESC LIMIT 10;
```

## Standard analyses

1. **Hook pattern** — classify top 20% posts' first 5 words by framework (Number/POV/Question/etc.)
2. **Hashtag effectiveness** — avg views per tag usage
3. **Time-of-day** — avg views by hour posted
4. **Day-of-week** — by weekday
5. **Caption length** — view bucket by 50-char bins
6. **Style** — performance by gen_z/professional/educational/storytelling

## Report format

```
📊 TIKTOK PERFORMANCE REPORT
Period: <start> → <end> (N posts, M total views, K avg)

━━━ WHAT WORKS ━━━
1. <insight with number>
2. ...

━━━ WHAT DOESN'T ━━━
1. <insight with number>
2. ...

━━━ ACTION ITEMS ━━━
□ <specific, measurable action>
□ ...

━━━ EXPERIMENTS ━━━
🧪 Hypothesis: ...
   Test: ...
```

## Diagnostic mode (for specific flops)

User asks "why did video X flop?" → run diagnostic:

```
Video: "<title>" — N views (avg M) ⬇ -X%

🔍 Red flags:
├─ Hook: "..." (generic, low tension) ❌
├─ Time: <when> (bad day + hour) ❌
├─ Caption: N chars (>200 penalty) ❌
├─ Tags: no niche tags ❌
└─ Length: Xs (retention cliff at 30s) ⚠️

Root cause: <primary driver>
Rewrite: <specific fix>
```

## Don't
- ❌ Invent "algorithm secrets" without data
- ❌ Generic blog advice — use user's real data
- ❌ Recommend 5+ changes at once (can't isolate effect)
- ❌ Over-fit on <20 data points (variance too high)
