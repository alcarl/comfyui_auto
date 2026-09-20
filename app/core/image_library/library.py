"""本地图片库：管理本地图片的存储、索引与防重复（基于 SQLite）。

设计目标（解耦、可测试）：
- 元数据持久化使用本地 SQLite（StorageDB），不再依赖 index.json。
- 防重复通过来源 URL（默认）或内容哈希实现，避免重复下载同一张图。
- 提供“扫描本地目录同步数据库”能力，供 UI 开关“打开时”增量更新状态。
- 上层 crawler / pipeline 通过简洁接口与之交互。
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import List, Optional

from .models import ImageRecord
from ..storage import StorageDB

# 保留历史文件名常量（原 index.json），供兼容导出；持久化已改用 SQLite。
INDEX_FILENAME = "index.json"


class ImageLibrary:
    """一个本地图片库（对应一个目录，含数据库）。"""

    def __init__(self, library_dir: str, dedupe_by_url: bool = True,
                 dedupe_by_hash: bool = False, db_path: Optional[str] = None):
        """
        :param library_dir: 图片库目录（绝对路径或相对路径）
        :param dedupe_by_url: 是否通过来源 URL 去重（默认开启）
        :param dedupe_by_hash: 是否通过内容哈希去重（可选）
        :param db_path: 数据库文件路径（默认在 library_dir 下）
        """
        self.library_dir = os.path.abspath(library_dir)
        self.dedupe_by_url = dedupe_by_url
        self.dedupe_by_hash = dedupe_by_hash
        self._lock = threading.RLock()
        os.makedirs(self.library_dir, exist_ok=True)
        if db_path is None:
            db_path = os.path.join(self.library_dir, "library.db")
        self.db = StorageDB(db_path)

    # ------------------------------------------------------------------ #
    # 去重判定
    # ------------------------------------------------------------------ #
    def exists_by_url(self, url: str) -> bool:
        norm = ImageRecord.normalize_url(url)
        if not norm:
            return False
        # 在 DB 中按规范化 URL 查找
        for rec in self.list_images():
            if ImageRecord.normalize_url(rec.source_url) == norm:
                return True
        return False

    def exists_by_hash(self, content_hash: str) -> bool:
        if not content_hash:
            return False
        return self.db.image_exists_by_hash(content_hash)

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

    def _record_to_dict(self, rec: ImageRecord) -> dict:
        return {
            "image_id": rec.image_id,
            "filename": rec.filename,
            "source_url": rec.source_url,
            "content_hash": rec.content_hash,
            "site": rec.site,
            "width": rec.width,
            "height": rec.height,
            "size": rec.size,
            "created_at": rec.created_at,
        }

    def _dict_to_record(self, d: dict) -> ImageRecord:
        return ImageRecord(
            image_id=d["image_id"], filename=d["filename"],
            source_url=d.get("source_url", ""),
            content_hash=d.get("content_hash", ""),
            site=d.get("site", ""), width=d.get("width"),
            height=d.get("height"), size=d.get("size", 0),
            created_at=d.get("created_at", ""),
        )

    def add_image(self, data: bytes, *, source_url: str = "",
                  site: str = "", image_id: Optional[str] = None,
                  ext: str = "jpg") -> ImageRecord:
        """将图片字节写入库，并返回记录。若已存在（重复）则直接返回已有记录。

        :raises ValueError: 当 data 为空时
        """
        if not data:
            raise ValueError("图片数据为空，无法入库")

        content_hash = ImageRecord.compute_hash(data)

        with self._lock:
            # 去重：重复则直接复用已有记录，不重复落盘
            if self.dedupe_by_url and source_url:
                norm = ImageRecord.normalize_url(source_url)
                for rec in self.list_images():
                    if ImageRecord.normalize_url(rec.source_url) == norm:
                        return rec
            if self.dedupe_by_hash and content_hash:
                for rec in self.list_images():
                    if rec.content_hash == content_hash:
                        return rec

            # 生成稳定的 image_id
            if image_id is None:
                image_id = content_hash[:16] or f"{self.count()}"

            # 避免 id 冲突
            base_id = image_id
            counter = 1
            while self.get_record(image_id) is not None:
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
            self.db.upsert_image(self._record_to_dict(record))
            return record

    def get_record(self, image_id: str) -> Optional[ImageRecord]:
        d = self.db.get_image(image_id)
        return self._dict_to_record(d) if d else None

    def get_path(self, image_id: str) -> Optional[str]:
        """返回图片本地绝对路径，若不存在返回 None。"""
        rec = self.get_record(image_id)
        if rec is None:
            return None
        path = os.path.join(self.library_dir, rec.filename)
        return path if os.path.exists(path) else None

    def list_images(self) -> List[ImageRecord]:
        """返回所有图片记录（按入库时间升序）。"""
        return [self._dict_to_record(d) for d in self.db.list_images()]

    def remove(self, image_id: str) -> bool:
        """删除一条记录及其文件（原图 + 生成图 + 反推提示词）。"""
        with self._lock:
            rec = self.get_record(image_id)
            if rec is None:
                return False
            path = os.path.join(self.library_dir, rec.filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            # 同时删除 ComfyUI 输出目录中的生成图（<image_id>.<ext>）
            out_dir = self._output_dir()
            if os.path.isdir(out_dir):
                for fname in os.listdir(out_dir):
                    if os.path.splitext(fname)[0] == image_id:
                        try:
                            os.remove(os.path.join(out_dir, fname))
                        except OSError:
                            pass
            # delete_image 级联清理 generations 与 tags 记录
            self.db.delete_image(image_id)
            return True

    def reset_generation(self, image_id: str) -> None:
        """删除该图片的生成结果，使其回到"未生成"（可被生成任务扫描）。

        与 ``remove`` 的区别：``remove`` 连原图一起删；本方法只清生成侧：

        1. 删 outputs/ 目录里 stem==image_id 的生成图文件
        2. 删 generations 记录（status / output_files 绑定 / generated_at）
           —— LEFT JOIN 视角下该图片回到待生成，list_pending_generation
           会重新包含它
        3. 删 tags 记录（旧生成图的反推标签已随文件失效）

        原图文件与 images 主记录均保留。
        """
        with self._lock:
            out_dir = self._output_dir()
            if os.path.isdir(out_dir):
                for fname in os.listdir(out_dir):
                    if os.path.splitext(fname)[0] == image_id:
                        try:
                            os.remove(os.path.join(out_dir, fname))
                        except OSError:
                            pass
            self.db.delete_generation(image_id)
            self.db.delete_tags(image_id)

    def count(self) -> int:
        return self.db.count_images()

    def clear(self) -> None:
        """清空整个图片库（含文件与记录）。谨慎使用。"""
        with self._lock:
            for rec in self.list_images():
                path = os.path.join(self.library_dir, rec.filename)
                if os.path.exists(path):
                    os.remove(path)
            # 删除所有图片记录
            for rec in self.list_images():
                self.db.delete_image(rec.image_id)

    # ------------------------------------------------------------------ #
    # 扫描本地目录，同步数据库
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # 生成状态（代理到 StorageDB）
    # ------------------------------------------------------------------ #
    def is_generated(self, image_id: str) -> bool:
        """判断该图片是否已在 ComfyUI 中生成过（从数据库判断）。"""
        return self.db.is_generated(image_id)

    def mark_generated(self, image_id: str, output_files: str = "") -> None:
        """标记该图片已生成。"""
        self.db.mark_generated(image_id, output_files)

    def mark_pending(self, image_id: str) -> None:
        """标记该图片未生成。"""
        self.db.mark_pending(image_id)

    def count_generated(self) -> int:
        return self.db.count_generated()

    # ------------------------------------------------------------------ #
    # 反推提示词（WD14 tagger，代理到 StorageDB）
    # ------------------------------------------------------------------ #
    def set_tags(self, image_id: str, filename: str, tags: list) -> int:
        """全量替换某张图片的反推提示词（每个提示词一行记录）。"""
        return self.db.set_tags(image_id, filename, tags)

    def get_tags(self, image_id: str) -> list:
        """返回某张图片的全部反推提示词。"""
        return self.db.get_tags(image_id)

    def has_tags(self, image_id: str) -> bool:
        """判断某张图片是否已有反推提示词。"""
        return self.db.has_tags(image_id)

    def list_distinct_tags(self) -> list:
        """列出全部去重后的提示词（供筛选）。"""
        return self.db.list_distinct_tags()

    def search_image_ids_by_tag(self, keyword: str) -> list:
        """按提示词关键词筛选图片 id 列表。"""
        return self.db.search_image_ids_by_tag(keyword)

    def generated_output_path(self, image_id: str) -> Optional[str]:
        """返回该图片的生成图路径。

        权威来源是数据库 ``generations.output_files``（生成流程在
        ``mark_generated`` 时把真实输出文件名记到那里），而不是按文件名
        在 ``outputs/`` 目录里模糊匹配。后者在以下两种情形会把别人/旧版
        的生成图当成目标，造成反推等下游读取错图：

        - 多个 image_id 的 stem 存在前缀重叠（如 ``abc`` 与 ``abc_1``）
        - outputs/ 目录里残留了上一次生成同名的旧文件

        当 DB 没有记录 / 记录的文件已不存在时，才回退到 outputs/ 目录按
        ``<image_id>.<ext>`` 精确匹配。
        """
        out_dir = self._output_dir()
        # 1. 优先：DB 登记的输出文件名（多张时取第一张仍存在的）
        gen = self.db.get_generation(image_id)
        if gen and gen.output_files:
            for fname in (f for f in gen.output_files.split(",") if f):
                p = os.path.join(out_dir, fname)
                if os.path.isfile(p):
                    return p
        # 2. 回退：精确 stem 匹配（兼容旧库/手工移入的生成图）
        if not os.path.isdir(out_dir):
            return None
        for fname in os.listdir(out_dir):
            if os.path.splitext(fname)[0] == image_id:
                p = os.path.join(out_dir, fname)
                if os.path.isfile(p):
                    return p
        return None

    def list_pending_generation(self) -> List[ImageRecord]:
        """返回“已下载但尚未生成”的图片记录（通过 JOIN 两表一次获取）。

        生成流程用此代替“取全部图片 + 逐条查生成状态”，减少查询次数。
        """
        return [self._dict_to_record(d)
                for d in self.db.list_images_pending_generation()]

    # ------------------------------------------------------------------ #
    # 下载队列（代理到 StorageDB）
    # ------------------------------------------------------------------ #
    def enqueue_download(self, source_url: str, content_type: str = "",
                         site: str = "") -> Optional[str]:
        """登记一条待下载记录（按 URL 去重），返回 image_id 或 None。"""
        return self.db.add_pending_download(source_url, content_type, site)

    def list_pending_downloads(self) -> list:
        """获取所有待下载记录。"""
        return self.db.list_pending_downloads()

    def count_pending_downloads(self) -> int:
        return self.db.count_pending_downloads()

    def get_download(self, image_id: str):
        return self.db.get_download(image_id)

    def mark_download_done(self, image_id: str) -> None:
        self.db.mark_download_done(image_id)

    def mark_download_failed(self, image_id: str) -> None:
        self.db.mark_download_failed(image_id)

    def scan_directory(self) -> tuple:
        """扫描图片库目录中的图片文件，将数据库中没有的记录补充进库。

        用于 UI 开关“打开时”更新数据库状态（增量同步本地文件到 DB）。
        - 只登记本库目录下的图片文件（jpg/jpeg/png/webp/gif/avif）。
        - 同时**双向**同步 ComfyUI 输出目录（<root>/outputs）的生成状态：
          * 正向：本地存在对应生成文件但 generations 表无记录 → 补一条
            “已生成”记录，避免下次生成时误判为未生成。
          * 反向：数据库标记已生成、但本地生成文件已不存在（被删除/移动）
            → 重置为“待生成”，让生成流程重新生成。

        :return: (新增图片记录数, 补登记“已生成”数, 重置回“待生成”数)
        """
        added = 0
        with self._lock:
            known = {rec.image_id: rec.filename for rec in self.list_images()}
            known_filenames = set(known.values())
            for fname in sorted(os.listdir(self.library_dir)):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"):
                    continue
                if fname in known_filenames:
                    continue
                image_id = os.path.splitext(fname)[0]
                path = os.path.join(self.library_dir, fname)
                if not os.path.isfile(path):
                    continue
                size = os.path.getsize(path)
                self.db.upsert_image({
                    "image_id": image_id, "filename": fname,
                    "source_url": "", "content_hash": "", "site": "",
                    "width": None, "height": None, "size": size,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                known[image_id] = fname
                known_filenames.add(fname)
                added += 1

            # 双向同步生成状态（见方法 docstring）
            marked, reset = self._sync_generation_status_from_disk()
        return added, marked, reset

    def _sync_generation_status_from_disk(self) -> tuple:
        """双向同步 ComfyUI 输出目录与 generations 表的生成状态。

        - 正向：本地存在生成文件（<image_id>.<ext>）但 DB 无记录
          → 补一条“已生成”，避免下次生成时误判为未生成。
        - 反向：DB 标记已生成、但本地输出目录中既无 <image_id>.<ext>、
          也无记录在 output_files 里的文件（被删除/移动）
          → 重置为“待生成”，让生成流程重新生成。

        :return: (补登记“已生成”数, 重置回“待生成”数)
        """
        output_dir = self._output_dir()
        out_stems: set = set()
        out_names: set = set()
        if os.path.isdir(output_dir):
            for fname in os.listdir(output_dir):
                base = os.path.splitext(fname)[0]
                if base:
                    out_stems.add(base)
                    out_names.add(fname)
        marked = reset = 0
        # 正向：本地有生成文件 -> 补“已生成”记录
        for fname in sorted(out_names):
            image_id = os.path.splitext(fname)[0]
            if self.db.get_image(image_id) is None:
                continue
            if self.db.is_generated(image_id):
                continue
            self.db.mark_generated(image_id, fname)
            marked += 1
        # 反向：DB 已生成但本地生成文件已不存在 -> 重置为待生成
        for rec in self.db.list_generated():
            if rec.image_id in out_stems:
                continue
            recorded = {f for f in (rec.output_files or "").split(",") if f}
            if recorded & out_names:
                continue
            self.db.mark_pending(rec.image_id)
            reset += 1
        return marked, reset

    def _output_dir(self) -> str:
        """推导 ComfyUI 输出目录（与库同级的 outputs 目录）。"""
        return os.path.join(os.path.dirname(self.library_dir), "outputs")

    def close(self) -> None:
        self.db.close()

    @classmethod
    def resolve(cls, root_dir: str, library_name: str,
                dedupe_by_url: bool = True,
                dedupe_by_hash: bool = False) -> "ImageLibrary":
        """根据根目录和库名解析出图片库实例（库名作为子目录）。"""
        library_dir = os.path.join(os.path.abspath(root_dir), library_name)
        return cls(library_dir, dedupe_by_url=dedupe_by_url,
                   dedupe_by_hash=dedupe_by_hash)
