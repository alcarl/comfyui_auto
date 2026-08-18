"""本地图片库模块测试：覆盖去重、入库、索引持久化。"""
import os
import shutil
import tempfile
import unittest

from app.core.image_library import ImageLibrary, ImageRecord


class TestImageLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lib_test_")
        self.lib = ImageLibrary(os.path.join(self.tmp, "my_lib"),
                                dedupe_by_url=True, dedupe_by_hash=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _png(self, color=b"\x89PNG"):
        # 仅用于构造非空的假图片字节
        return color + b"\x00" * 32

    def test_add_and_list(self):
        rec = self.lib.add_image(self._png(), source_url="http://a.com/1.jpg", site="s1")
        self.assertEqual(self.lib.count(), 1)
        self.assertTrue(os.path.exists(self.lib.get_path(rec.image_id)))
        self.assertIn(rec, self.lib.list_images())

    def test_dedupe_by_url(self):
        self.lib.add_image(self._png(b"A"), source_url="http://a.com/1.jpg")
        # 不同内容但相同 URL -> 应判重并复用已有记录
        rec2 = self.lib.add_image(self._png(b"B"), source_url="http://a.com/1.jpg/")
        self.assertEqual(self.lib.count(), 1)
        self.assertEqual(rec2.source_url, "http://a.com/1.jpg")

    def test_dedupe_by_hash(self):
        self.lib.add_image(self._png(b"X"), source_url="http://a.com/1.jpg")
        # 相同内容不同 URL -> 哈希去重生效
        rec2 = self.lib.add_image(self._png(b"X"), source_url="http://b.com/2.jpg")
        self.assertEqual(self.lib.count(), 1)

    def test_normalize_url_strips_query_and_trailing_slash(self):
        self.assertEqual(
            ImageRecord.normalize_url("https://x.com/p/1/?utm=abc"),
            "https://x.com/p/1",
        )

    def test_persistence_across_reload(self):
        self.lib.add_image(self._png(), source_url="http://a.com/1.jpg")
        # 重新加载（模拟重启）
        reloaded = ImageLibrary(os.path.join(self.tmp, "my_lib"),
                                dedupe_by_url=True)
        self.assertEqual(reloaded.count(), 1)
        # 重复 URL 不应重复入库
        reloaded.add_image(self._png(b"Z"), source_url="http://a.com/1.jpg")
        self.assertEqual(reloaded.count(), 1)

    def test_remove(self):
        rec = self.lib.add_image(self._png(), source_url="http://a.com/1.jpg")
        self.assertTrue(self.lib.remove(rec.image_id))
        self.assertEqual(self.lib.count(), 0)
        self.assertIsNone(self.lib.get_path(rec.image_id))

    def test_resolve_classmethod(self):
        lib = ImageLibrary.resolve(self.tmp, "another", dedupe_by_url=True)
        self.assertTrue(lib.library_dir.endswith(os.path.join("another")))
        lib.add_image(self._png(), source_url="http://a.com/9.jpg")
        self.assertEqual(lib.count(), 1)


if __name__ == "__main__":
    unittest.main()
