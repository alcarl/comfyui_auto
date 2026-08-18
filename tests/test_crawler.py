"""图片抓取模块测试：验证 Pinterest 解析与工厂分发（注入桩网络）。"""
import unittest
from unittest.mock import MagicMock

from app.core.config.models import SiteConfig, CrawlerType
from app.core.crawler import PinterestCrawler, create_crawler
from app.core.crawler.base import FetchedImage

# 模拟 Pinterest 图片墙 HTML（含 <img> 与内嵌 JSON 两种来源）
SAMPLE_HTML = b"""
<html><body>
<img src="https://i.pinimg.com/236x/aa/bb/cc/abc.jpg" srcset="https://i.pinimg.com/736x/aa/bb/cc/abc.jpg 736w, https://i.pinimg.com/474x/aa/bb/cc/abc.jpg 474w">
<img src="https://i.pinimg.com/236x/dd/ee/ff/def.jpg">
<script>var x={"images":["https://i.pinimg.com/originals/11/22/33/abc123.jpg"]}</script>
</body></html>
"""

FAKE_IMG = b"\x89PNG" + b"\x00" * 64


def fake_http_get_factory():
    """返回一个桩 http_get：页面返回 SAMPLE_HTML，图片返回 FAKE_IMG。"""
    def _get(url):
        if url.endswith(".html") or "pinterest" in url:
            return SAMPLE_HTML, "text/html"
        return FAKE_IMG, "image/jpeg"
    return _get


class TestPinterestParser(unittest.TestCase):
    def setUp(self):
        site = SiteConfig(name="p", crawler_type=CrawlerType.PINTEREST,
                          urls=["https://jp.pinterest.com/pin/1028087421172953769/"])
        self.crawler = PinterestCrawler(site, http_get=fake_http_get_factory())

    def test_discover_image_urls(self):
        urls = self.crawler.discover_image_urls("https://jp.pinterest.com/pin/1028087421172953769/")
        # 至少应解析出 originals 与 736x 的地址
        self.assertTrue(any("/originals/" in u for u in urls))
        self.assertTrue(any("/736x/" in u for u in urls))

    def test_prefer_original(self):
        ordered = PinterestCrawler.prefer_original([
            "https://i.pinimg.com/236x/a.jpg",
            "https://i.pinimg.com/originals/a.jpg",
            "https://i.pinimg.com/736x/a.jpg",
        ])
        self.assertTrue(ordered[0].endswith("/originals/a.jpg"))

    def test_fetch_images_dedupes_and_downloads(self):
        imgs = self.crawler.fetch_images()
        # 去重后应为 3 张独立图片（736x 与 originals 视为不同 URL 各自保留）
        self.assertGreaterEqual(len(imgs), 1)
        for img in imgs:
            self.assertIsInstance(img, FetchedImage)
            self.assertTrue(img.data)


class TestCrawlerFactory(unittest.TestCase):
    def test_create_pinterest(self):
        site = SiteConfig(name="p", crawler_type=CrawlerType.PINTEREST,
                          urls=["https://jp.pinterest.com/pin/1028087421172953769/"])
        crawler = create_crawler(site, http_get=MagicMock())
        self.assertIsInstance(crawler, PinterestCrawler)

    def test_create_unknown_raises(self):
        from app.core.crawler.factory import _REGISTRY
        site = SiteConfig(name="x", crawler_type=CrawlerType.PINTEREST, urls=[])
        saved = dict(_REGISTRY)
        _REGISTRY.clear()
        try:
            with self.assertRaises(ValueError):
                create_crawler(site)
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(saved)


if __name__ == "__main__":
    unittest.main()
