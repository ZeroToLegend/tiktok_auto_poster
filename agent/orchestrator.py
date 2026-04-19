"""
TikTok Posting Agent - Orchestrator
Điều phối toàn bộ quy trình tự động đăng bài.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from tools.tiktok_api import TikTokAPI, TikTokUploadError
from tools.video_processor import VideoProcessor
from tools.content_generator import ContentGenerator
from tools.hashtag_generator import HashtagGenerator
from tools.scheduler import PostScheduler, ScheduleSlot
from tools.analytics import AnalyticsTracker

logger = logging.getLogger(__name__)


class PostStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SCHEDULED = "scheduled"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class PostRequest:
    """Đơn vị công việc đăng bài."""
    video_path: Path
    topic: str = ""
    description: str = ""
    schedule_at: Optional[float] = None  # unix timestamp, None = đăng ngay
    privacy: str = "PUBLIC_TO_EVERYONE"   # hoặc MUTUAL_FOLLOW_FRIENDS, SELF_ONLY
    account_id: str = "default"
    style: str = "gen_z_engaging"

    # được điền khi xử lý
    processed_path: Optional[Path] = None
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    status: PostStatus = PostStatus.PENDING
    publish_id: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0


class TikTokAgent:
    """
    Agent chính. Dùng như:
        agent = TikTokAgent(config)
        agent.post(PostRequest(video_path=Path("video.mp4"), topic="học python"))
    """

    MAX_RETRIES = 5
    DAILY_POST_LIMIT = 6

    def __init__(self, config: dict):
        self.config = config
        self.api = TikTokAPI(
            client_key=config["tiktok"]["client_key"],
            client_secret=config["tiktok"]["client_secret"],
            access_token=config["tiktok"]["access_token"],
            refresh_token=config["tiktok"].get("refresh_token"),
        )
        self.video_processor = VideoProcessor(
            watermark_path=config.get("watermark_path"),
        )
        self.content_gen = ContentGenerator(
            claude_bin=config.get("claude_cli", {}).get("binary", "claude"),
            timeout=config.get("claude_cli", {}).get("timeout", 60),
        )
        self.hashtag_gen = HashtagGenerator()
        self.scheduler = PostScheduler(db_path=config["queue_db"])
        self.analytics = AnalyticsTracker(db_path=config["analytics_db"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def post(self, req: PostRequest) -> PostRequest:
        """Xử lý một yêu cầu đăng bài đầy đủ vòng đời."""
        logger.info(f"📥 Nhận yêu cầu đăng bài: {req.video_path.name}")

        try:
            self._precheck(req)
            self._process_video(req)
            self._generate_content(req)
            self._validate(req)

            if req.schedule_at and req.schedule_at > time.time():
                self._enqueue(req)
            else:
                self._upload_with_retry(req)

        except Exception as e:
            req.status = PostStatus.FAILED
            req.error = str(e)
            logger.exception(f"❌ Đăng bài thất bại: {e}")

        return req

    def run_scheduled_jobs(self) -> list[PostRequest]:
        """Chạy các job đã đến hạn trong queue. Dùng cho cron."""
        due = self.scheduler.pop_due_jobs(now=time.time())
        results = []
        for job in due:
            results.append(self._upload_with_retry(job))
        return results

    # ------------------------------------------------------------------
    # Quy trình theo SKILL.md
    # ------------------------------------------------------------------
    def _precheck(self, req: PostRequest) -> None:
        """Bước 1: tiền kiểm tra."""
        if not req.video_path.exists():
            raise FileNotFoundError(f"Video không tồn tại: {req.video_path}")

        # Quota ngày
        today_count = self.scheduler.count_published_today(req.account_id)
        if today_count >= self.DAILY_POST_LIMIT:
            raise RuntimeError(
                f"Đã đăng {today_count}/{self.DAILY_POST_LIMIT} video hôm nay. "
                "Đợi sang ngày mới."
            )

        # Trùng lặp (hash video)
        video_hash = self.video_processor.compute_hash(req.video_path)
        if self.scheduler.was_posted_recently(video_hash, days=7):
            raise RuntimeError("Video này đã đăng trong 7 ngày qua.")

    def _process_video(self, req: PostRequest) -> None:
        """Bước 2: xử lý video."""
        req.status = PostStatus.PROCESSING
        logger.info("🎬 Đang xử lý video (9:16, watermark, codec)...")
        req.processed_path = self.video_processor.prepare_for_tiktok(
            req.video_path,
            add_watermark=bool(self.config.get("watermark_path")),
        )

    def _generate_content(self, req: PostRequest) -> None:
        """Bước 3: sinh caption + hashtag."""
        logger.info("✍️  Đang sinh caption & hashtag...")

        description = req.description
        if not description:
            # dùng vision model đọc video để tự mô tả
            description = self.content_gen.describe_video(req.processed_path)

        req.caption = self.content_gen.generate(
            topic=req.topic or description[:100],
            description=description,
            style=req.style,
        )
        req.hashtags = self.hashtag_gen.suggest(
            topic=req.topic,
            count=5,
            strategy="balanced",  # 1 trend + 2 niche + 1 brand + 1 evergreen
        )

    def _validate(self, req: PostRequest) -> None:
        """Bước 4: kiểm tra cuối trước khi upload."""
        if not self.content_gen.is_safe(req.caption):
            raise ValueError("Caption chứa nội dung không phù hợp, cần review.")

        total_hashtag_len = sum(len(h) + 1 for h in req.hashtags)
        if total_hashtag_len > 100:
            logger.warning("Hashtag quá dài, đang cắt bớt...")
            req.hashtags = req.hashtags[:3]

        # refresh token nếu sắp hết hạn
        self.api.ensure_token_valid()

    def _enqueue(self, req: PostRequest) -> None:
        """Bước 5a: lên lịch."""
        req.status = PostStatus.SCHEDULED
        slot = ScheduleSlot(
            run_at=req.schedule_at,
            account_id=req.account_id,
            payload=req,
        )
        self.scheduler.enqueue(slot)
        logger.info(
            f"⏰ Đã xếp lịch đăng lúc "
            f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(req.schedule_at))}"
        )

    def _upload_with_retry(self, req: PostRequest) -> PostRequest:
        """Bước 5b: upload ngay, có retry."""
        req.status = PostStatus.UPLOADING

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"🚀 Upload (lần {attempt + 1}/{self.MAX_RETRIES})...")
                full_caption = self._build_full_caption(req)

                publish_id = self.api.upload_video(
                    video_path=req.processed_path,
                    caption=full_caption,
                    privacy=req.privacy,
                )
                req.publish_id = publish_id

                # Poll status
                final_status = self.api.wait_for_publish(publish_id, timeout=300)
                if final_status == "PUBLISH_COMPLETE":
                    req.status = PostStatus.PUBLISHED
                    self._record_success(req)
                    logger.info(f"✅ Đăng thành công! publish_id={publish_id}")
                    return req
                else:
                    raise TikTokUploadError(f"Trạng thái cuối: {final_status}")

            except TikTokUploadError as e:
                req.retries += 1
                if "rate_limit" in str(e).lower():
                    wait = 900  # 15 phút
                elif "spam_risk" in str(e).lower():
                    # spam risk không nên retry — dừng hẳn
                    req.status = PostStatus.FAILED
                    req.error = str(e)
                    raise
                else:
                    wait = 2 ** attempt  # exponential: 1,2,4,8,16s

                logger.warning(f"⚠️  Lỗi: {e}. Đợi {wait}s rồi thử lại.")
                time.sleep(wait)

        req.status = PostStatus.FAILED
        req.error = f"Hết {self.MAX_RETRIES} lần thử"
        return req

    def _build_full_caption(self, req: PostRequest) -> str:
        """Ghép caption + hashtag đúng format TikTok."""
        tags = " ".join(f"#{h.lstrip('#')}" for h in req.hashtags)
        return f"{req.caption}\n\n{tags}".strip()

    def _record_success(self, req: PostRequest) -> None:
        """Bước 6: ghi nhận để analytics sau."""
        self.analytics.record_post(
            publish_id=req.publish_id,
            account_id=req.account_id,
            caption=req.caption,
            hashtags=req.hashtags,
            posted_at=time.time(),
            video_hash=self.video_processor.compute_hash(req.video_path),
        )


# ----------------------------------------------------------------------
# Conversational interface — khi user nói chuyện tự nhiên với agent
# ----------------------------------------------------------------------
class ConversationalAgent:
    """
    Wrapper trả lời bằng ngôn ngữ tự nhiên.
    Dùng khi tích hợp vào chatbot.
    """

    def __init__(self, agent: TikTokAgent):
        self.agent = agent

    def handle_message(self, user_msg: str, attachments: list[Path] = None) -> str:
        """Phân tích ý định user và gọi agent."""
        intent = self._parse_intent(user_msg)

        if intent["action"] == "post_now":
            if not attachments:
                return "Bạn gửi file video lên giúp mình nhé? (MP4, 9:16 ưu tiên)"
            req = PostRequest(
                video_path=attachments[0],
                topic=intent.get("topic", ""),
                description=intent.get("description", ""),
            )
            result = self.agent.post(req)
            return self._format_result(result)

        if intent["action"] == "schedule":
            # ... logic lên lịch
            pass

        if intent["action"] == "report":
            return self._format_report(self.agent.analytics.last_24h())

        return "Mình có thể giúp: đăng video ngay, lên lịch đăng, xem báo cáo. Bạn muốn gì?"

    def _parse_intent(self, msg: str) -> dict:
        # Production: gọi LLM để parse. Ở đây rule-based đơn giản.
        msg_lower = msg.lower()
        if any(k in msg_lower for k in ["đăng ngay", "post now", "up luôn"]):
            return {"action": "post_now"}
        if any(k in msg_lower for k in ["lên lịch", "schedule", "đặt giờ"]):
            return {"action": "schedule"}
        if any(k in msg_lower for k in ["báo cáo", "report", "views", "analytics"]):
            return {"action": "report"}
        return {"action": "unknown"}

    def _format_result(self, req: PostRequest) -> str:
        if req.status == PostStatus.PUBLISHED:
            return (
                f"✅ Đã đăng thành công!\n"
                f"• publish_id: `{req.publish_id}`\n"
                f"• Caption: {req.caption[:80]}...\n"
                f"• Hashtag: {' '.join('#'+h for h in req.hashtags)}\n"
                f"• Sẽ có báo cáo views sau 24h."
            )
        return f"❌ Thất bại: {req.error}"

    def _format_report(self, stats: dict) -> str:
        return (
            f"📊 24h qua:\n"
            f"• Đã đăng: {stats.get('posts', 0)} video\n"
            f"• Tổng views: {stats.get('views', 0):,}\n"
            f"• Tổng likes: {stats.get('likes', 0):,}\n"
            f"• Top hashtag: {stats.get('top_hashtag', 'N/A')}"
        )
