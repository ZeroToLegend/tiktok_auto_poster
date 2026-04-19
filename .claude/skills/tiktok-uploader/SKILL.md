---
name: tiktok-uploader
description: Publish prepared video to TikTok via official Content Posting API. Requires processed video, final caption, valid OAuth token. Trigger only at final step after video-prep, caption-writer, hashtag-strategy complete. No API access → fall back to tiktok-advisory-mode.
---

# TikTok Uploader

Final step: push via official API.

## Prereqs — verify ALL before upload

Run pre-upload sensor:
```bash
python scripts/sensor_pre_upload.py --video=<path> --account=default
# Validates: processed? duplicate? quota? token valid? audit status?
```
Non-zero exit → read remediation, fix, re-run.

## Command

```bash
python scripts/tool_upload.py \
  --video=<processed_path> \
  --caption="<caption>" \
  --hashtags="fyp,pythontips,codingbeginner" \
  --privacy=PUBLIC_TO_EVERYONE \
  [--disable-duet] [--disable-stitch] [--disable-comment]
```

Returns:
```json
{"success": true, "publish_id": "...", "status": "PUBLISH_COMPLETE"}
```

## Privacy

| Value | When |
|---|---|
| PUBLIC_TO_EVERYONE | Default for audited apps |
| MUTUAL_FOLLOW_FRIENDS | Test with friends |
| SELF_ONLY | **Forced for unaudited apps** by TikTok |

⚠️ Unaudited app + send PUBLIC → TikTok overrides to SELF_ONLY. Not a code bug.

## Error handling

Tool error output has `remediation` field. Follow it exactly:

| Error | Action per remediation |
|---|---|
| `spam_risk_*` | HALT, no retry, notify user |
| `rate_limit_*` | Wait per remediation, retry |
| `unaudited_client_*` | HALT, suggest advisory-mode |
| `video_pull_failed` | Retry 3× then HALT |
| `invalid_file_*` | Re-run video-prep |

## Post-upload sensor

```bash
python scripts/sensor_post_upload.py --publish-id=<id>
# Verifies: video visible on profile after 5 min
```

## Output format

```
✅ PUBLISHED

├─ publish_id: v_pub_file~...
├─ Caption: <first 60 chars>...
├─ Hashtags: #fyp #pythontips ...
├─ Privacy: PUBLIC_TO_EVERYONE
├─ URL: https://tiktok.com/@user/video/... (available ~2 min)
├─ Quota: 4/6 used today
└─ Next slot: 2026-04-19 08:00
```

## On failure

```
❌ UPLOAD FAILED

Error: <type>
Why: <plain VN explanation>

Fix:
1. <from remediation>
2. <alternative>

Fall back to advisory-mode? (y/n)
```
