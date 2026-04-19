#!/usr/bin/env python3
"""
oauth_setup.py — Chạy 1 lần để lấy access_token + refresh_token từ TikTok.

Cách dùng:
  1. python scripts/oauth_setup.py
  2. Mở URL trả về trên browser, chấp thuận
  3. TikTok redirect về URL có ?code=..., paste code vào terminal
  4. Script lưu tokens vào config/.env
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv, set_key
from tools.tiktok_api import get_oauth_url, exchange_code_for_token


def main():
    env_path = ROOT / "config" / ".env"
    load_dotenv(env_path)

    client_key = os.environ.get("TIKTOK_CLIENT_KEY")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    redirect_uri = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:8000/callback")

    if not client_key or not client_secret:
        print("❌ Thiếu TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET trong .env")
        sys.exit(1)

    url = get_oauth_url(client_key, redirect_uri)
    print("\n🔗 Mở URL này trên browser:\n")
    print(f"  {url}\n")
    print("Sau khi approve, TikTok redirect về URL có ?code=...")
    print("Paste URL đó vào đây (hoặc chỉ mã code):\n")

    raw = input("> ").strip()
    if raw.startswith("http"):
        code = parse_qs(urlparse(raw).query).get("code", [""])[0]
    else:
        code = raw

    if not code:
        print("❌ Không tìm thấy code.")
        sys.exit(1)

    print("🔄 Đang đổi code lấy tokens...")
    data = exchange_code_for_token(client_key, client_secret, code, redirect_uri)

    access_token = data["access_token"]
    refresh_token = data.get("refresh_token", "")
    expires_in = data.get("expires_in", 86400)

    set_key(str(env_path), "TIKTOK_ACCESS_TOKEN", access_token)
    set_key(str(env_path), "TIKTOK_REFRESH_TOKEN", refresh_token)

    print(f"\n✅ Đã lưu tokens vào {env_path}")
    print(f"   Access token hết hạn sau {expires_in}s")
    print(f"   Refresh token dùng để tự gia hạn.")


if __name__ == "__main__":
    main()
