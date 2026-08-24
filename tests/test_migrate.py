"""迁移测试：index.json 无缝迁移到 SQLite。"""
import json
import os
import shutil
import tempfile
import unittest

from app.core.storage.migrate import migrate_index_to_db, migrate_library_dir
from app.core.storage import StorageDB


class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="migrate_test_")
        self.lib_dir = os.path.join(self.tmp, "lib")
        os.makedirs(self.lib_dir, exist_ok=True)
        self.index_path = os.path.join(self.lib_dir, "index.json")
        self.records = [
            {"image_id": "a1", "filename": "a1.jpg",
             "source_url": "http://x.com/1.jpg", "content_hash": "h1",
             "site": "s1", "width": None, "height": None,
             "size": 100, "created_at": "2026-01-01T00:00:00+00:00"},
            {"image_id": "a2", "filename": "a2.png",
             "source_url": "http://x.com/2.png", "content_hash": "h2",
             "site": "s1", "width": None, "height": None,
             "size": 200, "created_at": "2026-01-01T00:00:01+00:00"},
        ]
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migrate_imports_all(self):
        db = StorageDB(os.path.join(self.lib_dir, "library.db"))
        try:
            r = migrate_index_to_db(db, self.index_path, backup=False)
            self.assertEqual(r["total"], 2)
            self.assertEqual(r["imported"], 2)
            self.assertEqual(r["skipped"], 0)
            self.assertIsNotNone(db.get_image("a1"))
            self.assertIsNotNone(db.get_image("a2"))
            self.assertEqual(db.count_images(), 2)
        finally:
            db.close()

    def test_migrate_is_idempotent(self):
        db = StorageDB(os.path.join(self.lib_dir, "library.db"))
        try:
            migrate_index_to_db(db, self.index_path, backup=False)
            r2 = migrate_index_to_db(db, self.index_path, backup=False)
            self.assertEqual(r2["imported"], 0)
            self.assertEqual(r2["skipped"], 2)
            self.assertEqual(db.count_images(), 2)
        finally:
            db.close()

    def test_migrate_library_dir_creates_backup(self):
        migrate_library_dir(self.lib_dir, backup=True)
        self.assertTrue(os.path.exists(self.index_path + ".bak"))
        # 数据已导入
        db = StorageDB(os.path.join(self.lib_dir, "library.db"))
        try:
            self.assertEqual(db.count_images(), 2)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
