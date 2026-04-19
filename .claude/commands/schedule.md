---
description: Lên lịch đăng video vào giờ vàng (hoặc giờ cụ thể)
argument-hint: <video_path> [when: auto | "2026-04-20 20:00"]
---

Lên lịch đăng TikTok. Không upload ngay — đặt vào queue, worker sẽ pick up.

**User input:** $ARGUMENTS

## Pipeline

1-6. Giống `/post` (context, video-prep, hook, caption, hashtag)

7. Parse `when` từ $ARGUMENTS:
   - `auto` hoặc không có → invoke `tiktok-scheduler` để lấy `next-slot`
   - ISO datetime → validate (không quá khứ, không trong blackout window 2h với post gần nhất)
   - Dạng tự do ("mai 8h tối", "thứ 5 tuần sau") → parse thành ISO

8. Invoke `tiktok-scheduler` enqueue:
```bash
python scripts/tool_schedule.py enqueue \
  --video=<processed> \
  --caption="<caption>" \
  --hashtags="<tags>" \
  --when="<iso_or_auto>"
```

9. Verify worker đang chạy:
```bash
pgrep -f "cron_worker.py" && echo "RUNNING" || echo "NOT_RUNNING"
```

10. Output theo tiktok-scheduler SKILL.md (block "⏰ ĐÃ LÊN LỊCH") + warning nếu worker chưa chạy.

## Worker setup (hiển thị nếu not running)

```bash
# Option 1: Daemon
nohup python scripts/cron_worker.py --interval=300 > logs/worker.log 2>&1 &

# Option 2: Cron (chạy mỗi 5 phút)
(crontab -l; echo "*/5 * * * * cd $PWD && python scripts/cron_worker.py --once") | crontab -

# Option 3: Systemd (production, xem scripts/tiktok-worker.service)
sudo systemctl enable --now tiktok-worker
```

## Batch scheduling

Nếu user có nhiều video muốn schedule 1 tuần:
- Invoke `tiktok-scheduler` SKILL.md, xem phần "Batch scheduling"
- Phân bổ theo golden hours + cách nhau ≥ 12h
- Lặp enqueue cho từng video
