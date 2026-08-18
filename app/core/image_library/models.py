"""本地图片库的数据模型。"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from pydantic import BaseModel, Field


class ImageRecord(BaseModel):
    """单张图片在本地图片库中的记录（元数据）。"""
    # 在本库内的唯一 id（通常是文件名去掉扩展名，或稳定 hash）
    image_id: str
    # 本地相对图片库根目录的文件路径
    filename: str
    # 图片来源 URL（用于防重复判定）
    source_url: str = ""
    # 图片内容 sha256（可选，用于内容去重）
    content_hash: str = ""
    # 来源站点名称（如 pinterest_demo）
    site: str = ""
    # 宽度/高度（可选）
    width: Optional[int] = None
    height: Optional[int] = None
    # 文件大小（字节）
    size: int = 0
    # 入库时间戳（ISO 格式）
    created_at: str = ""

    @staticmethod
    def compute_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def normalize_url(url: str) -> str:
        """规范化 URL 以便稳定地去重比对。

        去掉末尾斜杠、fragment、查询参数中的追踪字段，保留核心路径。
        """
        if not url:
            return ""
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc.lower(), path, "", ""))
