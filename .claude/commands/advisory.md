---
description: Tạo package "ready-to-post" cho user đăng thủ công TikTok (không dùng API)
argument-hint: <video_path> [topic]
---

Chạy advisory-mode: chuẩn bị sẵn video + caption + hashtag + hướng dẫn, user copy-paste vào app TikTok tự đăng.

**User input:** $ARGUMENTS

## Khi nào dùng command này

- Chưa có TikTok Developer API approval
- Đang chờ audit
- Muốn dùng trending sounds (API không cho)
- Không muốn rủi ro ban account
- Chỉ quản lý 1 account cá nhân (không cần full auto)

## Pipeline

### Bước 1-6: Content (giống `/post`)
1. Check context (`.agents/tiktok-context.md`)
2. Invoke `tiktok-video-prep` → processed video + thumbnail
3. Invoke `tiktok-hook-writer`
4. Invoke `tiktok-caption-writer`
5. Invoke `tiktok-hashtag-strategy`
6. Invoke `tiktok-scheduler next-slot` để biết giờ tối ưu

### Bước 7: Invoke `tiktok-advisory-mode`

Theo SKILL.md của advisory-mode:
- Tạo folder `data/ready_to_post/<timestamp>_<topic>/`
- Copy processed video vào folder → đổi tên `video.mp4`
- Extract thumbnail → `cover.jpg`
- Tạo `caption.txt` (caption không có hashtag)
- Tạo `hashtags.txt` (chỉ hashtag, để user paste sau caption)
- Tạo `posting_guide.md` (hướng dẫn 60 giây)
- Tạo `metadata.json` (để analyze sau)

### Bước 8: Ghi vào DB
```bash
python -c "
import sys, json; sys.path.insert(0, '.')
from scripts.run_agent import load_config
from tools.scheduler import PostScheduler
# Record pending_manual record
# ...
"
```

### Bước 9: Output cho user

Theo format trong `tiktok-advisory-mode/SKILL.md` (block "📦 PACKAGE READY").

### Bước 10: Optional reminder
Hỏi user: "Nhắc bạn lúc 5 phút trước giờ vàng? (y/n)"
- Nếu yes → tạo calendar event (nếu có calendar MCP) hoặc hiển thị crontab command
- Nếu không → kết thúc

## Bonus features

Nếu user hỏi về notification publishing (Buffer/Later):
- Giải thích Buffer $6/tháng có notification publishing
- User được notification → tap → auto-fill caption/hashtag trong app TikTok
- Middle ground giữa manual và full auto
- Đề xuất convert nếu user scale lên ≥ 3 account
