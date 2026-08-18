"""nodriver 浏览器启动器：封装代理、用户数据目录（登录态持久化）。

设计目标（解耦、可测试）：
- 不直接依赖具体网站逻辑，只负责启动/关闭浏览器、加载/保存登录态。
- 所有外部不可控行为（真实启动浏览器）都通过本模块收敛，
  测试时可注入一个实现了相同接口的对象（见 tests 中的 FakeBrowser）。
- 登录态通过两步保存：
  1) user_data_dir 持久化浏览器本地存储（推荐，最完整）。
  2) cookies.save 序列化 cookie 到 session_file，便于快速恢复会话。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from ..config.models import BrowserConfig


class BrowserLauncher:
    """封装 nodriver 浏览器生命周期。

    用法（异步上下文管理器）::

        async with BrowserLauncher(browser_cfg) as browser:
            tab = await browser.get("https://jp.pinterest.com/")
            ...
    """

    def __init__(self, config: BrowserConfig,
                 browser_factory: Optional[Any] = None):
        """
        :param config: 浏览器配置（代理、user_data_dir、session_file 等）
        :param browser_factory: 注入的启动函数，签名为
            ``async def factory(config, **kwargs) -> browser``。真实环境下为
            ``nodriver.start``，测试时替换为桩函数。
        """
        self.config = config
        self._browser_factory = browser_factory
        self._browser = None
        self._tmp_user_data_dir = None

    # ------------------------------------------------------------------ #
    # 上下文管理器
    # ------------------------------------------------------------------ #
    async def __aenter__(self) -> Any:
        await self.start()
        return self._browser

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ------------------------------------------------------------------ #
    # 启动 / 关闭
    # ------------------------------------------------------------------ #
    async def start(self) -> Any:
        """启动浏览器（仅启动一次）。"""
        if self._browser is not None:
            return self._browser

        config = self.config
        factory = self._browser_factory or self._default_factory

        kwargs: dict = {
            "headless": config.headless,
        }
        # user_data_dir：若用户未指定，使用唯一临时目录，避免连续/并发
        # 固定 user_data_dir 持久化浏览器状态（含登录态）：登录一次后
        # 下次启动自动复用，无需再次登录。为空时默认使用项目内固定目录。
        if config.user_data_dir:
            ud = config.user_data_dir
        else:
            ud = os.path.join("libraries", "browser_profile")
        # 清理上次异常退出遗留的 SingletonLock，避免“已有实例占用”导致
        # Chrome 无法连接 DevTools。
        self._clear_stale_lock(ud)
        kwargs["user_data_dir"] = ud
        if config.browser_executable_path:
            kwargs["browser_executable_path"] = config.browser_executable_path

        # 默认附加的稳定性参数：关闭沙箱与 GPU，规避 Windows 下
        # “Failed to connect to browser” 的启动失败。
        browser_args: list = [
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
        ]
        if config.proxy:
            browser_args.append(f"--proxy-server={config.proxy}")
            # 关键：Chrome 的 DevTools 监听在 127.0.0.1，若不把回环地址
            # 加入绕过列表，代理会把本地调试端口的连接也走代理，导致
            # nodriver “Failed to connect to browser”。
            browser_args.append("--proxy-bypass-list=<-loopback>")
        kwargs["browser_args"] = browser_args

        self._browser = await factory(config, **kwargs)
        return self._browser

    async def close(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None

    # ------------------------------------------------------------------ #
    # 登录态保存 / 加载
    # ------------------------------------------------------------------ #
    async def save_session(self, session_file: Optional[str] = None) -> str:
        """保存当前登录态 cookie 到文件。

        :return: 实际保存的文件路径
        """
        if self._browser is None:
            raise RuntimeError("浏览器尚未启动，无法保存登录态")
        path = session_file or self.config.session_file or self._default_session_file()
        await self._browser.cookies.save(file=path, pattern=".*")
        return str(path)

    async def load_session(self, session_file: Optional[str] = None) -> bool:
        """从文件加载登录态 cookie。

        :return: 文件是否存在并成功加载
        """
        if self._browser is None:
            raise RuntimeError("浏览器尚未启动，无法加载登录态")
        path = session_file or self.config.session_file or self._default_session_file()
        if not os.path.exists(path):
            return False
        try:
            await self._browser.cookies.load(file=path, pattern=".*")
            return True
        except Exception:  # noqa: BLE001
            return False

    def _default_session_file(self) -> str:
        # 登录态 cookie 固定保存到项目内（libraries/ 已被 gitignore 忽略），
        # 与临时 user_data_dir 解耦，保证每次用新临时 profile 也能恢复登录态。
        base = self.config.user_data_dir or os.path.join("libraries", "browser_session")
        os.makedirs(base, exist_ok=True)
        return os.path.join(os.path.abspath(base), ".pinterest_session.dat")

    @staticmethod
    def _clear_stale_lock(user_data_dir: str) -> None:
        """删除残留的 Chrome 单例锁，避免“Failed to connect to browser”。"""
        lock = os.path.join(user_data_dir, "SingletonLock")
        try:
            if os.path.exists(lock):
                os.remove(lock)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # 真实启动函数（默认工厂，懒导入 nodriver 以便测试环境无需安装）
    # ------------------------------------------------------------------ #
    @staticmethod
    async def _default_factory(config: BrowserConfig, **kwargs):
        import nodriver
        return await nodriver.start(**kwargs)
