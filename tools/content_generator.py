"""
Content Generator — dùng Claude CLI (Claude Code) thay vì Anthropic API.

Yêu cầu:
  - Đã cài Claude Code: https://docs.claude.com/en/docs/claude-code/setup
  - Đã login: `claude login` (dùng account Pro/Max của bạn)
  - Command `claude` có trong PATH

Không cần ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UNSAFE_KEYWORDS = {
    "kill", "suicide", "drugs", "cocaine",
    "tự tử", "tự sát", "giết", "ma túy",
}

CAPTION_STYLES = {
    "gen_z_engaging": (
        "Phong cách Gen Z Việt Nam, vui, hook mạnh ở đầu câu. "
        "1-2 emoji tự nhiên, không spam. Câu ngắn, nhịp nhanh. "
        "Kết thúc bằng câu hỏi hoặc CTA nhẹ."
    ),
    "professional": (
        "Trang trọng, rõ ràng, xúc tích. Tối đa 1 emoji trung tính. "
        "Giá trị lên trước, chi tiết sau."
    ),
    "storytelling": (
        "Mở đầu bằng 'POV:' hoặc 'Tôi đã...' để tạo tò mò. "
        "Có conflict → giải pháp → bài học. Tối đa 3 câu."
    ),
    "educational": (
        "Format: '3 điều về X mà bạn chưa biết' / 'Mẹo Y trong 15 giây'. "
        "Số liệu cụ thể, actionable."
    ),
}


class ClaudeCLIError(RuntimeError):
    """Lỗi khi gọi Claude CLI."""


class ContentGenerator:
    """Sinh caption bằng cách gọi `claude` command line."""

    def __init__(self, claude_bin: str = "claude", timeout: int = 60):
        self.claude_bin = claude_bin
        self.timeout = timeout
        self._check_cli()

    def _check_cli(self) -> None:
        if not shutil.which(self.claude_bin):
            raise ClaudeCLIError(
                f"Không tìm thấy lệnh `{self.claude_bin}` trong PATH.\n"
                "Cài đặt: https://docs.claude.com/en/docs/claude-code/setup\n"
                "Sau khi cài, chạy: claude login"
            )

    # ------------------------------------------------------------------
    # Core: gọi Claude CLI
    # ------------------------------------------------------------------
    def _call_claude(
        self,
        prompt: str,
        system: Optional[str] = None,
        output_format: str = "text",
    ) -> str:
        """
        Gọi `claude -p <prompt>` và trả về response.

        output_format: "text" (mặc định) hoặc "json" để parse structured output.
        """
        cmd = [self.claude_bin, "-p", prompt]
        if system:
            cmd.extend(["--append-system-prompt", system])
        if output_format == "json":
            cmd.extend(["--output-format", "json"])

        logger.debug(f"Gọi Claude CLI: claude -p {prompt[:60]}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ClaudeCLIError(f"Claude CLI timeout sau {self.timeout}s")

        if result.returncode != 0:
            stderr = result.stderr.strip()
            low = stderr.lower()
            if "rate limit" in low or "usage limit" in low or "limit reached" in low:
                raise ClaudeCLIError(f"Đã đạt rate limit Claude Pro: {stderr}")
            if "authentication" in low or "not logged in" in low or "login" in low:
                raise ClaudeCLIError(
                    f"Claude CLI chưa login. Chạy: claude login\n{stderr}"
                )
            raise ClaudeCLIError(f"Claude CLI lỗi (code {result.returncode}): {stderr}")

        output = result.stdout.strip()

        if output_format == "json":
            try:
                parsed = json.loads(output)
                return parsed.get("result", output)
            except json.JSONDecodeError:
                logger.warning("Không parse được JSON từ Claude CLI, trả raw.")
                return output

        return output

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(
        self,
        topic: str,
        description: str = "",
        style: str = "gen_z_engaging",
        language: str = "vi",
    ) -> str:
        """Sinh caption TikTok."""
        style_guide = CAPTION_STYLES.get(style, CAPTION_STYLES["gen_z_engaging"])

        system = (
            "Bạn là chuyên gia viết caption TikTok viral. "
            "Trả về DUY NHẤT caption, không preamble, không giải thích, "
            "không dùng markdown, không quote bao ngoài."
        )

        prompt = f"""Viết caption TikTok bằng {language}.

