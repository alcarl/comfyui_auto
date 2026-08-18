"""基于 nodriver 真实浏览器的 Pinterest 图片墙抓取器。

设计原则（按需求）：
- 全程使用已打开的真实 Chrome 浏览器获取图片，**不经由 crawler 的
  http 下载**，避免直连被墙 / 代理不一致问题：图片字节通过页面内
  ``fetch()`` 在浏览器上下文获取（带代理），再转 base64 回传。
- 浏览器状态（含登录态）持久化到固定 ``user_data_dir``：登录一次后，
  下次启动自动复用，无需再次登录。
- 通过滚动加载更多图片，直接读取页面 ``<img>`` 元素的真实地址。

为可测试，浏览器实例与图片获取函数均通过参数注入；测试时传入桩对象。
"""
from __future__ import annotations

import asyncio
import base64
import re
from typing import Any, List, Optional

from ..config.models import SiteConfig
from ..crawler.base import BaseCrawler, FetchedImage, HttpGet
from .launcher import BrowserLauncher

# 仅用于测试/备用：从 HTML 提取图片地址（主路径已改为读取 DOM <img>）。
_IMG_EXT_RE = re.compile(
    r"https?://[^\s\"'\\]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s\"'\\]*)?",
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
        """同步包装：全程在事件循环中完成（浏览器驱动 + 浏览器内取图）。"""
        return asyncio.run(self._fetch_images_async())

    # ------------------------------------------------------------------ #
    # 异步实现
    # ------------------------------------------------------------------ #
    async def _discover_image_urls_async(self, page_url: str) -> List[str]:
        browser = await self._ensure_browser()
        tab = await browser.get(page_url)
        await self._scroll_to_load(tab)
        urls = await self._collect_img_urls(tab)
        await self._maybe_close_browser()
        return urls

    async def _fetch_images_async(self) -> List[FetchedImage]:
        browser = await self._ensure_browser()
        results: List[FetchedImage] = []
        seen_urls: set = set()
        for page_url in self.site.urls:
            try:
                tab = await browser.get(page_url)
                await self._scroll_to_load(tab)
            except Exception as e:  # noqa: BLE001
                self._progress("error", f"加载页面失败 {page_url}: {e}")
                continue
            # 直接读取页面上的 <img> 真实地址（优先大图）
            urls = await self._collect_img_urls(tab)
            self._progress("page", f"页面 {page_url} 发现 {len(urls)} 个图片地址")
            for img_url in urls:
                if img_url in seen_urls:
                    continue
                seen_urls.add(img_url)
                # 通过浏览器上下文获取图片字节（带代理，避免直连被墙）
                try:
                    data, ctype = await self._fetch_via_browser(tab, img_url)
                except Exception as e:  # noqa: BLE001
                    self._progress("error", f"浏览器取图失败 {img_url}: {e}")
                    continue
                if not data:
                    continue
                results.append(FetchedImage(
                    url=img_url, data=data, content_type=ctype,
                    source_page=page_url, site=self.site.name))
        self._progress("done", f"浏览器抓取完成，共 {len(results)} 张图片")
        await self._maybe_close_browser()
        return results

    # ------------------------------------------------------------------ #
    # 浏览器取图（核心：不经由 crawler 的 http）
    # ------------------------------------------------------------------ #
    async def _fetch_via_browser(self, tab: Any, img_url: str) -> tuple[bytes, str]:
        """在页面 JS 上下文用 fetch 获取图片字节（走浏览器代理），返回 (bytes, mime)。"""
        js = (
            "(async (u) => {"
            "  try {"
            "    const r = await fetch(u, {mode:'cors', credentials:'omit'});"
            "    const t = r.headers.get('content-type') || 'image/jpeg';"
            "    const b = await r.arrayBuffer();"
            "    let s = ''; const v = new Uint8Array(b);"
            "    const CH = 0x8000;"
            "    for (let i=0; i<v.length; i+=CH) {"
            "      s += String.fromCharCode.apply(null, v.subarray(i, i+CH));"
            "    }"
            "    return JSON.stringify({ok:true, mime:t, b64:btoa(s)});"
            "  } catch(e) { return JSON.stringify({ok:false, err:String(e)}); }"
            "})"
        )
        raw = await tab.evaluate(js, img_url)
        info = raw if isinstance(raw, dict) else _safe_json(raw)
        if not info or not info.get("ok"):
            raise RuntimeError(info.get("err") if info else "浏览器取图无返回")
        data = base64.b64decode(info["b64"])
        return data, info.get("mime", "image/jpeg")

    async def _collect_img_urls(self, tab: Any) -> List[str]:
        """读取页面所有 <img> 的 src（含 srcset 中的大图），去重排序。"""
        js = (
            "() => {"
            "  const out = [];"
            "  document.querySelectorAll('img').forEach(img => {"
            "    if (img.src) out.push(img.src);"
            "    const ss = img.getAttribute('srcset');"
            "    if (ss) {"
            "      ss.split(',').forEach(p => {"
            "        const u = p.trim().split(' ')[0];"
            "        if (u) out.push(u);"
            "      });"
            "    }"
            "  });"
            "  return out;"
            "}"
        )
        try:
            raw = await tab.evaluate(js)
        except Exception:  # noqa: BLE001
            return []
        urls = raw if isinstance(raw, list) else []
        # 过滤出 pinimg 图片地址，优先 originals / 736x
        pin_urls = [u for u in urls if "pinimg.com" in u]
        seen, ordered = set(), []
        for u in sorted(pin_urls, key=self._url_priority):
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered

    @staticmethod
    def _url_priority(u: str) -> int:
        if "/originals/" in u:
            return 0
        if "/736x/" in u:
            return 1
        return 2

    # ------------------------------------------------------------------ #
    # 浏览器辅助
    # ------------------------------------------------------------------ #
    async def _ensure_browser(self) -> Any:
        """启动浏览器（固定 user_data_dir 持久化登录态），必要时提示登录。"""
        if self._launcher is not None:
            browser = await self._launcher.start()
        else:
            from ..config.models import BrowserConfig
            cfg = self._browser_config or BrowserConfig()
            launcher = BrowserLauncher(cfg, browser_factory=self._browser_factory)
            self._launcher = launcher
            browser = await launcher.start()
            # 加载已有登录态 cookie（配合固定 user_data_dir 实现“登录一次后续免登录”）
            loaded = await launcher.load_session()
            self._progress("browser",
                           f"浏览器已启动（登录态:{'已加载' if loaded else '未加载'}）")

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
                # 持久化：user_data_dir 自动保存本地状态，cookie 再额外导出一份
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

    async def _maybe_close_browser(self) -> None:
        # 由外部（pipeline）控制是否关闭；这里默认不主动关闭，
        # 因为一次 crawl 可能含多个站点/URL，复用浏览器更高效。
        pass

    # ------------------------------------------------------------------ #
    # 解析（纯函数，便于单测 / 备用）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_img_urls(html: str) -> List[str]:
        urls = _IMG_EXT_RE.findall(html)
        seen, ordered = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered


def _safe_json(raw):
    if isinstance(raw, str):
        try:
            import json
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None
    return raw
