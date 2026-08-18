import flet as ft
from flet import (
    Page,
    Container,
    Column,
    Row,
    IconButton,
    Text,
    NavigationRail,
    NavigationRailDestination,
    colors,
    Icons,
    padding,
    margin,
    border_radius,
    alignment,
    Control,
    RadioGroup,
    Radio,
    ThemeMode,
    ScrollMode,
    ListTile,
    Icon,
    ProgressBar,
    WindowDragArea
)
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable


class ThemeColors:
    def __init__(self, is_dark: bool = True):
        if is_dark:
            self.title_bar_color = "#1E2228"
            self.bg_color = "#141518"
            self.nav_color = "#1E2228"
            self.card_color = "#1E2228"
            self.divider_color = "#0A0A0C"
            self.text_color = "#EEEEEE"
        else:
            self.title_bar_color = "#E9E9E9"  # 标题栏背景色 
            self.bg_color = "#F6F6F6"  # 更柔和的背景色
            self.nav_color = "#E9E9E9"  # 更清淡的导航背景色
            self.card_color = "#F2F2F2"  # 使用纯白色卡片，增加对比
            self.divider_color = "#9AA6B2"  # 稍微深一点的分隔线颜色
            self.text_color = "#333333"  # 更深的文本颜色，增加可读性


