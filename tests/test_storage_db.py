"""SQLite 存储层测试：图片记录 + 生成状态 + 扫描本地目录。"""
import os
import shutil
import tempfile
import unittest

from app.core.storage import StorageDB
from app.core.image_library import ImageLibrary


class TestStorageDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="db_test_")
        self.db_path = os.path.join(self.tmp, "library.db")
        self.db = StorageDB(self.db_path)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _img(self, image_id="img1", url="http://a.com/1.jpg", name="img1.jpg"):
        return {
            "image_id": image_id, "filename": name,
            "source_url": url, "content_hash": "h1",
            "site": "s1", "size": 10, "created_at": "2026-01-01T00:00:00+00:00",
        }

    def test_upsert_and_get_image(self):
        self.db.upsert_image(self._img())
        rec = self.db.get_image("img1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["filename"], "img1.jpg")
        self.assertEqual(self.db.count_images(), 1)

    def test_image_dedup_checks(self):
        self.db.upsert_image(self._img(url="http://a.com/1.jpg"))
        self.assertTrue(self.db.image_exists_by_url("http://a.com/1.jpg"))
        self.assertTrue(self.db.image_exists_by_hash("h1"))
        self.assertFalse(self.db.image_exists_by_url("http://b.com/x.jpg"))

    def test_generation_status(self):
        self.db.upsert_image(self._img())
        self.assertFalse(self.db.is_generated("img1"))
        self.db.mark_generated("img1", "out1.png,out2.png")
        self.assertTrue(self.db.is_generated("img1"))
        rec = self.db.get_generation("img1")
        self.assertEqual(rec.status, "generated")
        self.assertEqual(rec.output_files, "out1.png,out2.png")
        self.assertEqual(self.db.count_generated(), 1)

    def test_mark_pending_after_generated(self):
        self.db.upsert_image(self._img())
        self.db.mark_generated("img1")
        self.assertTrue(self.db.is_generated("img1"))
        self.db.mark_pending("img1")
        self.assertFalse(self.db.is_generated("img1"))

    def test_delete_image_cascades_generation(self):
        self.db.upsert_image(self._img())
        self.db.mark_generated("img1")
        self.assertTrue(self.db.is_generated("img1"))
        self.assertTrue(self.db.delete_image("img1"))
        self.assertEqual(self.db.count_images(), 0)
        self.assertFalse(self.db.is_generated("img1"))


class TestImageLibraryScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan_test_")
        self.lib_dir = os.path.join(self.tmp, "my_lib")
        os.makedirs(self.lib_dir, exist_ok=True)
        self.lib = ImageLibrary(self.lib_dir)

    def tearDown(self):
        self.lib.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_directory_discovers_new_files(self):
        # 预置两个图片文件（模拟手动放入）
        with open(os.path.join(self.lib_dir, "aaa.jpg"), "wb") as f:
            f.write(b"fake jpg 1")
        with open(os.path.join(self.lib_dir, "bbb.png"), "wb") as f:
            f.write(b"fake png 1")
        # 非图片文件不应被登记
        with open(os.path.join(self.lib_dir, "note.txt"), "w") as f:
            f.write("not image")

        added = self.lib.scan_directory()
        self.assertEqual(added, 2)
        self.assertEqual(self.lib.count(), 2)
        # 再次扫描不重复登记
        added2 = self.lib.scan_directory()
        self.assertEqual(added2, 0)
        # 能访问到扫描到的图片
        self.assertIsNotNone(self.lib.get_path("aaa"))
        self.assertIsNotNone(self.lib.get_path("bbb"))

    def test_generation_status_through_library(self):
        rec = self.lib.add_image(b"\x89PNG" + b"\x00" * 32,
                                 source_url="http://a.com/1.jpg")
        self.assertFalse(self.lib.is_generated(rec.image_id))
        self.lib.mark_generated(rec.image_id, "out.png")
        self.assertTrue(self.lib.is_generated(rec.image_id))
        self.assertEqual(self.lib.count_generated(), 1)


if __name__ == "__main__":
    unittest.main()
