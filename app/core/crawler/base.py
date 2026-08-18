"""图片抓取器抽象基类与抓取结果模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import requests

from ..config.models import SiteConfig

# http_get 的类型：url -> (content_bytes, content_type)
HttpGet = Callable[[str], tuple[bytes, str]]


@dataclass
class FetchedImage:
    """抓取到的单张图片。"""
    url: str                     # 图片原图 URL
    data: bytes                  # 图片二进制内容
    content_type: str = ""       # 如 image/jpeg
    source_page: str = ""        # 来自哪个页面 URL
    site: str = ""               # 来源站点名


class BaseCrawler:
    """抓取器抽象基类。

    子类需实现 ``discover_image_urls``（从页面发现图片 URL）与
    ``fetch_images``（下载图片）。网络请求通过可注入的 ``http_get`` 解耦，
    便于单元测试时替换为本地桩函数。
    """

    # 子类声明支持的 crawler_type
    crawler_type: str = ""

    def __init__(self, site: SiteConfig, timeout: int = 30,
                 max_concurrency: int = 4, retry: int = 2,
                 user_agent: str = "", http_get: Optional[HttpGet] = None):
        self.site = site
        self.timeout = timeout
        self.max_concurrency = max_concurrency or 1
        self.retry = retry
        self.user_agent = user_agent or "Mozilla/5.0"
        self._http_get = http_get or self._default_http_get

    # ------------------------------------------------------------------ #
    # 网络请求（可替换）
    # ------------------------------------------------------------------ #
    def _default_http_get(self, url: str) -> tuple[bytes, str]:
        headers = {"User-Agent": self.user_agent}
        last_err: Optional[Exception] = None
        for _ in range(max(1, self.retry)):
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.content, resp.headers.get("Content-Type", "")
            except Exception as e:  # noqa: BLE001
                last_err = e
        raise last_err or RuntimeError(f"下载失败: {url}")

    def http_get(self, url: str) -> tuple[bytes, str]:
        return self._http_get(url)

    # ------------------------------------------------------------------ #
    # 子类接口
    # ------------------------------------------------------------------ #
    def discover_image_urls(self, page_url: str) -> List[str]:
        """从给定页面发现图片原图 URL 列表。子类必须实现。"""
        raise NotImplementedError

    def fetch_images(self) -> List[FetchedImage]:
        """抓取站点配置中所有 URL 页面的图片，返回去重后的图片列表。"""
        results: List[FetchedImage] = []
        seen_urls = set()
        for page_url in self.site.urls:
            try:
                img_urls = self.discover_image_urls(page_url)
            except Exception as e:  # noqa: BLE001
                print(f"[crawler] 发现图片失败 {page_url}: {e}")
                continue
            for img_url in img_urls:
                if img_url in seen_urls:
                    continue
                seen_urls.add(img_url)
                try:
                    data, ctype = self.http_get(img_url)
                except Exception as e:  # noqa: BLE001
                    print(f"[crawler] 下载失败 {img_url}: {e}")
                    continue
                if not data:
                    continue
                results.append(FetchedImage(
                    url=img_url, data=data, content_type=ctype,
                    source_page=page_url, site=self.site.name))
        return results

    # 工具：根据 content-type / url 推断扩展名
    @staticmethod
    def guess_ext(url: str, content_type: str = "") -> str:
        if "png" in content_type:
            return "png"
        if "webp" in content_type:
            return "webp"
        if "gif" in content_type:
            return "gif"
        lower = url.lower().split("?")[0]
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            if lower.endswith(ext):
                return ext.lstrip(".")
        return "jpg"
