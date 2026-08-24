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
from typing import Any, List, Optional, Set

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
                 browser_config: Optional[Any] = None,
                 save_callback: Optional[Any] = None):
        super().__init__(site, timeout=timeout, max_concurrency=max_concurrency,
                         retry=retry, user_agent=user_agent, http_get=http_get)
        self._browser_factory = browser_factory
        self._launcher = launcher
        self._progress = progress or (lambda *a, **k: None)
        self._browser_config = browser_config
        # 每下载一张图片即调用一次，用于“下载一张保存一张”，避免全部下载完才保存。
        # 签名：save_callback(FetchedImage) -> Any
        self._save_callback = save_callback
        # 常驻会话持有的浏览器实例（由 open_session 设置，保持打开）
        self._browser: Optional[Any] = None

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
    # 常驻会话接口（浏览器保持打开，供 UI “下载当前页面”等使用）
    # ------------------------------------------------------------------ #
    def open_session(self) -> None:
        """启动浏览器并保持打开（供后续连续操作，不自动关闭）。"""
        asyncio.run(self._open_session_async())

    async def _open_session_async(self) -> None:
        self._browser = await self._ensure_browser()

    def download_urls(self, urls: List[str]) -> int:
        """对指定 URL 列表逐页滚动抓取并保存，浏览器保持打开。

        :return: 成功下载的图片张数
        """
        return asyncio.run(self._download_urls_async(urls))

    async def _download_urls_async(self, urls: List[str]) -> int:
        if self._browser is None:
            await self._open_session_async()
        browser = self._browser
        results: List[FetchedImage] = []
        seen_urls: Set[str] = set()
        for page_url in urls:
            try:
                n = await self._download_page(browser, page_url, seen_urls, results)
            except Exception as e:  # noqa: BLE001
                self._progress("error", f"下载页面失败 {page_url}: {e}")
        self._progress("done", f"下载完成，共 {len(results)} 张图片。")
        return len(results)

    def download_current_page(self) -> int:
        """下载浏览器当前标签页的图片，浏览器保持打开。

        :return: 成功下载的图片张数
        """
        return asyncio.run(self._download_current_page_async())

    async def _download_current_page_async(self) -> int:
        if self._browser is None:
            await self._open_session_async()
        browser = self._browser
        # 读取当前活动标签页
        tab = getattr(browser, "main_tab", None) or (browser.tabs[0] if browser.tabs else None)
        if tab is None:
            self._progress("error", "找不到当前浏览器标签页")
            return 0
        try:
            await tab
        except Exception:  # noqa: BLE001
            pass
        page_url = getattr(tab, "url", "") or "当前页面"
        results: List[FetchedImage] = []
        seen_urls: Set[str] = set()
        await self._download_page(browser, page_url, seen_urls, results, tab=tab)
        self._progress("done", f"当前页面下载完成，共 {len(results)} 张图片。")
        return len(results)

    def close_browser(self) -> None:
        """关闭浏览器，结束会话。"""
        asyncio.run(self._close_browser())
        self._browser = None

    async def _download_page(self, browser: Any, page_url: str,
                             seen_urls: Set[str],
                             results: List[FetchedImage],
                             tab: Optional[Any] = None) -> int:
        """对单个页面：滚动加载 -> 采集图片 URL -> 逐张下载保存。返回下载数。"""
        scroll_times = (self._browser_config.scroll_times
                        if self._browser_config else 5)
        scroll_pause = (self._browser_config.scroll_pause
                        if self._browser_config else 5.0)
        page_load_wait = (self._browser_config.page_load_wait
                          if self._browser_config else 3.0)
        try:
            if tab is None:
                tab = await browser.get(page_url)
                await asyncio.sleep(page_load_wait)
        except Exception as e:  # noqa: BLE001
            self._progress("error", f"加载页面失败 {page_url}: {e}")
            return 0

        # 先采集已加载的图片链接
        collected = await self._collect_img_urls(tab)
        self._progress("page", f"页面 {page_url} 初始发现 {len(collected)} 个图片地址")
        for i in range(1, scroll_times + 1):
            try:
                await tab.evaluate("window.scrollBy(0, 1500)")
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(scroll_pause)
            new_urls = await self._collect_img_urls(tab)
            before = len(collected)
            seen_round: Set[str] = set(collected)
            for u in new_urls:
                if u not in seen_round:
                    seen_round.add(u)
                    collected.append(u)
            self._progress("page",
                           f"滚动 {i}/{scroll_times} 后累计 {len(collected)} 个图片地址"
                           f"（本轮新增 {len(collected) - before}）")
            if len(collected) == before:
                self._progress("page", "本轮滚动未发现新图，提前停止。")
                break

        self._progress("page", f"页面 {page_url} 共发现 {len(collected)} 个图片地址")
        count = 0
        for img_url in collected:
            if img_url in seen_urls:
                continue
            seen_urls.add(img_url)
            try:
                data, ctype = await self._fetch_via_browser(tab, img_url)
            except Exception as e:  # noqa: BLE001
                self._progress("error", f"浏览器取图失败 {img_url}: {e}")
                continue
            if not data:
                continue
            fetched = FetchedImage(
                url=img_url, data=data, content_type=ctype,
                source_page=page_url, site=self.site.name)
            if self._save_callback is not None:
                try:
                    self._save_callback(fetched)
                except Exception as e:  # noqa: BLE001
                    self._progress("error", f"保存图片失败 {img_url}: {e}")
            results.append(fetched)
            count += 1
        return count

    # ------------------------------------------------------------------ #
    # 异步实现
    # ------------------------------------------------------------------ #
    async def _discover_image_urls_async(self, page_url: str) -> List[str]:
        browser = await self._ensure_browser()
        tab = await browser.get(page_url)
        await self._scroll_to_load(tab)
        urls = await self._collect_img_urls(tab)
        await self._close_browser()
        return urls

    async def _fetch_images_async(self) -> List[FetchedImage]:
        browser = await self._ensure_browser()
        results: List[FetchedImage] = []
        seen_urls: Set[str] = set()
        scroll_times = (self._browser_config.scroll_times
                        if self._browser_config else 5)
        scroll_pause = (self._browser_config.scroll_pause
                        if self._browser_config else 5.0)
        page_load_wait = (self._browser_config.page_load_wait
                          if self._browser_config else 3.0)
        for page_url in self.site.urls:
            try:
                tab = await browser.get(page_url)
                # 等待页面初始加载完成，否则 DOM 中还没有图片，采集不到任何地址
                await asyncio.sleep(page_load_wait)
            except Exception as e:  # noqa: BLE001
                self._progress("error", f"加载页面失败 {page_url}: {e}")
                continue

            # 先获取一次页面已加载的图片链接
            collected = await self._collect_img_urls(tab)
            self._progress("page", f"页面 {page_url} 初始发现 {len(collected)} 个图片地址")

            # 循环：向下滚屏 -> 等待页面自动加载 -> 再次采集并去重合并
            # 注意：必须用 scrollBy 增量滚动（每次向下滚一段距离），才能让可视
            # 内容真正移动并触发懒加载；scrollTo(0, scrollHeight) 一次性跳到底部
            # 时可视内容不随滚动更新，图片不会加载。
            for i in range(1, scroll_times + 1):
                try:
                    await tab.evaluate("window.scrollBy(0, 1500)")
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(scroll_pause)
                new_urls = await self._collect_img_urls(tab)
                before = len(collected)
                seen_round: Set[str] = set(collected)
                for u in new_urls:
                    if u not in seen_round:
                        seen_round.add(u)
                        collected.append(u)
                self._progress("page",
                               f"滚动 {i}/{scroll_times} 后累计 {len(collected)} 个图片地址"
                               f"（本轮新增 {len(collected) - before}）")
                # 本轮无新图可提前停止，避免无意义等待
                if len(collected) == before:
                    self._progress("page", "本轮滚动未发现新图，提前停止。")
                    break

            self._progress("page", f"页面 {page_url} 共发现 {len(collected)} 个图片地址")
            for img_url in collected:
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
                fetched = FetchedImage(
                    url=img_url, data=data, content_type=ctype,
                    source_page=page_url, site=self.site.name)
                # 下载一张、立即保存一张（通过回调实时入库），避免全部下载完才保存。
                if self._save_callback is not None:
                    try:
                        self._save_callback(fetched)
                    except Exception as e:  # noqa: BLE001
                        self._progress("error", f"保存图片失败 {img_url}: {e}")
                results.append(fetched)
        self._progress("done", f"浏览器抓取完成，共 {len(results)} 张图片")
        await self._close_browser()
        return results

    # ------------------------------------------------------------------ #
    # 浏览器取图（核心：不经由 crawler 的 http）
    # ------------------------------------------------------------------ #
    async def _fetch_via_browser(self, tab: Any, img_url: str) -> tuple[bytes, str]:
        """在页面 JS 上下文用 fetch 获取图片字节（走浏览器代理），返回 (bytes, mime)。

        nodriver 的 ``tab.evaluate`` 只执行“直接表达式/立即执行（IIFE）”并返回结果；
        传 ``() => {...}`` 函数定义会被当作函数对象而不执行。因此这里用 async IIFE，
        并传 ``await_promise=True`` 等待其返回；返回值可能是 DeepSerializedValue 包装，
        需用 ``_unwrap`` 还原为纯 Python 值。
        """
        # 注意：img_url 需安全嵌入 JS（JSON 序列化即可保证转义）。
        import json as _json
        u = _json.dumps(img_url)
        js = (
            f"(async () => {{"
            f"  const u = {u};"
            f"  try {{"
            f"    const r = await fetch(u, {{mode:'cors', credentials:'omit'}});"
            f"    const t = r.headers.get('content-type') || 'image/jpeg';"
            f"    const b = await r.arrayBuffer();"
            f"    let s = ''; const v = new Uint8Array(b);"
            f"    const CH = 0x8000;"
            f"    for (let i=0; i<v.length; i+=CH) {{"
            f"      s += String.fromCharCode.apply(null, v.subarray(i, i+CH));"
            f"    }}"
            f"    return JSON.stringify({{ok:true, mime:t, b64:btoa(s)}});"
            f"  }} catch(e) {{ return JSON.stringify({{ok:false, err:String(e)}}); }}"
            f"}})()"
        )
        raw = await tab.evaluate(js, await_promise=True)
        info = self._unwrap(raw)
        if isinstance(info, str):
            info = _safe_json(info)
        if not isinstance(info, dict) or not info.get("ok"):
            err = info.get("err") if isinstance(info, dict) else "浏览器取图无返回"
            raise RuntimeError(err)
        data = base64.b64decode(info["b64"])
        return data, info.get("mime", "image/jpeg")

    @staticmethod
    def _unwrap(value: Any) -> Any:
        """把 nodriver evaluate 返回的 DeepSerializedValue 结构还原为纯 Python 值。

        nodriver 的 ``deep_serialized_value`` 会用 ``{'type': 'string', 'value': ...}``
        等包装每一项。本函数递归解包为纯字符串/列表/字典，便于后续处理。
        """
        if isinstance(value, dict):
            # 无 'type' 字段 -> 普通 Python 字典（如测试桩的 {ok:...}），原样返回
            if "type" not in value:
                return value
            # {'type': 'string'|'number'|'boolean'|'bigint', 'value': v}
            t = value.get("type")
            if t in ("string", "number", "boolean", "bigint", "undefined", "null"):
                return value.get("value")
            if t == "array":
                v = value.get("value")
                return [PinterestBrowserCrawler._unwrap(i) for i in v] if isinstance(v, list) else v
            if t in ("object", "map", "set"):
                v = value.get("value")
                if isinstance(v, list):
                    return [PinterestBrowserCrawler._unwrap(i) for i in v]
                return v
            if t == "function":
                return None
            # 未知结构：尝试直接取 value
            return value.get("value")
        if isinstance(value, list):
            return [PinterestBrowserCrawler._unwrap(i) for i in value]
        return value

    async def _collect_img_urls(self, tab: Any) -> List[str]:
        """提取图片墙中 originals 级别的主图 URL。

        判定标准：
        - 只收集 ``alt`` 精确等于 ``"其中包括图片："`` 的 <img>（图片墙主图）。
        - 排除 alt 带具体描述文字的分类/选项缩略图（例如
          ``alt="其中包括图片：Round Bag Sewing Pattern ..."``）。
        - 仅保留含 ``/originals/`` 的图片地址，没有 originals 的跳过。

        注意：不使用 background-image / 全页 HTML 正则兜底，因为这些无法按
        alt 属性判断是否为主图，容易混入分类选项等非图片墙图片。
        """
        js = (
            "(() => {"
            "  const isOriginal = u => u && u.indexOf('/originals/') !== -1;"
            "  const isMainPin = img => {"
            "    const a = (img.getAttribute('alt') || '').trim();"
            "    return (a === '其中包括图片：' || a ==='This contains an image of:');"
            "  };"
            "  const out = [];"
            "  const push = u => { if (isOriginal(u) && !out.includes(u)) out.push(u); };"
            "  document.querySelectorAll('img').forEach(img => {"
            "    if (!isMainPin(img)) return;"
            "    const cands = [];"
            "    const addCand = u => { if (u && isOriginal(u)) cands.push(u); };"
            "    if (img.currentSrc) addCand(img.currentSrc);"
            "    if (img.src) addCand(img.src);"
            "    const ss = img.getAttribute('srcset');"
            "    if (ss) ss.split(',').forEach(p => { const u = p.trim().split(' ')[0]; if (u) addCand(u); });"
            "    ['data-src','data-imgurl','data-image','data-pin-url'].forEach(a => {"
            "      const v = img.getAttribute(a); if (v) addCand(v);"
            "    });"
            "    cands.forEach(u => push(u));"
            "  });"
            "  return out;"
            "})()"
        )
        try:
            raw = await tab.evaluate(js)
        except Exception:  # noqa: BLE001
            return []
        urls = self._unwrap(raw)
        if not isinstance(urls, list):
            return []
        # 严格只保留含 /originals/ 的 pinimg 图片地址，按 URL 去重
        seen: Set[str] = set()
        ordered: List[str] = []
        for u in urls:
            if isinstance(u, str) and "/originals/" in u and "pinimg.com" in u:
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
            loaded = await launcher.load_session()
            self._progress("browser",
                           f"浏览器已启动（登录态:{'已加载' if loaded else '未加载'}）")

        # 快速探测：访问 Pinterest 首页，检测右上角“账户按钮”是否存在
        # （已登录用户显示 header-accounts-options-button，未登录则没有），
        # 若已登录则直接跳过 60 秒的登录等待，节省时间且避免误判。
        if await self._is_logged_in_via_homepage(browser):
            self._progress("login", "已检测到登录态（首页右上角账户按钮存在），跳过登录。")
            return browser

        # 未登录：进入显式登录流程，等待用户手动输入（默认 60 秒）
        from .auth import pinterest_login
        login_timeout = (self._browser_config.login_timeout
                         if self._browser_config else 60)
        ok = await pinterest_login(
            browser,
            timeout=login_timeout,
            progress=lambda m: self._progress("login", m),
        )
        if ok and self._launcher is not None:
            await self._launcher.save_session()
        return browser

    async def _is_logged_in_via_homepage(self, browser: Any) -> bool:
        """打开 Pinterest 首页，检测“已登录”标志。

        已登录用户的 Pinterest 页面右上角会出现“账户选项”按钮：
        ``button[data-test-id="header-accounts-options-button"]``。
        未登录用户没有这个按钮，只有登录按钮。
        """
        js = (
            "(() => {"
            "  const sels = ["
            "    'button[data-test-id=\"header-accounts-options-button\"]',"
            "    'a[href^=\"/\"]:has(div[aria-hidden=\"true\"])'.replace(':has','') /* fallback noop */,"
            "    '[data-test-id=\"header-avatar\"]'"
            "  ];"
            "  if (document.querySelector('button[data-test-id=\"header-accounts-options-button\"]')) return true;"
            "  if (document.querySelector('[data-test-id=\"header-avatar\"]')) return true;"
            "  return false;"
            "})()"
        )
        try:
            tab = await browser.get("https://jp.pinterest.com/")
            await asyncio.sleep(5)
            raw = await tab.evaluate(js)
            v = self._unwrap(raw)
            return bool(v)
        except Exception:  # noqa: BLE001
            return False
            await self._launcher.save_session()
        return browser

    async def _scroll_to_load(self, tab: Any) -> None:
        times = self._browser_config.scroll_times if self._browser_config else 5
        pause = self._browser_config.scroll_pause if self._browser_config else 1.5
        for _ in range(times):
            try:
                await tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(pause)

    async def _close_browser(self) -> None:
        """在事件循环结束时关闭浏览器，避免 Windows 下 asyncio 子进程残留
        导致 “Exception ignored ... I/O operation on closed pipe” 告警。"""
        if self._launcher is not None:
            await self._launcher.close()
        self._launcher = None

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
