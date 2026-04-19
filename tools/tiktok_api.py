"""
TikTok Content Posting API Client
Docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post/

QUAN TRỌNG: Cần đăng ký TikTok for Developers và được duyệt scope
  - video.upload
  - video.publish
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB — TikTok yêu cầu chunk 5–64 MB


class TikTokUploadError(Exception):
    """Lỗi khi upload hoặc publish."""


class TikTokAPI:
    def __init__(
        self,
        client_key: str,
        client_secret: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: float = 0,
    ):
        self.client_key = client_key
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------
    def ensure_token_valid(self) -> None:
        """Refresh token nếu còn < 5 phút là hết hạn."""
        if time.time() + 300 > self.token_expires_at:
            self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        if not self.refresh_token:
            logger.warning("Không có refresh_token, bỏ qua refresh.")
            return
        resp = requests.post(
            f"{TIKTOK_API_BASE}/v2/oauth/token/",
            data={
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self.token_expires_at = time.time() + data.get("expires_in", 86400)
        logger.info("🔑 Refresh access_token thành công.")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    # ------------------------------------------------------------------
    # Upload flow
    # ------------------------------------------------------------------
    def upload_video(
        self,
        video_path: Path,
        caption: str,
        privacy: str = "PUBLIC_TO_EVERYONE",
        disable_duet: bool = False,
        disable_stitch: bool = False,
        disable_comment: bool = False,
    ) -> str:
        """
        Upload + publish video. Trả về publish_id để poll status.
        """
        file_size = video_path.stat().st_size
        if file_size > 287_600_000:
            raise TikTokUploadError("File > 287.6 MB, không thể upload.")

        # 1. Init
        init_data = self._init_publish(
            file_size=file_size,
            caption=caption,
            privacy=privacy,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            disable_comment=disable_comment,
        )
        publish_id = init_data["publish_id"]
        upload_url = init_data["upload_url"]

        # 2. Upload chunks
        self._upload_file_chunks(upload_url, video_path, file_size)

        logger.info(f"📤 Upload xong, publish_id={publish_id}")
        return publish_id

    def _init_publish(
        self,
        file_size: int,
        caption: str,
        privacy: str,
        disable_duet: bool,
        disable_stitch: bool,
        disable_comment: bool,
    ) -> dict:
        """Khởi tạo phiên upload."""
        chunk_size = min(CHUNK_SIZE, file_size)
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        payload = {
            "post_info": {
                "title": caption[:2200],  # TikTok giới hạn 2200 ký tự
                "privacy_level": privacy,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch,
                "video_cover_timestamp_ms": 1000,  # frame ở giây thứ 1 làm cover
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

        resp = requests.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/video/init/",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            raise TikTokUploadError(f"Init thất bại: {resp.status_code} {resp.text}")

        data = resp.json().get("data", {})
        if "publish_id" not in data or "upload_url" not in data:
            err = resp.json().get("error", {})
            raise TikTokUploadError(f"Init response thiếu field: {err}")
        return data

    def _upload_file_chunks(self, upload_url: str, video_path: Path, file_size: int) -> None:
        """Upload từng chunk lên URL signed."""
        chunk_size = min(CHUNK_SIZE, file_size)
        with open(video_path, "rb") as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(chunk_size)
                end = offset + len(chunk) - 1
                headers = {
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                }
                resp = requests.put(upload_url, data=chunk, headers=headers, timeout=120)
                if resp.status_code not in (200, 201, 206):
                    raise TikTokUploadError(
                        f"Chunk upload fail @ {offset}: {resp.status_code} {resp.text[:200]}"
                    )
                offset = end + 1
                logger.debug(f"  chunk {offset}/{file_size} ({offset*100//file_size}%)")

    # ------------------------------------------------------------------
    # Status polling
    # ------------------------------------------------------------------
    def wait_for_publish(self, publish_id: str, timeout: int = 300) -> str:
        """Poll status cho đến khi xong hoặc timeout. Trả về status cuối."""
        deadline = time.time() + timeout
        poll_interval = 5
        while time.time() < deadline:
            status = self.get_publish_status(publish_id)
            logger.debug(f"  status={status}")
            if status in ("PUBLISH_COMPLETE", "FAILED"):
                return status
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.3, 20)
        raise TikTokUploadError(f"Timeout chờ publish {publish_id}")

    def get_publish_status(self, publish_id: str) -> str:
        resp = requests.post(
            f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/",
            json={"publish_id": publish_id},
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        fail_reason = data.get("fail_reason")
        if fail_reason:
            raise TikTokUploadError(f"Publish failed: {fail_reason}")
        return data.get("status", "UNKNOWN")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    def get_video_stats(self, video_id: str) -> dict:
        """Lấy stats của video (views, likes, comments, shares)."""
        resp = requests.post(
            f"{TIKTOK_API_BASE}/v2/video/query/",
            json={
                "filters": {"video_ids": [video_id]},
            },
            params={
                "fields": "id,title,view_count,like_count,comment_count,share_count",
            },
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        videos = resp.json().get("data", {}).get("videos", [])
        return videos[0] if videos else {}


# ----------------------------------------------------------------------
# OAuth helper — chạy 1 lần để lấy access_token
# ----------------------------------------------------------------------
def get_oauth_url(client_key: str, redirect_uri: str, state: str = "tiktok") -> str:
    """Tạo URL để user ủy quyền."""
    from urllib.parse import urlencode
    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": "user.info.basic,video.upload,video.publish",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"


def exchange_code_for_token(
    client_key: str, client_secret: str, code: str, redirect_uri: str
) -> dict:
    """Đổi authorization code lấy access_token."""
    resp = requests.post(
        f"{TIKTOK_API_BASE}/v2/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
