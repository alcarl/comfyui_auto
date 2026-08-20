"""浏览器抓取模块测试：验证解析逻辑、launcher 会话、crawler 流程（注入桩）。"""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from app.core.config.models import SiteConfig, CrawlerType, CrawlerBackend, BrowserConfig
from app.core.crawler import create_crawler
from app.core.crawler.base import FetchedImage
from app.core.browser.pinterest_browser import PinterestBrowserCrawler
from app.core.browser.launcher import BrowserLauncher


SAMPLE_PAGE = """
<html><body>
<img src="https://i.pinimg.com/236x/aa/bb/cc/abc.jpg" srcset="https://i.pinimg.com/736x/aa/bb/cc/abc.jpg 736w">
<img src="https://i.pinimg.com/originals/11/22/33/xyz.jpg">
</body></html>
"""

FAKE_IMG = b"\x89PNG" + b"\x00" * 64


class FakeTab:
    def __init__(self, url="", html=SAMPLE_PAGE, logged_in=True):
        self.url = url
        self._html = html
        self._logged_in = logged_in

    async def get_content(self):
        return self._html

    async def evaluate(self, expr, *args, **kwargs):
        # 模拟浏览器上下文：返回 <img> 列表 或 fetch 取图的 base64
        if "querySelectorAll('img')" in expr:
            return [
                "https://i.pinimg.com/236x/aa/bb/cc/abc.jpg",
                "https://i.pinimg.com/originals/11/22/33/xyz.jpg",
            ]
        if "fetch" in expr:
            import base64
            b64 = base64.b64encode(FAKE_IMG).decode()
            return {"ok": True, "mime": "image/jpeg", "b64": b64}
        # 登录表单检测（auth.wait_for_login 用 email/password 输入框）：
        # 已登录则返回 False（无表单），未登录返回 True
        if 'input[type="email"]' in expr or "input#email" in expr \
                or "registerFormSubmitButton" in expr:
            return not self._logged_in
        return self._html

    async def find(self, *a, **k):
        return None


class FakeBrowser:
    def __init__(self, logged_in=True):
        self.main_tab = FakeTab(logged_in=logged_in)
        self.tabs = [self.main_tab]
        self._logged_in = logged_in
        self.closed = False
        self.cookies_saved = None
        self.cookies_loaded = False

    async def get(self, url):
        # 登录检测：访问 /login/ 时，若已登录会被重定向回首页（URL 不含 /login）
        if "/login/" in url:
            if self._logged_in:
                self.main_tab.url = "https://www.pinterest.com/"
            else:
                self.main_tab.url = url
        else:
            self.main_tab.url = url
        return self.main_tab

    async def aclose(self):
        self.closed = True

    @property
    def cookies(self):
        return self

    async def save(self, file=".session.dat", pattern=".*"):
        self.cookies_saved = file
        with open(file, "wb") as f:
            f.write(b"session-data")

    async def load(self, file=".session.dat", pattern=".*"):
        self.cookies_loaded = os.path.exists(file)


def fake_http_get(url):
    if "pinimg" in url:
        return FAKE_IMG, "image/jpeg"
    return b"", "text/html"


async def _fake_start(config, **kwargs):
    return FakeBrowser()


class TestPinterestBrowserParser(unittest.TestCase):
    def test_extract_img_urls(self):
        urls = PinterestBrowserCrawler._extract_img_urls(SAMPLE_PAGE)
        self.assertTrue(any("/originals/" in u for u in urls))
        self.assertTrue(any("/736x/" in u for u in urls))

    def test_url_priority(self):
        # originals 优先于 736x
        urls = [
            "https://i.pinimg.com/736x/a.jpg",
            "https://i.pinimg.com/originals/a.jpg",
        ]
        ordered = sorted(urls, key=PinterestBrowserCrawler._url_priority)
        self.assertTrue(ordered[0].endswith("/originals/a.jpg"))


class TestBrowserLauncherSession(unittest.IsolatedAsyncioTestCase):
    async def test_save_and_load_session(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = BrowserConfig(user_data_dir=d, session_file=os.path.join(d, "sess.dat"))
            launcher = BrowserLauncher(cfg, browser_factory=_fake_start)
            browser = await launcher.start()
            path = await launcher.save_session()
            self.assertTrue(os.path.exists(path))
            # 新建一个 browser 模拟重新打开
            launcher2 = BrowserLauncher(cfg, browser_factory=_fake_start)
            b2 = await launcher2.start()
            ok = await launcher2.load_session()
            self.assertTrue(ok)
            self.assertTrue(b2.cookies_loaded)


class TestPinterestBrowserCrawlerFlow(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_images_async(self):
        site = SiteConfig(
            name="p", crawler_type=CrawlerType.PINTEREST_BROWSER,
            backend=CrawlerBackend.BROWSER,
            urls=["https://jp.pinterest.com/pin/1028087421172953769/"],
            extra={"locale": "jp"},
        )
        browser_cfg = BrowserConfig(login_timeout=5)
        crawler = PinterestBrowserCrawler(
            site, http_get=fake_http_get,
            browser_factory=_fake_start,
            browser_config=browser_cfg,
        )
        imgs = await crawler._fetch_images_async()
        self.assertGreaterEqual(len(imgs), 1)
        for img in imgs:
            self.assertIsInstance(img, FetchedImage)
            self.assertTrue(img.data)


class TestBrowserCrawlerFactory(unittest.TestCase):
    def test_create_pinterest_browser(self):
        site = SiteConfig(name="p", crawler_type=CrawlerType.PINTEREST_BROWSER,
                          backend=CrawlerBackend.BROWSER,
                          urls=["https://jp.pinterest.com/pin/1028087421172953769/"])
        crawler = create_crawler(site, http_get=MagicMock(),
                                 browser_config=BrowserConfig())
        self.assertIsInstance(crawler, PinterestBrowserCrawler)


if __name__ == "__main__":
    unittest.main()
