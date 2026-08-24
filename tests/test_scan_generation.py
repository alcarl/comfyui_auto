"""扫描本地时同步生成状态的测试。"""
import os
import shutil
import tempfile
import unittest

from app.core.image_library import ImageLibrary


class TestScanGenerationSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan_gen_")
        # 模拟 <root>/default 与 <root>/outputs
        self.root = os.path.join(self.tmp, "root")
        self.lib_dir = os.path.join(self.root, "default")
        self.output_dir = os.path.join(self.root, "outputs")
        os.makedirs(self.lib_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        # 预置图片文件
        with open(os.path.join(self.lib_dir, "img1.jpg"), "wb") as f:
            f.write(b"fake jpg")
        with open(os.path.join(self.lib_dir, "img2.jpg"), "wb") as f:
            f.write(b"fake jpg 2")
        # img1 已有生成文件，img2 没有
        with open(os.path.join(self.output_dir, "img1.png"), "wb") as f:
            f.write(b"fake png out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_lib(self):
        return ImageLibrary(self.lib_dir)

    def test_scan_marks_generated_when_output_exists(self):
        lib = self._make_lib()
        try:
            # 扫描：登记图片 + 同步生成状态
            added = lib.scan_directory()
            self.assertEqual(added, 2)
            # img1 有生成文件 -> 应标记已生成
            self.assertTrue(lib.is_generated("img1"))
            # img2 无生成文件 -> 未生成
            self.assertFalse(lib.is_generated("img2"))
            self.assertEqual(lib.count_generated(), 1)
        finally:
            lib.close()

    def test_scan_does_not_duplicate_generation(self):
        lib = self._make_lib()
        try:
            lib.scan_directory()
            lib.scan_directory()  # 再次扫描，不应重复标记或新增
            self.assertEqual(lib.count_generated(), 1)
            self.assertEqual(lib.count(), 2)
        finally:
            lib.close()


if __name__ == "__main__":
    unittest.main()
