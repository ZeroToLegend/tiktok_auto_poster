---
name: tiktok-caption-writer
description: Write full TikTok caption body AFTER hook chosen via tiktok-hook-writer. Handles structure (hook+context+payoff+CTA), length, emoji balance, safety check. Trigger when user asks "viết caption" or when another skill needs full caption. Depends on tiktok-hook-writer for opening.
---

# TikTok Caption Writer

Writes body after hook is chosen.

## Prereqs
1. Hook from `tiktok-hook-writer`
2. Context from `.agents/tiktok-context.md`
3. Video description (user or extracted from thumbnail)

Missing any → invoke the prerequisite skill first.

## Structure

```
[HOOK]      ← from hook-writer, 5-8 words
[BODY]      ← 1-2 lines, expand hook
[PAYOFF]    ← concrete value delivered
[CTA]       ← soft, not spammy
```

## Length
- **Sweet spot**: 80-150 chars (no hashtags)
- **Hard cap**: 200 chars (engagement drops fast beyond)

## Styles (pick from context)

| Style | Tone | Emoji | CTA example |
|---|---|---|---|
| gen_z_engaging | fast, slangy | 1-2 natural | "save lại", "tag bạn nào cần" |
| professional | formal | 0-1 neutral | "Follow để xem thêm" |
| storytelling | setup→conflict→insight | sparse | question invite comment |
| educational | "X điều về Y" | 0-1 | "Part 2 không?" |

## Safety checklist (MUST pass all)

- [ ] No blacklist words (kill, suicide, drugs, tự tử, ma túy)
- [ ] No political/sensitive topics
- [ ] No false health/financial claims
- [ ] No @mentions without permission
- [ ] No hashtags (handled by hashtag-strategy skill)
- [ ] No quotes >15 words (copyright)

If any fails → rewrite or ask user.

## Validate with sensor

After drafting, run:
```bash
python scripts/sensor_caption_quality.py --caption="<text>"
```
If non-zero exit → read error message's `remediation` field, apply fix, re-run.

## Output format

```
✍️  CAPTION OPTIONS

[Recommended — <style>]
<full caption>
📏 <N> chars | ✅ safety passed

[Alt — <style>]
<full caption>
📏 <N> chars

Hook: "<hook>" | Style: <style>
```
