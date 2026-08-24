"""待下载队列（downloads 表）的单元测试。"""
import os
import shutil
import tempfile
import unittest

from app.core.storage import StorageDB
from app.core.image_library import ImageLibrary


class TestDownloadsDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dl_db_")
        self.db_path = os.path.join(self.tmp, "library.db")
        self.db = StorageDB(self.db_path)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_list_pending(self):
        id1 = self.db.add_pending_download("http://a/1.jpg", "image/jpeg", "s1")
        self.assertIsNotNone(id1)
        self.db.add_pending_download("http://a/2.jpg", "image/png", "s1")
        pending = self.db.list_pending_downloads()
        self.assertEqual(len(pending), 2)
        self.assertEqual(self.db.count_pending_downloads(), 2)

    def test_dedup_by_url(self):
        id1 = self.db.add_pending_download("http://a/1.jpg")
        id2 = self.db.add_pending_download("http://a/1.jpg")  # 重复 URL
        self.assertEqual(id1, id2)  # 返回同一 image_id
        self.assertEqual(self.db.count_pending_downloads(), 1)

    def test_skip_if_already_in_images(self):
        # 先在 images 表有该 URL，则不再入队
        self.db.upsert_image({
            "image_id": "x", "filename": "x.jpg",
            "source_url": "http://a/1.jpg", "content_hash": "", "site": "",
            "size": 0, "created_at": ""})
        result = self.db.add_pending_download("http://a/1.jpg")
        self.assertIsNone(result)
        self.assertEqual(self.db.count_pending_downloads(), 0)

    def test_mark_done_and_failed(self):
        id1 = self.db.add_pending_download("http://a/1.jpg")
        self.db.mark_download_done(id1)
        self.assertEqual(self.db.count_pending_downloads(), 0)
        id2 = self.db.add_pending_download("http://a/2.jpg")
        self.db.mark_download_failed(id2)
        self.assertEqual(self.db.count_pending_downloads(), 0)  # failed 不再待下载
        rec = self.db.get_download(id2)
        self.assertEqual(rec.status, "failed")


class TestImageLibraryDownloads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lib_dl_")
        self.lib = ImageLibrary(os.path.join(self.tmp, "lib"))

    def tearDown(self):
        self.lib.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_enqueue_and_count(self):
        self.lib.enqueue_download("http://a/1.jpg", "image/jpeg", "s1")
        self.lib.enqueue_download("http://a/2.jpg")
        self.assertEqual(self.lib.count_pending_downloads(), 2)
        self.assertEqual(len(self.lib.list_pending_downloads()), 2)


if __name__ == "__main__":
    unittest.main()
