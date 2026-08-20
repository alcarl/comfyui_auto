r"""用抓取到的 Pinterest 图片送入 ComfyUI 工作流，生成图片。

运行方式（需已激活 .venv）：
    # 仅对图片库中已有图片批量生成（不重新抓取）
    .venv\Scripts\python.exe examples/pinterest_generate.py --generate-only

    # 完整流程：先抓取 Pinterest 图片入库，再批量送入 ComfyUI 生成
    .venv\Scripts\python.exe examples/pinterest_generate.py

说明：
- 抓取使用浏览器后端（nodriver），登录态持久化到 libraries/browser_profile。
- 生成使用 config/krea2i2i_api.json 工作流（API 模式），输出到 libraries/outputs/。
- ComfyUI 地址默认 http://10.0.0.190:8188（见 config/core_config.json）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config.manager import CoreConfigManager  # noqa: E402
from app.core.config.models import (  # noqa: E402
    SiteConfig, CrawlerType, CrawlerBackend,
)
from app.core.crawler import create_crawler  # noqa: E402
from app.core.image_library import ImageLibrary  # noqa: E402
from app.core.comfyui import ComfyUIClient  # noqa: E402


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


def crawl_and_store(cfg) -> ImageLibrary:
    """从参数文件（config/core_config.json）读取站点 URL 列表并循环抓取。

    读取 cfg.sites 中第一个启用站点（Pinterest 相关）的 urls，转为浏览器后端
    后循环每个页面地址下载图片。若配置里没有 Pinterest 站点，使用一个默认示例。
    """
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

    # 从参数文件读取第一个启用的 Pinterest 相关站点（不限于 pinterest_browser，
    # 也兼容配置里仍为 pinterest/http 的旧站点），取其 urls 列表。
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

    # 统一使用浏览器后端抓取，循环遍历所有 URL
    site = SiteConfig(
        name=name,
        crawler_type=CrawlerType.PINTEREST_BROWSER,
        backend=CrawlerBackend.BROWSER,
        urls=urls,
        extra={"locale": "jp"},
    )
    print(f"将从参数文件读取 {len(urls)} 个页面地址循环抓取图片…", flush=True)
    for u in urls:
        print(f"  - {u}", flush=True)

    # 下载一张、立即保存一张：通过 save_callback 实时入库，避免全部下载完才保存。
    def _save_now(img) -> None:
        if library.is_duplicate(url=img.url):
            return
        library.add_image(
            img.data, source_url=img.url, site=img.site,
            ext=_ext_of(img.url, img.content_type))
        print(f"[saved] {img.url[:70]} -> 已保存（库中 {library.count()} 张）", flush=True)

    crawler = create_crawler(
        site,
        timeout=cfg.crawler.timeout,
        max_concurrency=cfg.crawler.max_concurrency,
        retry=cfg.crawler.retry,
        user_agent=cfg.crawler.user_agent,
        browser_config=cfg.crawler.browser,
        progress=lambda stage, msg="": print(f"[{stage}] {msg}", flush=True),
        save_callback=_save_now,
    )
    print("开始浏览器抓取（边下载边保存）…", flush=True)
    fetched = crawler.fetch_images()
    print(f"抓取完成：共 {len(fetched)} 张，图片库当前共 {library.count()} 张。", flush=True)
    return library


def generate_from_library(cfg, library, max_images=None) -> int:
    """对图片库中的图片逐一送入 ComfyUI 工作流生成。"""
    client = ComfyUIClient(cfg.comfyui)
    images = library.list_images()
    if max_images and max_images > 0:
        images = images[:max_images]
    output_dir = os.path.join(os.path.abspath(cfg.library.root_dir), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    total_ok = 0
    total_err = 0
    total_skip = 0
    for i, rec in enumerate(images, 1):
        path = library.get_path(rec.image_id)
        if not path:
            print(f"[skip] 图片文件缺失: {rec.image_id}", flush=True)
            continue
        try:
            outs = client.img2img(path, output_dir=output_dir)
            if not outs:
                total_skip += 1
                print(f"[skip] {i}/{len(images)} {rec.image_id} -> 输出已存在，跳过", flush=True)
                continue
            ok = sum(1 for o in outs if o.get("data"))
            total_ok += ok
            print(f"[gen] {i}/{len(images)} {rec.image_id} -> 生成 {ok} 张", flush=True)
        except KeyboardInterrupt:
            raise  # 交给 main 统一优雅处理
        except Exception as e:  # noqa: BLE001
            total_err += 1
            print(f"[error] 图生图失败 {rec.image_id}: {e}", flush=True)
    print(f"生成完成：成功 {total_ok} 张，跳过 {total_skip} 个，失败 {total_err} 个。"
          f"输出目录: {output_dir}", flush=True)
    return total_ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pinterest 图片抓取 + ComfyUI 图生图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  # 从参数文件(config/core_config.json)读取站点 URL 列表并循环抓取生成\n"
               "  python examples/pinterest_generate.py\n"
               "  # 仅对图片库已有图片生成\n"
               "  python examples/pinterest_generate.py --generate-only\n"
               "  # 只生成前 N 张\n"
               "  python examples/pinterest_generate.py --generate-only --max-images 5")
    parser.add_argument("--generate-only", action="store_true",
                        help="仅对图片库已有图片生成，不重新抓取")
    parser.add_argument("--max-images", type=int, default=0,
                        help="最多生成的图片数（0 表示全部）")
    args = parser.parse_args()

    mgr = CoreConfigManager()
    cfg = mgr.config

    if args.generate_only:
        library = ImageLibrary.resolve(
            root_dir=cfg.library.root_dir,
            library_name=cfg.crawler.output_library)
        print(f"从图片库读取 {library.count()} 张图片，开始生成…", flush=True)
    else:
        library = crawl_and_store(cfg)

    try:
        generate_from_library(cfg, library, max_images=args.max_images)
    except KeyboardInterrupt:
        print("\n已被用户中断（Ctrl+C）。已生成的图片均已保存到输出目录，可随时重新运行继续。",
              flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
