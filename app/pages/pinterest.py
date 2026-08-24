"""Pinterest 图片抓取 + ComfyUI 图生图页面。

在当前进程内用后台线程实现“后台运行”：
- “下载图片”：后台线程在常驻浏览器中下载 URL 列表图片，浏览器保持打开。
- “下载当前页面图片”：复用常驻浏览器，下载当前标签页图片。
- “生成图片”：另一个后台线程调用 ComfyUI 生成。

进度经回调写入日志区。
"""
from __future__ import annotations

import threading
from typing import Any, Optional

import flet as ft

from app.base import BasePage
from app.core.config.manager import CoreConfigManager
from app.core.pinterest_session import get_session


class PinterestPage(BasePage):
    def __init__(self, **kwargs):
        self._download_thread: Optional[threading.Thread] = None
        self._generate_thread: Optional[threading.Thread] = None
        self._dl_lock = threading.Lock()
        self._gen_lock = threading.Lock()

        # 控件（懒创建）
        self.url_input = None
        self.proxy_input = None
        self.scroll_input = None
        self.pause_input = None
        self.comfy_input = None
        self.workflow_input = None
        self.maxgen_input = None
        self.log_view = None
        self.download_btn = None
        self.current_btn = None
        self.generate_btn = None
        self.clear_btn = None
        self.stop_btn = None
        self.stop_gen_btn = None
        self._generate_stop_event = None

        super().__init__(title="Pinterest 抓取 / 生成", **kwargs)

    # ------------------------------------------------------------------ #
    # 控件懒创建
    # ------------------------------------------------------------------ #
    def _ensure_controls(self) -> None:
        if self.url_input is not None:
            return
        v = self._load_config_values()
        self.url_input = ft.TextField(
            label="页面 URL 列表（每行一个，或逗号分隔）",
            multiline=True, min_lines=2, max_lines=4,
            value="\n".join(v["urls"]),
            expand=True,
        )
        self.proxy_input = ft.TextField(
            label="代理地址", value=v["proxy"], width=320)
        self.scroll_input = ft.TextField(
            label="滚动次数", value=str(v["scroll_times"]),
            keyboard_type=ft.KeyboardType.NUMBER, width=140)
        self.pause_input = ft.TextField(
            label="滚动等待秒数", value=str(v["scroll_pause"]),
            keyboard_type=ft.KeyboardType.NUMBER, width=140)
        self.comfy_input = ft.TextField(
            label="ComfyUI 地址", value=v["comfy_base_url"], width=320)
        self.workflow_input = ft.TextField(
            label="工作流路径", value=v["workflow_path"], width=320)
        self.maxgen_input = ft.TextField(
            label="最多生成张数(0=全部)", value=str(v["max_images"]),
            keyboard_type=ft.KeyboardType.NUMBER, width=140)

        self.log_view = ft.ListView(
            expand=True, height=200, auto_scroll=True, spacing=1,
            padding=10, controls=[ft.Text("等待操作…", size=13)])

        self.download_btn = ft.FilledButton(
            "下载图片", icon=ft.Icons.DOWNLOAD, on_click=self.on_download)
        self.current_btn = ft.OutlinedButton(
            "下载当前页面图片", icon=ft.Icons.OPEN_IN_NEW,
            on_click=self.on_download_current)
        self.generate_btn = ft.FilledButton(
            "生成图片", icon=ft.Icons.AUTO_AWESOME, on_click=self.on_generate)
        self.clear_btn = ft.TextButton(
            "清空日志", on_click=lambda _: self._clear_log())
        self.stop_btn = ft.TextButton(
            "停止下载", icon=ft.Icons.STOP_CIRCLE, on_click=self.on_stop_download)
        self.stop_gen_btn = ft.TextButton(
            "停止生成", icon=ft.Icons.STOP, on_click=self.on_stop_generate)
        # 开关：打开=扫描本地图片更新数据库；关闭=直接从数据库判断状态
        self.scan_switch = ft.Switch(
            label="扫描本地图片更新数据库", value=False,
            on_change=lambda e: self._log(
                f"[info] 状态来源：{'扫描本地' if e.control.value else '仅数据库'}"))

    # ------------------------------------------------------------------ #
    # 布局
    # ------------------------------------------------------------------ #
    def build_content(self) -> ft.Column:
        self._ensure_controls()
        self._init_log()
        config_section = self.build_section(
            title="抓取配置",
            content=ft.Column([
                self.url_input,
                ft.Row([self.proxy_input, self.scroll_input, self.pause_input]),
            ], spacing=12),
        )
        comfy_section = self.build_section(
            title="ComfyUI 生成配置",
            content=ft.Column([
                ft.Row([self.comfy_input, self.workflow_input]),
                ft.Row([self.maxgen_input]),
            ], spacing=12),
        )
        action_row = ft.Row([self.download_btn, self.current_btn,
                             self.generate_btn, self.stop_gen_btn,
                             self.stop_btn, self.clear_btn],
                            spacing=10, wrap=True)
        switch_row = ft.Row([self.scan_switch], spacing=10)
        log_section = ft.Container(
            content=ft.Column([
                ft.Text("运行日志", size=16, weight="bold"),
                self.log_view,
            ], spacing=8),
            padding=12,
            border_radius=ft.border_radius.all(10),
            bgcolor=self.theme_colors.card_color,
            expand=True,
        )
        return ft.Column([
            config_section,
            comfy_section,
            action_row,
            switch_row,
            log_section,
        ], scroll="auto", spacing=10)

    # ------------------------------------------------------------------ #
    # 日志
    # ------------------------------------------------------------------ #
    # 跨线程 UI 更新：flet 的 control.update() 线程安全，可从后台线程调用。
    # 为避免高频日志时频繁 update 导致主线程过载，这里做简单的节流
    # （合并相近时间内的多次更新），并去掉耗时的 scroll_to 动画。
    def _init_log(self) -> None:
        import time as _time
        self._log_buf: list = []
        self._log_last = 0.0
        self._log_interval = 0.15  # 最小刷新间隔（秒）

    def _log(self, line: str) -> None:
        import time as _time
        if self.log_view is None:
            return
        self.log_view.controls.append(ft.Text(line, size=13))
        if len(self.log_view.controls) > 800:
            self.log_view.controls = self.log_view.controls[-500:]
        now = _time.time()
        # 节流：距上次刷新不足间隔时，先缓存，待主线程定时刷或下次触发补刷
        if now - self._log_last >= self._log_interval:
            self._log_last = now
            self._flush_log_view()
        # 若本次未刷新（节流），交给后续触发或生成结束前统一刷新

    def _flush_log_view(self) -> None:
        """直接刷新日志控件（线程安全）。"""
        if self.log_view is None:
            return
        try:
            self.log_view.auto_scroll = True
            self.log_view.update()
        except Exception:  # noqa: BLE001
            pass

    def _clear_log(self) -> None:
        if self.log_view is not None:
            self.log_view.controls = []
        self._log("日志已清空。")

    def _progress_cb(self):
        return lambda stage, msg="": self._log(f"[{stage}] {msg}")

    # ------------------------------------------------------------------ #
    # 事件
    # ------------------------------------------------------------------ #
    def on_download(self, e) -> None:
        if self._download_thread and self._download_thread.is_alive():
            self._log("[warn] 下载任务运行中，请稍候…")
            return
        urls = self._parse_urls()
        if not urls:
            self._log("[error] 请填写至少一个页面 URL")
            return
        self._apply_config()
        self._log(f"[info] 开始下载 {len(urls)} 个页面…")
        self._download_thread = threading.Thread(
            target=self._run_download, args=(urls,), daemon=True)
        self._download_thread.start()

    def on_download_current(self, e) -> None:
        if self._download_thread and self._download_thread.is_alive():
            self._log("[warn] 下载任务运行中，请稍候…")
            return
        self._apply_config()
        self._log("[info] 正在下载当前页面图片（请在浏览器中选择目标页面）…")
        self._download_thread = threading.Thread(
            target=self._run_download_current, daemon=True)
        self._download_thread.start()

    def on_generate(self, e) -> None:
        if self._generate_thread and self._generate_thread.is_alive():
            self._log("[warn] 生成任务运行中，请稍候…")
            return
        self._apply_config()
        max_n = 0
        try:
            max_n = int(self.maxgen_input.value or "0")
        except ValueError:
            pass
        # 创建停止事件，用于轮询过程中停止
        self._generate_stop_event = threading.Event()
        self._log("[info] 启动持续轮询生成任务（每 5 秒查询数据库）…")
        self._generate_thread = threading.Thread(
            target=self._run_generate, args=(max_n,), daemon=True)
        self._generate_thread.start()

    def on_stop_generate(self, e) -> None:
        if self._generate_stop_event is not None:
            self._generate_stop_event.set()
            self._log("[warn] 已发送停止生成指令，将在本轮完成后停止轮询。")
        else:
            self._log("[warn] 当前没有运行中的生成任务。")

    def on_stop_download(self, e) -> None:
        self._log("[warn] 停止下载仅会在当前下载任务结束后关闭浏览器。")
        session = get_session()
        threading.Thread(target=session.close, daemon=True).start()

    # ------------------------------------------------------------------ #
    # 后台执行
    # ------------------------------------------------------------------ #
    def _scan_if_enabled(self, session) -> None:
        """若开关打开，则先扫描本地图片目录，更新数据库状态。"""
        try:
            if self.scan_switch.value:
                self._log("[info] 开关已打开，扫描本地图片更新数据库…")
                session.scan_library(self._progress_cb())
        except Exception as ex:  # noqa: BLE001
            self._log(f"[error] 扫描本地图片失败: {ex}")

    def _run_download(self, urls: list) -> None:
        session = get_session()
        try:
            self._scan_if_enabled(session)
            session.download_urls(urls, self._progress_cb())
        except Exception as ex:  # noqa: BLE001
            self._log(f"[error] 下载失败: {ex}")
        finally:
            self._flush_log_view()

    def _run_download_current(self) -> None:
        session = get_session()
        try:
            self._scan_if_enabled(session)
            session.download_current_page(self._progress_cb())
        except Exception as ex:  # noqa: BLE001
            self._log(f"[error] 下载当前页面失败: {ex}")
        finally:
            self._flush_log_view()

    def _run_generate(self, max_n: int) -> None:
        session = get_session()
        try:
            self._scan_if_enabled(session)
            session.generate(max_n, self._progress_cb(),
                             stop_event=self._generate_stop_event,
                             poll_interval=5.0)
        except Exception as ex:  # noqa: BLE001
            self._log(f"[error] 生成失败: {ex}")
        finally:
            self._flush_log_view()
            self._generate_stop_event = None

    # ------------------------------------------------------------------ #
    # 配置
    # ------------------------------------------------------------------ #
    def _pin_site(self, cfg):
        """返回第一个启用的 Pinterest 相关站点。"""
        from app.core.config.models import CrawlerType
        for s in cfg.sites:
            if s.enabled and s.crawler_type.value in (
                    CrawlerType.PINTEREST_BROWSER.value,
                    CrawlerType.PINTEREST.value):
                return s
        return None

    def _load_config_values(self) -> dict:
        """从配置文件读取各项默认值。"""
        cfg = CoreConfigManager().config
        site = self._pin_site(cfg)
        urls = list(site.urls) if site and site.urls else [
            "https://jp.pinterest.com/pin/1028087421172953769/"]
        return {
            "urls": urls,
            "proxy": cfg.crawler.browser.proxy or "http://10.0.0.51:1072",
            "scroll_times": cfg.crawler.browser.scroll_times,
            "scroll_pause": cfg.crawler.browser.scroll_pause,
            "comfy_base_url": cfg.comfyui.base_url,
            "workflow_path": cfg.comfyui.workflow_path,
            "max_images": 0,
        }

    def _parse_urls(self) -> list:
        urls = []
        raw = self.url_input.value or ""
        for part in raw.replace("，", ",").replace("\n", ",").split(","):
            p = part.strip()
            if p:
                urls.append(p)
        return urls

    def _apply_config(self) -> None:
        """把界面输入写回配置文件。"""
        mgr = CoreConfigManager()
        cfg = mgr.config

        # URL 列表写回第一个 Pinterest 站点
        urls = self._parse_urls()
        site = self._pin_site(cfg)
        if site is not None:
            site.urls = urls
        elif urls:
            from app.core.config.models import SiteConfig, CrawlerType, CrawlerBackend
            cfg.sites.append(SiteConfig(
                name="pinterest_ui",
                crawler_type=CrawlerType.PINTEREST_BROWSER,
                backend=CrawlerBackend.BROWSER,
                urls=urls, extra={"locale": "jp"}))

        if self.proxy_input.value:
            cfg.crawler.browser.proxy = self.proxy_input.value.strip()
        try:
            cfg.crawler.browser.scroll_times = int(self.scroll_input.value or "10")
        except ValueError:
            pass
        try:
            cfg.crawler.browser.scroll_pause = float(self.pause_input.value or "5")
        except ValueError:
            pass
        if self.comfy_input.value:
            cfg.comfyui.base_url = self.comfy_input.value.strip()
        if self.workflow_input.value:
            cfg.comfyui.workflow_path = self.workflow_input.value.strip()
        mgr.save()
