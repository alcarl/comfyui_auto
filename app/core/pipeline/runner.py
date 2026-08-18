"""业务编排层：将抓取、图片库、ComfyUI 串成完整流程。

职责边界：
- pipeline 不实现具体抓取/去重/出图逻辑，只负责调度与数据流。
- 依赖 config / crawler / image_library / comfyui 各模块，彼此通过接口解耦。
- 提供进度回调，方便 UI 层实时展示。

典型流程：
    crawl -> 写入本地图片库（按 URL 自动去重） -> 对库中图片逐一图生图 -> 输出
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..config.manager import CoreConfigManager
from ..config.models import CoreConfig
from ..crawler import create_crawler
from ..crawler.base import HttpGet
from ..image_library import ImageLibrary
from ..comfyui import ComfyUIClient

# 进度回调： (stage: str, current: int, total: int, message: str)
ProgressCallback = Callable[[str, int, int, str], None]


@dataclass
class PipelineResult:
    """一次流程执行的结果汇总。"""
    crawled_total: int = 0          # 抓取到的新图片数（去重后入库）
    crawled_skipped: int = 0        # 因重复被跳过的图片数
    generated_total: int = 0        # 成功生成的图片数
    errors: List[str] = field(default_factory=list)


class Pipeline:
    """完整业务流程编排器。"""

    def __init__(self, config: Optional[CoreConfig] = None,
                 config_manager: Optional[CoreConfigManager] = None,
                 http_get: Optional[HttpGet] = None,
                 progress: Optional[ProgressCallback] = None):
        """
        :param config: 业务核心配置（不传则使用 CoreConfigManager 单例）
        :param http_get: 注入的下载函数（测试用）
        :param progress: 进度回调
        """
        self.config_manager = config_manager or CoreConfigManager()
        self.config: CoreConfig = config or self.config_manager.config
        self._http_get = http_get
        self._progress = progress or (lambda *a, **k: None)

    # ------------------------------------------------------------------ #
    # 阶段一：抓取并入库
    # ------------------------------------------------------------------ #
    def crawl_to_library(self, site_names: Optional[List[str]] = None) -> ImageLibrary:
        """抓取配置的站点图片，写入本地图片库，返回图片库实例。"""
        cfg = self.config
        library = ImageLibrary.resolve(
            root_dir=cfg.library.root_dir,
            library_name=cfg.crawler.output_library,
            dedupe_by_url=cfg.library.dedupe_by_url,
            dedupe_by_hash=cfg.library.dedupe_by_hash,
        )

        sites = [s for s in cfg.sites if s.enabled]
        if site_names:
            sites = [s for s in sites if s.name in site_names]

        total_new, total_skip = 0, 0
        for site in sites:
            crawler = create_crawler(
                site,
                timeout=cfg.crawler.timeout,
                max_concurrency=cfg.crawler.max_concurrency,
                retry=cfg.crawler.retry,
                user_agent=cfg.crawler.user_agent,
                http_get=self._http_get,
            )
            self._progress("crawl", 0, 1, f"开始抓取站点: {site.name}")
            fetched = crawler.fetch_images()
            for i, img in enumerate(fetched, 1):
                if library.is_duplicate(url=img.url):
                    total_skip += 1
                    continue
                library.add_image(
                    img.data, source_url=img.url, site=img.site,
                    ext=crawler.guess_ext(img.url, img.content_type))
                total_new += 1
                self._progress("crawl", i, len(fetched),
                               f"[{site.name}] 入库 {total_new} 张，跳过重复 {total_skip} 张")

        self._last_library = library
        return library

    # ------------------------------------------------------------------ #
    # 阶段二：对图片库做图生图
    # ------------------------------------------------------------------ #
    def generate_from_library(self, library: Optional[ImageLibrary] = None,
                              output_dir: Optional[str] = None) -> PipelineResult:
        """对图片库中的每张图片执行图生图。"""
        library = library or getattr(self, "_last_library", None)
        if library is None:
            library = ImageLibrary.resolve(
                root_dir=self.config.library.root_dir,
                library_name=self.config.crawler.output_library)

        client = ComfyUIClient(self.config.comfyui)
        images = library.list_images()
        result = PipelineResult()
        output_dir = output_dir or os.path.join(
            os.path.abspath(self.config.library.root_dir), "outputs")

        for i, rec in enumerate(images, 1):
            path = library.get_path(rec.image_id)
            if not path:
                result.errors.append(f"图片文件缺失: {rec.image_id}")
                continue
            try:
                outs = client.img2img(path, output_dir=output_dir)
                ok = sum(1 for o in outs if o.get("data"))
                result.generated_total += ok
                self._progress("generate", i, len(images),
                               f"已处理 {i}/{len(images)}，生成 {ok} 张")
            except Exception as e:  # noqa: BLE001
                result.errors.append(f"图生图失败 {rec.image_id}: {e}")
                self._progress("generate", i, len(images), f"失败: {e}")

        return result

    # ------------------------------------------------------------------ #
    # 一键全流程
    # ------------------------------------------------------------------ #
    def run(self, site_names: Optional[List[str]] = None,
            output_dir: Optional[str] = None) -> PipelineResult:
        """执行完整流程：抓取入库 -> 图生图。"""
        self._progress("start", 0, 0, "流程开始")
        library = self.crawl_to_library(site_names)
        result = self.generate_from_library(library, output_dir=output_dir)
        # 把抓取统计并入
        result.crawled_total = library.count()
        self._progress("done", 0, 0, "流程结束")
        return result
