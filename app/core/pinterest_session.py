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


def _make_crawler(cfg: Any, library: ImageLibrary, progress: ProgressCB) -> Any:
    """构造浏览器后端 crawler，支持保存回调与进度回调。"""
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
        loop = self._ensure_loop()
        self._crawler = _make_crawler(cfg, self._library, progress)
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
