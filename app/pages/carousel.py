import flet as ft
from components.fletcarousel.horizontal import BasicHorizontalCarousel, BasicAnimatedHorizontalCarousel
from components.fletcarousel.attributes import AutoCycle, HintLine
from app.base import BasePage

class CarouselPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="轮播图示例", **kwargs)

    def _build_basic_carousel(self) -> ft.Container:
        """构建基础轮播图示例"""
        return ft.Container(
            content=BasicHorizontalCarousel(
                page=self.page,
                items_count=3,
                # 主动控制是否自动轮播
                # auto_cycle=AutoCycle(duration=2),
                items=[
                    ft.Container(
                        content=ft.Text(value=str(i), size=20, color=self.theme_colors.text_color),
                        height=200,
                        width=300,
                        bgcolor=self.theme_colors.card_color,
                        border_radius=15,
                        alignment=ft.alignment.center,
                    ) for i in range(10)
                ],
                buttons=[
                    ft.FloatingActionButton(
                        icon=ft.Icons.NAVIGATE_BEFORE,
                        bgcolor=self.theme_colors.divider_color,
                    ),
                    ft.FloatingActionButton(
                        icon=ft.Icons.NAVIGATE_NEXT,
                        bgcolor=self.theme_colors.divider_color,
                    )
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                items_alignment=ft.MainAxisAlignment.CENTER
            ),
            margin=10,
        )

    def _build_animated_carousel(self) -> ft.Container:
        """构建动画轮播图示例"""
        # 创建一个空的容器作为初始内容
        initial_content = ft.Container(
            content=ft.Text(value="0", size=30, color=self.theme_colors.text_color),
            height=400,
            expand=True,
            bgcolor=self.theme_colors.card_color,
            border_radius=15,
            alignment=ft.alignment.center,
        )
        
        return ft.Container(
            content=BasicAnimatedHorizontalCarousel(
                page=self.page,
                auto_cycle=AutoCycle(duration=3),
                expand=True,
                padding=50,
                hint_lines=HintLine(
                    active_color=self.theme_colors.card_color,
                    inactive_color=self.theme_colors.text_color,
                    alignment=ft.MainAxisAlignment.CENTER,
                    max_list_size=300,
                ),
                animated_switcher=ft.AnimatedSwitcher(
                    content=initial_content,
                    transition=ft.AnimatedSwitcherTransition.SCALE,
                    duration=300,
                    reverse_duration=100,
                    switch_in_curve=ft.AnimationCurve.EASE_IN_OUT,
                    switch_out_curve=ft.AnimationCurve.EASE_IN_OUT,
                ),
                items=[
                    ft.Container(
                        content=ft.Text(value=str(i), size=30, color=self.theme_colors.text_color),
                        height=400,
                        expand=True,
                        bgcolor=self.theme_colors.card_color,
                        border_radius=15,
                        alignment=ft.alignment.center,
                    ) for i in range(10)
                ],
            ),
            clip_behavior="hardEdge",
        )
        
    def _build_animated_carousel_FADE(self) -> ft.Container:
        """构建动画轮播图示例"""
        # 创建一个空的容器作为初始内容
        initial_content = ft.Container(
            content=ft.Text(value="0", size=30, color=self.theme_colors.text_color),
            height=400,
            expand=True,
            bgcolor=self.theme_colors.card_color,
            border_radius=15,
            alignment=ft.alignment.center,
        )
        
        return ft.Container(
            content=BasicAnimatedHorizontalCarousel(
                page=self.page,
                auto_cycle=AutoCycle(duration=3),
                expand=True,
                padding=50,
                hint_lines=HintLine(
                    active_color=self.theme_colors.card_color,
                    inactive_color=self.theme_colors.text_color,
                    alignment=ft.MainAxisAlignment.CENTER,
                    max_list_size=300,
                ),
                animated_switcher=ft.AnimatedSwitcher(
                    content=initial_content,
                    transition=ft.AnimatedSwitcherTransition.FADE,
                    duration=800,
                    reverse_duration=400,
                    switch_in_curve=ft.AnimationCurve.EASE_OUT,
                    switch_out_curve=ft.AnimationCurve.EASE_IN,
                ),
                items=[
                    ft.Container(
                        content=ft.Text(value=str(i), size=30, color=self.theme_colors.text_color),
                        height=400,
                        expand=True,
                        bgcolor=self.theme_colors.card_color,
                        border_radius=15,
                        alignment=ft.alignment.center,
                    ) for i in range(10)
                ],
            ),
            clip_behavior="hardEdge",
        )

    def build_content(self) -> ft.Column:
        return ft.Column(
            controls=[
                ft.Text("基础轮播图", size=24, color=self.theme_colors.text_color),
                self._build_basic_carousel(),
                ft.Text("动画轮播图", size=24, color=self.theme_colors.text_color),
                self._build_animated_carousel(),
                ft.Text("动画轮播图-FADE", size=24, color=self.theme_colors.text_color),
                self._build_animated_carousel_FADE(),
            ],
            scroll="auto",
            spacing=10,
        )
