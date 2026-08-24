"""SQLite 并发访问测试：生成与下载两个连接同时读写不阻塞。"""
import os
import shutil
import tempfile
import threading
import time
import unittest

from app.core.storage import StorageDB


class TestDBConcurrency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="db_con_")
        self.db_path = os.path.join(self.tmp, "library.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_concurrent_read_write(self):
        """两个连接分别在线程里同时读写，不应互相阻塞卡死。"""
        conn_a = StorageDB(self.db_path)  # 模拟生成连接
        conn_b = StorageDB(self.db_path)  # 模拟下载连接
        done = []
        errors = []

        def writer_loop(conn, prefix):
            try:
                for i in range(20):
                    conn.upsert_image({
                        "image_id": f"{prefix}_{i}", "filename": f"{prefix}_{i}.jpg",
                        "source_url": f"http://x/{prefix}_{i}.jpg",
                        "content_hash": "", "site": "", "size": 1,
                        "created_at": ""})
                    conn.mark_generated(f"{prefix}_{i}", "out.png")
                done.append(prefix)
            except Exception as e:
                errors.append(f"{prefix}: {e}")

        t1 = threading.Thread(target=writer_loop, args=(conn_a, "gen"))
        t2 = threading.Thread(target=writer_loop, args=(conn_b, "dl"))
        t1.start()
        t2.start()
        # 等待最多 15 秒，确认两个线程都完成（不卡死）
        t1.join(timeout=15)
        t2.join(timeout=15)
        self.assertFalse(t1.is_alive(), "生成连接线程卡死")
        self.assertFalse(t2.is_alive(), "下载连接线程卡死")
        self.assertEqual(errors, [])
        self.assertEqual(set(done), {"gen", "dl"})
        # 验证数据都写入
        self.assertEqual(conn_a.count_images(), 40)
        conn_a.close()
        conn_b.close()


if __name__ == "__main__":
    unittest.main()
