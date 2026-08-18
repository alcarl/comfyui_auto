import flet as ft
from app.base import BasePage
from app.app import ThemeColors
from typing import Callable
from . import FloatingPage, TimePickerPage, ChartPage, ButtonsPage

class SubNavRail:
    """导航栏类，用于构建应用程序的导航栏。"""

    def __init__(
        self,
        page: ft.Page,
        theme_colors,
        on_change: Callable = None,
    ):
        self.page = page
        self.theme_colors: ThemeColors = theme_colors
        self.buttons = {}
        self.pages = {}  # 存储页面实例
        self.current_page = None
        self.nav_bar = []
        self.bottom_buttons = [ft.Container(expand=True)]  # 添加一个弹性容器作为占位符
        self.on_change = on_change  # 保存回调函数
        self.first_page_added = False  # 添加标记，用于跟踪第一个页面

    def add_page(self, name: str, page_class, icon, is_bottom=False):
        """
        添加页面和对应的导航按钮
        :param name: 页面唯一标识
        :param page_class: 页面类
        :param icon: 按钮图标
        :param is_bottom: 是否固定在底部
        """
        # 创建页面实例 - 直接使用已经创建的实例
        page_instance = page_class
        self.pages[name] = page_instance

        # 如果是第一个添加的页面，则自动激活
        active = not self.first_page_added
        if not self.first_page_added:
            self.first_page_added = True

        # 添加对应的导航按钮
        self.add_button(name, icon, active, is_bottom)

    # 显示第一个页面
    def show_first_page(self):
        if self.first_page_added:
            self.show_page(next(iter(self.pages.keys())))

    def show_page(self, name):
        """显示指定页面"""
        if name not in self.pages:
            print(f"页面 {name} 不存在！")
            return

        for btn_name, button in self.buttons.items():
            is_current = btn_name == name
            # 更新图标和文本颜色
            if isinstance(button.content, ft.Row):
                icon = button.content.controls[0]
                text = button.content.controls[1]
                icon.color = self.theme_colors.accent_color if is_current else ft.Colors.with_opacity(0.7, self.theme_colors.text_color)
                text.color = self.theme_colors.accent_color if is_current else ft.Colors.with_opacity(0.7, self.theme_colors.text_color)
            # 更新背景色
            button.bgcolor = ft.Colors.with_opacity(0.1, self.theme_colors.sub_nav_color) if is_current else None
            button.update()
            
        # 更新当前页面
        self.current_page = name

        # 调用回调函数通知页面变更
        if self.on_change:
            self.on_change(self.pages[name])

        self.page.update()

    def add_button(self, name, icon, active=False, is_bottom=False, on_click=None):
        """
        添加一个导航按钮
        :param name: 按钮唯一标识
        :param icon: 按钮图标 (Flet 图标名称)
        :param active: 是否默认激活
        :param is_bottom: 是否固定在底部
        """
        if name in self.buttons:
            raise ValueError(f"按钮 '{name}' 已存在！")

        button = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        icon,
                        size=26,
                        color=self.theme_colors.accent_color if active else ft.Colors.with_opacity(0.7, self.theme_colors.text_color),
                    ),
                    ft.Text(
                        name,
                        color=self.theme_colors.accent_color if active else ft.Colors.with_opacity(0.7, self.theme_colors.text_color),
                        size=13,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=12,
            ),
            padding=ft.padding.only(left=12, top=8, bottom=8, right=12),
            border_radius=ft.border_radius.all(6),
            bgcolor=ft.Colors.with_opacity(0.1, self.theme_colors.sub_nav_color) if active else None,
            ink=True,  # 添加水波纹效果
            on_hover=lambda e: self._handle_hover(e, name),  # 添加悬停效果
            on_click=lambda e: self._handle_click(name) if on_click is None else on_click(e),
            width=150,
        )
        self.buttons[name] = button

        # 如果按钮需要固定在底部，将它单独存储
        if is_bottom:
            self.bottom_buttons.append(button)
        else:
            self.nav_bar.append(button)

    def _handle_hover(self, e: ft.HoverEvent, name: str):
        """处理按钮悬停事件"""
        # 如果不是当前选中的按钮，才改变背景色
        if name != self.current_page:
            e.control.bgcolor = ft.Colors.with_opacity(0.05, self.theme_colors.sub_nav_color) if e.data == "true" else None
            e.control.update()

    def _handle_click(self, name):
        """处理按钮点击事件"""
        self.show_page(name)

    def switch_to(self, page_name: str):
        """
        切换到指定页面
        :param page_name: 页面名称
        :return: 是否切换成功
        """
        if page_name not in self.pages:
            print(f"页面 {page_name} 不存在！")
            return False

        # 更新按钮状态
        for btn_name, button in self.buttons.items():
            button.icon_color = ft.Colors.GREEN if btn_name == page_name else self.theme_colors.text_color
            button.text_color = ft.Colors.GREEN if btn_name == page_name else self.theme_colors.text_color
        # 显示页面
        self.show_page(page_name)
        return True

    def build(self):
        """
        返回导航栏控件
        """
        # 在主导航栏的按钮和底部按钮之间插入一个 Spacer
        controls = []  # 顶部空隙和用户头像
        controls.extend(self.nav_bar)  # 主按钮
        controls.extend(self.bottom_buttons)  # 底部按钮

        return ft.Container(
            content=ft.Column(
                controls=controls,
                alignment=ft.MainAxisAlignment.START,
                spacing=2,
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
            bgcolor=ft.Colors.with_opacity(0.95, self.theme_colors.sub_nav_color),
            padding=ft.padding.only(top=8),
            width=150,
            left=0,
            top=0,
            bottom=0,
            expand=True,
            border=ft.border.only(right=ft.BorderSide(1, self.theme_colors.divider_color)),
        )

class SubNavigationBar(BasePage):
    """子导航栏示例"""

    def __init__(self, **kwargs):
        # 设置为有子导航栏
        self.has_sub_nav = True
        super().__init__(title="子导航栏示例", has_sub_nav=self.has_sub_nav, **kwargs)

    def build_content(self) -> ft.Control:
        """构建页面内容"""
        # 定义子页面
        self._pages = [
            {"icon": ft.Icons.RECTANGLE, "name": "按钮", "page_class": ButtonsPage},
            {"icon": ft.Icons.ADD, "name": "主页", "page_class": FloatingPage},
            {"icon": ft.Icons.TEXT_FIELDS, "name": "时间选择", "page_class": TimePickerPage},
            {"icon": ft.Icons.BAR_CHART, "name": "图表", "page_class": ChartPage},
        ]

        # 初始化页面实例
        self._page_instances = {}
        for page_info in self._pages:
            self._page_instances[page_info["name"]] = page_info["page_class"](
                theme_colors=self.theme_colors,
                theme_mode=self.theme_mode,
                page=self.page,  # 使用从父类继承的 page 实例
            )

        # 设置当前页面
        self.current_page = list(self._page_instances.values())[0]

        # 创建自定义导航栏
        self.nav_rail = SubNavRail(
            page=self.page,
            theme_colors=self.theme_colors,
            on_change=self._handle_nav_change,
        )

        # 添加导航按钮
        for page_info in self._pages:
            self.nav_rail.add_page(
                name=page_info["name"],
                page_class=self._page_instances[page_info["name"]],
                icon=page_info["icon"],
            )

        # 构建内容区域
        self.content_area = ft.Container(
            content=self.current_page.build_content(),
            expand=True,
            padding=ft.padding.only(left=150),  # 为导航栏留出空间
        )

        # 构建布局
        return ft.Stack(
            controls=[
                # 内容区域
                self.content_area,
                # 子导航容器
                self.nav_rail.build(),
            ],
            expand=True,
        )

    def _handle_nav_change(self, page_instance):
        """处理子导航切换事件"""
        # 更新当前页面
        self.current_page: BasePage = page_instance

        # 更新内容区域
        if hasattr(self, 'content_area'):
            self.content_area.content = self.current_page.content
            self.page.update()
    
    def switch_page(self, page_name: str) -> bool:
        """
        切换到指定页面
        :param page_name: 页面名称
        :return: 是否切换成功
        """
        return self.nav_rail.switch_to(page_name)
