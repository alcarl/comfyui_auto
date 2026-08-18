import flet as ft
from components.fletcarousel.horizontal import BasicHorizontalCarousel
from components.fletcarousel.attributes import AutoCycle
from app.base import BasePage
import asyncio
import time

class HomePage(BasePage):
    def __init__(self, **kwargs):
        self.save_state_text = ft.TextField(label="保存状态测试文本框", hint_text="请在此输入，文字在切换主题时会保留")
        super().__init__(title="", **kwargs)
    
    def set_button_loading(self, button: ft.FloatingActionButton, is_loading: bool):
        """
        设置按钮的加载状态
        
        加载按钮动画
        
        要使用该方法，所有button在创建时必须设置width,否则显示不正常
        """
        if not hasattr(self, 'page') or not self.page or self.is_rebuilding():
            return
            
        if is_loading:
            # 创建一个环形加载动画
            progress_ring = ft.ProgressRing(
                width=16,
                height=16,
                stroke_width=2,
                color=self.theme_colors.text_color,
            )
            button.content = ft.Row(
                [
                    progress_ring,
                    ft.Text(
                        button.text,
                        color=self.theme_colors.text_color,
                        size=14,
                        weight=ft.FontWeight.W_500
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            )
        else:
            # 恢复按钮原始状态
            button.content = None
            button.text = button.text  # 保持原有文本
            # 如果要恢复原来的图标，可以添加以下代码
            # button.icon = {
            #     self.refresh_button: ft.Icons.REFRESH,
            #     self.continue_button: ft.Icons.PLAY_ARROW,
            #     self.stop_button: ft.Icons.STOP,
            # }.get(button)
        try:
            button.update()
        except AssertionError:
            # 忽略在页面重建过程中的更新错误
            pass

    def show_img_dialog(self, e, img_src):
        self.image_dialog.content.src = img_src
        self.page.open(self.image_dialog)
        self.page.update()
    
    def close_img_dialog(self, e):
        self.page.close(self.image_dialog)
        self.page.update()

    def _build_carousel(self) -> ft.Container:
        """构建轮播图"""
        # 根据窗口的大小来修改轮播图显示的数量
        # 添加图片对话框
        self.image_dialog = ft.AlertDialog(
            content=ft.Image(
                width=800,
                fit=ft.ImageFit.CONTAIN,
            ),
            actions=[
                ft.TextButton("关闭", on_click=self.close_img_dialog),
            ],
        )
        items_count = int((self.page.window.width - 400) // 300)

        # 轮播图项目
        carousel_items = [
            ft.Container(
                ft.Image( 
                    src=f"/images/screenshot{i}.png",
                    width=300,
                    fit=ft.ImageFit.CONTAIN,
                ),
                on_click=lambda e, img_num=i: self.show_img_dialog(e, f"/images/screenshot{img_num}.png"),
            ) for i in range(1, 5)            
        ]

        # 导航按钮
        nav_buttons = [
            ft.FloatingActionButton(
                icon=ft.Icons.NAVIGATE_BEFORE,
                bgcolor=self.theme_colors.divider_color,
            ),
            ft.FloatingActionButton(
                icon=ft.Icons.NAVIGATE_NEXT,
                bgcolor=self.theme_colors.divider_color,
            )
        ]

        carousel = BasicHorizontalCarousel(
            page=self.page,
            items_count=items_count,
            auto_cycle=AutoCycle(duration=5),
            items=carousel_items,
            buttons=nav_buttons,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            items_alignment=ft.MainAxisAlignment.CENTER,
            margin=ft.margin.all(20),
        )

        return carousel
    
    async def start_loading(self, e):
        """
        异步的方式：加载按钮动画
        
        所有的点击事件都需要一个默认参数，所以添加e参数
        """
        self.set_button_loading(self.loading_button, True)
        self.loading_button.disabled = True
        self.show_snackbar("按钮将被禁用，并且动画将持续10秒")
        await asyncio.sleep(10)
        self.set_button_loading(self.loading_button, False)
        self.loading_button.disabled = False
        self.page.update()
        
    def start_loading_thread(self):
        """
        子线程的方式：加载按钮动画
        
        所有的点击事件都需要一个默认参数，所以添加e参数
        """
        self.set_button_loading(self.loading_button_thread, True)
        self.loading_button_thread.disabled = True
        self.show_dialog("按钮将被禁用，并且动画将持续10秒", "加载中")
        time.sleep(10)
        self.set_button_loading(self.loading_button_thread, False)
        self.loading_button_thread.disabled = False
        self.page.update()

    def _build_stats_section(self) -> ft.Container:
        """构建统计信息部分"""
        # 活跃项目卡片
        projects_card = ft.Container(
            content=ft.Column([
                ft.Text("Statistics", color=self.theme_colors.text_color, size=20),
                ft.Text("125", color=self.theme_colors.text_color,
                        size=40, weight="bold"),
                ft.Text("Active Projects",
                        color=self.theme_colors.text_color, size=14),
            ]),
            bgcolor=self.theme_colors.card_color,
            padding=20,
            border_radius=ft.border_radius.all(10),
            width=200,
            height=150,
        )

        # 待办任务卡片
        tasks_card = ft.Container(
            content=ft.Column([
                ft.Text("Tasks", color=self.theme_colors.text_color, size=20),
                ft.Text("42", color=self.theme_colors.text_color,
                        size=40, weight="bold"),
                ft.Text("Pending Tasks",
                        color=self.theme_colors.text_color, size=14),
            ]),
            bgcolor=self.theme_colors.card_color,
            padding=20,
            border_radius=ft.border_radius.all(10),
            width=200,
            height=150,
        )
        
        self.loading_button = ft.FloatingActionButton(
                    icon=ft.Icons.REFRESH,
                    text="点击加载-异步",
                    width=150,
                    on_click=self.start_loading,
                    height=30,
                )
        self.loading_button_thread = ft.FloatingActionButton(
                    icon=ft.Icons.REFRESH,
                    text="点击加载-线程",
                    width=150,
                    on_click=lambda _: self.page.run_thread(self.start_loading_thread),
                    height=30,
                    bgcolor=ft.Colors.GREEN
                )
        self.loading_button_show = ft.Container(
            content=ft.Column([
                ft.Text("Loading Button", color=self.theme_colors.text_color, size=20),
                self.loading_button,
                self.loading_button_thread,
            ]),
            bgcolor=self.theme_colors.card_color,
            padding=20,
            border_radius=ft.border_radius.all(10),
            width=200,
            height=150,
        )
        
        self.notification_button = ft.FloatingActionButton(
            icon=ft.Icons.NOTIFICATIONS,
            text="显示通知",
            height=30,
            on_click=lambda _: self.show_notification("这是一条可叠加通知"),
        )
        
        self.notification_clear_button = ft.FloatingActionButton(
            icon=ft.Icons.CLEAR,
            text="清除所有通知",
            height=30,
            on_click=lambda _: self.notifications.clear(),
        )
        
        self.notification_button_show = ft.Container(
            content=ft.Column([
                ft.Text("通知测试", color=self.theme_colors.text_color, size=20),
                self.notification_button,
                self.notification_clear_button,
            ]),
            bgcolor=self.theme_colors.card_color,
            padding=20,
            border_radius=ft.border_radius.all(10),
            width=200,
            height=150,
        )
        
        self.button_switch_page = ft.FloatingActionButton(
            icon=ft.Icons.SWITCH_RIGHT,
            text="切换到Todo页面",
            on_click=lambda _: self.app.switch_page("todo"),
            bgcolor=self.theme_colors.accent_color,
        )
        
        stats_row = ft.Row([projects_card, tasks_card, self.loading_button_show, self.notification_button_show, self.button_switch_page], spacing=20)
        container = ft.Container(content=stats_row, padding=20)

        return container

    def _build_actions_section(self) -> ft.Container:
        """构建操作按钮部分"""
        action_buttons = [
            ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE,
                icon_color=self.theme_colors.text_color,
                icon_size=30,
                tooltip="Add New",
            ),
            ft.IconButton(
                icon=ft.Icons.FAVORITE,
                icon_color="red",
                icon_size=30,
                tooltip="Favorite",
            ),
            ft.IconButton(
                icon=ft.Icons.SHARE,
                icon_color=self.theme_colors.text_color,
                icon_size=30,
                tooltip="Share",
            ),
        ]

        return ft.Container(
            content=ft.Row(action_buttons, spacing=10),
            padding=20,
        )

    def _build_progress_section(self) -> ft.Container:
        """构建进度���分"""
        container = ft.Container(
            content=ft.Column([
                ft.Text("Project Progress", size=20,
                        color=self.theme_colors.text_color),
                ft.ProgressBar(
                    width=400,
                    value=0.7,
                    color="blue",
                    bgcolor=self.theme_colors.card_color,
                ),
                ft.Text("70% Completed", size=14,
                        color=self.theme_colors.text_color),
            ], spacing=10),
            padding=20,
        )
        return container

    def _build_activities_section(self) -> ft.Container:
        """构建活动列表部分"""
        activities = [
            ("Team Meeting", "10:00 AM", ft.Icons.CALENDAR_MONTH),
            ("Project Review", "2:30 PM", ft.Icons.WORK),
            ("Client Meeting", "4:00 PM", ft.Icons.PERSON),
        ]

        activity_items = [
            ft.ListTile(
                leading=ft.Icon(icon),
                title=ft.Text(title, color=self.theme_colors.text_color),
                subtitle=ft.Text(time, color=self.theme_colors.text_color),
            ) for title, time, icon in activities
        ]

        activities_list = ft.Container(
            content=ft.Column(activity_items),
            bgcolor=self.theme_colors.card_color,
            border_radius=ft.border_radius.all(10),
            padding=10,
        )

        title = ft.Text("Recent Activities", size=20,
                        color=self.theme_colors.text_color)
        content = ft.Column([title, activities_list], spacing=10)
        container = ft.Container(content=content, padding=20)

        return container

    def build_content(self) -> ft.Column:
        """构建页面内容"""
        section = self.build_section("测试保留数据", self.save_state_text)
        container = ft.Container(
            content=ft.Column([
                self._build_carousel(),
                self._build_stats_section(),
                section,
                self.build_section("", self._build_actions_section()),
                self._build_progress_section(),
                self._build_activities_section(),
            ], scroll="auto", spacing=10),
            bgcolor=self.theme_colors.bg_color,
        )
        return container
