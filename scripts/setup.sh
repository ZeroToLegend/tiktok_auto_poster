#!/usr/bin/env bash
# setup.sh — Cài đặt môi trường
set -euo pipefail

echo "📦 Kiểm tra dependencies hệ thống..."
command -v ffmpeg >/dev/null 2>&1 || {
    echo "Cài ffmpeg:"
    echo "  Ubuntu: sudo apt install ffmpeg"
    echo "  macOS:  brew install ffmpeg"
    exit 1
}

echo "🐍 Tạo virtualenv..."
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo "📚 Cài Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📁 Khởi tạo thư mục data..."
mkdir -p data/videos data/processed logs

echo "🔐 Tạo .env từ template..."
if [ ! -f config/.env ]; then
    cp config/.env.example config/.env
    echo "⚠️  Hãy điền credentials vào config/.env"
fi

echo ""
echo "✅ Cài đặt xong!"
echo ""
echo "Các bước tiếp theo:"
echo "  1. Đăng ký TikTok Developer: https://developers.tiktok.com"
echo "  2. Tạo app, bật scope: video.upload, video.publish"
echo "  3. Chạy OAuth flow: python scripts/oauth_setup.py"
echo "  4. Điền tokens vào config/.env"
echo "  5. Chạy thử: python scripts/run_agent.py --mode=once --video=test.mp4"
