"""本地图片库：管理本地图片的存储、索引与防重复。

设计目标（解耦、可测试）：
- 不依赖任何网络与 UI，仅依赖文件系统与本地的 index.json 元数据。
- 防重复通过来源 URL（默认）或内容哈希实现，避免重复下载同一张图。
- 上层 crawler / pipeline 通过简洁接口与之交互。
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from typing import List, Optional

from .models import ImageRecord

INDEX_FILENAME = "index.json"


class ImageLibrary:
    """一个本地图片库（对应一个目录）。"""

    def __init__(self, library_dir: str, dedupe_by_url: bool = True,
                 dedupe_by_hash: bool = False):
        """
        :param library_dir: 图片库目录（绝对路径或相对路径）
        :param dedupe_by_url: 是否通过来源 URL 去重（默认开启）
        :param dedupe_by_hash: 是否通过内容哈希去重（可选）
        """
        self.library_dir = os.path.abspath(library_dir)
        self.dedupe_by_url = dedupe_by_url
        self.dedupe_by_hash = dedupe_by_hash
        self._lock = threading.RLock()
        self._records: dict[str, ImageRecord] = {}
        os.makedirs(self.library_dir, exist_ok=True)
        self._load_index()

    # ------------------------------------------------------------------ #
    # 索引持久化
    # ------------------------------------------------------------------ #
    @property
    def index_path(self) -> str:
        return os.path.join(self.library_dir, INDEX_FILENAME)

    def _load_index(self) -> None:
        if not os.path.exists(self.index_path):
            self._records = {}
            return
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._records = {r["image_id"]: ImageRecord(**r) for r in data}
        except (json.JSONDecodeError, KeyError, TypeError):
            # 索引损坏时重建为空，不丢图片文件
            self._records = {}

    def _save_index(self) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump() for r in self._records.values()],
                      f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # 去重判定
    # ------------------------------------------------------------------ #
    def exists_by_url(self, url: str) -> bool:
        norm = ImageRecord.normalize_url(url)
        if not norm:
            return False
        return any(ImageRecord.normalize_url(r.source_url) == norm
                   for r in self._records.values())

    def exists_by_hash(self, content_hash: str) -> bool:
        if not content_hash:
            return False
        return any(r.content_hash == content_hash for r in self._records.values())

    def is_duplicate(self, url: str = "", content_hash: str = "") -> bool:
        """综合判定是否为重复图片（依据初始化时的去重开关）。"""
        if self.dedupe_by_url and self.exists_by_url(url):
            return True
        if self.dedupe_by_hash and self.exists_by_hash(content_hash):
            return True
        return False

    # ------------------------------------------------------------------ #
    # 写入 / 读取
    # ------------------------------------------------------------------ #
    def _make_filename(self, image_id: str, ext: str) -> str:
        ext = (ext or "jpg").lstrip(".")
        return f"{image_id}.{ext}"

    def add_image(self, data: bytes, *, source_url: str = "",
                  site: str = "", image_id: Optional[str] = None,
                  ext: str = "jpg") -> ImageRecord:
        """将图片字节写入库，并返回记录。若已存在（重复）则直接返回已有记录。

        :raises ValueError: 当 content 为空时
        """
        if not data:
            raise ValueError("图片数据为空，无法入库")

        content_hash = ImageRecord.compute_hash(data)

        with self._lock:
            # 去重：重复则直接复用已有记录，不重复落盘
            if self.dedupe_by_url and source_url:
                norm = ImageRecord.normalize_url(source_url)
                for r in self._records.values():
                    if ImageRecord.normalize_url(r.source_url) == norm:
                        return r
            if self.dedupe_by_hash and content_hash:
                for r in self._records.values():
                    if r.content_hash == content_hash:
                        return r

            # 生成稳定的 image_id
            if image_id is None:
                image_id = content_hash[:16] or f"{len(self._records)}"

            # 避免 id 冲突
            base_id = image_id
            counter = 1
            while image_id in self._records:
                image_id = f"{base_id}_{counter}"
                counter += 1

            filename = self._make_filename(image_id, ext)
            filepath = os.path.join(self.library_dir, filename)
            with open(filepath, "wb") as f:
                f.write(data)

            record = ImageRecord(
                image_id=image_id,
                filename=filename,
                source_url=source_url,
                content_hash=content_hash,
                site=site,
                size=len(data),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._records[image_id] = record
            self._save_index()
            return record

    def get_record(self, image_id: str) -> Optional[ImageRecord]:
        return self._records.get(image_id)

    def get_path(self, image_id: str) -> Optional[str]:
        """返回图片本地绝对路径，若不存在返回 None。"""
        rec = self._records.get(image_id)
        if rec is None:
            return None
        path = os.path.join(self.library_dir, rec.filename)
        return path if os.path.exists(path) else None

    def list_images(self) -> List[ImageRecord]:
        """返回所有图片记录（按入库时间升序）。"""
        return sorted(self._records.values(), key=lambda r: r.created_at)

    def remove(self, image_id: str) -> bool:
        """删除一条记录及其文件。"""
        with self._lock:
            rec = self._records.get(image_id)
            if rec is None:
                return False
            path = os.path.join(self.library_dir, rec.filename)
            if os.path.exists(path):
                os.remove(path)
            del self._records[image_id]
            self._save_index()
            return True

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        """清空整个图片库（含文件）。谨慎使用。"""
        with self._lock:
            for rec in list(self._records.values()):
                path = os.path.join(self.library_dir, rec.filename)
                if os.path.exists(path):
                    os.remove(path)
            self._records = {}
            self._save_index()

    @classmethod
    def resolve(cls, root_dir: str, library_name: str,
                dedupe_by_url: bool = True,
                dedupe_by_hash: bool = False) -> "ImageLibrary":
        """根据根目录和库名解析出图片库实例（库名作为子目录）。"""
        library_dir = os.path.join(os.path.abspath(root_dir), library_name)
        return cls(library_dir, dedupe_by_url=dedupe_by_url,
                   dedupe_by_hash=dedupe_by_hash)
