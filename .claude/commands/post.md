---
description: Full pipeline đăng TikTok - video prep, hook, caption, hashtag, upload
argument-hint: <video_path> [topic]
---

Đăng 1 video lên TikTok theo full pipeline đa-skill.

**User input:** $ARGUMENTS

## Pipeline bắt buộc

### Phase 0: Setup
1. Check `.agents/tiktok-context.md` tồn tại?
   - Nếu không → invoke skill `tiktok-context` trước, hỏi user niche + style
2. Check API access (xem CLAUDE.md Rule 2)
   - Có → tiếp tục với uploader path
   - Không → chuyển sang advisory path (xem command `/advisory` tương đương)

### Phase 1: Content preparation
3. Invoke skill `tiktok-video-prep`:
   - Probe video → check duplicate → prepare → get `processed_path`
   - Nếu duplicate → DỪNG

4. Invoke skill `tiktok-hook-writer`:
   - Nếu user cung cấp topic trong $ARGUMENTS → dùng
   - Sinh 5-7 hook variants theo 7 framework
   - Present top 2, default chọn top 1 (hỏi user nếu muốn iterate)

5. Invoke skill `tiktok-caption-writer`:
   - Dùng hook đã chọn
   - Đọc style từ context
   - Sinh 2-3 variant caption đầy đủ
   - Safety check
   - Default chọn top 1

6. Invoke skill `tiktok-hashtag-strategy`:
   - Chạy `tool_hashtag.py` với topic
   - 5 tag pyramid
   - Validate độ dài tổng

### Phase 2: Timing
7. Invoke skill `tiktok-scheduler`:
   - Check quota today với `tool_schedule.py check-quota`
   - Nếu full → ngừng, thông báo user
   - Nếu user không chỉ định giờ → hỏi: "Đăng ngay hay slot vàng kế tiếp (<time>)?"

### Phase 3: Publish
8. Invoke skill `tiktok-uploader`:
   - Verify prerequisites checklist
   - `python scripts/tool_upload.py --video=... --caption="..." --hashtags="..."`
   - Parse JSON output
   - Handle error theo error map trong SKILL.md

### Phase 4: Record
9. Output format theo tiktok-uploader SKILL.md (block "✅ ĐĂNG THÀNH CÔNG")

## Xử lý fail

Nếu bất kỳ bước nào fail:
- Duplicate → DỪNG, không retry
- `spam_risk` → DỪNG, báo user
- `unaudited_client_*` → hỏi user có muốn chuyển sang advisory-mode không
- Lỗi khác → retry với backoff (đã có trong tool), sau 3 lần thì báo user

## Option flags

Nếu $ARGUMENTS chứa flag:
- `--style=<style>` → override style từ context
- `--privacy=<level>` → override privacy
- `--now` → skip scheduler, upload ngay
- `--schedule=<ISO>` → schedule cụ thể
- `--advisory` → force advisory-mode path
