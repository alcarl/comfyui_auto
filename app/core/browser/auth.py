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

# 登录表单特征：Pinterest 登录表单含邮箱/密码输入框。
# 登录成功以“登录表单从页面消失”为判据（用户输完账号密码提交后，表单被移除）。
_LOGIN_FORM_JS = """
(() => {
  const email = document.querySelector('input#email, input[name="email"], input[type="email"]');
  const pwd   = document.querySelector('input#password, input[name="password"], input[type="password"]');
  const btn   = document.querySelector('button[type="submit"], button[data-test-id="registerFormSubmitButton"]');
  return !!(email || pwd || btn);
})()
"""
_LOGIN_URL_PARTS = ("/login/", "/login")


async def _form_present(t) -> bool:
    """返回登录表单当前是否存在于页面上（加载失败/异常视为不存在）。"""
    try:
        return bool(await t.evaluate(_LOGIN_FORM_JS, return_by_value=True))
    except Exception:  # noqa: BLE001
        return False


async def _current_url(t) -> str:
    """获取当前页面 URL。nodriver 中需先 ``await t`` 刷新 target 信息，URL 才准确。"""
    try:
        await t
    except Exception:  # noqa: BLE001
        pass
    try:
        url = t.url if hasattr(t, "url") else ""
    except Exception:  # noqa: BLE001
        url = ""
    return url or ""


async def wait_for_login(tab: Any, *,
                         timeout: float = 60,
                         is_logged_in: Optional[Callable[[Any], bool]] = None,
                         progress: Optional[Callable[[str], None]] = None) -> bool:
    """阻塞等待用户完成登录（默认超时 60 秒）。

    以“登录表单是否出现”为锚点区分已登录/未登录：
    1. 打开登录页后，若**已登录**，Pinterest 会把它重定向回首页，登录表单
       **不会出现** -> 判定已登录（快速通过，不打扰用户）。
    2. 若**未登录**，登录表单会**出现**，此时循环等待用户手动输入账号密码，
       直到表单消失（提交成功）即判定登录成功。

    如此可避免：登录页加载中 URL 短暂不含 /login 被误判；以及未登录访客
    首页没有登录表单却需登录。

    :param tab: nodriver tab 实例（登录页所在标签页）
    :param timeout: 最大等待秒数（默认 60）
    :param is_logged_in: 自定义登录判定函数 (tab) -> bool；若提供则直接用其循环判定
    :param progress: 进度提示回调 (message) -> None
    :return: 是否在超时前登录成功
    """
    if is_logged_in is not None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        if progress:
            progress("请在浏览器窗口中手动输入 Pinterest 用户名和密码完成登录…")
        while loop.time() < deadline:
            try:
                if await is_logged_in(tab):
                    return True
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(2)
        if progress:
            progress("登录等待超时。未完成登录。")
        return False

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    if progress:
        progress("请在浏览器窗口中手动输入 Pinterest 用户名和密码完成登录…")

    # 阶段一：等待登录表单出现（登录框真正弹出）。
    appeared = False
    while loop.time() < deadline:
        if await _form_present(tab):
            appeared = True
            break
        # 表单尚未出现时，若已跳离登录页（已登录被重定向回首页），视为已登录。
        url = await _current_url(tab)
        if url and not any(p in url for p in _LOGIN_URL_PARTS):
            if progress:
                progress("已检测到登录态（登录页已跳离）。")
            return True
        await asyncio.sleep(1)

    if not appeared:
        if progress:
            progress("未检测到登录表单且仍停留在登录页，登录流程未完成。")
        return False

    # 阶段二：表单已出现，等待表单消失 = 用户提交成功 = 已登录。
    while loop.time() < deadline:
        if not await _form_present(tab):
            if progress:
                progress("检测到已登录（登录表单已消失）。")
            return True
        await asyncio.sleep(2)

    if progress:
        progress("登录等待超时（60 秒）。未完成登录。")
    return False


async def pinterest_login(browser: Any, *,
                          login_url: str = "https://www.pinterest.com/login/",
                          timeout: float = 60,
                          is_logged_in: Optional[Callable[[Any], bool]] = None,
                          progress: Optional[Callable[[str], None]] = None) -> bool:
    """打开 Pinterest 登录页并等待用户手动登录。

    :return: 登录是否成功
    """
    tab = await browser.get(login_url)
    return await wait_for_login(
        tab, timeout=timeout, is_logged_in=is_logged_in, progress=progress
    )
