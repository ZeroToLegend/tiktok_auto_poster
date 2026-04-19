---
name: tiktok-advisory-mode
description: Fallback when TikTok API unavailable — unaudited app, rate limited, user prefers manual, or any upload error. Generates a "ready-to-post package" (processed video + caption + hashtags + guide) that user copy-pastes into TikTok app in 60s. Trigger automatically on tiktok-uploader failure, or when user says "đăng thủ công", "không dùng API".
---

# TikTok Advisory Mode

Fallback skill. Prepare package for user to post manually in 60s.

## When to invoke
- `tiktok-uploader` fails with `spam_risk`, `unaudited_client_*`, `no_api_access`
- User has no Developer account
- Waiting for audit approval
- User says "manual", "không cần API", "tạo sẵn cho tôi"

## Why this is often the right choice (not a downgrade)
- ✅ No audit needed
- ✅ No ban risk from automation
- ✅ Can use trending sounds (API can't)
- ✅ Only TikTok native limits apply
- ⚠️ ~60s user time per post

## Pipeline

1. Run video-prep, hook-writer, caption-writer, hashtag-strategy, scheduler next-slot (same as API path)
2. Extract thumbnail: `--action=thumbnail`
3. Create package folder: `data/ready_to_post/<YYYYMMDD_HHMM>_<slug>/`
4. Populate:
   ```
   video.mp4         ← processed, rename
   cover.jpg         ← thumbnail
   caption.txt       ← caption without hashtags
   hashtags.txt      ← just hashtags
   posting_guide.md  ← 60s walkthrough
   metadata.json     ← for analytics later
   ```
5. Record in SQLite `pending_manual` table
6. Output package info to user

## posting_guide.md template

```markdown
# How to post (60 seconds)

⏰ Optimal time: <datetime> (in <X>h)

1. TikTok app → ➕
2. Upload → pick `video.mp4`
3. Copy from `caption.txt` → paste
4. Copy from `hashtags.txt` → append after caption
5. Cover → select `cover.jpg` (or better frame)
6. Settings: Public, comments ON, duet/stitch ON
7. Post

💡 Say hook in first 2s of video: "<hook>"
🎵 Want trending sound? Pick BEFORE pasting caption.

After posting: `python scripts/tool_record_manual_post.py --url=<video_url>`
```

## Output to user

```
📦 PACKAGE READY
Path: data/ready_to_post/20260418_2000_pythontips/

🎬 video.mp4 (24 MB, 28s, 1080×1920) ✅
🎯 Hook: "7 shortcut VS Code tiết kiệm 3 tiếng/ngày"
✍️  Caption: 127 chars
🏷️  Tags: #fyp #pythontips #codingbeginner #learnontiktok #mybrand
🖼️  Cover: frame at 1s
⏰ Suggested time: 2026-04-18 20:00 (in 3h 15m)

📖 See posting_guide.md in folder.

🔔 Remind at 19:55? (y/n)
```

## Upsell path

If user scales ≥3 accounts or ≥15 posts/week → suggest Buffer ($6/mo) notification publishing as middle ground.
