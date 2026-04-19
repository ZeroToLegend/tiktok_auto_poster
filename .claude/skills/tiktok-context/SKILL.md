---
name: tiktok-context
description: Use FIRST before any TikTok task. Captures creator niche, audience, brand voice, pillars. All other tiktok-* skills depend on this. Trigger when user first mentions TikTok, when .agents/tiktok-context.md missing, or when user wants to update context. Stores context in .agents/tiktok-context.md.
---

# TikTok Context Skill

Foundation skill. Creates `.agents/tiktok-context.md` that other skills read.

## When to invoke
- First TikTok task in project
- `.agents/tiktok-context.md` doesn't exist
- User says "update context" / "đổi niche"
- Another skill reports "CONTEXT_MISSING"

## What to capture

Ask user **one section at a time**, not all at once. Offer defaults for speed.

1. **Niche** — topic + target audience (e.g. "Python tutorials for VN beginners")
2. **Language** — vi / en / both (default: vi)
3. **Content pillars** — 3-5 themes with % distribution
4. **Voice** — tone, do's, don'ts, signature phrases
5. **Goals** — primary (followers/engagement/sales), posts/week
6. **Defaults** — privacy, watermark path, brand hashtags

## Output template

```markdown
# TikTok Creator Context
Updated: <ISO>

## Identity
- Niche: ...
- Language: vi
- Region: VN

## Pillars
1. Quick tips (45%)
2. Mistakes to avoid (25%)
3. ...

## Voice
Tone: gen_z_engaging
Do: concise hooks, 1-2 emoji
Don't: political topics, health claims

## Goals
Primary: followers
Frequency: 3-5/week

## Defaults
Privacy: PUBLIC_TO_EVERYONE
Brand tags: [mybrand]
```

## Fast path

User says "use defaults" → create context with VN defaults, let user edit file later.

## How others use it

```bash
cat .agents/tiktok-context.md
# if missing → halt and invoke this skill first
```
