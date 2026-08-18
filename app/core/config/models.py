"""业务核心配置的数据模型定义。

使用 pydantic 定义类型安全的配置结构，与 UI 层的 AppConfig 相互独立。
"""
from __future__ import annotations

import os
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CrawlerType(str, Enum):
    """抓取器类型枚举，用于配置中指定使用哪个抓取器。"""
    PINTEREST = "pinterest"


class ComfyUIUploadMethod(str, Enum):
    """ComfyUI 图片上传方式。"""
    # 通过 /upload/image 接口上传本地文件
    UPLOAD_IMAGE = "upload_image"
    # 直接把图片以 base64 写入工作流节点（无需上传接口）
    BASE64_INLINE = "base64_inline"


class SiteConfig(BaseModel):
    """单个图片网站的抓取配置。"""
    name: str = Field(..., description="网站别名，如 pinterest、unsplash")
    crawler_type: CrawlerType = Field(..., description="抓取器类型")
    enabled: bool = Field(default=True, description="是否启用该站点")
    # 一期：支持在 URL 列表中配置 Pinterest 图片墙链接
    urls: List[str] = Field(default_factory=list, description="待抓取的图片墙/画板 URL 列表")
    # 每个站点可覆盖全局的并发与超时设置（可选）
    max_concurrency: Optional[int] = Field(default=None, description="单站点最大并发数")
    timeout: Optional[int] = Field(default=None, description="单站点请求超时(秒)")
    # 抓取器自定义扩展参数（如 Pinterest 的 locale/分页）
    extra: dict = Field(default_factory=dict, description="抓取器自定义参数")


class CrawlerConfig(BaseModel):
    """抓取相关全局配置。"""
    output_library: str = Field(default="default", description="抓取结果写入的本地图片库名称")
    max_concurrency: int = Field(default=4, description="全局最大并发下载数")
    timeout: int = Field(default=30, description="全局请求超时(秒)")
    retry: int = Field(default=2, description="下载失败重试次数")
    user_agent: str = Field(
        default=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
        description="下载使用的 User-Agent",
    )


class ComfyUIConfig(BaseModel):
    """ComfyUI 服务及图生图相关配置。"""
    base_url: str = Field(default="http://127.0.0.1:8188", description="ComfyUI 服务地址")
    upload_method: ComfyUIUploadMethod = Field(
        default=ComfyUIUploadMethod.UPLOAD_IMAGE, description="原图上传方式")
    workflow_path: str = Field(default="", description="图生图工作流 JSON 文件路径")
    # 工作流中 LoadImage 节点标题（title），用于替换输入图片
    load_image_node_title: str = Field(default="Load Image", description="工作流 LoadImage 节点标题")
    # 保存图片节点（如 SaveImage）的标题，用于定位输出
    save_image_node_title: str = Field(default="Save Image", description="工作流 SaveImage 节点标题")
    client_id: str = Field(default="comfyui_auto", description="客户端标识，用于接收 WS 消息")
    timeout: int = Field(default=300, description="等待出图完成超时(秒)")


class LibraryConfig(BaseModel):
    """本地图片库全局配置。"""
    root_dir: str = Field(default="libraries", description="所有图片库的根目录")
    # 防重复判定方式
    dedupe_by_url: bool = Field(default=True, description="通过图片来源 URL 去重（默认开启）")
    dedupe_by_hash: bool = Field(default=False, description="通过图片内容哈希去重（可选）")


class CoreConfig(BaseModel):
    """业务核心总配置。"""
    library: LibraryConfig = Field(default_factory=LibraryConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    sites: List[SiteConfig] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "CoreConfig":
        """返回带一代默认站点（Pinterest 示例）的配置。"""
        return cls(
            sites=[
                SiteConfig(
                    name="pinterest_demo",
                    crawler_type=CrawlerType.PINTEREST,
                    urls=[
                        "https://jp.pinterest.com/pin/1028087421172953769/",
                    ],
                    extra={"locale": "jp"},
                )
            ]
        )
