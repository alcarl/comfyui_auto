"""tags 表（WD14 反推提示词）的数据库层测试。"""
import os
import shutil
import tempfile
import unittest

from app.core.storage.db import StorageDB
from app.core.image_library import ImageLibrary


class TestTagsDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tags_db_")
        self.db = StorageDB(os.path.join(self.tmp, "library.db"))

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _img(self, iid="img1"):
        return {"image_id": iid, "filename": f"{iid}.jpg",
                "source_url": f"http://a/{iid}.jpg", "content_hash": "",
                "site": "", "size": 1, "created_at": "2026-01-01T00:00:00"}

    def test_set_and_get_tags(self):
        self.db.upsert_image(self._img())
        n = self.db.set_tags("img1", "img1.jpg", ["1girl", "solo", "smile"])
        self.assertEqual(n, 3)
        self.assertEqual(self.db.get_tags("img1"), ["1girl", "smile", "solo"])
        self.assertTrue(self.db.has_tags("img1"))
        self.assertFalse(self.db.has_tags("img2"))

    def test_set_tags_replaces_all(self):
        self.db.upsert_image(self._img())
        self.db.set_tags("img1", "img1.jpg", ["a", "b", "c"])
        # 全量替换：旧标签被清掉
        self.db.set_tags("img1", "img1.jpg", ["x", "y"])
        self.assertEqual(self.db.get_tags("img1"), ["x", "y"])

    def test_set_tags_ignores_empty_and_strips(self):
        self.db.upsert_image(self._img())
        n = self.db.set_tags("img1", "img1.jpg", ["  1girl ", "", "   "])
        self.assertEqual(n, 1)
        self.assertEqual(self.db.get_tags("img1"), ["1girl"])

    def test_list_distinct_tags(self):
        self.db.upsert_image(self._img("a"))
        self.db.upsert_image(self._img("b"))
        self.db.set_tags("a", "a.jpg", ["1girl", "solo"])
        self.db.set_tags("b", "b.jpg", ["solo", "cat"])
        self.assertEqual(self.db.list_distinct_tags(), ["1girl", "cat", "solo"])

    def test_search_image_ids_by_tag(self):
        self.db.upsert_image(self._img("a"))
        self.db.upsert_image(self._img("b"))
        self.db.set_tags("a", "a.jpg", ["1girl", "long_hair"])
        self.db.set_tags("b", "b.jpg", ["cat", "animal_ears"])
        # 部分匹配
        self.assertEqual(self.db.search_image_ids_by_tag("girl"), ["a"])
        self.assertEqual(self.db.search_image_ids_by_tag("hair"), ["a"])
        self.assertEqual(self.db.search_image_ids_by_tag("ears"), ["b"])
        # 空关键词
        self.assertEqual(self.db.search_image_ids_by_tag(""), [])
        self.assertEqual(self.db.search_image_ids_by_tag("zzz"), [])

    def test_delete_tags_for_image(self):
        self.db.upsert_image(self._img())
        self.db.set_tags("img1", "img1.jpg", ["a", "b"])
        self.assertEqual(self.db.delete_tags_for_image("img1"), 2)
        self.assertEqual(self.db.get_tags("img1"), [])

    def test_delete_image_cascades_tags(self):
        self.db.upsert_image(self._img())
        self.db.set_tags("img1", "img1.jpg", ["a", "b"])
        self.assertTrue(self.db.delete_image("img1"))
        self.assertEqual(self.db.get_tags("img1"), [])
        self.assertFalse(self.db.has_tags("img1"))


class TestTagsThroughLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tags_lib_")
        self.root = os.path.join(self.tmp, "root")
        self.lib_dir = os.path.join(self.root, "default")
        self.out_dir = os.path.join(self.root, "outputs")
        os.makedirs(self.lib_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)
        self.lib = ImageLibrary(self.lib_dir)

    def tearDown(self):
        self.lib.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_library_tags_proxy(self):
        rec = self.lib.add_image(b"\x89PNG" + b"\x00" * 32,
                                 source_url="http://a/1.jpg")
        iid = rec.image_id
        self.assertEqual(self.lib.set_tags(iid, rec.filename, ["1girl", "solo"]), 2)
        self.assertEqual(self.lib.get_tags(iid), ["1girl", "solo"])
        self.assertTrue(self.lib.has_tags(iid))
        self.assertEqual(self.lib.search_image_ids_by_tag("1girl"), [iid])

    def test_generated_output_path(self):
        rec = self.lib.add_image(b"\x89PNG" + b"\x00" * 32,
                                 source_url="http://a/1.jpg")
        self.assertIsNone(self.lib.generated_output_path(rec.image_id))
        out = os.path.join(self.out_dir, f"{rec.image_id}.png")
        with open(out, "wb") as f:
            f.write(b"fake out")
        self.assertEqual(self.lib.generated_output_path(rec.image_id), out)

    def test_generated_output_path_uses_db_when_recorded(self):
        """DB 中 mark_generated 记下了真实输出文件名，应以它为准。

        防止按 stem 模糊匹配时把别人/旧版的生成图当成目标。
        """
        rec = self.lib.add_image(b"\x89PNG" + b"\x00" * 32,
                                 source_url="http://a/1.jpg")
        iid = rec.image_id
        # outputs/ 里**多**放几个相似前缀的文件（制造容易匹配错的场景）
        for name in (f"{iid}.png", f"{iid}_legacy.png", "decoy.png"):
            with open(os.path.join(self.out_dir, name), "wb") as f:
                f.write(b"x")
        # 在 DB 里只把 decoy 标记为这张图的生成图（模拟错位）
        self.lib.mark_generated(iid, "decoy.png")
        self.assertEqual(
            self.lib.generated_output_path(iid),
            os.path.join(self.out_dir, "decoy.png"))
        # 把 decoy 删掉，DB 还有记录但文件不在 → 应回退到精确 stem
        os.remove(os.path.join(self.out_dir, "decoy.png"))
        self.assertEqual(
            self.lib.generated_output_path(iid),
            os.path.join(self.out_dir, f"{iid}.png"))
        # DB 删掉记录 → 仍按精确 stem 找到遗留文件
        self.lib.db.delete_generation(iid)
        self.assertEqual(
            self.lib.generated_output_path(iid),
            os.path.join(self.out_dir, f"{iid}.png"))

    def test_remove_cleans_outputs_and_tags(self):
        rec = self.lib.add_image(b"\x89PNG" + b"\x00" * 32,
                                 source_url="http://a/1.jpg")
        iid = rec.image_id
        self.lib.set_tags(iid, rec.filename, ["1girl"])
        out = os.path.join(self.out_dir, f"{iid}.png")
        with open(out, "wb") as f:
            f.write(b"fake out")
        self.assertTrue(self.lib.remove(iid))
        # 原图 / 生成图文件与 tags 记录全部清理
        self.assertFalse(os.path.exists(out))
        self.assertFalse(os.path.exists(os.path.join(self.lib_dir, rec.filename)))
        self.assertEqual(self.lib.get_tags(iid), [])
        self.assertIsNone(self.lib.get_record(iid))


if __name__ == "__main__":
    unittest.main()
