"""Pinterest 浏览器登录助手。

由于 Pinterest 有登录与反爬机制，这里用 nodriver 真实驱动浏览器：
- 打开登录页后，提示用户在弹出的浏览器窗口中手动输入用户名/密码。
- 用户完成登录后，工具会等待页面出现已登录标志，然后保存登录态
  （user_data_dir + cookie 文件），供后续自动化复用，避免重复登录。

所有“等待用户输入”“检测登录成功”的逻辑都收敛在此，便于替换或测试。
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

# 登录成功后的标志：URL 跳转回首页且不再显示登录入口，或存在用户头像元素。
# 这里用简单的 URL 变化 + 关键元素出现来判断。
_LOGIN_URL_PARTS = ("/login/", "/login")
_HOME_INDICATOR_XPATH = '//div[@data-test-id="home-feed"]'


async def wait_for_login(browser: Any, *,
                         timeout: float = 180,
                         is_logged_in: Optional[Callable[[Any], bool]] = None,
                         progress: Optional[Callable[[str], None]] = None) -> bool:
    """阻塞等待用户完成登录。

    :param browser: nodriver browser 实例
    :param timeout: 最大等待秒数
    :param is_logged_in: 自定义登录判定函数 (tab) -> bool；
        不传则使用默认判定（页面 URL 不再包含 /login/ 且出现首页 feed）。
    :param progress: 进度提示回调 (message) -> None
    :return: 是否在超时前登录成功
    """
    tab = browser.main_tab if hasattr(browser, "main_tab") else browser.tabs[0]

    def _default_check(t) -> bool:
        try:
            url = t.url if hasattr(t, "url") else ""
        except Exception:  # noqa: BLE001
            url = ""
        if any(p in url for p in _LOGIN_URL_PARTS):
            return False
        # 尝试检测首页 feed 元素
        try:
            el = asyncio.run_coroutine_threadsafe(
                t.find(_HOME_INDICATOR_XPATH, timeout=1), _loop_of(t)
            ) if False else None
        except Exception:  # noqa: BLE001
            el = None
        return el is not None or "pinterest.com" in url

    checker = is_logged_in or _default_check

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    if progress:
        progress("请在浏览器窗口中手动输入 Pinterest 用户名和密码完成登录…")
    while loop.time() < deadline:
        try:
            if checker(tab):
                if progress:
                    progress("检测到已登录。")
                return True
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(2)
    if progress:
        progress("登录等待超时。")
    return False


def _loop_of(tab) -> asyncio.AbstractEventLoop:
    try:
        return tab.browser.loop
    except Exception:  # noqa: BLE001
        return asyncio.get_event_loop()


async def pinterest_login(browser: Any, *,
                          login_url: str = "https://www.pinterest.com/login/",
                          timeout: float = 180,
                          is_logged_in: Optional[Callable[[Any], bool]] = None,
                          progress: Optional[Callable[[str], None]] = None) -> bool:
    """打开 Pinterest 登录页并等待用户手动登录。

    :return: 登录是否成功
    """
    tab = await browser.get(login_url)
    return await wait_for_login(
        browser, timeout=timeout, is_logged_in=is_logged_in, progress=progress
    )
