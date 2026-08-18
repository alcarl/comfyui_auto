"""图片抓取模块。"""
from .base import BaseCrawler, FetchedImage, HttpGet
from .pinterest import PinterestCrawler
from .factory import create_crawler, register_crawler

__all__ = [
    "BaseCrawler",
    "FetchedImage",
    "HttpGet",
    "PinterestCrawler",
    "create_crawler",
    "register_crawler",
]
