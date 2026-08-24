"""Pinterest 图片抓取 + ComfyUI 图生图的业务流程封装。

供前端界面（flet main.py）与命令行示例共用：
- crawl_pinterest：从配置读取 URL 列表，循环抓取图片并实时入库。
- generate_from_library：把图片库中的图片送入 ComfyUI 生成。

均通过 progress 回调实时上报进度，便于界面展示。
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from .config.models import SiteConfig, CrawlerType, CrawlerBackend
from .crawler import create_crawler
from .image_library import ImageLibrary
from .comfyui import ComfyUIClient

# 进度回调类型：progress(stage: str, message: str) -> None
ProgressCB = Callable[[str, str], None]


def _ext_of(url: str, ctype: str) -> str:
    mapping = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
               "image/gif": "gif", "image/avif": "avif", "image/bmp": "bmp"}
    if ctype:
        ext = mapping.get((ctype or "").split(";")[0].strip().lower())
        if ext:
            return ext
    p = url.rsplit("?", 1)[0].lower()
    for ext in ("jpg", "jpeg", "png", "webp", "gif", "avif"):
        if p.endswith(f".{ext}"):
            return "jpg" if ext == "jpeg" else ext
    return "jpg"


def crawl_pinterest(cfg: Any, *,
                    progress: Optional[ProgressCB] = None,
                    urls: Optional[list] = None) -> ImageLibrary:
    """从配置（或传入的 urls）读取站点 URL 列表，循环抓取图片并实时入库。

    :param cfg: CoreConfig 实例
    :param progress: 进度回调 (stage, message)
    :param urls: 可选的 URL 列表；为空则读取配置里第一个启用站点
    :return: ImageLibrary 实例
    """
    _log = progress or (lambda s, m: None)

    library = ImageLibrary.resolve(
        root_dir=cfg.library.root_dir,
        library_name=cfg.crawler.output_library,
        dedupe_by_url=cfg.library.dedupe_by_url,
        dedupe_by_hash=cfg.library.dedupe_by_hash,
    )

    if not cfg.crawler.browser.proxy:
        cfg.crawler.browser.proxy = "http://10.0.0.51:1072"
    if not cfg.crawler.browser.login_timeout or cfg.crawler.browser.login_timeout > 60:
        cfg.crawler.browser.login_timeout = 60

    # 优先使用传入 urls；否则读取配置里第一个启用的 Pinterest 相关站点
    if not urls:
        pin_site = next((s for s in cfg.sites
                         if s.enabled and s.crawler_type.value in (
                             CrawlerType.PINTEREST_BROWSER.value,
                             CrawlerType.PINTEREST.value)), None)
        if pin_site and pin_site.urls:
            urls = pin_site.urls
            name = pin_site.name
        else:
            urls = ["https://jp.pinterest.com/pin/1028087421172953769/"]
            name = "pinterest_demo"
    else:
        name = "pinterest_cli"

    site = SiteConfig(
        name=name,
        crawler_type=CrawlerType.PINTEREST_BROWSER,
        backend=CrawlerBackend.BROWSER,
        urls=urls,
        extra={"locale": "jp"},
    )
    _log("info", f"将从 {len(urls)} 个页面地址循环抓取图片：")
    for u in urls:
        _log("info", f"  - {u}")

    # 下载一张、立即保存一张
    def _save_now(img) -> None:
        if library.is_duplicate(url=img.url):
            return
        library.add_image(
            img.data, source_url=img.url, site=img.site,
            ext=_ext_of(img.url, img.content_type))
        _log("saved", f"{img.url[:70]} -> 已保存（库中 {library.count()} 张）")

    crawler = create_crawler(
        site,
        timeout=cfg.crawler.timeout,
        max_concurrency=cfg.crawler.max_concurrency,
        retry=cfg.crawler.retry,
        user_agent=cfg.crawler.user_agent,
        browser_config=cfg.crawler.browser,
        progress=lambda stage, msg="": _log(f"page::{stage}", msg),
        save_callback=_save_now,
    )
    _log("info", "开始浏览器抓取（边下载边保存）…")
    fetched = crawler.fetch_images()
    _log("done", f"抓取完成：共 {len(fetched)} 张，图片库当前共 {library.count()} 张。")
    return library


def generate_from_library(cfg: Any, library: ImageLibrary, *,
                          max_images: int = 0,
                          progress: Optional[ProgressCB] = None,
                          stop_event: Optional[Any] = None,
                          poll_interval: float = 5.0) -> int:
    """把图片库中的“已下载但未生成”图片送入 ComfyUI 生成。

    支持两种模式：
    - 不传 stop_event：处理完当前一批待生成图片后退出（一次性）。
    - 传入 stop_event（threading.Event）：进入持续轮询，每 poll_interval 秒
      重新查询一次数据库待生成条目并生成，直到 stop_event 被设置；这样
      轮询期间新下载的图片也会被自动处理，可通过“停止生成”按钮停止。

    :param max_images: 每轮最多生成的张数（0 表示不限制）
    :param progress: 进度回调 (stage, message)
    :param stop_event: 用于停止轮询的 threading.Event（可选）
    :param poll_interval: 轮询间隔秒数（默认 5 秒）
    :return: 成功生成的图片张数
    """
    _log = progress or (lambda s, m: None)
    client = ComfyUIClient(cfg.comfyui)
    output_dir = os.path.join(os.path.abspath(cfg.library.root_dir), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    import time as _time
    total_ok = total_err = total_skip = 0

    def _process_batch() -> tuple:
        # 每次查询都通过 JOIN 两表获取“已下载但未生成”的条目
        images = library.list_pending_generation()
        if max_images and max_images > 0:
            images = images[:max_images]
        ok = err = skip = 0
        for i, rec in enumerate(images, 1):
            if stop_event is not None and stop_event.is_set():
                _log("warn", "已收到停止指令，中止本轮生成。")
                break
            path = library.get_path(rec.image_id)
            if not path:
                _log("skip", f"图片文件缺失: {rec.image_id}")
                skip += 1
                continue
            # gif 动图不适合送入 ComfyUI 图生图，跳过
            if os.path.splitext(path)[1].lower() == ".gif":
                skip += 1
                _log("skip", f"[{i}/{len(images)}] {rec.image_id} -> gif 图片跳过")
                continue
            try:
                _log("info", f"[{i}/{len(images)}] 正在生成 {rec.image_id}…")
                outs = client.img2img(path, output_dir=output_dir)
                if not outs:
                    skip += 1
                    _log("skip",
                         f"[{i}/{len(images)}] {rec.image_id} -> 未返回生成结果，跳过")
                    continue
                n = sum(1 for o in outs if o.get("data"))
                # 生成成功，记录输出文件名并更新数据库状态
                out_files = ",".join(
                    o.get("filename", "") for o in outs if o.get("filename"))
                library.mark_generated(rec.image_id, out_files)
                ok += n
                _log("gen", f"[{i}/{len(images)}] {rec.image_id} -> 生成 {n} 张")
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001
                err += 1
                _log("error", f"图生图失败 {rec.image_id}: {e}")
        return ok, err, skip

    while True:
        ok, err, skip = _process_batch()
        total_ok += ok
        total_err += err
        total_skip += skip

        # 无 stop_event：一次性模式，处理完当前批次即退出
        if stop_event is None:
            break

        # 有 stop_event：持续轮询，间隔 poll_interval 秒（期间可被停止）
        if stop_event.is_set():
            _log("warn", "生成已停止。")
            break
        _log("info",
             f"本轮完成（成功 {ok}，跳过 {skip}，失败 {err}），"
             f"{int(poll_interval)} 秒后再次轮询…")
        waited = 0.0
        while waited < poll_interval:
            if stop_event.is_set():
                break
            _time.sleep(0.5)
            waited += 0.5

    _log("done", f"生成结束：成功 {total_ok} 张，跳过 {total_skip} 个，失败 {total_err} 个。"
                 f"输出目录: {output_dir}")
    return total_ok
