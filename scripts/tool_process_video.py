#!/usr/bin/env python3
"""CLI wrapper cho VideoProcessor — với self-correcting error messages."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.video_processor import VideoProcessor


def error(error_type: str, raw_error: str, remediation: dict) -> None:
    print(json.dumps({
        "success": False,
        "error_type": error_type,
        "raw_error": raw_error,
        "remediation": remediation,
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--watermark", default="")
    p.add_argument("--trim", type=int, default=None)
    p.add_argument("--action", choices=["prepare", "probe", "hash", "thumbnail"],
                   default="prepare")
    args = p.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        error("file_not_found", f"Path: {args.input}", {
            "explanation": "File video không tồn tại tại path đã cho",
            "action": "halt",
            "next_step": "Verify path đúng. Hỏi user nếu path có trong context không.",
            "do_not": "assume path exists — luôn stat trước",
            "user_message": f"Không tìm thấy file: {args.input}",
        })

    try:
        vp = VideoProcessor(watermark_path=args.watermark or None)
    except RuntimeError as ex:
        if "ffmpeg" in str(ex).lower():
            error("ffmpeg_missing", str(ex), {
                "explanation": "ffmpeg chưa được cài trong hệ thống",
                "action": "halt",
                "next_step": "User cần: `apt install ffmpeg` (Linux) hoặc `brew install ffmpeg` (macOS)",
                "do_not": "thử alternate video tool — workflow này phụ thuộc ffmpeg",
                "user_message": "Cần cài ffmpeg trước. Xem docs/setup.md.",
            })
        raise

    try:
        if args.action == "probe":
            info = vp.probe(input_path)
            # Sanity warnings
            warnings = []
            if info["duration"] < 15:
                warnings.append(f"duration {info['duration']:.1f}s < 15s (TikTok min recommended)")
            if info["duration"] > 180:
                warnings.append(f"duration {info['duration']:.1f}s > 180s (will be trimmed)")
            if info["width"] == 0:
                warnings.append("no video stream detected")

            print(json.dumps({
                "success": True,
                "info": info,
                "warnings": warnings,
            }, ensure_ascii=False, indent=2))

        elif args.action == "hash":
            h = vp.compute_hash(input_path)
            print(json.dumps({"success": True, "hash": h}, ensure_ascii=False, indent=2))

        elif args.action == "thumbnail":
            out = vp.extract_thumbnail(input_path)
            print(json.dumps({
                "success": True,
                "thumbnail_path": str(out),
                "size_bytes": out.stat().st_size,
            }, ensure_ascii=False, indent=2))

        else:  # prepare
            info = vp.probe(input_path)
            out = vp.prepare_for_tiktok(
                input_path,
                add_watermark=bool(args.watermark),
                trim_to=args.trim,
            )
            size_mb = out.stat().st_size / 1e6

            # Check if processed file still within TikTok limits
            if size_mb > 287.6:
                error("output_too_large", f"{size_mb:.1f} MB > 287.6 MB", {
                    "explanation": "Sau khi process, file vẫn quá lớn",
                    "action": "reprocess_with_higher_crf",
                    "next_step": "Retry với CRF=28 thay vì 23 (giảm quality, giảm size)",
                    "do_not": "upload file này — sẽ fail ở TikTok API",
                    "user_message": "Video quá lớn sau khi nén. Cần giảm thêm.",
                })

            warnings = []
            if info["duration"] > 60 and not args.trim:
                warnings.append("duration >60s, consider --trim=30 for retention")

            print(json.dumps({
                "success": True,
                "processed_path": str(out),
                "size_mb": round(size_mb, 2),
                "hash": vp.compute_hash(input_path),
                "duration_s": round(info["duration"], 1),
                "dimensions": f"{info['width']}x{info['height']}",
                "warnings": warnings,
            }, ensure_ascii=False, indent=2))

    except RuntimeError as ex:
        msg = str(ex).lower()
        if "ffmpeg" in msg:
            error("ffmpeg_processing_failed", str(ex), {
                "explanation": "ffmpeg fail khi encode/probe",
                "action": "check_input",
                "next_step": "Probe input trước (--action=probe) xem codec có corrupt không",
                "do_not": "retry cùng input — thường là video corrupt hoặc codec exotic",
                "user_message": "Video bị lỗi hoặc codec không hỗ trợ. Thử convert sang MP4 H.264 trước.",
            })
        error("unexpected_processing_error", str(ex), {
            "explanation": "Lỗi không xác định khi process video",
            "action": "halt_and_log",
            "next_step": "Log raw error, báo user review thủ công",
            "user_message": "Gặp lỗi lạ khi xử lý video.",
        })


if __name__ == "__main__":
    main()
