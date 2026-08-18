"""快速验证：用真实浏览器抓取 Pinterest 图片墙（浏览器内取图，不走 requests）。

运行：.venv\Scripts\python.exe test_quick.py
首次会弹出 Chrome，如需登录请手动登录（登录态持久化到 libraries/browser_profile）。
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

from app.core.config.models import SiteConfig, CrawlerType, CrawlerBackend, BrowserConfig
from app.core.browser.pinterest_browser import PinterestBrowserCrawler

site = SiteConfig(
    name="p",
    crawler_type=CrawlerType.PINTEREST_BROWSER,
    backend=CrawlerBackend.BROWSER,
    urls=["https://jp.pinterest.com/pin/1028087421172953769/"],
)
cfg = BrowserConfig(proxy="http://10.0.0.51:1072", login_timeout=120)

c = PinterestBrowserCrawler(
    site, browser_config=cfg,
    progress=lambda s, m="": print(f"[{s}] {m}", flush=True),
)
imgs = c.fetch_images()
print("TOTAL", len(imgs))
for i in imgs[:3]:
    print("img bytes=", len(i.data), "url=", i.url[:70])
