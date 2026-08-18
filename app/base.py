import flet as ft
from abc import ABC, abstractmethod
from typing import Callable, TYPE_CHECKING

from components.stacked_notifications import NotificationManager
from .config.theme import ThemeColors

if TYPE_CHECKING:
    from app.app import App

class BasePage(ABC):
    _notification_manager = None
    def __init__(self,
                on_theme_changed: Callable = None,
                theme_colors: ThemeColors = None,
                theme_mode: str = "dark",
                title: str = "",
                page: ft.Page = None,
                app: 'App' = None,
                has_sub_nav: bool = False
        ):
        
        self.on_theme_changed = on_theme_changed
        self.theme_colors = theme_colors or ThemeColors()
        self.theme_mode = theme_mode
        self.title = title
        self.page = page
        self._is_rebuilding = False  # 添加重建标志
        self._state = {}  # 添加状态存储
        self.proxies = None  # 添加代理设置
        self.has_sub_nav = has_sub_nav  # 是否启用子导航
        self.app : 'App' = app
        
        # 初始化 NotificationManager
        if page is not None and BasePage._notification_manager is None:
            BasePage._notification_manager = NotificationManager(page)
        
        # 添加一个新的属性来缓存构建的内容
        self._built_content = None
        self.content = self.build()
        
    def show_dialog(self, message: str, title: str = "提示"):
        """
        显示弹窗提示，可自定义动作

        了解更多请访问
        url: https://flet.qiannianlu.com/docs/controls/alertdialog
        """
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            # actions=[
            #     ft.TextButton("确定", on_click=lambda _: self.page.open(None)),
            #     ft.TextButton("取消", on_click=lambda _: self.page.open(None))
            #     ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dialog)
        self.page.update()
    
    def show_snackbar(self, message: str):
        """
        一条带有可选操作的轻量级消息，会在屏幕底部短暂显示。
        
        了解更多请访问
        url: https://flet.qiannianlu.com/docs/controls/snackbar
        """
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            show_close_icon=True,
            close_icon_color=self.theme_colors.accent_color,
        )
        self.page.open(snackbar)
        self.page.update()
    
    @property
    def notifications(self):
        """
        提供对 NotificationManager 的访问
        如果 NotificationManager 尚未初始化，会引发异常
        """
        if BasePage._notification_manager is None:
            raise RuntimeError("NotificationManager has not been initialized. Make sure 'page' is provided in the constructor.")
        return BasePage._notification_manager

    def show_notification(self, message: str, type: str = "info", duration: float = None, action: ft.Control = None):
        """
        便捷方法用于显示通知
        
        参数:
        message (str): 要显示的通知消息。
        type (str): 通知的类型，默认为 "info"。可选值包括 "info", "warning", "success", "error" 等。
        duration (float): 通知显示的持续时间，单位为秒。默认为 4s，表示持续显示直到用户关闭。
        action (ft.Control): 可选的操作控件，用户可以通过该控件进行交互。
        """
        self.notifications.show(message, type=type, duration=duration, action=action)

    def save_state(self):
        """保存页面状态，子类可以重写此方法来保存额外的状态"""
        state = {}
        # 只保存控件的值，让样式跟随主题
        for control_name, control in vars(self).items():
            if isinstance(control, (ft.TextField, ft.Dropdown, ft.RadioGroup, ft.Text)):
                state[control_name] = control.value
            elif isinstance(control, ft.ListView):
                state[control_name] = [c for c in control.controls]
            elif isinstance(control, ft.FloatingActionButton):
                state[control_name] = control.content
        return state

    def restore_state(self, state):
        """恢复页面状态，子类可以重写此方法来恢复额外的状态"""
        # 只恢复控件的值，让样式跟随主题
        for control_name, value in state.items():
            if hasattr(self, control_name):
                control = getattr(self, control_name)
                if isinstance(control, (ft.TextField, ft.Dropdown, ft.RadioGroup, ft.Text)):
                    control.value = value
                elif isinstance(control, ft.ListView):
                    control.controls = value

    def update_theme(self, theme_colors: ThemeColors, theme_mode: str):
        """更新主题时的处理"""
        self._is_rebuilding = True  # 设置重建标志

        # 保存当前状态
        self._state = self.save_state()

        # 更新主题
        self.theme_colors = theme_colors
        self.theme_mode = theme_mode

        # 清除缓存，强制下次调用build时重新构建
        self._built_content = None

        # 重建页面
        self.content = self.build()
        # 恢复状态
        self.restore_state(self._state)

        self._is_rebuilding = False  # 清除重建标志

    def is_rebuilding(self) -> bool:
        """检查页面是否正在重建"""
        return getattr(self, '_is_rebuilding', False)

    def build_title(self) -> ft.Container:
        """构建统一的标题栏"""
        container = ft.Container(
            content=ft.Text(
                self.title,
                size=23,
                color=self.theme_colors.text_color,
            ),
            padding=ft.padding.only(top=10, bottom=10, left=30),
            bgcolor=self.theme_colors.bg_color,
            margin=ft.margin.only(bottom=20) if not self.has_sub_nav else ft.margin.only(bottom=0),
            width=5000,
        )
        return container

    @abstractmethod
    def build_content(self) -> ft.Column:
        """
        子类实现此方法来构建页面主要内容
        
        避免重复创建的控件应该放在 __init__ 中
        """
        pass

    def build(self) -> ft.Container:
        """构建完整的页面布局"""
        if self._built_content is None or self.is_rebuilding():
            self._built_content = ft.Container(
                content=ft.Column(
                    controls=[
                        self.build_title(),
                        ft.Container(
                            content=self.build_content(),
                            expand=True,
                            bgcolor=self.theme_colors.bg_color,
                        ),
                    ],
                    spacing=0,
                    scroll="none",
                ),
                expand=True,
                bgcolor=self.theme_colors.bg_color,
            )
        return self._built_content

    def build_section(self, title: str = None, content: ft.Control = None, expand=None, **kwargs) -> ft.Container:
        """构建一个带标题的部分"""
        controls = []
        container_control = []

        if title:
            title_text = ft.Container(
                content=ft.Text(title, size=22, weight="bold",color=self.theme_colors.text_color),
                padding=ft.padding.only(left=30),
                )
            container_control.append(title_text)

        if content:
            if not isinstance(content, ft.Container):
                content = ft.Container(
                    content=content,
                    expand=True,
                )
            controls.append(content)

        section_content = ft.Column(
            controls=controls,
            spacing=10,
        )
        
        container_control.append(ft.Container(
                    content=section_content,
                    bgcolor=self.theme_colors.card_color,
                    padding=20 if title else 10,
                    border_radius=ft.border_radius.all(10),
                    border=ft.border.all(1, self.theme_colors.divider_color),
                    margin=ft.padding.symmetric(horizontal=10, vertical=5),
                    expand=expand,
                    **kwargs
                ))

        container = ft.Column(
            controls=container_control,
            spacing=0,
            scroll="none",
        )
        

        return container

    def get_proxies(self):
        """
        获取代理设置
        
        如果配置文件中没有设置代理，则返回None
        
        return 
            {"http": proxy_url, "https": proxy_url}
            {"http": None, "https": None}
        """
        if hasattr(self, "config_manager"):
            return {"http": None, "https": None}
        
        enabled_str = self.config_manager.get("Proxy", "enabled", False)
        proxy_url = self.config_manager.get("Proxy", "url", None)

        enabled = enabled_str.lower() == "true"
        
        if enabled and proxy_url:
            self.proxies = {"http": proxy_url, "https": proxy_url}
        else:
            self.proxies = {"http": None, "https": None}

        return self.proxies
