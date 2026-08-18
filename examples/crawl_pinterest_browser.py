r"""真实抓取示例：用 nodriver 浏览器抓取 Pinterest 图片墙。

运行方式（需已激活 .venv，且已 pip install -r requirements.txt）：
    .venv\Scripts\python.exe examples/crawl_pinterest_browser.py

说明：
- 首次运行会弹出浏览器，请在其中手动输入 Pinterest 账号密码完成登录，
  登录态将保存到 crawler.browser 配置的 user_data_dir / session_file。
- 之后运行会自动加载登录态，无需再次登录。
- 抓取到的图片会写入本地图片库（默认 libraries/default），并按 URL 去重。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config.manager import CoreConfigManager  # noqa: E402
from app.core.config.models import (  # noqa: E402
    SiteConfig, CrawlerType, CrawlerBackend, BrowserConfig,
)
from app.core.crawler import create_crawler  # noqa: E402
from app.core.image_library import ImageLibrary  # noqa: E402


def main() -> None:
    mgr = CoreConfigManager()
    cfg = mgr.config

    # 确保使用浏览器后端与代理（也可直接在 config/core_config.json 配置）
    if not cfg.crawler.browser.proxy:
        cfg.crawler.browser.proxy = "http://10.0.0.51:1072"
    if not cfg.crawler.browser.user_data_dir:
        cfg.crawler.browser.user_data_dir = "libraries/browser_profile"

    # 选取/创建浏览器站点
    site = next((s for s in cfg.sites
                 if s.crawler_type == CrawlerType.PINTEREST_BROWSER), None)
    if site is None:
        site = SiteConfig(
            name="pinterest_demo",
            crawler_type=CrawlerType.PINTEREST_BROWSER,
            backend=CrawlerBackend.BROWSER,
            urls=["https://jp.pinterest.com/pin/1028087421172953769/"],
            extra={"locale": "jp"},
        )
        cfg.sites.append(site)

    library = ImageLibrary.resolve(
        root_dir=cfg.library.root_dir,
        library_name=cfg.crawler.output_library,
        dedupe_by_url=cfg.library.dedupe_by_url,
        dedupe_by_hash=cfg.library.dedupe_by_hash,
    )

    crawler = create_crawler(
        site,
        timeout=cfg.crawler.timeout,
        max_concurrency=cfg.crawler.max_concurrency,
        retry=cfg.crawler.retry,
        user_agent=cfg.crawler.user_agent,
        browser_config=cfg.crawler.browser,
        progress=lambda stage, msg="": print(f"[{stage}] {msg}"),
    )

    print("开始浏览器抓取（如未登录请在弹出的浏览器中手动登录）…")
    images = crawler.fetch_images()
    print(f"抓取到 {len(images)} 张图片，正在写入本地图片库（按 URL 去重）…")
    added = 0
    for img in images:
        if library.add_image(img.data, source_url=img.url,
                             content_type=img.content_type,
                             site=img.site, source_page=img.source_page):
            added += 1
    print(f"完成：新入库 {added} 张，图片库当前共 {library.count()} 张。")


if __name__ == "__main__":
    main()
