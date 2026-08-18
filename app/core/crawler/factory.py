"""抓取器工厂：根据配置中的 crawler_type 分发到对应实现。"""
from __future__ import annotations

from typing import Dict, Type

from ..config.models import CrawlerType, SiteConfig
from .base import BaseCrawler
from .pinterest import PinterestCrawler

_REGISTRY: Dict[str, Type[BaseCrawler]] = {
    CrawlerType.PINTEREST.value: PinterestCrawler,
    # 后续可在此注册更多抓取器：unsplash、pixiv 等
}


def register_crawler(crawler_type: str, cls: Type[BaseCrawler]) -> None:
    """注册新的抓取器类型（便于扩展）。"""
    _REGISTRY[crawler_type] = cls


def create_crawler(site: SiteConfig, **kwargs) -> BaseCrawler:
    """为站点配置创建对应抓取器实例。"""
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
