"""
Hashtag Generator — chọn hashtag theo chiến lược pyramid.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Hashtag pool — trong production nên fetch từ TikTok Trends API
TRENDING_TAGS = [
    "fyp", "foryou", "xuhuong", "viral", "trending",
    "xuhuongtiktok", "foryoupage", "parati",
]

EVERGREEN_TAGS = [
    "tiktokvietnam", "vietnam", "learnontiktok", "mẹohay",
]

NICHE_MAP = {
    "coding": ["coding", "programmer", "python", "webdev", "techtips"],
    "food": ["foodtiktok", "amthuc", "monngon", "foodie", "recipe"],
    "beauty": ["beautytips", "skincare", "makeup", "glowup"],
    "fitness": ["fitnesstips", "workout", "gym", "homeworkout"],
    "study": ["study", "studygram", "hoctap", "studymotivation"],
    "business": ["entrepreneur", "kinhdoanh", "marketing", "sales"],
    "lifestyle": ["lifestyle", "dailyvlog", "aesthetic", "vlog"],
    "travel": ["travel", "dulich", "vietnamtravel", "wanderlust"],
    "comedy": ["funny", "haihuoc", "meme", "vietcomedy"],
    "music": ["music", "cover", "singing", "musiccover"],
}


class HashtagGenerator:
    def __init__(self, brand_tags: list[str] = None, custom_pool: Path = None):
        self.brand_tags = brand_tags or []
        self.custom_pool = {}
        if custom_pool and Path(custom_pool).exists():
            with open(custom_pool) as f:
                self.custom_pool = json.load(f)

    def suggest(
        self,
        topic: str,
        count: int = 5,
        strategy: Literal["trending", "niche", "balanced"] = "balanced",
    ) -> list[str]:
        """
        Chiến lược pyramid:
          - 1 trending (đổ vào big pool, khó lên fyp nhưng có chance viral)
          - 2 niche (target audience đúng)
          - 1 evergreen (luôn có lượt xem)
          - 1 brand
        """
        niche_category = self._detect_category(topic)
        niche_tags = NICHE_MAP.get(niche_category, ["fyp"])

        if strategy == "trending":
            pool = TRENDING_TAGS + EVERGREEN_TAGS
            return random.sample(pool, min(count, len(pool)))

        if strategy == "niche":
            return niche_tags[:count]

        # balanced
        result = []
        result.append(random.choice(TRENDING_TAGS))
        result.extend(random.sample(niche_tags, min(2, len(niche_tags))))
        result.append(random.choice(EVERGREEN_TAGS))
        if self.brand_tags:
            result.append(self.brand_tags[0])

        # Dedup, cắt về đúng count
        seen = set()
        out = []
        for t in result:
            t = t.lstrip("#").lower()
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out[:count]

    def _detect_category(self, topic: str) -> str:
        """Map topic → category. Production: dùng embedding similarity."""
        topic_lower = topic.lower()
        keywords_map = {
            "coding": ["code", "python", "javascript", "lập trình", "dev", "programming"],
            "food": ["food", "ăn", "món", "recipe", "nấu", "cooking"],
            "beauty": ["beauty", "makeup", "skincare", "đẹp", "dưỡng da"],
            "fitness": ["gym", "workout", "tập", "fitness", "yoga"],
            "study": ["study", "học", "bài tập", "trường", "sinh viên"],
            "business": ["business", "kinh doanh", "bán hàng", "marketing"],
            "travel": ["travel", "du lịch", "phượt", "trip"],
            "comedy": ["hài", "vui", "funny", "meme"],
            "music": ["music", "nhạc", "bài hát", "cover", "hát"],
        }
        for cat, words in keywords_map.items():
            if any(w in topic_lower for w in words):
                return cat
        return "lifestyle"
