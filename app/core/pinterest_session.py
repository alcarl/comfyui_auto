"""Pinterest 下载 / ComfyUI 生成的线程化会话管理。

在当前进程内用后台线程实现“后台运行”，无需启动独立进程：
- 下载：后台线程执行，浏览器常驻保持打开；下载当前页面复用同一浏览器。
- 生成：另一个后台线程执行，不阻塞下载。

关键：nodriver 浏览器必须在一个“常驻事件循环”中运行，不能每次操作都
asyncio.run 新建循环（否则浏览器后台协程会访问已关闭的循环而报错）。
因此本会话启动一个专用事件循环线程，所有浏览器操作通过
run_coroutine_threadsafe 调度到该循环执行。
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

_APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from app.core.config.manager import CoreConfigManager  # noqa: E402
from app.core.config.models import (  # noqa: E402
    SiteConfig, CrawlerType, CrawlerBackend,
)
from app.core.crawler import create_crawler  # noqa: E402
from app.core.image_library import ImageLibrary  # noqa: E402
from app.core.pinterest_flow import _ext_of  # noqa: E402

# 进度回调类型：progress(stage: str, message: str) -> None
ProgressCB = Callable[[str, str], None]


def _new_library(cfg: Any) -> ImageLibrary:
    return ImageLibrary.resolve(
        root_dir=cfg.library.root_dir,
        library_name=cfg.crawler.output_library,
        dedupe_by_url=cfg.library.dedupe_by_url,
        dedupe_by_hash=cfg.library.dedupe_by_hash,
    )


def _make_crawler(cfg: Any, library: ImageLibrary, progress: ProgressCB,
                  enqueue_callback: Optional[Any] = None) -> Any:
    """构造浏览器后端 crawler，支持保存回调、进度回调与待下载登记回调。"""
    if not cfg.crawler.browser.proxy:
        cfg.crawler.browser.proxy = "http://10.0.0.51:1072"
    if not cfg.crawler.browser.login_timeout or cfg.crawler.browser.login_timeout > 60:
        cfg.crawler.browser.login_timeout = 60

    site = SiteConfig(
        name="pinterest_session",
        crawler_type=CrawlerType.PINTEREST_BROWSER,
        backend=CrawlerBackend.BROWSER,
        urls=["https://jp.pinterest.com/"],
        extra={"locale": "jp"},
    )

    def _save_now(img) -> None:
        if library.is_duplicate(url=img.url):
            return
        library.add_image(
            img.data, source_url=img.url, site=img.site,
            ext=_ext_of(img.url, img.content_type))
        progress("saved", f"{img.url[:70]} -> 已保存（库中 {library.count()} 张）")

    return create_crawler(
        site,
        timeout=cfg.crawler.timeout,
        max_concurrency=cfg.crawler.max_concurrency,
        retry=cfg.crawler.retry,
        user_agent=cfg.crawler.user_agent,
        browser_config=cfg.crawler.browser,
        progress=progress,
        save_callback=_save_now,
        enqueue_callback=enqueue_callback,
    )


class _EventLoopThread(threading.Thread):
    """持有常驻事件循环的后台线程。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()

    def run(self) -> None:
        # Windows 下 nodriver 需要 ProactorEventLoop（asyncio.run 默认使用）。
        # 使用 asyncio.new_event_loop() 在 Windows 会创建 SelectorEventLoop，
        # 导致 Chrome DevTools 连接失败（"Failed to connect to browser"）。
        if sys.platform == "win32":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.close()
            except Exception:  # noqa: BLE001
                pass

    def run_coro(self, coro):
        """在常驻循环中执行协程并等待结果。"""
        if self.loop is None:
            raise RuntimeError("事件循环线程尚未就绪")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def stop(self) -> None:
        if self.loop is not None:
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception:  # noqa: BLE001
                pass


