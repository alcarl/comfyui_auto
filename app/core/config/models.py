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
    PINTEREST_BROWSER = "pinterest_browser"


class CrawlerBackend(str, Enum):
    """抓取后端：http（纯请求）或 browser（nodriver 真实浏览器）。"""
    HTTP = "http"
    BROWSER = "browser"


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
    # 抓取后端：http（纯请求）或 browser（nodriver 真实浏览器，可绕过反爬与登录）
    backend: CrawlerBackend = Field(default=CrawlerBackend.HTTP, description="抓取后端")
    # 一期：支持在 URL 列表中配置 Pinterest 图片墙链接
    urls: List[str] = Field(default_factory=list, description="待抓取的图片墙/画板 URL 列表")
    # 每个站点可覆盖全局的并发与超时设置（可选）
    max_concurrency: Optional[int] = Field(default=None, description="单站点最大并发数")
    timeout: Optional[int] = Field(default=None, description="单站点请求超时(秒)")
    # 抓取器自定义扩展参数（如 Pinterest 的 locale/分页）
    extra: dict = Field(default_factory=dict, description="抓取器自定义参数")


class BrowserConfig(BaseModel):
    """nodriver 浏览器自动化相关配置。"""
    # 浏览器启动用户数据目录（持久化登录态），为空时每次临时
    user_data_dir: str = Field(default="", description="浏览器用户数据目录(持久化登录态)")
    # 浏览器是否无头（生产建议 False 以便用户手动登录）
    headless: bool = Field(default=False, description="是否无头模式")
    # 代理服务器地址，如 http://10.0.0.51:1072 ；为空则不使用代理
    proxy: str = Field(default="", description="浏览器代理地址")
    # 登录态（cookie）保存文件路径，为空则默认放在 user_data_dir 旁
    session_file: str = Field(default="", description="登录态 cookie 保存文件")
    # 浏览器可执行文件路径，为空则自动查找
    browser_executable_path: str = Field(default="", description="浏览器可执行文件路径")
    # 手动登录等待超时(秒)
    login_timeout: int = Field(default=180, description="等待用户手动登录超时(秒)")
    # 页面加载与滚动等待时间(秒)
    page_load_wait: float = Field(default=3.0, description="页面加载后等待秒数")
    scroll_times: int = Field(default=5, description="滚动加载次数")
    scroll_pause: float = Field(default=1.5, description="每次滚动停顿秒数")


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
    browser: BrowserConfig = Field(default_factory=BrowserConfig, description="浏览器自动化配置")


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
        """返回带一代默认站点（Pinterest 示例，使用浏览器后端）的配置。"""
        return cls(
            sites=[
                SiteConfig(
                    name="pinterest_demo",
                    crawler_type=CrawlerType.PINTEREST_BROWSER,
                    backend=CrawlerBackend.BROWSER,
                    urls=[
                        "https://jp.pinterest.com/pin/1028087421172953769/",
                    ],
                    extra={"locale": "jp"},
                )
            ]
        )

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
