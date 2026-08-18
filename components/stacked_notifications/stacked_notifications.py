import flet as ft
from typing import List, Optional, Dict
import time
import threading
from dataclasses import dataclass

@dataclass
class NotificationType:
    """通知类型枚举"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class NotificationStyle:
    """通知样式配置类"""
    bgcolor: str
    icon: str
    text_color: str = ft.Colors.WHITE
    

class NotificationManager:
    """
    通知管理器类
    实现了单例模式，用于管理和显示堆叠式通知
    """
    _instance = None

    def __new__(cls, page: Optional[ft.Page] = None):
        if cls._instance is None:
            if page is None:
                raise ValueError("Page must be provided when creating the first instance")
            cls._instance = super(NotificationManager, cls).__new__(cls)
            cls._instance._initialize(page)
        return cls._instance

    def _initialize(self, page: ft.Page):
        self.page = page
        self.notifications: List[ft.Container] = []
        # 设置通知容器
        self.container = ft.Container(
            content=ft.Column([], spacing=10),
            right=20,                               # 设置通知容器左对齐
            bottom=20,                             # 设置通知容器底部对齐
            width=280,                              # 设置通知容器宽度
        )
        self.max_notifications = 5               # 设置最大通知数量
        self.default_duration = 3                # 设置默认通知持续时间
        # 设置通知样式
        self._styles: Dict[str, NotificationStyle] = {
            NotificationType.INFO: NotificationStyle(
                bgcolor=ft.Colors.BLUE,
                icon=ft.Icons.INFO,
            ),
            NotificationType.SUCCESS: NotificationStyle(
                bgcolor=ft.Colors.GREEN,
                icon=ft.Icons.CHECK_CIRCLE,
            ),
            NotificationType.WARNING: NotificationStyle(
                bgcolor=ft.Colors.ORANGE,
                icon=ft.Icons.WARNING,
            ),
            NotificationType.ERROR: NotificationStyle(
                bgcolor=ft.Colors.RED,
                icon=ft.Icons.ERROR,
            ),
        }
        page.overlay.append(self.container)
        page.update()

    def show(self, 
            message: str, 
            type: str = NotificationType.INFO,
            duration: float = None,
            action: ft.Control = None):
        if len(self.notifications) >= self.max_notifications:
            self._remove_notification(self.notifications[0])

        style = self._styles.get(type, self._styles[NotificationType.INFO])
        
        content_controls = [
            ft.Icon(style.icon, color=style.text_color, size=20),
            ft.Text(message, color=style.text_color, size=14),
        ]
        
        if action:
            content_controls.append(ft.Container(
                content=action,
                margin=ft.margin.only(left=10)
            ))

        notification = ft.Container(
            content=ft.Row(
                content_controls,
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
            ),
            bgcolor=style.bgcolor,
            padding=10,
            border_radius=8,
            opacity=1,
            animate_opacity=300,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=ft.Colors.BLACK26,
            )
        )
        
        self.notifications.append(notification)
        self.container.content.controls.append(notification)
        self.page.update()

        self._schedule_dismiss(notification, duration or self.default_duration)

    def _schedule_dismiss(self, notification: ft.Container, duration: float):
        def dismiss():
            time.sleep(duration)
            self._remove_notification(notification)

        threading.Thread(target=dismiss, daemon=True).start()

    def _remove_notification(self, notification: ft.Container):
        if notification in self.notifications:
            notification.opacity = 0
            self.page.update()
            time.sleep(0.2)
            if notification in self.notifications:
                self.notifications.remove(notification)
                self.container.content.controls.remove(notification)
                self.page.update()

    def clear(self):
        """
        清除所有通知
        """
        for notification in self.notifications[:]:
            self._remove_notification(notification)

    def set_max_notifications(self, max_count: int):
        """
        设置最大通知数量
        """
        self.max_notifications = max_count

    def set_default_duration(self, duration: float):
        """
        设置默认通知持续时间
        """
        self.default_duration = duration

    def add_custom_style(self, type_name: str, style: NotificationStyle):
        """
        添加自定义通知样式
        """
        self._styles[type_name] = style
        return type_name