class PinterestSession:
    """线程安全的 Pinterest 浏览器会话单例。

    浏览器在常驻事件循环中保持打开，支持连续操作：
    - download_urls：下载一组页面。
    - download_current_page：下载当前浏览器标签页。
    - generate：调用 ComfyUI 生成。
    - close：关闭浏览器。
    """

    _instance: Optional["PinterestSession"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._crawler: Any = None
        self._library: Optional[ImageLibrary] = None
        self._lock = threading.RLock()  # 防止并发操作同一浏览器
        # 常驻事件循环线程（浏览器必须运行在持续循环中）
        self._loop_thread: Optional[_EventLoopThread] = None

    def _ensure_loop(self) -> _EventLoopThread:
        if self._loop_thread is None or not self._loop_thread.is_alive():
            t = _EventLoopThread()
            t.start()
            t._ready.wait(timeout=10)
            self._loop_thread = t
        return self._loop_thread

    def _ensure_crawler(self, progress: ProgressCB) -> Any:
        if self._crawler is not None:
            return self._crawler
        cfg = CoreConfigManager().config
        self._library = _new_library(cfg)

        def _enqueue(source_url, content_type="", site=""):
            return self._library.enqueue_download(source_url, content_type, site)

        loop = self._ensure_loop()
        self._crawler = _make_crawler(cfg, self._library, progress,
                                      enqueue_callback=_enqueue)
        # 在常驻循环中启动浏览器
        loop.run_coro(self._crawler._open_session_async())
        progress("info", "浏览器已打开并保持运行。")
        return self._crawler

    def download_urls(self, urls: list, progress: ProgressCB) -> int:
        with self._lock:
            crawler = self._ensure_crawler(progress)
            progress("info", f"开始下载 {len(urls)} 个页面…")
            for u in urls:
                progress("info", f"  - {u}")
            n = self._loop_thread.run_coro(crawler._download_urls_async(urls))
            progress("done", f"下载完成，共 {n} 张。浏览器保持打开。")
            return n

    def download_current_page(self, progress: ProgressCB) -> int:
        with self._lock:
            crawler = self._ensure_crawler(progress)
            progress("info", "开始下载当前页面图片…")
            n = self._loop_thread.run_coro(crawler._download_current_page_async())
            progress("done", f"当前页面下载完成，共 {n} 张。")
            return n

    # ------------------------------------------------------------------ #
    # 下载两步式：第一步采集入队，第二步后台轮询下载
    # ------------------------------------------------------------------ #
    def collect_and_enqueue(self, urls: list, progress: ProgressCB) -> int:
        """第一步：从 URL 列表采集图片地址，登记为待下载（不下载文件）。

        :return: 登记到待下载队列的条数
        """
        with self._lock:
            crawler = self._ensure_crawler(progress)
            progress("info", f"开始采集 {len(urls)} 个页面…")
            for u in urls:
                progress("info", f"  - {u}")
            n = self._loop_thread.run_coro(crawler._collect_urls_async(urls))
            pending = self._library.count_pending_downloads()
            progress("done", f"采集完成：登记 {n} 个待下载，当前待下载共 {pending} 条。")
            return n

    def collect_current_page(self, progress: ProgressCB) -> int:
        """第一步：采集浏览器当前页面的图片并登记为待下载。

        直接使用浏览器当前标签页，**不重新加载当前页面**、不跳转。
        仅当浏览器尚未打开时提示先打开（避免自动导航覆盖用户所在页）。
        """
        with self._lock:
            if self._crawler is None:
                progress("warn", "浏览器尚未打开，请先点击“打开浏览器”并手动选择页面。")
                return 0
            crawler = self._ensure_crawler(progress)
            progress("info", "开始采集当前页面图片（不重新加载，直接滚动下滑采集）…")
            n = self._loop_thread.run_coro(crawler._collect_current_page_async())
            pending = self._library.count_pending_downloads()
            progress("done", f"当前页面采集完成：登记 {n} 个待下载，"
                             f"当前待下载共 {pending} 条。")
            return n

    def open_pinterest(self, progress: ProgressCB,
                       url: str = "https://jp.pinterest.com") -> bool:
        """打开浏览器并跳转到 Pinterest（供用户手动选择页面），不采集。"""
        with self._lock:
            crawler = self._ensure_crawler(progress)
            progress("info", f"打开浏览器并跳转 {url}…（请在浏览器中手动选择页面）")
            try:
                self._loop_thread.run_coro(crawler._navigate(url))
            except Exception as e:  # noqa: BLE001
                progress("error", f"打开浏览器失败: {e}")
                return False
            progress("done", "浏览器已就绪，请在浏览器中手动选择想下载的页面，"
                             "然后点击“采集当前页面”。")
            return True

    def download_pending_loop(self, progress: ProgressCB,
                              stop_event: Optional[Any] = None,
                              poll_interval: float = 5.0) -> int:
        """第二步：持续轮询数据库待下载记录并自动下载。

        每 poll_interval 秒查询一次待下载表，逐条下载保存，直到 stop_event 被设置。

        :return: 成功下载的图片张数
        """
        import time as _time
        with self._lock:
            crawler = self._ensure_crawler(progress)
            library = self._library
            total_ok = 0
            if stop_event is None:
                progress("info", "开始下载待下载队列（一次性）…")
            else:
                progress("info", "开始持续轮询下载待下载队列（每 5 秒）…")
            while True:
                pending = library.list_pending_downloads()
                if pending:
                    progress("info", f"本轮获取 {len(pending)} 条待下载记录…")
                for rec in pending:
                    if stop_event is not None and stop_event.is_set():
                        progress("warn", "已收到停止指令，中止下载。")
                        break
                    ok, data, ctype = self._loop_thread.run_coro(
                        crawler._download_pending_async(rec.source_url))
                    if not ok or not data:
                        library.mark_download_failed(rec.image_id)
                        progress("error", f"下载失败: {rec.source_url[:70]}")
                        continue
                    # 下载成功：保存到图片库，标记待下载为完成
                    if library.is_duplicate(url=rec.source_url):
                        library.mark_download_done(rec.image_id)
                        continue
                    ext = _ext_of(rec.source_url, ctype)
                    library.add_image(data, source_url=rec.source_url,
                                      site=rec.site, image_id=rec.image_id,
                                      ext=ext)
                    library.mark_download_done(rec.image_id)
                    total_ok += 1
                    progress("saved", f"已下载 {rec.source_url[:70]} "
                                      f"（库中 {library.count()} 张）")
                if stop_event is None:
                    break
                if stop_event.is_set():
                    progress("warn", "下载已停止。")
                    break
                # 等待下一次轮询（期间可被停止）
                progress("info",
                         f"本轮完成，{int(poll_interval)} 秒后再次轮询…")
                waited = 0.0
                while waited < poll_interval:
                    if stop_event.is_set():
                        break
                    _time.sleep(0.5)
                    waited += 0.5
            progress("done", f"下载任务结束，共成功 {total_ok} 张。")
            return total_ok

    def generate(self, max_images: int, progress: ProgressCB,
                 stop_event: Optional[Any] = None,
                 poll_interval: float = 5.0) -> int:
        from app.core.pinterest_flow import generate_from_library
        cfg = CoreConfigManager().config
        library = _new_library(cfg)
        if stop_event is None:
            progress("info", "开始调用 ComfyUI 生成…")
        else:
            progress("info", "开始持续轮询生成（每 5 秒查询数据库）…")
        n = generate_from_library(cfg, library, max_images=max_images,
                                  progress=progress, stop_event=stop_event,
                                  poll_interval=poll_interval)
        progress("done", f"生成结束，共成功 {n} 张。")
        return n

    def scan_library(self, progress: ProgressCB) -> int:
        """扫描本地图片目录，把未登记的图片补充进数据库。

        供 UI 开关“打开时”调用：先扫描同步数据库，再据此判断状态。
        """
        with self._lock:
            if self._library is None:
                self._library = _new_library(CoreConfigManager().config)
            progress("info", "开始扫描本地图片目录，更新数据库…")
            added = self._library.scan_directory()
            progress("done",
                     f"扫描完成：新增 {added} 张，图片库当前共 "
                     f"{self._library.count()} 张（已生成 {self._library.count_generated()}）。")
            return added

    def close(self) -> None:
        with self._lock:
            if self._crawler is not None:
                try:
                    self._loop_thread.run_coro(self._crawler._close_browser())
                except Exception:  # noqa: BLE001
                    pass
                self._crawler = None
            if self._loop_thread is not None:
                try:
                    self._loop_thread.stop()
                    self._loop_thread.join(timeout=5)
                except Exception:  # noqa: BLE001
                    pass
                self._loop_thread = None


def get_session() -> PinterestSession:
    """获取全局单例会话。"""
    return PinterestSession()
