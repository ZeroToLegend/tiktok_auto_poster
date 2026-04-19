---
name: tiktok-hook-writer
description: Craft the opening 5 words / 2 seconds of a TikTok caption. Hooks determine retention — #1 ranking factor on TikTok. Trigger when user asks for "hook", "opening line", "câu mở đầu", or when caption-writer needs a hook first. Keep separate from caption-writer because hooks need focused iteration.
---

# TikTok Hook Writer

5 từ đầu quyết định có được xem hết 3s không → quyết định push FYP.

## Prereq
Read `.agents/tiktok-context.md` first. If missing → invoke `tiktok-context`.

## 7 hook frameworks

| Framework | Example |
|---|---|
| **Question** | "Tại sao 99% dev viết `if x == True` sai?" |
| **Number** | "7 shortcut VS Code tiết kiệm 3 tiếng/ngày" |
| **POV** | "POV: sếp hỏi bạn biết SQL và bạn vừa Google 5 phút trước" |
| **Contrarian** | "Đừng học JavaScript nếu muốn có job" |
| **Curiosity gap** | "Mẹo này làm code nhanh 10× mà trường không dạy" |
| **Pain/Problem** | "Code đúng nhưng vẫn bị reject phỏng vấn? Đây là lý do" |
| **Outcome** | "Từ 0 thành senior dev 18 tháng, đây là roadmap" |

## Rules
- ≤ 8 words (5-7 ideal)
- Specific > vague: "7 shortcut" > "nhiều shortcut"
- Odd numbers beat even (7, 13, 37 > 5, 10)
- Stop-the-scroll tension from word 1
- Match pillar from context
- No "Chào các bạn", "Hôm nay mình sẽ" — TikTok down-ranks these
- No emoji in hook (save for body)

## Workflow

1. Clarify topic + key payoff + target pain point
2. Generate 5-7 variants, one per framework
3. Recommend top 2 with reasoning (match pillar, specificity, tension)
4. User picks or iterates

## Output format

```
🎯 HOOK for "<topic>"

[Top] "<hook>"
→ <why it works, 1 line>

[Alt] "<hook>"
→ ...

[Others for iteration]
1. ... (Question)
2. ... (POV)
3. ...
```
