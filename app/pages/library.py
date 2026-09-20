"""图片库管理页面。

布局：左侧图片列表（文件名 / 下载时间 / 生成时间 / 是否已反推），
右侧预览原图与生成图并展示反推提示词。

功能：
- 点击列表行 → 右侧显示原图 + 生成图 + 该图的提示词。
- “WD14 反推提示词”：对选中（或全部已生成）的图片本地 ONNX 推理
  booru 标签，按“每个提示词一行”写入 tags 表。
- 筛选框：按提示词关键词筛选列表并自动勾选匹配图片。
- “删除选中”：删除选中图片的原图 / 生成图 / 数据库记录，
  并级联清理 tags 表条目。
"""
from __future__ import annotations

import base64
import os
import threading
from typing import Any, Optional

import flet as ft

from app.base import BasePage
from app.core.config.manager import CoreConfigManager
from app.core.image_library import ImageLibrary
from app.core.tagger import Wd14Tagger

# 反推详细度预设：键是 UI 显示，值是 (general_threshold, character_threshold)
# SmilingWolf 官方默认 general=0.35/character=0.85（精简），其它三档
# 主动拉低 character 阈值，让 long_hair/blue_eyes/blush 等人体特征
# 能进到默认 0.35 以下置信度的也能浮出来。
# "极详细"档 character 阈值压到 0.05，几乎所有模型给出的预测都会保留
# ——但要注意：模型本身没有预测的特征（标签压根不存在）阈值再低也浮不出来。
_TAG_PRESETS = {
    "精简": (0.45, 0.85),
    "标准": (0.35, 0.55),
    "详细": (0.35, 0.35),
    "极详细": (0.20, 0.05),
}

# 1x1 透明 PNG，用作图片控件占位
_BLANK_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
    "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _fmt_time(s: str) -> str:
    """ISO 时间字符串 → 'YYYY-MM-DD HH:MM:SS'（非法/空返回 '-'）。"""
    s = (s or "").strip()
    if not s:
        return "-"
    return s[:19].replace("T", " ")


