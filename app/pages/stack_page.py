import time
import flet as ft
from app.base import BasePage


class StackPage(BasePage):
    def __init__(self, config_manager=None, app=None, **kwargs):
        self.config_manager = config_manager
        self.app = app
        super().__init__(**kwargs)

    def show_settings_popup(self, e):
        # self.settings_popup.visible = True
        self.settings_popup.height = None
        self.settings_popup.offset = ft.transform.Offset(0, 0)
        self.settings_button.on_click = self.close_settings_popup
        self.page.update()

    def close_settings_popup(self, e):
        self.settings_popup.offset = ft.transform.Offset(0, -1.5)
        self.settings_button.on_click = self.show_settings_popup
        self.page.update()
        time.sleep(0.51)
        self.settings_popup.height = 0
        self.settings_popup.update()
        self.page.update()

    def _handle_theme_change(self, e):
        """处理主题模式变更"""
        pass

    def _handle_theme_color_change(self, e):
        """处理主题颜色变更"""
        pass

    def _handle_window_size_change(self, e):
        """处理窗口尺寸变更"""
        pass

    def _handle_nav_rail_change(self, e):
        pass

    def build_settings_popup(self):
        # 创建设置弹窗
        self.settings_popup = ft.Container(
            border_radius=10,
            # bottom=10,
            left=130,  # 因为有动画, 弹窗的窗口需要绝对定位
            height=0,
            offset=ft.transform.Offset(0, -1.5),  # 控制窗口从上或者下弹出  ft.transform.Offset(0, 1.5)
            animate_offset=ft.animation.Animation(500, "decelerate"),
            bgcolor=self.theme_colors.divider_color,
            content=ft.Container(
                width=500,
                padding=20,
                content=ft.Column(
                    [
                        ft.Row([ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD), ft.Container(expand=True), ft.IconButton(icon=ft.Icons.CLOSE, on_click=self.close_settings_popup)], alignment=ft.MainAxisAlignment.END),
                        ft.Divider(),
                        # 主题设置部分
                        ft.Text("Theme", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                ft.Text("Theme Mode", size=14),
                                ft.Container(width=20),
                                ft.SegmentedButton(
                                    segments=[
                                        ft.Segment(
                                            value="light",
                                            label=ft.Text("Light"),
                                            icon=ft.Icon(ft.Icons.LIGHT_MODE),
                                        ),
                                        ft.Segment(
                                            value="dark",
                                            label=ft.Text("Dark"),
                                            icon=ft.Icon(ft.Icons.DARK_MODE),
                                        ),
                                        ft.Segment(
                                            value="system",
                                            label=ft.Text("System"),
                                            icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO),
                                        ),
                                    ],
                                    selected={self.config_manager.get("Theme", "mode", "system") if self.config_manager else "system"},
                                    on_change=self._handle_theme_change,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        ft.Row(
                            [
                                ft.Text("Theme Color", size=14),
                                ft.Container(width=20),
                                ft.Dropdown(
                                    width=200,
                                    value=self.config_manager.get("Theme", "color", "#4F46E5") if self.config_manager else "#4F46E5",
                                    content_padding=ft.padding.symmetric(horizontal=10),
                                    options=[
                                        ft.dropdown.Option(key=color, content=ft.Row([ft.Icon(ft.Icons.COLOR_LENS, color=color), ft.Text(name)]))
                                        for name, color in [("Light Blue", "#6E9ECF"), ("Indigo", "#4F46E5"), ("Emerald", "#10B981"), ("Coral", "#F43F5E"), ("Amber", "#F59E0B"), ("Amethyst", "#8B5CF6"), ("Cyan", "#06B6D4"), ("Rose Gold", "#F472B6")]
                                    ],
                                    on_change=self._handle_theme_color_change,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        ft.Divider(),
                        # 窗口设置部分
                        ft.Text("Window", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                ft.TextField(
                                    label="Default Width",
                                    value=self.config_manager.get("Window", "width", "1300") if self.config_manager else "1300",
                                    width=150,
                                    data="width",
                                    on_change=self._handle_window_size_change,
                                ),
                                ft.TextField(
                                    label="Default Height",
                                    value=self.config_manager.get("Window", "height", "800") if self.config_manager else "800",
                                    width=150,
                                    data="height",
                                    on_change=self._handle_window_size_change,
                                ),
                            ],
                            spacing=20,
                        ),
                        ft.Row(
                            [
                                ft.TextField(
                                    label="Min Width",
                                    value=self.config_manager.get("Window", "min_width", "500") if self.config_manager else "500",
                                    width=150,
                                    data="min_width",
                                    on_change=self._handle_window_size_change,
                                ),
                                ft.TextField(
                                    label="Min Height",
                                    value=self.config_manager.get("Window", "min_height", "400") if self.config_manager else "400",
                                    width=150,
                                    data="min_height",
                                    on_change=self._handle_window_size_change,
                                ),
                            ],
                            spacing=20,
                        ),
                        ft.Divider(),
                        # 导航栏设置
                        ft.Text("Navigation", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                ft.Text("Navigation Bar", size=14),
                                ft.Container(width=20),
                                ft.Switch(
                                    label="Default Extended",
                                    value=self.config_manager.get("Theme", "nav_rail_extended", "true").lower() == "true" if self.config_manager else True,
                                    on_change=self._handle_nav_rail_change,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        ft.Text("Navigation", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                ft.Text("Navigation Bar", size=14),
                                ft.Container(width=20),
                                ft.Switch(
                                    label="Default Extended",
                                    value=self.config_manager.get("Theme", "nav_rail_extended", "true").lower() == "true" if self.config_manager else True,
                                    on_change=self._handle_nav_rail_change,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                    ],
                    scroll=ft.ScrollMode.ALWAYS,
                    spacing=20,
                    height=500,
                ),
            ),
        )
        return self.settings_popup

    def build_animate_container(self):
        self.animate_status = True
        c1 = ft.Container(width=50, height=50, bgcolor="red", top=10, left=0, animate_position=1000)

        c2 = ft.Container(
            width=50, height=50, bgcolor="green", top=70, left=0, animate_position=500
        )

        c3 = ft.Container(
            width=50, height=50, bgcolor="blue", top=130, left=0, animate_position=1000
        )
        
        def animate_container(e):
            if self.animate_status:
                c1.top = 20
                c1.left = 200
                c2.top = 100
                c2.left = 40
                c3.top = 180
                c3.left = 100
                self.animate_status = False
            else:
                c1.top = 10
                c1.left = 0
                c2.top = 70
                c2.left = 0
                c3.top = 130
                c3.left = 0
                self.animate_status = True
            self.page.update()
        
        return ft.Container(
            content=ft.Stack(
                controls=[
                    c1, 
                    c2, 
                    c3,
                    ft.ElevatedButton("Animate!", on_click=animate_container, bottom=10),
                ],
            ),
            width=400,
            height=250,
            left=400,
            border=ft.border.all(1, self.theme_colors.divider_color),
            border_radius=10,
        )
        

    def build_content(self):
        self.settings_button = ft.FloatingActionButton(
            icon=ft.Icons.SETTINGS,
            text="Settings",
            on_click=self.show_settings_popup,
        )

        self.avatar = ft.Stack(
            controls=[
                    ft.CircleAvatar(foreground_image_src="https://avatars.githubusercontent.com/u/5041459?s=88&v=4"),
                    ft.Container(
                        content=ft.CircleAvatar(bgcolor=ft.Colors.GREEN, radius=5),
                        alignment=ft.alignment.bottom_left,
                    ),
                ],
            width=40,
            height=40,
            right=10,
            top=10,
        )

        # stack 上面所有的元素都有绝对定位, 通过 left, top, right, bottom 来控制位置
        self.stack = ft.Stack(
            controls=[
                ft.Row(
                    [self.settings_button],
                    alignment=ft.MainAxisAlignment.START,
                    expand=True,
                    bottom=10,
                ),
                ft.Image(
                    src="images/screenshot1.png",
                    width=300,
                    height=300,
                    fit=ft.ImageFit.CONTAIN,
                    left=10,
                ),
                ft.Row(
                    [
                        ft.Text(
                            "image demo",
                            color="black",
                            size=40,
                            weight="bold",
                            opacity=0.5,
                        )
                    ],
                    left=20,
                ),
                self.avatar,
                self.build_animate_container(),

                # 最后创建的在最上层
                self.build_settings_popup(),
            ],
            expand=True,
        )
        return self.build_section(title="", content=self.stack, expand=True)
