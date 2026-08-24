"""数据迁移：将旧版 index.json 图片库元数据迁移到 SQLite 数据库。

目标：无缝迁移，不丢失任何已存在的数据。
- 读取 index.json 的全部记录。
- 逐条写入数据库（按 image_id 去重，已存在的记录不覆盖）。
- 迁移完成后可将 index.json 重命名为 .bak 备份（不删除原文件）。
- 幂等：重复执行不会产生重复数据。
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, List, Optional

from .db import StorageDB

# 允许被迁移的 index.json 字段
_ALLOWED_FIELDS = (
    "image_id", "filename", "source_url", "content_hash", "site",
    "width", "height", "size", "created_at",
)


def _read_index(index_path: str) -> List[Dict[str, Any]]:
    """读取 index.json 中的记录列表。"""
    if not os.path.exists(index_path):
        return []
    with open(index_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("images"), list):
        return data["images"]
    return []


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """只保留数据库支持的字段，并保证必要字段存在。"""
    clean = {
        "image_id": str(rec.get("image_id") or ""),
        "filename": str(rec.get("filename") or ""),
        "source_url": str(rec.get("source_url") or ""),
        "content_hash": str(rec.get("content_hash") or ""),
        "site": str(rec.get("site") or ""),
        "width": rec.get("width"),
        "height": rec.get("height"),
        "size": int(rec.get("size") or 0),
        "created_at": str(rec.get("created_at") or ""),
    }
    return clean


def migrate_index_to_db(db: StorageDB, index_path: str,
                        backup: bool = True) -> Dict[str, int]:
    """把 index.json 中的图片记录迁移到数据库。

    :param db: 目标 StorageDB 实例
    :param index_path: index.json 路径
    :param backup: 迁移成功后是否把 index.json 备份为 .json.bak
    :return: {"total": 总数, "imported": 新增导入数, "skipped": 跳过(已存在)数}
    """
    records = _read_index(index_path)
    total = len(records)
    imported = 0
    skipped = 0
    for rec in records:
        clean = _sanitize(rec)
        image_id = clean["image_id"]
        if not image_id:
            continue
        # 已存在则不覆盖（保留数据库中原有记录）
        if db.get_image(image_id) is not None:
            skipped += 1
            continue
        db.upsert_image(clean)
        imported += 1

    # 迁移成功后备份原 index.json（不删除，避免误删数据）
    if backup and total > 0:
        backup_path = index_path + ".bak"
        try:
            shutil.copy2(index_path, backup_path)
        except OSError:
            pass

    return {"total": total, "imported": imported, "skipped": skipped}


def migrate_library_dir(library_dir: str,
                        db_path: Optional[str] = None,
                        backup: bool = True) -> Dict[str, int]:
    """便捷入口：按图片库目录执行迁移。

    :param library_dir: 图片库目录（含 index.json 与图片文件）
    :param db_path: 数据库文件路径（默认 <library_dir>/library.db）
    :param backup: 迁移成功后是否备份 index.json
    """
    index_path = os.path.join(library_dir, "index.json")
    db = StorageDB(db_path or os.path.join(library_dir, "library.db"))
    try:
        return migrate_index_to_db(db, index_path, backup=backup)
    finally:
        db.close()
