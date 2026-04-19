# TikTok Creator Templates

Pre-filled contexts for common niches. Cắt setup từ 30 phút xuống 2 phút.

## Available templates

| Template | Folder | For |
|---|---|---|
| Coding | `coding-creator/` | Python/web/tech tutorials, dev tips |
| Food | `food-creator/` | Recipes, reviews, street food |
| Beauty | `beauty-creator/` | Skincare, makeup, product reviews |

## Each template contains

- `tiktok-context.md` — pre-filled creator context (niche, audience, pillars, voice)
- `hashtag-pool.json` — niche-specific hashtags + blacklist
- `hook-examples.md` (some templates) — verified hooks for the niche

## Install

```bash
# Pick a template
TEMPLATE=coding-creator

# Copy context
cp templates/$TEMPLATE/tiktok-context.md .agents/tiktok-context.md

# Copy hashtag pool (optional)
cp templates/$TEMPLATE/hashtag-pool.json data/custom_hashtags.json

# Edit .agents/tiktok-context.md to fill in your specifics
# (brand name, specific topics, etc.)
```

## Creating your own template

1. Copy closest existing template to new folder
2. Customize `tiktok-context.md` for your niche
3. Build `hashtag-pool.json` — research top 50 tags in niche on TikTok Creative Center
4. Document verified hooks in `hook-examples.md` after 20+ posts
5. Submit PR if generally useful

## Beauty compliance note

Beauty niche has additional compliance requirements because TikTok enforces medical claim rules strictly. See `beauty-creator/tiktok-context.md` "Compliance notes" section — these should be read before ANY beauty-niche post.
