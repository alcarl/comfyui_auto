"""基于 nodriver 真实浏览器的 Pinterest 图片墙抓取器。

相比纯 http 抓取，浏览器方式可以直接拿到渲染后的 DOM、绕过大部分
反爬与登录限制，且无需研究 Pinterest 私有 API。流程：

1. 通过 BrowserLauncher 启动（带代理、加载已有登录态）。
2. 若未登录（页面跳转登录），提示用户手动登录并保存登录态。
3. 进入目标 pin / board 页面，滚动加载更多图片。
4. 提取页面中所有 <img> 的高清原图 URL（originals / 736x 优先）。
5. 用可注入的 http_get 把图片字节下载下来，返回 FetchedImage 列表。

为了可测试，浏览器实例和 http_get 都通过参数注入；测试时传入桩对象。
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, List, Optional

from ..config.models import SiteConfig
from ..crawler.base import BaseCrawler, FetchedImage, HttpGet
from .launcher import BrowserLauncher

# 从浏览器 DOM 中提取的图片地址（与 http 版共用同样的 pinimg 域名规则）
_PIN_IMG_RE = re.compile(
    r"https?://(?:[^/]+\.)*pinimg\.com/(?:originals|736x|474x|564x|345x|236x)/[^\s\"'\\]+",
    re.IGNORECASE,
)


class PinterestBrowserCrawler(BaseCrawler):
    crawler_type = "pinterest_browser"

    def __init__(self, site: SiteConfig, timeout: int = 30,
                 max_concurrency: int = 4, retry: int = 2,
                 user_agent: str = "", http_get: Optional[HttpGet] = None,
                 browser_factory: Optional[Any] = None,
                 launcher: Optional[BrowserLauncher] = None,
                 progress: Optional[Any] = None,
                 browser_config: Optional[Any] = None):
        super().__init__(site, timeout=timeout, max_concurrency=max_concurrency,
                         retry=retry, user_agent=user_agent, http_get=http_get)
        self._browser_factory = browser_factory
        self._launcher = launcher
        self._progress = progress or (lambda *a, **k: None)
        self._browser_config = browser_config

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def discover_image_urls(self, page_url: str) -> List[str]:
        """同步包装：在事件循环中驱动真实浏览器提取图片 URL。"""
        return asyncio.run(self._discover_image_urls_async(page_url))

    def fetch_images(self) -> List[FetchedImage]:
        """同步包装：全程在事件循环中完成（含浏览器驱动与下载）。"""
        return asyncio.run(self._fetch_images_async())

    # ------------------------------------------------------------------ #
    # 异步实现
    # ------------------------------------------------------------------ #
    async def _discover_image_urls_async(self, page_url: str) -> List[str]:
        browser = await self._ensure_browser()
        tab = await browser.get(page_url)
        await self._scroll_to_load(tab)
        html = await self._get_page_html(tab)
        urls = self._extract_img_urls(html)
        await self._maybe_close_browser()
        return urls

    async def _fetch_images_async(self) -> List[FetchedImage]:
        browser = await self._ensure_browser()
        results: List[FetchedImage] = []
        seen_urls = set()
        for page_url in self.site.urls:
            try:
                tab = await browser.get(page_url)
                await self._scroll_to_load(tab)
                html = await self._get_page_html(tab)
            except Exception as e:  # noqa: BLE001
                self._progress("error", f"加载页面失败 {page_url}: {e}")
                continue
            urls = self._extract_img_urls(html)
            for img_url in urls:
                if img_url in seen_urls:
                    continue
                seen_urls.add(img_url)
                try:
                    data, ctype = self.http_get(img_url)
                except Exception as e:  # noqa: BLE001
                    self._progress("error", f"下载失败 {img_url}: {e}")
                    continue
                if not data:
                    continue
                results.append(FetchedImage(
                    url=img_url, data=data, content_type=ctype,
                    source_page=page_url, site=self.site.name))
        await self._maybe_close_browser()
        return results

    # ------------------------------------------------------------------ #
    # 浏览器辅助
    # ------------------------------------------------------------------ #
    async def _ensure_browser(self) -> Any:
        """启动浏览器（如已注入 launcher 则复用），加载登录态，必要时登录。"""
        if self._launcher is not None:
            browser = await self._launcher.start()
        else:
            from ..config.models import BrowserConfig
            cfg = self._browser_config or BrowserConfig()
            launcher = BrowserLauncher(cfg, browser_factory=self._browser_factory)
            self._launcher = launcher
            self._launcher = launcher
            browser = await launcher.start()
            # 尝试加载已有登录态
            await launcher.load_session()

        # 判断是否已登录（简单判定：能打开首页且无登录跳转）
        logged_in = await self._check_logged_in(browser)
        if not logged_in:
            self._progress("login", "未检测到登录态，请在浏览器中手动登录 Pinterest。")
            from .auth import pinterest_login
            ok = await pinterest_login(
                browser,
                timeout=self._browser_config.login_timeout
                if self._browser_config else 180,
                progress=lambda m: self._progress("login", m),
            )
            if ok and self._launcher is not None:
                await self._launcher.save_session()
        return browser

    async def _check_logged_in(self, browser: Any) -> bool:
        try:
            tab = await browser.get("https://www.pinterest.com/")
            await asyncio.sleep(2)
            url = tab.url if hasattr(tab, "url") else ""
            return "/login" not in url
        except Exception:  # noqa: BLE001
            return False

    async def _scroll_to_load(self, tab: Any) -> None:
        times = self._browser_config.scroll_times if self._browser_config else 5
        pause = self._browser_config.scroll_pause if self._browser_config else 1.5
        for _ in range(times):
            try:
                await tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(pause)

    async def _get_page_html(self, tab: Any) -> str:
        try:
            return await tab.get_content() or ""
        except Exception:  # noqa: BLE001
            try:
                return await tab.evaluate("document.documentElement.outerHTML") or ""
            except Exception:  # noqa: BLE001
                return ""

    async def _maybe_close_browser(self) -> None:
        # 由外部（pipeline）控制是否关闭；这里默认不主动关闭，
        # 因为一次 crawl 可能含多个站点/URL，复用浏览器更高效。
        pass

    # ------------------------------------------------------------------ #
    # 解析（纯函数，便于单测）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_img_urls(html: str) -> List[str]:
        urls = _PIN_IMG_RE.findall(html)
        # 去重保序，originals / 736x 优先
        seen, ordered = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered

    @staticmethod
    def prefer_original(urls: List[str]) -> List[str]:
        def score(u: str) -> int:
            if "/originals/" in u:
                return 0
            if "/736x/" in u:
                return 1
            return 2
        return sorted(urls, key=score)
