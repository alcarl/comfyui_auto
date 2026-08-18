"""Pinterest 图片墙抓取器（一期实现）。

实现思路（稳健、可测试）：
- Pinterest 页面为 SPA，但 HTML 中会以 <img> 标签与内嵌 JSON 暴露图片地址。
- 我们同时解析：
  1) 所有 <img> 的 src / srcset（取高清原图，优先 originals / 736x）。
  2) 页面内嵌 JSON（__PINTEREST_STATE__ / 任意含图片 URL 的字段）中的图片地址。
- 通过注入的 http_get 获取页面 HTML，便于在单元测试中用本地 HTML 桩验证解析逻辑。
"""
from __future__ import annotations

import json
import re
from typing import List

from ..config.models import SiteConfig
from .base import BaseCrawler

# 匹配 pinterest 图片地址（含 originals / 736x / 474x 等尺寸目录）
_PIN_IMG_RE = re.compile(
    r"https?://(?:[^/]+\.)*pinimg\.com/(?:originals|736x|474x|564x|345x|236x)/[^\s\"'\\]+",
    re.IGNORECASE,
)

# 匹配 HTML 内 <img ... > 标签
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SRC_RE = re.compile(r"""src=["']([^"']+)["']""", re.IGNORECASE)
_SRCSET_RE = re.compile(r"""srcset=["']([^"']+)["']""", re.IGNORECASE)


class PinterestCrawler(BaseCrawler):
    crawler_type = "pinterest"

    def discover_image_urls(self, page_url: str) -> List[str]:
        html, _ = self.http_get(page_url)
        text = html.decode("utf-8", errors="ignore")
        urls = self._extract_from_html(text)
        urls += self._extract_from_json(text)
        # 去重并保持顺序
        seen, ordered = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered

    # ------------------------------------------------------------------ #
    # 解析逻辑（纯函数，便于单测）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_from_html(text: str) -> List[str]:
        urls: List[str] = []
        for tag in _IMG_TAG_RE.findall(text):
            # srcset 优先，包含多分辨率
            m = _SRCSET_RE.search(tag)
            if m:
                # srcset 形如 "url 736w, url2 474w"
                for part in m.group(1).split(","):
                    candidate = part.strip().split()[0] if part.strip() else ""
                    if candidate:
                        urls.append(candidate)
            m = _SRC_RE.search(tag)
            if m:
                urls.append(m.group(1))
        return urls

    @staticmethod
    def _extract_from_json(text: str) -> List[str]:
        """从页面内嵌 JSON 中扫描 pinimg 图片地址。"""
        return _PIN_IMG_RE.findall(text)

    @staticmethod
    def prefer_original(urls: List[str]) -> List[str]:
        """将 originals 高清原图排序在前，提升抓取质量。"""
        def score(u: str) -> int:
            if "/originals/" in u:
                return 0
            if "/736x/" in u:
                return 1
            return 2
        return sorted(urls, key=score)
