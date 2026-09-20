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

import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

DB_FILENAME = "library.db"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_image_id(source_url: str) -> str:
    """根据来源 URL 生成稳定的 image_id（URL 的 SHA1 前 16 位）。"""
    return hashlib.sha1((source_url or "").encode("utf-8")).hexdigest()[:16]


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


class DownloadRecord:
    """一条待下载 / 下载记录。"""

    __slots__ = ("image_id", "source_url", "content_type", "site",
                 "status", "created_at", "downloaded_at")

    def __init__(self, image_id: str, source_url: str, content_type: str = "",
                 site: str = "", status: str = "pending",
                 created_at: str = "", downloaded_at: str = ""):
        self.image_id = image_id
        self.source_url = source_url
        self.content_type = content_type
        self.site = site
        self.status = status
        self.created_at = created_at
        self.downloaded_at = downloaded_at

    def as_dict(self) -> dict:
        return {
            "image_id": self.image_id, "source_url": self.source_url,
            "content_type": self.content_type, "site": self.site,
            "status": self.status, "created_at": self.created_at,
            "downloaded_at": self.downloaded_at,
        }


class StorageDB:
    """统一的本地 SQLite 存储接口。

    :param db_path: 数据库文件路径（不传则使用默认文件名）
    :param autocommit: 每个写操作后自动提交（默认 True）
    """

    # 生成状态常量
    STATUS_GENERATED = "generated"
    STATUS_PENDING = "pending"
    # 下载状态常量
    DOWNLOAD_PENDING = "pending"      # 待下载（已采集 URL，未下载文件）
    DOWNLOAD_DONE = "downloaded"      # 已下载
    DOWNLOAD_FAILED = "failed"        # 下载失败

    def __init__(self, db_path: Optional[str] = None, autocommit: bool = True):
        self.db_path = os.path.abspath(db_path or DB_FILENAME)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.autocommit = autocommit
        # 支持多线程访问：check_same_thread=False + busy_timeout（写锁等待）
        # + timeout（连接建立等待），避免生成/下载等多个线程并发访问数据库时
        # 互相阻塞或抛 "database is locked"。
        self._conn = sqlite3.connect(
            self.db_path, check_same_thread=False,
            timeout=30)  # 连接/写锁最长等待 30 秒
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        # 开启 WAL 模式：允许并发读 + 单写，显著降低多线程写冲突
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
        except sqlite3.Error:
            pass
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

                CREATE TABLE IF NOT EXISTS downloads (
                    image_id      TEXT PRIMARY KEY,
                    source_url    TEXT DEFAULT '',
                    content_type  TEXT DEFAULT '',
                    site          TEXT DEFAULT '',
                    status        TEXT DEFAULT 'pending',
                    created_at    TEXT DEFAULT '',
                    downloaded_at TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_downloads_status
                    ON downloads(status);

                CREATE TABLE IF NOT EXISTS tags (
                    image_id   TEXT NOT NULL,
                    filename   TEXT DEFAULT '',
                    tag        TEXT NOT NULL,
                    created_at TEXT DEFAULT '',
                    PRIMARY KEY (image_id, tag)
                );
                CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
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
        # 级联清理反推提示词（若存在）
        self._execute("DELETE FROM tags WHERE image_id=?", (image_id,))
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

    def delete_generation(self, image_id: str) -> bool:
        """删除某张图片的生成记录（不删图、不删 tags）。返回是否存在该记录。"""
        cur = self._execute(
            "DELETE FROM generations WHERE image_id=?", (image_id,))
        return cur.rowcount > 0

    def delete_tags(self, image_id: str) -> int:
        """删除某张图片的全部反推提示词记录。返回删除的条数。"""
        cur = self._execute("DELETE FROM tags WHERE image_id=?", (image_id,))
        return cur.rowcount

    def clear_output_files(self, image_id: Optional[str] = None) -> int:
        """清空 generations.output_files（保留 status、generated_at、记录行）。

        用于排查/恢复"DB 里登记的输出文件名错位"——清空后，
        ImageLibrary.generated_output_path 会回退到精确 stem 匹配，
        不会再用错位的文件名。

        :param image_id: 限定单条；None 则清空所有记录。
        :return: 受影响的行数
        """
        if image_id is None:
            cur = self._execute(
                "UPDATE generations SET output_files='' "
                "WHERE output_files IS NOT NULL AND output_files != ''")
        else:
            cur = self._execute(
                "UPDATE generations SET output_files='' WHERE image_id=?",
                (image_id,))
        return cur.rowcount

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

    # ------------------------------------------------------------------ #
    # 下载队列（采集到的图片先登记为待下载，再由后台任务下载）
    # ------------------------------------------------------------------ #
    def add_pending_download(self, source_url: str, content_type: str = "",
                             site: str = "") -> Optional[str]:
        """登记一条待下载记录（按 source_url 去重），返回 image_id 或 None。

        若该 URL 已在 downloads 表（无论状态）或 images 表中存在，则跳过。
        """
        if not source_url:
            return None
        # 已存在于待下载队列
        cur = self._conn.execute(
            "SELECT image_id FROM downloads WHERE source_url=?", (source_url,))
        row = cur.fetchone()
        if row:
            return row["image_id"]
        # 已下载进图片库
        if self.image_exists_by_url(source_url):
            return None
        image_id = _make_image_id(source_url)
        self._execute(
            "INSERT INTO downloads "
            "(image_id, source_url, content_type, site, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (image_id, source_url, content_type, site,
             self.DOWNLOAD_PENDING, _utcnow()))
        return image_id

    def list_pending_downloads(self) -> List[DownloadRecord]:
        """获取所有待下载记录（按采集时间升序）。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM downloads WHERE status=? ORDER BY created_at ASC",
                (self.DOWNLOAD_PENDING,))
            rows = cur.fetchall()
        return [DownloadRecord(
            image_id=r["image_id"], source_url=r["source_url"] or "",
            content_type=r["content_type"] or "", site=r["site"] or "",
            status=r["status"] or "", created_at=r["created_at"] or "",
            downloaded_at=r["downloaded_at"] or "") for r in rows]

    def count_pending_downloads(self) -> int:
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM downloads WHERE status=?",
                (self.DOWNLOAD_PENDING,))
            return int(cur.fetchone()[0])

    def get_download(self, image_id: str) -> Optional[DownloadRecord]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM downloads WHERE image_id=?", (image_id,))
            row = cur.fetchone()
        if not row:
            return None
        return DownloadRecord(
            image_id=row["image_id"], source_url=row["source_url"] or "",
            content_type=row["content_type"] or "", site=row["site"] or "",
            status=row["status"] or "", created_at=row["created_at"] or "",
            downloaded_at=row["downloaded_at"] or "")

    def mark_download_done(self, image_id: str) -> None:
        """将一条待下载记录标记为已下载。"""
        self._execute(
            "UPDATE downloads SET status=?, downloaded_at=? WHERE image_id=?",
            (self.DOWNLOAD_DONE, _utcnow(), image_id))

    def mark_download_failed(self, image_id: str) -> None:
        """将一条待下载记录标记为失败（下次轮询会重新尝试）。"""
        self._execute(
            "UPDATE downloads SET status=?, downloaded_at=? WHERE image_id=?",
            (self.DOWNLOAD_FAILED, _utcnow(), image_id))

    # ------------------------------------------------------------------ #
    # 反推提示词（WD14 tagger 结果，每行一个提示词）
    # ------------------------------------------------------------------ #
    def set_tags(self, image_id: str, filename: str,
                 tags: List[str]) -> int:
        """全量替换某张图片的反推提示词（每个提示词一行记录）。

        :return: 实际写入的提示词条数
        """
        with self._lock:
            self._execute("DELETE FROM tags WHERE image_id=?", (image_id,))
            now = _utcnow()
            rows = [(image_id, filename or "", t.strip(), now)
                    for t in tags if t and t.strip()]
            if rows:
                self._conn.executemany(
                    "INSERT OR REPLACE INTO tags "
                    "(image_id, filename, tag, created_at) VALUES (?,?,?,?)",
                    rows)
                self._conn.commit()
            return len(rows)

    def get_tags(self, image_id: str) -> List[str]:
        """返回某张图片的全部反推提示词。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT tag FROM tags WHERE image_id=? ORDER BY tag ASC",
                (image_id,))
            return [r["tag"] for r in cur.fetchall()]

    def has_tags(self, image_id: str) -> bool:
        """判断某张图片是否已有反推提示词。"""
        cur = self._conn.execute(
            "SELECT 1 FROM tags WHERE image_id=? LIMIT 1", (image_id,))
        return cur.fetchone() is not None

    def list_distinct_tags(self) -> List[str]:
        """列出全部去重后的提示词（按字母序，供筛选框建议）。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT tag FROM tags ORDER BY tag ASC")
            return [r["tag"] for r in cur.fetchall()]

    def search_image_ids_by_tag(self, keyword: str) -> List[str]:
        """按提示词关键词（包含匹配，忽略 ASCII 大小写）筛选图片 id 列表。"""
        kw = (keyword or "").strip()
        if not kw:
            return []
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT image_id FROM tags WHERE tag LIKE ?"
                " ORDER BY image_id ASC",
                (f"%{kw}%",))
            return [r["image_id"] for r in cur.fetchall()]

    def delete_tags_for_image(self, image_id: str) -> int:
        """删除某张图片的全部反推提示词。"""
        cur = self._execute("DELETE FROM tags WHERE image_id=?", (image_id,))
        return cur.rowcount