CHỦ ĐỀ: {topic}
MÔ TẢ VIDEO: {description or "(không có)"}

YÊU CẦU:
- Style: {style_guide}
- Độ dài: 80-150 ký tự (KHÔNG tính hashtag)
- 5 từ đầu PHẢI là hook mạnh (câu hỏi, con số, POV, tuyên bố)
- KHÔNG thêm hashtag (sẽ thêm sau ở bước khác)
- KHÔNG dùng dấu ** hay markdown

Chỉ in ra caption, không gì khác."""

        caption = self._call_claude(prompt, system=system)
        caption = self._cleanup(caption)
        logger.info(f"✍️  Caption ({len(caption)} chars): {caption[:60]}...")
        return caption

    def _cleanup(self, text: str) -> str:
        """Loại bỏ markdown, quote marks bao ngoài, hashtag lẫn trong."""
        text = text.strip().strip('"').strip("'").strip("`")
        text = re.sub(r"^(caption|đây là caption|caption TikTok)[:\s]*",
                      "", text, flags=re.IGNORECASE)
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"#\w+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ------------------------------------------------------------------
    def describe_video(self, video_path: Path, max_frames: int = 3) -> str:
        """
        Mô tả video bằng cách trích frames rồi bảo Claude Code đọc bằng tool Read.
        Claude Code có vision khi đọc image file qua tool Read.
        """
        from tools.video_processor import VideoProcessor
        vp = VideoProcessor()
        info = vp.probe(video_path)

        timestamps = [0.5, info["duration"] / 2, max(info["duration"] - 1, 0)]
        frame_paths = []
        for ts in timestamps[:max_frames]:
            thumb = vp.extract_thumbnail(video_path, timestamp=ts)
            frame_paths.append(str(thumb.absolute()))

        file_list = "\n".join(f"- {p}" for p in frame_paths)
        prompt = f"""Hãy dùng tool Read để đọc các ảnh sau (frames từ 1 video TikTok):

{file_list}

Sau khi xem xong, mô tả NGẮN (1-2 câu) nội dung chính của video, tập trung vào điểm thú vị.
Trả về duy nhất mô tả, không preamble."""

        return self._call_claude(prompt)

    # ------------------------------------------------------------------
    def is_safe(self, text: str) -> bool:
        text_lower = text.lower()
        for kw in UNSAFE_KEYWORDS:
            if kw in text_lower:
                logger.warning(f"Caption chứa từ nhạy cảm: '{kw}'")
                return False
        return True

    def rewrite_safer(self, text: str) -> str:
        return self._call_claude(
            f"Caption này có thể vi phạm policy TikTok. "
            f"Viết lại giữ ý chính nhưng bỏ từ nhạy cảm. "
            f"Trả về duy nhất caption mới:\n\n{text}"
        )

    # ------------------------------------------------------------------
    def generate_with_hashtags(
        self, topic: str, description: str = "", style: str = "gen_z_engaging"
    ) -> dict:
        """
        Sinh caption + hashtag trong 1 lần gọi duy nhất.
        Tiết kiệm quota Claude Pro — 1 call thay vì 2.
        """
        system = (
            "Bạn là chuyên gia TikTok marketing. "
            "Trả về DUY NHẤT JSON hợp lệ, không markdown code fence, không giải thích."
        )
        prompt = f"""Sinh nội dung TikTok cho chủ đề: "{topic}"
Mô tả video: {description or "(không có)"}
Style: {CAPTION_STYLES.get(style)}

Trả về JSON với schema:
{{"caption": "...", "hashtags": ["tag1", "tag2", ...]}}

Yêu cầu:
- caption: 80-150 ký tự, hook mạnh, KHÔNG chứa hashtag
- hashtags: 5 tag theo pyramid (1 trending + 2 niche + 1 evergreen + 1 brand)
- Không có '#' trong hashtags, chỉ text thuần"""

        raw = self._call_claude(prompt, system=system)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Không parse được JSON: {raw[:200]}")
            raise ClaudeCLIError(f"Claude trả về JSON invalid: {e}")