class LibraryPage(BasePage):
    def __init__(self, **kwargs):
        # 控件（懒创建，主题切换后可恢复状态）
        self.filter_input: Optional[ft.TextField] = None
        self.image_list: Optional[ft.ListView] = None
        self.tagger_btn: Optional[ft.FilledButton] = None
        self.delete_btn: Optional[ft.OutlinedButton] = None
        self.refresh_btn: Optional[ft.TextButton] = None
        self.orig_image: Optional[ft.Image] = None
        self.gen_image: Optional[ft.Image] = None
        self.tags_text: Optional[ft.Text] = None
        # 当前预览这张图的 (conf, name) 元组；None 表示没有置信度
        # （DB 里的老标签没有置信度）。用于在"显示置信度"开关下展示。
        self._current_scored: Optional[list] = None
        # 是否在 tags_text 中附带置信度显示
        self._show_conf: bool = False
        self.status_text: Optional[ft.Text] = None
        self.log_view: Optional[ft.ListView] = None
        self.clear_log_btn: Optional[ft.TextButton] = None
        self.level_dropdown: Optional[ft.Dropdown] = None
        self.detail_dropdown: Optional[ft.Dropdown] = None
        self._tag_preset: str = "详细"  # 默认详细，能拿到人体特征标签
        # 状态
        self._rows: list = []            # 列表数据（见 _refresh_rows）
        self._selected: set = set()      # 选中的 image_id 集合
        self._current_id: str = ""       # 当前预览的 image_id
        self._filter_ids: Optional[set] = None  # 筛选结果（None=未筛选）
        self._task_thread: Optional[threading.Thread] = None
        self._library: Optional[ImageLibrary] = None
        self._tagger: Optional[Wd14Tagger] = None
        super().__init__(title="图片库", **kwargs)

    # ------------------------------------------------------------------ #
    # 控件懒创建 / 布局
    # ------------------------------------------------------------------ #
    def _ensure_controls(self) -> None:
        if self.filter_input is not None:
            return
        self.filter_input = ft.TextField(
            label="按提示词筛选（包含匹配）", hint_text="如 1girl",
            expand=True, dense=True, on_submit=lambda _: self.on_filter())
        # 注意：ListView 必须给固定高度。build_section 内部的 Column/Container
        # 不会沿链传递 expand，无固定高度的 ListView 高度会塌陷为 0，
        # 导致列表有数据但显示为空白。
        self.image_list = ft.ListView(
            height=380, spacing=2, padding=4)
        self.tagger_btn = ft.FilledButton(
            "WD14反推提示词", icon=ft.Icons.LABEL,
            on_click=lambda _: self.on_tagger())
        self.tag_untagged_btn = ft.FilledButton(
            "反推未反推图片", icon=ft.Icons.LABEL_OFF,
            tooltip="只反推还没有提示词的已生成图片（跳过已有标签的）",
            on_click=lambda _: self.on_tag_untagged())
        self.delete_btn = ft.OutlinedButton(
            "删除选中", icon=ft.Icons.DELETE_OUTLINE,
            on_click=lambda _: self.on_delete())
        self.reset_gen_btn = ft.OutlinedButton(
            "删除生成结果", icon=ft.Icons.MOVIE_EDIT,
            tooltip="只删除选中图片的生成图文件、生成状态与反推提示词，"
                    "原图保留，记录回到\"未生成\"，可被生成任务重新扫描生成",
            on_click=lambda _: self.on_reset_generation())
        self.select_all_btn = ft.TextButton(
            "全选", icon=ft.Icons.SELECT_ALL,
            tooltip="全选/取消全选当前列表中的图片（受筛选影响，只作用于可见项）",
            on_click=lambda _: self.on_select_all())
        self.refresh_btn = ft.TextButton(
            "刷新列表", icon=ft.Icons.REFRESH,
            on_click=lambda _: self.on_refresh())
        self.reset_output_btn = ft.TextButton(
            "重置生成图绑定", icon=ft.Icons.LINK_OFF,
            tooltip="清空 DB 里记录的 output_files，使查找回退到文件名匹配。"
                    "适用于 DB 中文件名错位的排查与恢复",
            on_click=lambda _: self.on_reset_output_bindings())
        self.orig_image = ft.Image(
            src_base64=_BLANK_PNG, fit=ft.ImageFit.CONTAIN, height=300)
        self.gen_image = ft.Image(
            src_base64=_BLANK_PNG, fit=ft.ImageFit.CONTAIN, height=300)
        self.tags_text = ft.Text(
            "点击左侧列表中的图片查看提示词", size=13, selectable=True)
        self.status_text = ft.Text("就绪", size=12,
                                   color=ft.Colors.with_opacity(
                                       0.7, ft.Colors.ON_SURFACE))
        self.log_view = ft.ListView(
            height=130, auto_scroll=True, spacing=1, padding=10,
            controls=[ft.Text("等待操作…", size=13)])
        self.clear_log_btn = ft.TextButton(
            "清空日志", icon=ft.Icons.DELETE_SWEEP,
            on_click=lambda _: self._clear_log())
        self.level_dropdown = ft.Dropdown(
            label="日志级别", width=160, value="info",
            options=[ft.dropdown.Option("debug", "调试 debug"),
                     ft.dropdown.Option("info", "常规 info"),
                     ft.dropdown.Option("warn", "警告 warn"),
                     ft.dropdown.Option("error", "错误 error")],
            on_change=lambda e: self._set_log_level(e.control.value))
        self.detail_dropdown = ft.Dropdown(
            label="反推详细度", width=160, value=self._tag_preset,
            options=[ft.dropdown.Option(k, f"{k}（general {_TAG_PRESETS[k][0]} / "
                                            f"character {_TAG_PRESETS[k][1]}）")
                     for k in _TAG_PRESETS],
            tooltip="调整 general / character 标签置信度阈值。"
                    "character 阈值越低，越能拿到 long_hair/blue_eyes/blush 等"
                    "人体特征细节。切换后会话内立即生效",
            on_change=lambda e: self._set_tag_preset(e.control.value))
        self.show_conf_switch = ft.Switch(
            label="显示置信度", value=False,
            tooltip="开启后，右侧提示词会附带每个标签的模型置信度。"
                    "用它来判断\"极详细档还没出人体特征\"是阈值问题还是"
                    "模型本身就没预测到（置信度低 ≈ 模型觉得该特征不存在）",
            on_change=lambda e: self._set_show_conf(e.control.value))
        self._init_log()

    def build_content(self) -> ft.Column:
        self._ensure_controls()

        # 左侧：筛选 + 列表 + 操作按钮
        left = self.build_section(
            title="图片列表",
            content=ft.Column([
                ft.Row([self.filter_input,
                        ft.IconButton(icon=ft.Icons.FILTER_ALT,
                                      tooltip="筛选并选中匹配图片",
                                      on_click=lambda _: self.on_filter()),
                        ft.IconButton(icon=ft.Icons.FILTER_ALT_OFF,
                                      tooltip="清除筛选",
                                      on_click=lambda _: self.on_clear_filter()),
                        self.select_all_btn],
                       spacing=4),
                self.image_list,
                ft.Row([self.tagger_btn, self.tag_untagged_btn,
                        self.delete_btn, self.reset_gen_btn,
                        self.refresh_btn, self.reset_output_btn],
                       spacing=6, wrap=True),
                self.status_text,
            ], spacing=8),
            expand=True,
        )
        left.width = 420

        # 右侧：原图 / 生成图 预览 + 提示词
        preview = self.build_section(
            title="图片预览",
            content=ft.Row([
                ft.Column([ft.Text("原图", size=13, weight="bold"),
                           self.orig_image], expand=True, spacing=4),
                ft.Column([ft.Text("生成图", size=13, weight="bold"),
                           self.gen_image], expand=True, spacing=4),
            ], expand=True, spacing=12),
            expand=True,
        )
        tags_section = self.build_section(
            title="反推提示词",
            content=ft.Container(
                content=self.tags_text, padding=6,
                height=100),
        )

        log_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("运行日志", size=16, weight="bold"),
                    self.detail_dropdown,
                    self.level_dropdown,
                    self.clear_log_btn,
                ], spacing=10),
                ft.Row([self.show_conf_switch], spacing=10),
                self.log_view,
            ], spacing=8),
            padding=12,
            border_radius=ft.border_radius.all(10),
            bgcolor=self.theme_colors.card_color,
        )
        # 页面主体允许滚动：各区块用固定高度（见 _ensure_controls 注释），
        # 若窗口较矮放不下全部内容，纵向滚动查看，避免底部按钮被
        # 日志框遮挡 / 列表被截断。
        return ft.Column([
            ft.Row([left, ft.Column([preview, tags_section],
                                    expand=True, spacing=10)],
                   spacing=10),
            log_section,
        ], spacing=10, expand=True,
           scroll=ft.ScrollMode.AUTO)

    def on_page_mounted(self) -> None:
        """页面首次显示后自动加载列表（后台线程，避免阻塞 UI）。"""
        threading.Thread(target=self._auto_load, daemon=True).start()

    def _auto_load(self) -> None:
        try:
            self._log("[info] 页面加载：正在读取图片库列表…")
            self._refresh_rows()
            self._render_list()
            self._log(f"[info] 列表加载完成，共 {len(self._rows)} 张。")
        except Exception as ex:  # noqa: BLE001
            self._set_status(f"加载图片列表失败: {ex}")
            self._log("[error]", f"加载图片列表失败: {ex}")

    # ------------------------------------------------------------------ #
    # 数据
    # ------------------------------------------------------------------ #
    def _lib(self) -> ImageLibrary:
        """懒创建图片库实例（与抓图/生成页面同库）。"""
        if self._library is None:
            cfg = CoreConfigManager().config
            self._library = ImageLibrary.resolve(
                root_dir=cfg.library.root_dir,
                library_name=cfg.crawler.output_library,
                dedupe_by_url=cfg.library.dedupe_by_url,
                dedupe_by_hash=cfg.library.dedupe_by_hash,
            )
        return self._library

    def _refresh_rows(self) -> None:
        """从数据库读取列表数据（文件名 / 下载时间 / 生成时间 / 是否已反推）。"""
        lib = self._lib()
        rows = []
        for rec in lib.list_images():
            gen = lib.db.get_generation(rec.image_id)
            rows.append({
                "image_id": rec.image_id,
                "filename": rec.filename,
                "created_at": rec.created_at,
                "generated_at": (gen.generated_at if gen else "") or "",
                "generated": bool(gen and gen.status == lib.db.STATUS_GENERATED),
                "has_tags": lib.has_tags(rec.image_id),
            })
        if self._filter_ids is not None:
            rows = [r for r in rows if r["image_id"] in self._filter_ids]
        self._rows = rows

    def _render_list(self) -> None:
        """按 self._rows 重建列表控件。"""
        self._ensure_controls()
        self.image_list.controls.clear()
        for r in self._rows:
            checked = r["image_id"] in self._selected
            cb = ft.Checkbox(
                value=checked,
                on_change=lambda e, iid=r["image_id"]: self._on_check(iid, e))
            title = ft.Text(r["filename"], size=13, weight="bold",
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
            meta = ft.Text(
                f"下载 {_fmt_time(r['created_at'])} | "
                f"生成 {_fmt_time(r['generated_at'])}"
                + (" | 已反推" if r["has_tags"] else ""),
                size=11, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE))
            tile = ft.Container(
                content=ft.Row(
                    [cb, ft.Column([title, meta], spacing=1, expand=True)],
                    spacing=4),
                padding=ft.padding.symmetric(6, 4), border_radius=6,
                on_click=lambda e, row=r: self._on_row_click(row),
            )
            self.image_list.controls.append(tile)
        self._update_select_all_btn()
        self._set_status(f"共 {len(self._rows)} 张，选中 {len(self._selected)} 张")

    def _set_status(self, msg: str) -> None:
        self._ensure_controls()
        self.status_text.value = msg
        self._update()

    def _update(self) -> None:
        """安全刷新页面（UI 线程与后台线程均可调用）。"""
        try:
            if self.page:
                self.page.update()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    # 日志：分级（debug < info < warn < error）+ 节流刷新
    # 高频过程日志（逐张反推/删除明细）用 debug，默认 info 不显示，
    # 需要调试时切到 debug。
    # ------------------------------------------------------------------ #
    _LOG_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}

    def _init_log(self) -> None:
        import time as _time
        self._log_last = 0.0
        self._log_interval = 0.15  # 最小刷新间隔（秒）
        self._log_level = "info"   # 默认过滤级别

    def _log(self, level_or_line: str, message: str = "") -> None:
        """追加一条日志。支持 ``_log("warn", "…")`` 与 ``_log("[error] …")``。"""
        if self.log_view is None:
            return
        if message:
            level, line = level_or_line, message
        else:
            line = level_or_line
            level = "info"
            if line.startswith("["):
                tag, _, rest = line[1:].partition("]")
                if tag in self._LOG_LEVELS:
                    level = tag
                    line = rest.strip()
        if self._LOG_LEVELS.get(level, 20) < self._LOG_LEVELS.get(
                self._log_level, 20):
            return
        self.log_view.controls.append(
            ft.Text(f"[{level.upper()}] {line}", size=13,
                    color={"error": ft.Colors.ERROR,
                           "warn": ft.Colors.ORANGE}.get(level)))
        if len(self.log_view.controls) > 800:
            self.log_view.controls = self.log_view.controls[-500:]
        import time as _time
        now = _time.time()
        if now - self._log_last >= self._log_interval:
            self._log_last = now
            self._flush_log_view()

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

    def _set_log_level(self, level: str) -> None:
        if level not in self._LOG_LEVELS:
            return
        self._log_level = level
        self._log("[info] 日志级别已切换为 {0}。".format(level))

    def _set_tag_preset(self, preset: str) -> None:
        """切换反推详细度预设；仅重建 tagger 实例，不会重新下载模型。"""
        if preset not in _TAG_PRESETS:
            return
        self._tag_preset = preset
        # 让旧的 tagger 实例失效：下次 _get_tagger() 会按新阈值重建
        self._tagger = None
        g, c = _TAG_PRESETS[preset]
        self._log(f"[info] 反推详细度已切换为 {preset} "
                  f"（general={g} / character={c}），下次反推生效。")

    def _set_show_conf(self, on: bool) -> None:
        """切换"显示置信度"开关；立刻按当前 _current_scored 重渲染 tags_text。"""
        self._show_conf = bool(on)
        if self._current_scored is not None:
            self.tags_text.value = self._format_scored(self._current_scored)
            self._update()
        else:
            # 没有 scored 数据（未反推 / 老标签没有置信度）只切换状态即可
            self._log("[info] 显示置信度：开" if on else "[info] 显示置信度：关"
                      + "（如需看到置信度，请重新运行 WD14 反推）")

    def _format_scored(self, scored) -> str:
        """将 [(conf, name), ...] 按当前 _show_conf 渲染为 tags_text 内容。

        conf 为 None 时（DB 中老标签，没有置信度）按无置信度渲染。
        """
        if not scored:
            return ""
        if self._show_conf:
            return "\n".join(
                f"{name} ({conf:.2f})" if conf is not None else name
                for conf, name in scored)
        return "\n".join(name for _, name in scored)

    # ------------------------------------------------------------------ #
    # 事件：列表交互
    # ------------------------------------------------------------------ #
    def _on_check(self, image_id: str, e) -> None:
        if e.control.value:
            self._selected.add(image_id)
        else:
            self._selected.discard(image_id)
        self._set_status(f"共 {len(self._rows)} 张，选中 {len(self._selected)} 张")

    def on_select_all(self) -> None:
        """全选/取消全选当前列表中的图片（受筛选影响，只作用于可见项）。"""
        if not self._rows:
            self.show_notification("列表为空，没有可全选的图片", type="warning")
            return
        visible_ids = {r["image_id"] for r in self._rows}
        # 可见项已全部选中 → 取消全选；否则全选
        if visible_ids and visible_ids <= self._selected:
            self._selected -= visible_ids
            self._log("[info] 已取消全选。")
        else:
            self._selected |= visible_ids
            self._log(f"[info] 已全选 {len(visible_ids)} 张。")
        self._update_select_all_btn()
        self._render_list()

    def _update_select_all_btn(self) -> None:
        """按当前选择状态刷新"全选"按钮的文案（全选 ↔ 取消全选）。"""
        if self.select_all_btn is None:
            return
        visible_ids = {r["image_id"] for r in self._rows}
        all_on = bool(visible_ids) and visible_ids <= self._selected
        self.select_all_btn.text = "取消全选" if all_on else "全选"
        self.select_all_btn.icon = (ft.Icons.DESELECT if all_on
                                    else ft.Icons.SELECT_ALL)

    def _on_row_click(self, row: dict) -> None:
        """点击列表行：右侧显示原图 + 生成图 + 反推提示词。"""
        self._current_id = row["image_id"]
        lib = self._lib()
        orig_path = lib.get_path(row["image_id"])
        gen_path = lib.generated_output_path(row["image_id"])
        self.orig_image.src_base64 = self._read_b64(orig_path)
        self.gen_image.src_base64 = self._read_b64(gen_path)
        tags = lib.get_tags(row["image_id"])
        # 老标签没有置信度，置 None 便于 _format_scored 在开关关闭时正常显示
        self._current_scored = [(None, t) for t in tags] if tags else []
        self.tags_text.value = (self._format_scored(self._current_scored)
                                if self._current_scored
                                else "（尚未反推：选中后点击“WD14反推提示词”）")
        # 调试：把"行点击 → 显示这行用的是哪个 image_id / 加载到几个标签"
        # 也写进日志，便于诊断"不同图片显示同一组标签"是显示问题还是数据问题。
        self._log(f"[debug] 预览 {row['filename']} (id={row['image_id']})："
                  f"显示 {len(tags)} 个标签")
        self._update()

    @staticmethod
    def _read_b64(path: Optional[str]) -> str:
        if not path:
            return _BLANK_PNG
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except OSError:
            return _BLANK_PNG

    def on_refresh(self) -> None:
        try:
            self._log("[info] 刷新列表…")
            self._refresh_rows()
            self._render_list()
            self._log(f"[info] 刷新完成，共 {len(self._rows)} 张"
                      f"（已生成 {sum(1 for r in self._rows if r['generated'])} 张，"
                      f"已反推 {sum(1 for r in self._rows if r['has_tags'])} 张）。")
        except Exception as ex:  # noqa: BLE001
            # UI 事件线程里未捕获的异常只会打印 "Future exception was never
            # retrieved"，用户看不到任何反馈；这里转为可见的错误通知。
            self.show_notification(f"刷新列表失败: {ex}", type="error")
            self._log("[error]", f"刷新列表失败: {ex}")

    def on_reset_output_bindings(self) -> None:
        """清空 generations.output_files，使查找回退到文件名匹配。

        排查场景：DB 里记录的 output_files 错位（例如多库共享 outputs/ 时
        写入了别的库的文件名），导致反推全部图片都跑在同一张生成图上，
        反推结果"全一样"。点此按钮后下次反推会按 ``<image_id>.<ext>``
        精确匹配 outputs/ 中的生成图。
        """
        try:
            n = self._lib().db.clear_output_files()
            self._log(f"[warn] 已清空 {n} 条记录的 output_files，"
                      f"下次反推将按文件名精确匹配。")
            self.show_notification(
                f"已清空 {n} 条记录的生成图绑定，请重新运行反推",
                type="warning")
        except Exception as ex:  # noqa: BLE001
            self.show_notification(f"重置失败: {ex}", type="error")
            self._log("[error]", f"重置生成图绑定失败: {ex}")

    # ------------------------------------------------------------------ #
    # 事件：筛选（按反推提示词筛选并选中匹配图片）
    # ------------------------------------------------------------------ #
    def on_filter(self) -> None:
        kw = (self.filter_input.value or "").strip()
        if not kw:
            self.show_notification("请输入提示词关键词", type="warning")
            return
        ids = self._lib().search_image_ids_by_tag(kw)
        self._filter_ids = set(ids) if ids else set()
        self._selected = set(ids)
        self._refresh_rows()
        self._render_list()
        self._log(f"[info] 筛选 “{kw}”：命中 {len(ids)} 张。")
        if not ids:
            self.show_notification(f"没有图片命中提示词 “{kw}”", type="warning")
        else:
            self.show_notification(f"命中 {len(ids)} 张（已选中）", type="success")

    def on_clear_filter(self) -> None:
        self._filter_ids = None
        self.filter_input.value = ""
        self._refresh_rows()
        self._render_list()
        self._log("[info] 已清除筛选。")

    # ------------------------------------------------------------------ #
    # 事件：WD14 反推提示词（对选中 / 全部已生成的图片）
    # ------------------------------------------------------------------ #
    def on_tagger(self) -> None:
        if self._task_thread and self._task_thread.is_alive():
            self.show_notification("任务运行中，请稍候…", type="warning")
            return
        # 列表未加载（如首次进入且未挂载完成）时先加载
        if not self._rows:
            try:
                self._refresh_rows()
                self._render_list()
            except Exception as ex:  # noqa: BLE001
                self.show_notification(f"加载图片列表失败: {ex}", type="error")
                return
        # 目标：选中的图片；若无选中则列表中全部“已生成”的图片
        targets = [r for r in self._rows if r["image_id"] in self._selected]
        if targets:
            mode = f"选中的 {len(targets)} 张"
        else:
            targets = [r for r in self._rows if r["generated"]]
            if not targets:
                self.show_notification("没有已生成的图片可反推（先选中或先生成）",
                                       type="warning")
                return
            mode = f"全部已生成的 {len(targets)} 张"
        self._start_tagger(targets, mode)

    def on_tag_untagged(self) -> None:
        """反推所有"已生成但还没有提示词"的图片（跳过已有标签的）。

        与 ``on_tagger`` 的区别：on_tagger 会重推选中的/全部已生成图片
        （覆盖已有标签），本入口只补缺——适合修复预处理 bug 之后批量
        补推旧图，不会覆盖已经推好的结果。
        """
        if self._task_thread and self._task_thread.is_alive():
            self.show_notification("任务运行中，请稍候…", type="warning")
            return
        if not self._rows:
            try:
                self._refresh_rows()
                self._render_list()
            except Exception as ex:  # noqa: BLE001
                self.show_notification(f"加载图片列表失败: {ex}", type="error")
                return
        targets = [r for r in self._rows
                   if r["generated"] and not r["has_tags"]]
        if not targets:
            self.show_notification("没有未反推的图片（全部已生成图片都有提示词）",
                                   type="info")
            return
        mode = f"未反推的 {len(targets)} 张"
        self._start_tagger(targets, mode)

    def _start_tagger(self, targets: list, mode: str) -> None:
        """公共入口：后台线程启动 WD14 反推任务。"""
        self._task_thread = threading.Thread(
            target=self._run_tagger, args=(targets, mode), daemon=True)
        self._task_thread.start()
        self._log(f"[info] 开始 WD14 反推（{mode}），"
                  f"首次运行需从 HuggingFace 下载模型…")

    def _get_tagger(self) -> Wd14Tagger:
        if self._tagger is None:
            g, c = _TAG_PRESETS.get(self._tag_preset, (0.35, 0.35))
            self._tagger = Wd14Tagger(
                general_threshold=g, character_threshold=c)
        return self._tagger

    def _run_tagger(self, targets: list, mode: str) -> None:
        lib = self._lib()
        tagger = self._get_tagger()
        ok = skip = err = 0
        first_error = ""
        total = len(targets)
        self._set_status(f"WD14 反推中（{mode}，首次运行需下载模型）…")
        for i, r in enumerate(targets, 1):
            iid = r["image_id"]
            gen_path = lib.generated_output_path(iid)
            if not gen_path:
                skip += 1
                self._log(f"[debug] 跳过 {r['filename']}：无生成输出文件")
                continue
            try:
                # 关键改动：用 tag_image_with_scores 拿 (conf, name)，
                # 便于诊断"为什么极详细档还没有人体特征"——
                # 到底是阈值过滤掉了，还是模型本身没预测到。
                scored = tagger.tag_image_with_scores(gen_path)
                tags = [name for _, name in scored]
                lib.set_tags(iid, r["filename"], tags)
                # 缓存当前预览这张图的 scored 数据，便于反推完成后
                # 即便切换开关 / 重渲染都能保留置信度
                if iid == self._current_id:
                    self._current_scored = list(scored)
                ok += 1
                # 诊断日志：把"用了哪张生成图 → 推得哪些标签 → 存在哪个
                # image_id 下"完整打印出来，便于排查"全部图片都显示
                # 同一组标签"这类问题（推断/存储/显示三方都可能是元凶）。
                sample = ", ".join(f"{n}({c:.2f})" for c, n in scored[:3])
                if len(scored) > 3:
                    sample += "..."
                self._log(
                    f"[debug] 反推成功 {r['filename']} (id={iid}) "
                    f"→ 生成图 {os.path.basename(gen_path)}，"
                    f"共 {len(scored)} 个标签: {sample}")
                # 黄金诊断：dump top 30 原始预测，便于看清模型"原本"
                # 给出了什么——即便过阈值被过滤掉的也能看到，用来区分
                # "模型没预测到人体特征" vs "阈值过滤掉了人体特征"。
                # 仅在调试 debug 级别输出，避免信息过载。
                if self._log_level == "debug" and scored:
                    top = ", ".join(f"{n}({c:.2f})" for c, n in scored[:30])
                    self._log(f"[debug]   top-30: {top}")
            except Exception as ex:  # noqa: BLE001
                err += 1
                self._log("[error]",
                          f"反推失败 {r['filename']}: {ex}")
                if not first_error:
                    # 记住第一个失败原因：依赖缺失 / 模型下载失败等
                    # 环境性问题会让所有图片都失败，原因必须展示出来
                    first_error = str(ex)
            self._set_status(f"WD14 反推进度 {i}/{total}（成功 {ok}，"
                             f"跳过 {skip}，失败 {err}）")
        # 当前预览的图片若被反推，刷新提示词显示（保留置信度）
        if self._current_id and lib.has_tags(self._current_id):
            if self._current_scored and any(
                    c is not None for c, _ in self._current_scored):
                # 刚反推完，已带置信度
                self.tags_text.value = self._format_scored(self._current_scored)
            else:
                # 走的 DB 老标签，无置信度
                tags = lib.get_tags(self._current_id)
                self.tags_text.value = "\n".join(tags)
        self._refresh_rows()
        self._render_list()
        # 显示本轮实际使用的推理设备（GPU 加速是否生效一目了然）
        if tagger.active_provider:
            self._log(f"[info] WD14 推理设备：{tagger.active_provider}")
        if err and first_error:
            # 失败时把具体原因留在状态栏（不被后续进度覆盖）并带进通知
            self._set_status(f"反推失败 {err}/{total}，原因：{first_error}")
            self._log(f"[error] 反推结束：失败 {err}/{total}，原因：{first_error}")
            self.show_notification(
                f"反推失败 {err} 张：{first_error}", type="error")
        else:
            self._log(f"[info] 反推完成：成功 {ok} 张，跳过 {skip} 张"
                      f"（无生成图），失败 {err} 张。")
            self.show_notification(
                f"反推完成：成功 {ok} 张，跳过 {skip} 张（无生成图），失败 {err} 张",
                type="success")

    # ------------------------------------------------------------------ #
    # 事件：删除选中（同时清理生成图与 tags 表条目）
    # ------------------------------------------------------------------ #
    def on_delete(self) -> None:
        if self._task_thread and self._task_thread.is_alive():
            self.show_notification("任务运行中，请稍候…", type="warning")
            return
        if not self._selected:
            self.show_notification("请先勾选要删除的图片（可用筛选框批量选中）",
                                   type="warning")
            return
        ids = list(self._selected)
        self._task_thread = threading.Thread(
            target=self._run_delete, args=(ids,), daemon=True)
        self._task_thread.start()

    def _run_delete(self, ids: list) -> None:
        lib = self._lib()
        deleted = 0
        self._log(f"[info] 开始删除 {len(ids)} 张图片…")
        for i, iid in enumerate(ids, 1):
            # ImageLibrary.remove：删原图 + 删生成图 + 删记录
            # （StorageDB.delete_image 级联清理 generations 与 tags）
            if lib.remove(iid):
                deleted += 1
                if iid == self._current_id:
                    self._current_id = ""
                    self.orig_image.src_base64 = _BLANK_PNG
                    self.gen_image.src_base64 = _BLANK_PNG
                    self.tags_text.value = "点击左侧列表中的图片查看提示词"
            else:
                self._log(f"[warn] 删除失败（记录不存在）：{iid}")
            self._set_status(f"删除进度 {i}/{len(ids)}")
        self._selected -= set(ids)
        if self._filter_ids is not None:
            self._filter_ids -= set(ids)
        self._refresh_rows()
        self._render_list()
        self._log(f"[info] 删除完成：{deleted} 张（含生成图与反推提示词记录）。")
        self.show_notification(f"已删除 {deleted} 张（含生成图与反推提示词记录）",
                               type="success")

    # ------------------------------------------------------------------ #
    # 事件：删除生成结果（保留原图，记录回到未生成、可被生成任务扫描）
    # ------------------------------------------------------------------ #
    def on_reset_generation(self) -> None:
        if self._task_thread and self._task_thread.is_alive():
            self.show_notification("任务运行中，请稍候…", type="warning")
            return
        if not self._selected:
            self.show_notification("请先勾选要重置的图片", type="warning")
            return
        ids = list(self._selected)
        self._task_thread = threading.Thread(
            target=self._run_reset_generation, args=(ids,), daemon=True)
        self._task_thread.start()

    def _run_reset_generation(self, ids: list) -> None:
        lib = self._lib()
        self._log(f"[info] 开始重置生成结果 {len(ids)} 张（原图保留）…")
        for i, iid in enumerate(ids, 1):
            lib.reset_generation(iid)
            # 当前预览的图片被重置：生成图清空、提示词清空
            if iid == self._current_id:
                self.gen_image.src_base64 = _BLANK_PNG
                self.tags_text.value = "（已重置为未生成：可重新生成后再反推）"
                self._current_scored = []
            self._set_status(f"重置生成结果 {i}/{len(ids)}")
        self._refresh_rows()
        self._render_list()
        self._log(f"[info] 生成结果重置完成：{len(ids)} 张已回到未生成状态，"
                  f"可被生成任务扫描重新生成。")
        self.show_notification(
            f"已重置 {len(ids)} 张为未生成（原图已保留）", type="success")
