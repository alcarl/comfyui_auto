"""抓取器工厂：根据配置中的 crawler_type 分发到对应实现。"""
from __future__ import annotations

from typing import Dict, Type

from ..config.models import CrawlerType, SiteConfig
from .base import BaseCrawler
from .pinterest import PinterestCrawler

# 浏览器抓取器延迟导入以避免与 app.core.browser 形成循环依赖。
try:
    from ..browser.pinterest_browser import PinterestBrowserCrawler  # type: ignore
except Exception:  # noqa: BLE001  (首次部分初始化时可能尚未就绪)
    PinterestBrowserCrawler = None  # type: ignore

_REGISTRY: Dict[str, Type[BaseCrawler]] = {
    CrawlerType.PINTEREST.value: PinterestCrawler,
    # PinterestBrowserCrawler 在模块首次导入时可能为 None，
    # 由 ensure_browser_crawler() 在运行时补全。
}

if PinterestBrowserCrawler is not None:
    _REGISTRY[CrawlerType.PINTEREST_BROWSER.value] = PinterestBrowserCrawler


def register_crawler(crawler_type: str, cls: Type[BaseCrawler]) -> None:
    """注册新的抓取器类型（便于扩展）。"""
    _REGISTRY[crawler_type] = cls


def ensure_browser_crawler() -> None:
    """运行时确保浏览器抓取器已注册（打破循环导入）。"""
    global PinterestBrowserCrawler
    if PinterestBrowserCrawler is None:
        from ..browser.pinterest_browser import PinterestBrowserCrawler as _PBC  # type: ignore
        PinterestBrowserCrawler = _PBC  # type: ignore
        _REGISTRY[CrawlerType.PINTEREST_BROWSER.value] = _PBC


def create_crawler(site: SiteConfig, **kwargs) -> BaseCrawler:
    """为站点配置创建对应抓取器实例。"""
    ensure_browser_crawler()
    cls = _REGISTRY.get(site.crawler_type.value if hasattr(site.crawler_type, "value")
                        else site.crawler_type)
    if cls is None:
        raise ValueError(f"未注册的抓取器类型: {site.crawler_type}")
    # 站点级覆盖
    if site.timeout is not None:
        kwargs.setdefault("timeout", site.timeout)
    if site.max_concurrency is not None:
        kwargs.setdefault("max_concurrency", site.max_concurrency)
    return cls(site, **kwargs)
