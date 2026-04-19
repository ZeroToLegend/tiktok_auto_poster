"""
Video Processor — chuẩn hóa video cho TikTok.
Dùng ffmpeg-python làm wrapper.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Chuẩn hóa video về spec TikTok: 9:16, H.264, AAC, ≤ 60s, ≤ 287.6 MB."""

    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_FPS = 30
    MAX_DURATION = 180  # giây
    CRF = 23  # chất lượng (thấp hơn = đẹp hơn, 18–28 là hợp lý)

    def __init__(self, watermark_path: Optional[Path] = None, output_dir: Path = None):
        self.watermark_path = Path(watermark_path) if watermark_path else None
        self.output_dir = output_dir or Path("data/processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "ffmpeg chưa được cài. Cài: `apt install ffmpeg` hoặc `brew install ffmpeg`."
            )

    # ------------------------------------------------------------------
    def prepare_for_tiktok(
        self, input_path: Path, add_watermark: bool = False, trim_to: Optional[int] = None
    ) -> Path:
        """
        Pipeline chính: resize 9:16, normalize audio, optional watermark.
        Trả về path của file đã xử lý.
        """
        input_path = Path(input_path)
        output_path = self.output_dir / f"tt_{input_path.stem}.mp4"

        info = self.probe(input_path)
        logger.info(
            f"📹 Input: {info['width']}x{info['height']}, "
            f"{info['duration']:.1f}s, {info['video_codec']}/{info['audio_codec']}"
        )

        # Build filter graph
        video_filters = self._build_video_filters(info)
        audio_filters = "loudnorm=I=-14:TP=-1.5:LRA=11"  # chuẩn TikTok

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
        ]

        if add_watermark and self.watermark_path and self.watermark_path.exists():
            cmd.extend(["-i", str(self.watermark_path)])
            # Đè watermark vào góc phải dưới, cách mép 40px
            filter_complex = (
                f"[0:v]{video_filters}[v0];"
                f"[v0][1:v]overlay=W-w-40:H-h-200[v]"
            )
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
        else:
            cmd.extend(["-vf", video_filters])

        cmd.extend([
            "-af", audio_filters,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(self.CRF),
            "-pix_fmt", "yuv420p",
            "-r", str(self.TARGET_FPS),
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-movflags", "+faststart",  # quan trọng: cho phép stream
        ])

        duration_limit = trim_to or min(info["duration"], self.MAX_DURATION)
        cmd.extend(["-t", str(duration_limit)])
        cmd.append(str(output_path))

        logger.info(f"🎬 Đang encode → {output_path.name}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(result.stderr[-500:])
            raise RuntimeError(f"ffmpeg thất bại: {result.stderr[-200:]}")

        logger.info(f"✅ Xử lý xong: {output_path} ({output_path.stat().st_size/1e6:.1f} MB)")
        return output_path

    def _build_video_filters(self, info: dict) -> str:
        """
        Resize+crop về 9:16. Nếu video landscape thì scale vừa chiều ngang + letterbox đen;
        nếu portrait thì crop center.
        """
        src_ratio = info["width"] / info["height"]
        tgt_ratio = self.TARGET_WIDTH / self.TARGET_HEIGHT  # 0.5625

        if abs(src_ratio - tgt_ratio) < 0.01:
            # Đã 9:16, chỉ scale
            return f"scale={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:flags=lanczos"
        elif src_ratio > tgt_ratio:
            # Landscape → scale theo chiều ngang rồi pad đen trên/dưới
            return (
                f"scale={self.TARGET_WIDTH}:-2:flags=lanczos,"
                f"pad={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"
            )
        else:
            # Portrait hơi hẹp → crop center
            return (
                f"scale=-2:{self.TARGET_HEIGHT}:flags=lanczos,"
                f"crop={self.TARGET_WIDTH}:{self.TARGET_HEIGHT}"
            )

    # ------------------------------------------------------------------
    def probe(self, path: Path) -> dict:
        """Lấy thông tin video qua ffprobe."""
        import json
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(path),
            ],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
        audio_stream = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})
        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "duration": float(data["format"].get("duration", 0)),
            "video_codec": video_stream.get("codec_name", "unknown"),
            "audio_codec": audio_stream.get("codec_name", "none"),
            "bitrate": int(data["format"].get("bit_rate", 0)),
        }

    def compute_hash(self, path: Path) -> str:
        """Hash SHA-256 của file để detect trùng lặp."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def extract_thumbnail(self, path: Path, timestamp: float = 1.0) -> Path:
        """Xuất thumbnail tại giây `timestamp`."""
        out = self.output_dir / f"thumb_{path.stem}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(path),
             "-vframes", "1", "-q:v", "2", str(out)],
            capture_output=True, check=True,
        )
        return out
