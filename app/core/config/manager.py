"""CoreConfigManager：负责业务核心配置的读写。

与 UI 层的 AppConfig 相互独立，避免业务配置污染界面配置。
配置持久化在 core_config.json 中，支持单例调用。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

from .models import CoreConfig


class CoreConfigManager:
    """业务核心配置管理器（线程安全单例）。"""

    _instance: Optional["CoreConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        if config_path is None:
            # 默认放在项目根的 config 目录
            base = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(base, "config", "core_config.json")
        self.config_path = config_path
        self._ensure_config_file()
        self._config = self.load()

    # ------------------------------------------------------------------ #
    # 文件读写
    # ------------------------------------------------------------------ #
    def _ensure_config_file(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        if not os.path.exists(self.config_path):
            self._create_default_config()

    def _create_default_config(self) -> None:
        cfg = CoreConfig.default()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg.model_dump(), f, indent=4, ensure_ascii=False)

    def load(self) -> CoreConfig:
        """从磁盘加载配置；损坏或缺失时回退到默认配置。"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CoreConfig.model_validate(data)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return CoreConfig.default()

    def save(self) -> None:
        """将内存中的配置写回磁盘。"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config.model_dump(), f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # 访问接口
    # ------------------------------------------------------------------ #
    @property
    def config(self) -> CoreConfig:
        return self._config

    def get_site(self, name: str) -> Optional["__import__('typing').Any"]:
        """按名称获取站点配置。"""
        for site in self._config.sites:
            if site.name == name:
                return site
        return None

    def add_site(self, site) -> None:
        """新增或覆盖同名站点配置并保存。"""
        self._config.sites = [s for s in self._config.sites if s.name != site.name]
        self._config.sites.append(site)
        self.save()

    def update(self, **kwargs) -> None:
        """更新顶层配置字段（如 crawler/comfyui/library 对象）并保存。"""
        for k, v in kwargs.items():
            if hasattr(self._config, k):
                setattr(self._config, k, v)
        self.save()

    @classmethod
    def reset(cls) -> None:
        """清除单例，便于测试重新初始化。"""
        cls._instance = None
