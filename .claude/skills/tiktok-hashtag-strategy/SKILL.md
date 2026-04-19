---
name: tiktok-hashtag-strategy
description: Select 3-5 hashtags using pyramid strategy (1 trending + 2 niche + 1 evergreen + 1 brand). Trigger when a post needs tags, user asks "gợi ý hashtag", or caption-writer finalizes and needs tags appended. DO NOT stuff 10+ tags — hurts reach on TikTok 2026.
---

# TikTok Hashtag Strategy

## 2026 reality
- **3-5 tags > 10+** (10+ reads as spam signal)
- **Niche > trending** for reach targeting
- **#fyp alone is not magic** — everyone uses it
- Tags must be clickable (no special chars, no spaces)

## Pyramid strategy

```
  [1 TRENDING]      high volume, low win rate
 [2 NICHE]          ← most important, determines audience
[1 EVERGREEN]       steady reach
[1 BRAND]           recall
```

## Workflow

```bash
python scripts/tool_hashtag.py \
  --topic="<topic>" \
  --count=5 \
  --strategy=balanced \
  --brand-tags="<from_context>"
```

Tool returns `{"hashtags": [...]}`.

## Validation
- Total length ≤100 chars (including spaces)
- Each tag ≤30 chars
- No underscore-as-space (`#hoc_python` doesn't link)
- Not in blacklist

## Blacklist (avoid)
- Spam signals: `#follow4follow`, `#like4like`, `#sub4sub`
- Off-topic generic: `#love`, `#lol` when content isn't
- Old year tags: `#2020`, `#2021` (deprioritized)
- Tags >30 chars

## Output format

```
🏷️  HASHTAGS for "<topic>"

#fyp #pythontips #codingbeginner #learnontiktok #<brand>

📊 Breakdown:
├─ Trending:  #fyp
├─ Niche:     #pythontips #codingbeginner
├─ Evergreen: #learnontiktok
└─ Brand:     #<brand>

💡 Niche tags drive audience targeting. Change them to shift reach.
```

## Research mode (if user wants trending research)
Point user to TikTok Creative Center (ads.tiktok.com) → top 100 hashtags by region+category. Update `data/custom_hashtags.json`.
