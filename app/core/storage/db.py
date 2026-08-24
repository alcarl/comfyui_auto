"""本地 SQLite 存储：图片记录 + ComfyUI 生成状态。

设计目标（工程化、解耦）：
- 用 SQLite 替代图片库的 index.json，并把“图片是否已生成”等状态也落到库中。
- 对外暴露简单、稳定的接口（StorageDB），上层（图片库 / 生成流程 / UI）
  只需调用几个方法即可，无需关心建表、SQL、连接管理等细节。
- 线程安全（单连接 + 锁），支持并发写入。

表结构：
- images        ：图片元数据（image_id 主键，source_url/content_hash 用于去重）
- generations   ：某张图片的 ComfyUI 生成状态（image_id 外键，status + 输出文件）
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

DB_FILENAME = "library.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class GeneratedRecord:
    """一条生成记录。"""

    __slots__ = ("image_id", "status", "output_files", "generated_at")

    def __init__(self, image_id: str, status: str,
                 output_files: str = "", generated_at: str = ""):
        self.image_id = image_id
        self.status = status
        self.output_files = output_files
        self.generated_at = generated_at

    def as_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "status": self.status,
            "output_files": self.output_files,
            "generated_at": self.generated_at,
        }


class StorageDB:
    """统一的本地 SQLite 存储接口。

    :param db_path: 数据库文件路径（不传则使用默认文件名）
    :param autocommit: 每个写操作后自动提交（默认 True）
    """

    # 生成状态常量
    STATUS_GENERATED = "generated"
    STATUS_PENDING = "pending"

    def __init__(self, db_path: Optional[str] = None, autocommit: bool = True):
        self.db_path = os.path.abspath(db_path or DB_FILENAME)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.autocommit = autocommit
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS images (
                    image_id     TEXT PRIMARY KEY,
                    filename     TEXT NOT NULL,
                    source_url   TEXT DEFAULT '',
                    content_hash TEXT DEFAULT '',
                    site         TEXT DEFAULT '',
                    width        INTEGER,
                    height       INTEGER,
                    size         INTEGER DEFAULT 0,
                    created_at   TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_images_source_url
                    ON images(source_url);
                CREATE INDEX IF NOT EXISTS idx_images_content_hash
                    ON images(content_hash);

                CREATE TABLE IF NOT EXISTS generations (
                    image_id      TEXT PRIMARY KEY,
                    status        TEXT DEFAULT 'pending',
                    output_files  TEXT DEFAULT '',
                    generated_at  TEXT DEFAULT '',
                    FOREIGN KEY (image_id) REFERENCES images(image_id)
                );
                """
            )
            self._conn.commit()

    def _execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            if self.autocommit:
                self._conn.commit()
            return cur

    def _row_to_image(self, row: sqlite3.Row) -> dict:
        return {
            "image_id": row["image_id"],
            "filename": row["filename"],
            "source_url": row["source_url"] or "",
            "content_hash": row["content_hash"] or "",
            "site": row["site"] or "",
            "width": row["width"],
            "height": row["height"],
            "size": row["size"] or 0,
            "created_at": row["created_at"] or "",
        }

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    # 图片记录
    # ------------------------------------------------------------------ #
    def upsert_image(self, record: Dict[str, Any]) -> None:
        """插入或更新一条图片记录（按 image_id）。"""
        self._execute(
            """
            INSERT INTO images
                (image_id, filename, source_url, content_hash, site,
                 width, height, size, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(image_id) DO UPDATE SET
                filename=excluded.filename,
                source_url=excluded.source_url,
                content_hash=excluded.content_hash,
                site=excluded.site,
                width=excluded.width,
                height=excluded.height,
                size=excluded.size,
                created_at=excluded.created_at
            """,
            (record.get("image_id", ""), record.get("filename", ""),
             record.get("source_url", ""), record.get("content_hash", ""),
             record.get("site", ""), record.get("width"),
             record.get("height"), record.get("size", 0),
             record.get("created_at", "")),
        )

    def get_image(self, image_id: str) -> Optional[dict]:
        cur = self._conn.execute("SELECT * FROM images WHERE image_id=?", (image_id,))
        row = cur.fetchone()
        return self._row_to_image(row) if row else None

    def image_exists_by_url(self, source_url: str) -> bool:
        if not source_url:
            return False
        cur = self._conn.execute(
            "SELECT 1 FROM images WHERE source_url=? LIMIT 1", (source_url,))
        return cur.fetchone() is not None

    def image_exists_by_hash(self, content_hash: str) -> bool:
        if not content_hash:
            return False
        cur = self._conn.execute(
            "SELECT 1 FROM images WHERE content_hash=? LIMIT 1", (content_hash,))
        return cur.fetchone() is not None

    def list_images(self) -> List[dict]:
        cur = self._conn.execute(
            "SELECT * FROM images ORDER BY created_at ASC")
        return [self._row_to_image(r) for r in cur.fetchall()]

    def count_images(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM images")
        return int(cur.fetchone()[0])

    def delete_image(self, image_id: str) -> bool:
        cur = self._execute("DELETE FROM images WHERE image_id=?", (image_id,))
        self._execute("DELETE FROM generations WHERE image_id=?", (image_id,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # 生成状态
    # ------------------------------------------------------------------ #
    def mark_generated(self, image_id: str, output_files: str = "") -> None:
        """将某张图片标记为已生成。"""
        self._execute(
            """
            INSERT INTO generations (image_id, status, output_files, generated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(image_id) DO UPDATE SET
                status=excluded.status,
                output_files=excluded.output_files,
                generated_at=excluded.generated_at
            """,
            (image_id, self.STATUS_GENERATED, output_files, _utcnow()),
        )

    def mark_pending(self, image_id: str) -> None:
        """将某张图片标记为未生成（待生成）。"""
        self._execute(
            "INSERT OR REPLACE INTO generations "
            "(image_id, status, output_files, generated_at) VALUES (?,?,?,?)",
            (image_id, self.STATUS_PENDING, "", _utcnow()),
        )

    def is_generated(self, image_id: str) -> bool:
        """判断某张图片是否已生成。"""
        cur = self._conn.execute(
            "SELECT status FROM generations WHERE image_id=?",
            (image_id,))
        row = cur.fetchone()
        return bool(row and row["status"] == self.STATUS_GENERATED)

    def get_generation(self, image_id: str) -> Optional[GeneratedRecord]:
        cur = self._conn.execute(
            "SELECT * FROM generations WHERE image_id=?",
            (image_id,))
        row = cur.fetchone()
        if not row:
            return None
        return GeneratedRecord(
            image_id=row["image_id"],
            status=row["status"],
            output_files=row["output_files"] or "",
            generated_at=row["generated_at"] or "",
        )

    def list_generated(self) -> List[GeneratedRecord]:
        cur = self._conn.execute(
            "SELECT * FROM generations WHERE status=? ORDER BY generated_at DESC",
            (self.STATUS_GENERATED,))
        return [GeneratedRecord(
            image_id=r["image_id"], status=r["status"],
            output_files=r["output_files"] or "",
            generated_at=r["generated_at"] or "") for r in cur.fetchall()]

    def count_generated(self) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM generations WHERE status=?", (self.STATUS_GENERATED,))
        return int(cur.fetchone()[0])

    def list_images_pending_generation(self) -> List[dict]:
        """查询“已下载但尚未生成”的图片（通过 JOIN 两表，一次获取）。

        即 images 中存在、但 generations 中无记录或状态不是 generated 的图片。
        避免逐条遍历 + 逐条查生成状态的 N 次查询。
        """
        cur = self._conn.execute(
            """
            SELECT images.* FROM images
            LEFT JOIN generations ON images.image_id = generations.image_id
            WHERE generations.image_id IS NULL
               OR generations.status != ?
            ORDER BY images.created_at ASC
            """,
            (self.STATUS_GENERATED,))
        return [self._row_to_image(r) for r in cur.fetchall()]

    def count_pending_generation(self) -> int:
        cur = self._conn.execute(
            """
            SELECT COUNT(*) FROM images
            LEFT JOIN generations ON images.image_id = generations.image_id
            WHERE generations.image_id IS NULL
               OR generations.status != ?
            """,
            (self.STATUS_GENERATED,))
        return int(cur.fetchone()[0])
