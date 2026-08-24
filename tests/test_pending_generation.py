"""JOIN 查询“已下载但未生成”图片的测试。"""
import os
import shutil
import tempfile
import unittest

from app.core.image_library import ImageLibrary


class TestPendingGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pending_gen_")
        self.lib_dir = os.path.join(self.tmp, "lib")
        os.makedirs(self.lib_dir, exist_ok=True)
        self.lib = ImageLibrary(self.lib_dir)

    def tearDown(self):
        self.lib.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pending_lists_only_not_generated(self):
        # 3 张图片：1 张生成过，2 张未生成
        r1 = self.lib.add_image(b"img1", source_url="http://a/1.jpg")
        r2 = self.lib.add_image(b"img2", source_url="http://a/2.jpg")
        r3 = self.lib.add_image(b"img3", source_url="http://a/3.jpg")
        self.lib.mark_generated(r2.image_id, "out2.png")

        pending = self.lib.list_pending_generation()
        pending_ids = {r.image_id for r in pending}
        self.assertIn(r1.image_id, pending_ids)
        self.assertNotIn(r2.image_id, pending_ids)  # 已生成，不应出现
        self.assertIn(r3.image_id, pending_ids)
        self.assertEqual(len(pending), 2)

    def test_pending_after_all_generated_is_empty(self):
        r1 = self.lib.add_image(b"img1", source_url="http://a/1.jpg")
        r2 = self.lib.add_image(b"img2", source_url="http://a/2.jpg")
        self.lib.mark_generated(r1.image_id)
        self.lib.mark_generated(r2.image_id)
        self.assertEqual(self.lib.list_pending_generation(), [])

    def test_pending_after_mark_pending_again(self):
        r1 = self.lib.add_image(b"img1", source_url="http://a/1.jpg")
        self.lib.mark_generated(r1.image_id)
        self.assertEqual(self.lib.list_pending_generation(), [])
        # 手动标记回 pending 后，应重新出现在待生成列表
        self.lib.mark_pending(r1.image_id)
        pending = self.lib.list_pending_generation()
        self.assertEqual([r.image_id for r in pending], [r1.image_id])


if __name__ == "__main__":
    unittest.main()
