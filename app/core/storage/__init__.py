"""本地 SQLite 存储层（图片记录 + 生成状态 + 数据迁移）。

为图片库与 ComfyUI 生成状态提供统一的本地持久化，替代 index.json。
对外暴露 `StorageDB` 与迁移工具 `migrate_library_dir`。
"""
from .db import StorageDB, GeneratedRecord, DownloadRecord
from .migrate import migrate_index_to_db, migrate_library_dir

__all__ = ["StorageDB", "GeneratedRecord", "DownloadRecord",
           "migrate_index_to_db", "migrate_library_dir"]
