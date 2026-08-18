import flet as ft
import os
from app.base import BasePage
from app.config.version import VERSION, APP_DESCRIPTION, GITHUB_URL
import requests
import asyncio

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.app import AppConfig

class SettingsPage(BasePage):
    def __init__(self, config_manager, **kwargs):
        self.config_manager: AppConfig = config_manager
        super().__init__(title="设置", **kwargs)
        self.proxy_test_text = None
        self.proxy_url = None
        self.proxy_controls = None
        self.proxy_switch = None

    def _build_theme_settings(self) -> ft.Container:
        """构建主题设置部分"""
        # 主题模式和主题色选择
        theme_mode_row = ft.Row([
            ft.Text("主题模式", size=16, color=self.theme_colors.text_color),
            ft.Container(width=20),
            ft.SegmentedButton(
                segments=[
                    ft.Segment(
                        value="light",
                        label=ft.Text("浅色"),
                        icon=ft.Icon(ft.Icons.LIGHT_MODE),
                    ),
                    ft.Segment(
                        value="dark",
                        label=ft.Text("深色"),
                        icon=ft.Icon(ft.Icons.DARK_MODE),
                    ),
                    ft.Segment(
                        value="system",
                        label=ft.Text("跟随系统"),
                        icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO),
                    ),
                ],
                selected={self.theme_mode},
                on_change=lambda e: self._handle_theme_change(e),
            ),
        ], alignment=ft.MainAxisAlignment.START)

        # 主题色选择
        current_color = self.config_manager.get("Theme", "color", ft.Colors.BLUE)
        theme_colors_row = ft.Row([
            ft.Text("主题色 ", size=16, color=self.theme_colors.text_color),
            ft.Container(width=20),
            ft.Dropdown(
                width=200,
                value=current_color,
                content_padding=ft.padding.symmetric(horizontal=10),
                options=[
                    ft.dropdown.Option(
                        key=color,
                        content=ft.Row([
                            ft.Icon(ft.Icons.COLOR_LENS, color=color),
                            ft.Text(name, color=self.theme_colors.text_color)
                        ])
                    )
                    for name, color in [
                        ("淡蓝色", "#6E9ECF"),
                        ("靛蓝", "#4F46E5"),
                        ("翠绿", "#10B981"),
                        ("珊瑚", "#F43F5E"),
                        ("琥珀", "#F59E0B"),
                        ("紫水晶", "#8B5CF6"),
                        ("青碧", "#06B6D4"),
                        ("玫瑰金", "#F472B6")
                    ]
                ],
                on_change=lambda e: self._handle_theme_color_change(e.data),
                select_icon=ft.Icons.CHECK,
                select_icon_enabled_color=self.theme_colors.text_color,
            ),
        ], alignment=ft.MainAxisAlignment.START)

        # 背景图片选择
        current_bg = self.config_manager.get("Theme", "background_image", "images/backgrounds/background1.jpg").split("/")[-1]
        # 获取背景图片列表
        bg_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "images", "backgrounds")
        bg_files = [f for f in os.listdir(bg_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        background_row = ft.Row([
            ft.Text("背景图片", size=16, color=self.theme_colors.text_color),
            ft.Container(width=20),
            ft.Dropdown(
                width=200,
                value=current_bg,
                content_padding=ft.padding.symmetric(horizontal=10),
                options=[
                    ft.dropdown.Option(
                        key=bg_file,
                        content=ft.Row([
                            ft.Icon(ft.Icons.IMAGE, color=self.theme_colors.text_color),
                            ft.Text(f"{bg_file.split('.')[0]}", color=self.theme_colors.text_color)
                        ])
                    )
                    for bg_file in bg_files
                ],
                on_change=lambda e: self._handle_background_change(e.data),
                select_icon=ft.Icons.CHECK,
                select_icon_enabled_color=self.theme_colors.text_color,
            ),
        ], alignment=ft.MainAxisAlignment.START)

        return self.build_section(
            "主题设置",
            ft.Column([
                theme_mode_row,
                ft.Container(height=20),
                theme_colors_row,
                ft.Container(height=20),
                background_row,
            ], spacing=0)
        )

    def _build_proxy_settings(self) -> ft.Container:
        """构建代理设置部分"""
        # 代理开关
        self.proxy_switch = ft.Switch(
            label="启用代理",
            value=self.config_manager.get("Proxy", "enabled", False),
            on_change=lambda e: self._handle_proxy_change(e),
        )

        # 代理地址输入框
        self.proxy_url = ft.TextField(
            label="代理地址",
            value=self.config_manager.get("Proxy", "url", ""),
            hint_text="例如: http://127.0.0.1:7890",
            on_change=lambda e: self._handle_proxy_url_change(e),
        )

        # 测试按钮和结果文本
        self.proxy_test_text = ft.Text("", size=14, color=self.theme_colors.text_color)
        test_button = ft.ElevatedButton(
            "测试代理",
            icon=ft.Icons.NETWORK_CHECK,
            on_click=self._test_proxy,
        )

        # 创建一个容器来包含代理URL输入框、测试按钮和结果文本
        self.proxy_controls = ft.Column([
            ft.Row(
                [self.proxy_switch,self.proxy_url, test_button, self.proxy_test_text],
                spacing=20,
            ),
        ], spacing=10, expand=True)

        return self.build_section(
            title="代理设置",
            content=self.proxy_controls,
            expand=True
        )

    def _build_window_settings(self) -> ft.Container:
        """构建窗口设置部分"""
        # 默认尺寸设置
        default_size = ft.Row([
            ft.TextField(
                label="默认宽度",
                value=self.config_manager.get("Window", "width", 1300),
                width=150,
                data="width",
                on_change=lambda e: self._handle_window_size_change(e),
            ),
            ft.TextField(
                label="默认高度",
                value=self.config_manager.get("Window", "height", 800),
                width=150,
                data="height",
                on_change=lambda e: self._handle_window_size_change(e),
            ),
            ft.Container(width=100),
            ft.TextField(
                label="最小宽度",
                value=self.config_manager.get("Window", "min_width", 500),
                width=150,
                data="min_width",
                on_change=lambda e: self._handle_window_size_change(e),
            ),
            ft.TextField(
                label="最小高度",
                value=self.config_manager.get("Window", "min_height", 400),
                width=150,
                data="min_height",
                on_change=lambda e: self._handle_window_size_change(e),
            ),
        ], spacing=20)

        return self.build_section(
            "窗口设置",
            ft.Column([default_size], spacing=20)
        )

    def _build_about_section(self) -> ft.Container:
        """构建关于部分"""
        # 头部信息
        header = ft.Row([
            ft.Column([
                ft.Text("PyDracula", size=30, weight="bold", color=self.theme_colors.text_color),
                ft.Text(f"Version {VERSION}", size=16, color=self.theme_colors.text_color, opacity=0.8),
            ]),
            ft.Container(expand=True),
            ft.TextButton("访问 GitHub", icon=ft.Icons.OPEN_IN_NEW, url=GITHUB_URL),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # 底部信息
        footer = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.COPYRIGHT, color=self.theme_colors.text_color, opacity=0.5, size=16),
                    ft.Text("2024 calg", size=14, color=self.theme_colors.text_color, opacity=0.5),
                ], spacing=5),
            ),
            ft.Container(expand=True),
            ft.TextButton("检查更新", icon=ft.Icons.SYSTEM_UPDATE, on_click=self._check_updates),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        return self.build_section(
            "关于",
            ft.Column([
                header,
                ft.Container(height=20),
                ft.Text(APP_DESCRIPTION, size=14, color=self.theme_colors.text_color, opacity=0.7),
                ft.Container(height=10),
                footer,
            ], spacing=10)
        )

    def build_content(self) -> ft.Column:
        """构建页面内容"""
        return ft.Column([
            self._build_theme_settings(),
            self._build_proxy_settings(),
            self._build_window_settings(),
            self._build_about_section(),
        ], scroll=ft.ScrollMode.ALWAYS, spacing=20, height=500)

    # 事件处理方法
    def _handle_theme_change(self, e):
        if self.on_theme_changed:
            self.on_theme_changed(e.control.selected.pop())
        if self.config_manager:
            self.config_manager.set("Theme", "mode", e.control.selected.pop())

    def _handle_theme_color_change(self, color: str):
        """处理主题色变更"""
        if not color:
            return
        self.page.theme = ft.Theme(
            color_scheme_seed=color,
            font_family="Microsoft YaHei UI" if self.page.platform != "macos" else None
        )
        if self.config_manager:
            self.config_manager.set("Theme", "color", color)
            
        if self.on_theme_changed:
            self.theme_colors.current_color = self.page.theme.color_scheme_seed
            theme_mode = self.config_manager.get("Theme", "mode", "dark")
            self.on_theme_changed(theme_mode)
        self.page.update()

    def _handle_background_change(self, background: str):
        """处理背景图片变更"""
        if not background:
            return
            
        # 更新配置文件
        if self.config_manager:
            self.config_manager.set("Theme", "background_image", f"images/backgrounds/{background}")
            
        # 通知主题变化
        if self.on_theme_changed:
            self.app.config.set("Theme", "background_image", f"images/backgrounds/{background}")
            self.on_theme_changed(self.config_manager.get("Theme", "mode", "dark"))
        self.page.update()

    def _handle_window_size_change(self, e):
        if self.config_manager:
            try:
                value = int(e.control.value)
                self.config_manager.set("Window", e.control.data, str(value))
            except ValueError:
                pass

    def _check_updates(self, e):
        """检查更新"""
        pass

    def _handle_proxy_change(self, e):
        if self.config_manager:
            enabled = e.control.value
            self.config_manager.set("Proxy", "enabled", str(enabled))

    def _handle_proxy_url_change(self, e):
        if self.config_manager:
            proxy_url = e.control.value
            self.config_manager.set("Proxy", "url", proxy_url)

    async def _test_proxy(self, e):
        if not self.proxy_test_text:
            return

        self.proxy_test_text.value = "正在测试..."
        self.proxy_test_text.color = self.theme_colors.text_color
        self.page.update()

        try:
            # 使用 asyncio.to_thread 在后台线程中运行同步的 requests 调用
            def make_request():
                return requests.get("http://ip-api.com/json/", proxies=self.get_proxies(), timeout=10)

            response = await asyncio.to_thread(make_request)
            data = response.json()
            
            if response.status_code == 200:
                self.proxy_test_text.value = f"当前IP: {data.get('query', 'Unknown')} ({data.get('country', 'Unknown')})"
                self.proxy_test_text.color = self.theme_colors.text_color
            else:
                self.proxy_test_text.value = "测试失败: 无法获取IP信息"
                self.proxy_test_text.color = self.theme_colors.text_color
                
        except Exception as ex:
            self.proxy_test_text.value = f"测试失败: {str(ex)}"
            self.proxy_test_text.color = self.theme_colors.text_color
            
        self.page.update()
