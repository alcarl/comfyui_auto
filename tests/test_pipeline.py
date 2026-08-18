"""编排层与配置层测试：端到端串联（全部使用注入桩，不触网）。"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from app.core.config.manager import CoreConfigManager
from app.core.config.models import (
    CoreConfig, SiteConfig, CrawlerType, CrawlerConfig, ComfyUIConfig,
    LibraryConfig,
)
from app.core.pipeline import Pipeline, PipelineResult


class StubTransport:
    def upload_image(self, image_path, image_data=None, name="image.png"):
        return {"name": "up.png"}

    def post_prompt(self, prompt, client_id):
        return {"prompt_id": "pid-x"}

    def get_history(self, prompt_id):
        import base64
        png = base64.b64encode(b"\x89PNG gen").decode()
        return {prompt_id: {"outputs": {
            "20": {"images": [{"filename": "g.png", "data": png}]}}}}


def fake_http_get(url):
    # 任何图片墙 URL 都返回含一张 pinimg 图片的 HTML
    html = (b'<img srcset="https://i.pinimg.com/736x/aa/bb/cc/x.jpg 736w">'
            b'<script>{"img":"https://i.pinimg.com/originals/aa/bb/cc/x.jpg"}</script>')
    if "pin" in url or "pinterest" in url:
        return html, "text/html"
    return b"\x89PNG fakeimg" + b"\x00" * 32, "image/jpeg"


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pipe_test_")
        root = os.path.join(self.tmp, "libraries")
        cfg = CoreConfig(
            library=LibraryConfig(root_dir=root, dedupe_by_url=True),
            crawler=CrawlerConfig(output_library="default", max_concurrency=2),
            comfyui=ComfyUIConfig(workflow_path=""),
            sites=[SiteConfig(
                name="p_demo", crawler_type=CrawlerType.PINTEREST,
                urls=["https://jp.pinterest.com/pin/1028087421172953769/"])],
        )
        self.pipeline = Pipeline(config=cfg, http_get=fake_http_get)
        # 替换 ComfyUI 传输层为桩
        self.pipeline._orig_make_client = self.pipeline.generate_from_library
        self._transport = StubTransport()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _patch_client(self):
        from app.core.comfyui import ComfyUIClient
        orig = ComfyUIClient.__init__
        def patched(self_c, config, transport=None):
            orig(self_c, config, transport=self._transport)
        ComfyUIClient.__init__ = patched
        return ComfyUIClient

    def test_crawl_to_library_dedupes(self):
        lib = self.pipeline.crawl_to_library()
        self.assertGreaterEqual(lib.count(), 1)
        # 再次抓取相同站点，因 URL 去重，数量不应增长
        lib2 = self.pipeline.crawl_to_library()
        self.assertEqual(lib2.count(), lib.count())

    def test_run_full_pipeline(self):
        # 写入临时工作流文件，避免 load_workflow 失败
        import json
        wf = {
            "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
            "20": {"class_type": "SaveImage", "inputs": {}},
        }
        wf_path = os.path.join(self.tmp, "wf.json")
        with open(wf_path, "w") as f:
            json.dump(wf, f)
        self.pipeline.config.comfyui.workflow_path = wf_path

        # 注入桩 transport
        import app.core.comfyui.client as client_mod
        real_init = client_mod.ComfyUIClient.__init__
        client_mod.ComfyUIClient.__init__ = (
            lambda self_c, config, transport=None: real_init(self_c, config, transport=StubTransport()))

        result = self.pipeline.run()
        self.assertIsInstance(result, PipelineResult)
        self.assertGreaterEqual(result.crawled_total, 1)
        self.assertGreaterEqual(result.generated_total, 1)
        self.assertEqual(len(result.errors), 0)


class TestCoreConfigManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmp, "core_config.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        CoreConfigManager.reset()

    def test_load_default_and_persist(self):
        mgr = CoreConfigManager(self.cfg_path)
        self.assertGreaterEqual(len(mgr.config.sites), 1)
        # 修改并保存
        mgr.config.crawler.max_concurrency = 8
        mgr.save()
        # 重新加载
        mgr2 = CoreConfigManager(self.cfg_path)
        self.assertEqual(mgr2.config.crawler.max_concurrency, 8)

    def test_add_site(self):
        mgr = CoreConfigManager(self.cfg_path)
        mgr.add_site(SiteConfig(name="new_site", crawler_type=CrawlerType.PINTEREST,
                                urls=["https://x.com"]))
        self.assertIsNotNone(mgr.get_site("new_site"))


if __name__ == "__main__":
    unittest.main()
