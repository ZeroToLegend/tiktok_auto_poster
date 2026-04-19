---
name: tiktok-video-prep
description: Use when a video needs prep for TikTok — resize 9:16, normalize audio, watermark, thumbnail, hash. Trigger when user provides raw video intending TikTok post, or when another skill needs processed video. Not for general video editing.
---

# TikTok Video Prep Skill

Normalize video to TikTok spec.

## Target spec (2026)
- 1080×1920 (9:16), H.264, AAC 44.1kHz, 30fps
- -14 LUFS loudness, ≤287.6 MB, 15-180s

## Pipeline

```bash
# 1. Probe first
python scripts/tool_process_video.py --input=<path> --action=probe

# 2. Hash + duplicate check
HASH=$(python scripts/tool_process_video.py --input=<path> --action=hash)
python scripts/tool_schedule.py check-duplicate --hash=$HASH --days=7
# → if duplicate: HALT

# 3. Prepare
python scripts/tool_process_video.py --input=<path> --action=prepare [--trim=60]
# → returns {"processed_path": ..., "hash": ..., "warnings": [...]}

# 4. Thumbnail (for cover or vision describe)
python scripts/tool_process_video.py --input=<path> --action=thumbnail
```

## Resize logic (tool handles automatically)
- Already 9:16 → scale Lanczos
- Landscape → scale + letterbox (warns user: letterbox hurts reach)
- Portrait non-9:16 → scale + center crop

## Decisions to escalate to user
- Duration >60s → "Cắt còn 30s?" (retention drops after 30s)
- Duration <15s → "Quá ngắn, tiếp tục?"
- Landscape input → "Letterbox (reach ↓) hoặc user tự crop?"
- No audio → "Video mute, vẫn đăng?"

## Output shape
```json
{
  "processed_path": "/abs/path/tt_video.mp4",
  "size_mb": 23.4,
  "hash": "sha256-...",
  "duration_s": 28.5,
  "dimensions": "1080x1920",
  "warnings": []
}
```