class BasePage(ABC):
    def __init__(self, on_theme_changed: Callable = None, theme_colors: ThemeColors = None, theme_mode: str = "dark", title: str = ""):
        self.on_theme_changed = on_theme_changed
        self.theme_colors = theme_colors or ThemeColors()
        self.theme_mode = theme_mode
        self.title = title
        self.content = self.build()

    def build_title(self) -> Container:
        """构建统一的标题栏"""
        return Container(
            content=Text(
                self.title,
                size=23,
                color=self.theme_colors.text_color,
                # left=10,
            ),
            padding=padding.only(top=10, bottom=10, left=30),
            bgcolor=self.theme_colors.nav_color,
            # 向左偏移
            margin=margin.only(left=-10),
            # 横向布满
            width=5000,
        )

    def build_content(self) -> Column:
        """子类实现此方法来构建页面主要内容"""
        pass

    def build(self) -> Container:
        """构建完整的页面布局"""
        return Container(
            content=Column(
                controls=[
                    self.build_title(),  # 标题部分
                    Container(  # 内容部分
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

    def update_theme(self, theme_colors: ThemeColors, theme_mode: str):
        self.theme_colors = theme_colors
        self.theme_mode = theme_mode
        self.content = self.build()


class HomePage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="主页", **kwargs)

    def build_content(self) -> Column:
        return Column(
            controls=[
                # 卡片行
                Container(
                    content=Row(
                        controls=[
                            Container(
                                content=Column([
                                    Text(
                                        "Statistics", color=self.theme_colors.text_color, size=20),
                                    Text(
                                        "125", color=self.theme_colors.text_color, size=40, weight="bold"),
                                    Text(
                                        "Active Projects", color=self.theme_colors.text_color, size=14),
                                ]),
                                bgcolor=self.theme_colors.card_color,
                                padding=20,
                                border_radius=10,
                                width=200,
                                height=150,
                            ),
                            Container(
                                content=Column([
                                    Text(
                                        "Tasks", color=self.theme_colors.text_color, size=20),
                                    Text(
                                        "42", color=self.theme_colors.text_color, size=40, weight="bold"),
                                    Text(
                                        "Pending Tasks", color=self.theme_colors.text_color, size=14),
                                ]),
                                bgcolor=self.theme_colors.card_color,
                                padding=20,
                                border_radius=10,
                                width=200,
                                height=150,
                            ),
                        ],
                        spacing=20,
                    ),
                    padding=20,
                ),
                # 按钮示例行
                Container(
                    content=Row(
                        controls=[
                            IconButton(
                                icon=Icons.ADD_CIRCLE,
                                icon_color=self.theme_colors.text_color,
                                icon_size=30,
                                tooltip="Add New",
                            ),
                            IconButton(
                                icon=Icons.FAVORITE,
                                icon_color="red",
                                icon_size=30,
                                tooltip="Favorite",
                            ),
                            IconButton(
                                icon=Icons.SHARE,
                                icon_color=self.theme_colors.text_color,
                                icon_size=30,
                                tooltip="Share",
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=20,
                ),
                # 进度指示器示例
                Container(
                    content=Column(
                        controls=[
                            Text("Project Progress", size=20,
                                 color=self.theme_colors.text_color),
                            ProgressBar(
                                width=400,
                                value=0.7,
                                color="blue",
                                bgcolor=self.theme_colors.card_color,
                            ),
                            Text("70% Completed", size=14,
                                 color=self.theme_colors.text_color),
                        ],
                        spacing=10,
                    ),
                    padding=20,
                ),
                # 列表示例
                Container(
                    content=Column(
                        controls=[
                            Text("Recent Activities", size=20,
                                 color=self.theme_colors.text_color),
                            Container(
                                content=Column([
                                    ListTile(
                                        leading=Icon(Icons.CALENDAR_MONTH),
                                        title=Text(
                                            "Team Meeting", color=self.theme_colors.text_color),
                                        subtitle=Text(
                                            "10:00 AM", color=self.theme_colors.text_color),
                                    ),
                                    ListTile(
                                        leading=Icon(Icons.WORK),
                                        title=Text(
                                            "Project Review", color=self.theme_colors.text_color),
                                        subtitle=Text(
                                            "2:30 PM", color=self.theme_colors.text_color),
                                    ),
                                    ListTile(
                                        leading=Icon(Icons.PERSON),
                                        title=Text(
                                            "Client Meeting", color=self.theme_colors.text_color),
                                        subtitle=Text(
                                            "4:00 PM", color=self.theme_colors.text_color),
                                    ),
                                ]),
                                bgcolor=self.theme_colors.card_color,
                                border_radius=10,
                                padding=10,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=20,
                ),
            ],
            scroll=ScrollMode.AUTO,
            spacing=0,
        )


class WidgetsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Widgets Page", **kwargs)

    def build_content(self) -> Column:
        return Column(
            controls=[
                Container(
                    content=Row(
                        controls=[
                            Container(
                                content=Text(
                                    "Widget Controls", color=self.theme_colors.text_color),
                                bgcolor=self.theme_colors.card_color,
                                padding=20,
                                border_radius=10,
                                width=200,
                                height=100,
                            ),
                        ],
                    ),
                    padding=20,
                ),
                # ... 其他内容 ...
            ],
            scroll=ScrollMode.AUTO,
            spacing=0,
        )


class NewPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="New Page", **kwargs)

    def build_content(self) -> Column:
        return Column(
            controls=[
                Container(
                    content=Text("New Page", size=32,
                                 color=self.theme_colors.text_color),
                    padding=20,
                ),
            ],
            scroll=ScrollMode.AUTO,
            spacing=0,
        )


class SavePage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Save Page", **kwargs)

    def build_content(self) -> Column:
        return Column(
            controls=[
                Container(
                    content=Text("Save Page", size=32,
                                 color=self.theme_colors.text_color),
                    padding=20,
                ),
            ],
            scroll=ScrollMode.AUTO,
            spacing=0,
        )


class SettingsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="设置", **kwargs)

    def build_content(self) -> Column:
        def on_theme_change(e):
            if self.on_theme_changed:
                self.on_theme_changed(e.control.value)

        return Column(
            controls=[
                Container(
                    content=Column(
                        controls=[
                            Text("Theme Mode", size=20,
                                 color=self.theme_colors.text_color),
                            RadioGroup(
                                content=Column(
                                    controls=[
                                        Radio(value="dark",
                                              label="Dark Theme"),
                                        Radio(value="light",
                                              label="Light Theme"),
                                        Radio(value="system",
                                              label="System Theme"),
                                    ]
                                ),
                                value=self.theme_mode,
                                on_change=on_theme_change,
                            ),
                        ],


                    ),
                    bgcolor=self.theme_colors.card_color,
                    padding=20,
                    border_radius=10,
                    margin=margin.only(top=10),
                ),
            ],
            scroll=ScrollMode.AUTO,
            spacing=0,
        )


class App:
    def __init__(self):
        self.page = None
        # app 标题
        self.app_title = "PyDracula"
        self.theme_mode = "dark"  # 'dark', 'light', or 'system'
        self.theme_colors = ThemeColors(is_dark=True)
        self.content_area = None
        self.nav_rail = None
        self.current_page_index = 0
        self.pages: Dict[int, BasePage] = {}
        self.is_nav_extended = True  # 添加这行，用于跟踪导航栏的展开状态
        self._init_pages()

    def _update_pages_theme(self):
        for page in self.pages.values():
            page.update_theme(self.theme_colors, self.theme_mode)
        # Update current page content
        self.content_area.content = self.pages[self.current_page_index].content

    def _update_layout_theme(self):
        if self.content_area:
            self.content_area.bgcolor = self.theme_colors.bg_color
        if self.nav_rail:
            self.nav_rail.bgcolor = self.theme_colors.nav_color
        if self.page:
            self.page.bgcolor = self.theme_colors.bg_color
            # 更新标题栏颜色
            if self.page.controls and self.page.controls[0].controls:
                title_bar = self.page.controls[0].controls[0]
                title_bar.bgcolor = self.theme_colors.nav_color

    def _get_effective_theme(self) -> bool:
        """Returns True for dark theme, False for light theme"""
        if self.theme_mode == "system":
            # Get the system theme from the page's system_theme
            return self.page.platform_brightness == "dark"
        return self.theme_mode == "dark"

    def _update_theme_colors(self):
        is_dark = self._get_effective_theme()
        self.theme_colors = ThemeColors(is_dark=is_dark)

    def change_theme(self, theme_mode: str):
        self.theme_mode = theme_mode

        if theme_mode == "system":
            # Get current system theme and set the corresponding theme mode
            is_dark = self.page.platform_brightness == "dark"
            self.page.theme_mode = ThemeMode.DARK if is_dark else ThemeMode.LIGHT
        elif theme_mode == "dark":
            self.page.theme_mode = ThemeMode.DARK
        else:  # light
            self.page.theme_mode = ThemeMode.LIGHT

        self._update_theme_colors()
        self._update_pages_theme()
        self._update_layout_theme()
        self.page.update()

    def _init_pages(self):
        """
        当用户选择一个导航项时，nav_change 函数会被调用。该函数通过 e.control.selected_index 获取用户选择的索引，并使用该索引来访问 self.pages 中的相应页面实例
        """
        self.pages = {
            0: HomePage(theme_colors=self.theme_colors, theme_mode=self.theme_mode),
            1: WidgetsPage(theme_colors=self.theme_colors, theme_mode=self.theme_mode),
            2: NewPage(theme_colors=self.theme_colors, theme_mode=self.theme_mode),
            3: SavePage(theme_colors=self.theme_colors, theme_mode=self.theme_mode),
            4: SettingsPage(
                on_theme_changed=self.change_theme,
                theme_colors=self.theme_colors,
                theme_mode=self.theme_mode
            ),
        }

    def init_page(self, page: Page):
        """
        初始化页面，设置页面属性，并设置系统主题变化处理程序
        """
        self.page = page

        # Set up system theme change handler
        def handle_system_theme_change(e):
            if self.theme_mode == "system":
                is_dark = e.data == "dark"
                self.page.theme_mode = ThemeMode.DARK if is_dark else ThemeMode.LIGHT
                self.theme_colors = ThemeColors(is_dark=is_dark)
                self._update_pages_theme()
                self._update_layout_theme()
                self.page.update()

        # Set page properties
        page.padding = 0
        page.theme_mode = ThemeMode.DARK
        page.bgcolor = self.theme_colors.bg_color
        page.on_platform_brightness_change = handle_system_theme_change

        # 修改窗口属性设置方式
        page.window.title_bar_hidden = True
        # page.window.frameless = True

        # 设置窗口大小和位置
        page.window.width = 1300
        page.window.height = 800
        page.window.min_width = 500
        page.window.min_height = 400

        # 将窗口居中显示
        page.window.center()

        def nav_change(e):
            selected_index = e.control.selected_index
            # Exit button (moved to index 5 due to settings)
            if selected_index == 5:
                page.window.close()
            else:
                self.current_page_index = selected_index
                self.content_area.content = self.pages[selected_index].content
                page.update()

        def toggle_nav_rail(e):
            self.is_nav_extended = not self.is_nav_extended
            # 重新创建导航栏以更新所有样式
            old_selected_index = self.nav_rail.selected_index
            self.nav_rail = NavigationRail(
                selected_index=old_selected_index,
                label_type="selected" if self.is_nav_extended else "none",
                min_width=60,
                min_extended_width=200,
                extended=self.is_nav_extended,
                bgcolor=self.theme_colors.nav_color,
                leading=Container(
                    content=Text(
                        " PyDracula " if self.is_nav_extended else "PD",
                        size=30,
                        weight="bold",
                        color="#89A8B2"
                    ),
                    margin=padding.only(top=20, bottom=20),
                    padding=0,
                ),
                # group_alignment=-0.9,
                destinations=[
                    NavigationRailDestination(
                        icon=item["icon"],
                        selected_icon=item["icon"],
                        label=item["label"],
                        padding=padding.only(
                            left=10) if self.is_nav_extended else None,
                    ) for item in self.nav_items
                ],
                on_change=nav_change,
                trailing=Container(
                    content=IconButton(
                        icon=Icons.CHEVRON_LEFT if self.is_nav_extended else Icons.CHEVRON_RIGHT,
                        # icon_color=self.theme_colors.nav_color,
                        on_click=toggle_nav_rail,
                    ),
                    margin=padding.only(bottom=20),
                ),
            )
            # 更新页面布局
            self.page.controls[0].controls[1].controls[0] = self.nav_rail
            self.page.update()

        # Navigation items 修改导航栏的图标和标签
        self.nav_items = [

            {"icon": Icons.HOME_ROUNDED, "label": "主页"},
            {"icon": Icons.WIDGETS_ROUNDED, "label": "组件"},
            {"icon": Icons.ADD_ROUNDED, "label": "新建"},
            {"icon": Icons.SAVE_ROUNDED, "label": "保存"},
            {"icon": Icons.SETTINGS_ROUNDED, "label": "设置"},

            {"icon": Icons.CLOSE_ROUNDED, "label": "退出"},
        ]

        # Create navigation rail LOGO
        self.nav_rail = NavigationRail(
            selected_index=0,
            label_type="selected" if self.is_nav_extended else "none",
            min_width=60,  # 收缩时的最小宽度
            min_extended_width=200,  # 展开时的宽度
            extended=self.is_nav_extended,
            bgcolor=self.theme_colors.nav_color,
            leading=Container(
                content=Text(
                    f" {self.app_title} " if self.is_nav_extended else self.app_title[0],
                    size=30,
                    weight="bold",
                    color="#89A8B2"
                ),
                margin=padding.only(top=20, bottom=20),
                padding=0,
            ),
            group_alignment=-0.9,
            destinations=[
                NavigationRailDestination(
                    icon=item["icon"],
                    selected_icon=item["icon"],
                    label=item["label"],
                    padding=padding.only(
                        left=10) if self.is_nav_extended else None,
                ) for item in self.nav_items
            ],
            on_change=nav_change,
            trailing=Container(
                content=IconButton(
                    icon=Icons.CHEVRON_LEFT if self.is_nav_extended else Icons.CHEVRON_RIGHT,
                    icon_color=self.theme_colors.text_color,
                    on_click=toggle_nav_rail,
                ),
                margin=padding.only(bottom=20),
            ),
        )

        # Main content area
        self.content_area = Container(
            content=self.pages[0].content,
            expand=True,
            bgcolor=self.theme_colors.bg_color,
        )

        # Main layout
        page.add(
            Column(
                controls=[
                    # 添加标题栏
                    self._build_title_bar(),
                    # 主内容区域
                    Row(
                        controls=[
                            Container(  # 将 NavigationRail 包装在 Container 中
                                content=self.nav_rail,
                                padding=0,  # 移除内边距
                            ),
                            # 分割线
                            Container(  # 将分割线包装在 Container 中
                                content=ft.VerticalDivider(
                                    width=1,
                                    color=self.theme_colors.divider_color,
                                ),
                                padding=padding.only(
                                    left=0, right=0),  # 移除水平内边距
                                margin=margin.all(0),  # 移除外边距
                            ),
                            Container(
                                content=self.content_area,
                                padding=padding.only(left=10),  # 移除水平内边距
                                expand=True,
                            ),
                        ],
                        expand=True,
                        spacing=0,  # 设置间距为0
                        tight=True,  # 添加这个属性使元素紧密排列
                    ),
                ],
                expand=True,
                spacing=0,
            )
        )

    # 在 App 类中添加一个方法来创建标题栏
    def _build_title_bar(self) -> Container:
        def minimize(e):
            self.page.window.minimized = True
            self.page.update()

        def maximize(e):
            self.page.window.maximized = not self.page.window.maximized
            # 强制重新构建标题栏以更新图标
            if self.page.controls and self.page.controls[0].controls:
                self.page.controls[0].controls[0] = self._build_title_bar()
            self.page.update()

        def close(e):
            self.page.window.close()
            self.page.update()

        return WindowDragArea(
            content=Container(
                content=Row(
                    controls=[
                        # 标题文本
                        Container(
                            content=Text(
                                self.app_title,
                                size=14,
                                weight="bold",
                            ),
                            alignment=alignment.center,
                            expand=True,
                        ),
                        # 使用空白Container来推动按钮到右侧
                        # Container(expand=True),
                        # 窗口控制按钮组
                        Container(
                            content=Row(
                                controls=[
                                    IconButton(
                                        icon=Icons.REMOVE,
                                        icon_size=20,
                                        tooltip="最小化",
                                        on_click=minimize,
                                    ),
                                    IconButton(
                                        # 根据窗口状态切换图标
                                        icon=Icons.CROP_DIN if self.page.window.maximized else Icons.CROP_SQUARE,
                                        icon_size=20,
                                        tooltip="还原" if self.page.window.maximized else "最大化",
                                        on_click=maximize,
                                    ),
                                    IconButton(
                                        icon=Icons.CLOSE,
                                        icon_size=20,
                                        tooltip="关闭",
                                        on_click=close,
                                    ),
                                ],
                                spacing=0,
                            ),
                            padding=padding.only(right=10),
                        ),
                    ],
                    spacing=0,
                ),
                bgcolor=self.theme_colors.nav_color,
            )
        )


def main(page: Page):
    app = App()
    app.init_page(page)


if __name__ == "__main__":
    ft.app(target=main)
