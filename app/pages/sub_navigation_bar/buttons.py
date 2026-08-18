import flet as ft
from app.base import BasePage


class ButtonsPage(BasePage):
    """按钮示例页面"""

    def __init__(self, **kwargs):
        super().__init__(title="按钮", **kwargs)

    def _build_activities_section(self) -> ft.Container:
        """构建活动列表部分"""
        activities = [
            ("Team Meeting", "10:00 AM", ft.Icons.CALENDAR_MONTH),
            ("Project Review", "2:30 PM", ft.Icons.WORK),
            ("Client Meeting", "4:00 PM", ft.Icons.PERSON),
        ]

        activity_items = [
            ft.ListTile(
                leading=ft.Icon(icon, color=self.theme_colors.text_color),
                title=ft.Text(title, color=self.theme_colors.text_color),
                subtitle=ft.Text(time, color=self.theme_colors.text_color),
            ) for title, time, icon in activities
        ]

        return ft.Container(
            content=ft.Column([
                ft.Text("Recent Activities", size=20, color=self.theme_colors.text_color),
                ft.Container(
                    content=ft.Column(activity_items),
                    bgcolor=self.theme_colors.card_color,
                    border_radius=ft.border_radius.all(10),
                    padding=10,
                )
            ], 
            spacing=10),
            padding=20,
            bgcolor=self.theme_colors.bg_color,
        )
    
    def build_content(self) -> ft.Control:
        # 创建基本按钮行
        button_row1 = ft.Row(
            controls=[
                ft.FilledButton(text="基本按钮"),
                ft.FilledButton(
                    text="带图标的按钮",
                    icon=ft.Icons.ADD,
                ),
                ft.FilledButton(
                    text="禁用按钮",
                    disabled=True,
                ),
            ],
            spacing=10,
        )
        
        button_row2 = ft.Row(
                controls=[
                    ft.OutlinedButton(text="基本轮廓按钮"),
                    ft.OutlinedButton(
                        text="带图标",
                        icon=ft.Icons.SETTINGS,
                    ),
                    ft.OutlinedButton(
                        text="禁用",
                        disabled=True,
                    ),
                ],
                spacing=10,
            )
        
        button_row3 = ft.Row(
                controls=[
                    ft.TextButton(text="基本文本按钮"),
                    ft.TextButton(
                        text="带图标",
                        icon=ft.Icons.INFO,
                    ),
                    ft.TextButton(
                        text="禁用",
                        disabled=True,
                    ),
                ],
                spacing=10,
            )
        
        button_row4 = ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.FAVORITE_BORDER,
                        icon_color="red",
                        icon_size=30,
                        tooltip="收藏",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SHARE,
                        icon_size=30,
                        tooltip="分享",
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        icon_size=30,
                        tooltip="删除",
                        disabled=True,
                    ),
                ],
                spacing=10,
            )
        
        button_row5 = ft.Row(
                controls=[  
                    ft.PopupMenuButton(
                        icon=ft.Icons.MENU,
                        items=[
                            ft.PopupMenuItem(text="选项 1"),
                            ft.PopupMenuItem(text="选项 2"),
                            ft.PopupMenuItem(text="选项 3"),
                        ],
                    ),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        items=[
                            ft.PopupMenuItem(
                                text="设置",
                                icon=ft.Icons.SETTINGS,
                            ),
                            ft.PopupMenuItem(),
                            ft.PopupMenuItem(
                                text="删除",
                                icon=ft.Icons.DELETE,
                            ),
                        ],
                    ),
                    ft.Container(
                        content=ft.PopupMenuButton(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ARROW_DROP_DOWN),
                                    ft.Text("更多选项"),
                                ],
                            ),
                            items=[
                                ft.PopupMenuItem(text="子选项 1"),
                                ft.PopupMenuItem(text="子选项 2"),
                            ],
                        ),
                        border=ft.border.all(1, ft.Colors.BLUE),
                        border_radius=ft.border_radius.all(4),
                        padding=ft.padding.all(8),
                    ),
                ],
                spacing=10,
            )

        # 创建按钮示例部分
        buttons_section1 = self.build_section(
            "填充按钮",
            ft.Column([button_row1], spacing=10),
            expand=True,
        )
        
        buttons_section2 = self.build_section(
            "轮廓按钮",
            ft.Column([button_row2], spacing=10),
            expand=True,
        )
        
        buttons_section3 = self.build_section(
            "文本按钮",
            ft.Column([button_row3], spacing=10),
            expand=True,
        )
        
        buttons_section4 = self.build_section(
            "图标按钮",
            ft.Column([button_row4], spacing=10),
            expand=True,
        )
        
        buttons_section5 = self.build_section(
            "菜单按钮",
            ft.Column([button_row5], spacing=10),
            expand=True,
        )
        

        # 创建活动列表部分
        activities_section = self.build_section(
            "活动列表",
            self._build_activities_section(),
            expand=True,
        )

        # 将所有部分放入一个可滚动的列中
        return ft.Column(
            controls=[
                buttons_section1,
                buttons_section2,
                buttons_section3,
                buttons_section4,
                buttons_section5,
                activities_section,
            ],
            scroll="auto",
            expand=True,
            spacing=20,
        )
