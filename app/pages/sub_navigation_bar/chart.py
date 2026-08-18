import flet as ft
from app.base import BasePage

class ChartPage(BasePage):
    """图表示例页面"""
    
    def __init__(self, **kwargs):
        self.toggle = False
        super().__init__(title="图表", **kwargs)
    
    def build_pie_chart(self):
        pie_chart1_normal_border = ft.BorderSide(0, ft.Colors.with_opacity(0, ft.Colors.WHITE))
        pie_chart1_hovered_border = ft.BorderSide(6, ft.Colors.WHITE)


        def on_chart_event(e: ft.PieChartEvent):
            for idx, section in enumerate(self.pie_chart1.sections):
                section.border_side = (
                    pie_chart1_hovered_border if idx == e.section_index else pie_chart1_normal_border
                )
            self.pie_chart1.update()

        self.pie_chart1 = ft.PieChart(
            sections=[
                ft.PieChartSection(
                    25,
                    color=ft.Colors.BLUE,
                    radius=80,
                    border_side=pie_chart1_normal_border,
                ),
                ft.PieChartSection(
                    25,
                    color=ft.Colors.YELLOW,
                    radius=65,
                    border_side=pie_chart1_normal_border,
                ),
                ft.PieChartSection(
                    25,
                    color=ft.Colors.PINK,
                    radius=60,
                    border_side=pie_chart1_normal_border,
                ),
                ft.PieChartSection(
                    25,
                    color=ft.Colors.GREEN,
                    radius=70,
                    border_side=pie_chart1_normal_border,
                ),
            ],
            sections_space=1,
            center_space_radius=0,
            on_chart_event=on_chart_event,
            expand=True,
        )
        
        # 饼图 2
        pie_chart2_normal_radius = 50
        pie_chart2_hover_radius = 60
        pie_chart2_normal_title_style = ft.TextStyle(
            size=16, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
        )
        pie_chart2_hover_title_style = ft.TextStyle(
            size=22,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.BOLD,
            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK54),
        )

        def on_chart_event2(e: ft.PieChartEvent):
            for idx, section in enumerate(self.pie_chart2.sections):
                if idx == e.section_index:
                    section.radius = pie_chart2_hover_radius
                    section.title_style = pie_chart2_hover_title_style
                else:
                    section.radius = pie_chart2_normal_radius
                    section.title_style = pie_chart2_normal_title_style
            self.pie_chart2.update()

        self.pie_chart2 = ft.PieChart(
            sections=[
                ft.PieChartSection(
                    40,
                    title="40%",
                    title_style=pie_chart2_normal_title_style,
                    color=ft.Colors.BLUE,
                    radius=pie_chart2_normal_radius,
                ),
                ft.PieChartSection(
                    30,
                    title="30%",
                    title_style=pie_chart2_normal_title_style,
                    color=ft.Colors.YELLOW,
                    radius=pie_chart2_normal_radius,
                ),
                ft.PieChartSection(
                    15,
                    title="15%",
                    title_style=pie_chart2_normal_title_style,
                    color=ft.Colors.PURPLE,
                    radius=pie_chart2_normal_radius,
                ),
                ft.PieChartSection(
                    15,
                    title="15%",
                    title_style=pie_chart2_normal_title_style,
                    color=ft.Colors.GREEN,
                    radius=pie_chart2_normal_radius,
                ),
            ],
            sections_space=0,
            center_space_radius=40,
            on_chart_event=on_chart_event2,
            expand=True,
        )
        
        # 饼图 3
        pie_chart3_normal_radius = 100
        pie_chart3_hover_radius = 110
        pie_chart3_normal_title_style = ft.TextStyle(
            size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
        )
        pie_chart3_hover_title_style = ft.TextStyle(
            size=16,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.BOLD,
            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK54),
        )
        pie_chart3_normal_badge_size = 40

        def badge(icon, size):
            return ft.Container(
                ft.Icon(icon),
                width=size,
                height=size,
                border=ft.border.all(1, ft.Colors.BROWN),
                border_radius=size / 2,
                bgcolor=ft.Colors.WHITE,
            )

        def on_chart_event(e: ft.PieChartEvent):
            for idx, section in enumerate(self.pie_chart3.sections):
                if idx == e.section_index:
                    section.radius = pie_chart3_hover_radius
                    section.title_style = pie_chart3_hover_title_style
                else:
                    section.radius = pie_chart3_normal_radius
                    section.title_style = pie_chart3_normal_title_style
            self.pie_chart3.update()

        self.pie_chart3 = ft.PieChart(
            sections=[
                ft.PieChartSection(
                    40,
                    title="40%",
                    title_style=pie_chart3_normal_title_style,
                    color=ft.Colors.BLUE,
                    radius=pie_chart3_normal_radius,
                    badge=badge(ft.Icons.AC_UNIT, pie_chart3_normal_badge_size),
                    badge_position=0.98,
                ),
                ft.PieChartSection(
                    30,
                    title="30%",
                    title_style=pie_chart3_normal_title_style,
                    color=ft.Colors.YELLOW,
                    radius=pie_chart3_normal_radius,
                    badge=badge(ft.Icons.ACCESS_ALARM, pie_chart3_normal_badge_size),
                    badge_position=0.98,
                ),
                ft.PieChartSection(
                    15,
                    title="15%",
                    title_style=pie_chart3_normal_title_style,
                    color=ft.Colors.PURPLE,
                    radius=pie_chart3_normal_radius,
                    badge=badge(ft.Icons.APPLE, pie_chart3_normal_badge_size),
                    badge_position=0.98,
                ),
                ft.PieChartSection(
                    15,
                    title="15%",
                    title_style=pie_chart3_normal_title_style,
                    color=ft.Colors.GREEN,
                    radius=pie_chart3_normal_radius,
                    badge=badge(ft.Icons.PEDAL_BIKE, pie_chart3_normal_badge_size),
                    badge_position=0.98,
                ),
            ],
            sections_space=0,
            center_space_radius=0,
            on_chart_event=on_chart_event,
            expand=True,
        )
        
        return self.build_section(
            "饼图", 
            ft.Row([self.pie_chart1, self.pie_chart2, self.pie_chart3], spacing=10)
        )
    
    def toggle_data(self,e):
        if self.toggle:
            self.line_chart.data_series = self.data_1
            self.line_chart.max_y = 4
            self.line_chart.interactive = True
        else:
            self.line_chart.data_series = self.data_2
            self.line_chart.data_series[2].point = True
            self.line_chart.max_y = 6
            self.line_chart.interactive = False
        self.toggle = not self.toggle
        self.line_chart.update()
        
    def build_content(self) -> ft.Control:
        # 折线图数据1
        self.data_1 = [
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 1),
                    ft.LineChartDataPoint(3, 1.5),
                    ft.LineChartDataPoint(5, 1.4),
                    ft.LineChartDataPoint(7, 3.4),
                    ft.LineChartDataPoint(10, 2),
                    ft.LineChartDataPoint(12, 2.2),
                    ft.LineChartDataPoint(13, 1.8),
                ],
                stroke_width=8,
                color=ft.Colors.LIGHT_GREEN,
                curved=True,
                stroke_cap_round=True,
            ),
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 1),
                    ft.LineChartDataPoint(3, 2.8),
                    ft.LineChartDataPoint(7, 1.2),
                    ft.LineChartDataPoint(10, 2.8),
                    ft.LineChartDataPoint(12, 2.6),
                    ft.LineChartDataPoint(13, 3.9),
                ],
                color=ft.Colors.PINK,
                below_line_bgcolor=ft.Colors.with_opacity(0, ft.Colors.PINK),
                stroke_width=8,
                curved=True,
                stroke_cap_round=True,
            ),
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 2.8),
                    ft.LineChartDataPoint(3, 1.9),
                    ft.LineChartDataPoint(6, 3),
                    ft.LineChartDataPoint(10, 1.3),
                    ft.LineChartDataPoint(13, 2.5),
                ],
                color=ft.Colors.CYAN,
                stroke_width=8,
                curved=True,
                stroke_cap_round=True,
            ),
        ]

        # 折线图数据2
        self.data_2 = [
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 1),
                    ft.LineChartDataPoint(3, 4),
                    ft.LineChartDataPoint(5, 1.8),
                    ft.LineChartDataPoint(7, 5),
                    ft.LineChartDataPoint(10, 2),
                    ft.LineChartDataPoint(12, 2.2),
                    ft.LineChartDataPoint(13, 1.8),
                ],
                stroke_width=4,
                color=ft.Colors.with_opacity(0.5, ft.Colors.LIGHT_GREEN),
                stroke_cap_round=True,
            ),
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 1),
                    ft.LineChartDataPoint(3, 2.8),
                    ft.LineChartDataPoint(7, 1.2),
                    ft.LineChartDataPoint(10, 2.8),
                    ft.LineChartDataPoint(12, 2.6),
                    ft.LineChartDataPoint(13, 3.9),
                ],
                color=ft.Colors.with_opacity(0.5, ft.Colors.PINK),
                below_line_bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PINK),
                stroke_width=4,
                curved=True,
                stroke_cap_round=True,
            ),
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(1, 3.8),
                    ft.LineChartDataPoint(3, 1.9),
                    ft.LineChartDataPoint(6, 5),
                    ft.LineChartDataPoint(10, 3.3),
                    ft.LineChartDataPoint(13, 4.5),
                ],
                color=ft.Colors.with_opacity(0.5, ft.Colors.CYAN),
                stroke_width=4,
                stroke_cap_round=True,
            ),
        ]

        # 创建折线图
        self.line_chart = ft.LineChart(
            data_series=self.data_1,
            border=ft.Border(
                bottom=ft.BorderSide(4, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))
            ),
            left_axis=ft.ChartAxis(
                labels=[
                    ft.ChartAxisLabel(
                        value=1,
                        label=ft.Text("1m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                    ft.ChartAxisLabel(
                        value=2,
                        label=ft.Text("2m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                    ft.ChartAxisLabel(
                        value=3,
                        label=ft.Text("3m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                    ft.ChartAxisLabel(
                        value=4,
                        label=ft.Text("4m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                    ft.ChartAxisLabel(
                        value=5,
                        label=ft.Text("5m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                    ft.ChartAxisLabel(
                        value=6,
                        label=ft.Text("6m", size=14, weight=ft.FontWeight.BOLD),
                    ),
                ],
                labels_size=40,
            ),
            bottom_axis=ft.ChartAxis(
                labels=[
                    ft.ChartAxisLabel(
                        value=2,
                        label=ft.Container(
                            ft.Text(
                                "SEP",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                            margin=ft.margin.only(top=10),
                        ),
                    ),
                    ft.ChartAxisLabel(
                        value=7,
                        label=ft.Container(
                            ft.Text(
                                "OCT",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                            margin=ft.margin.only(top=10),
                        ),
                    ),
                    ft.ChartAxisLabel(
                        value=12,
                        label=ft.Container(
                            ft.Text(
                                "DEC",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                            ),
                            margin=ft.margin.only(top=10),
                        ),
                    ),
                ],
                labels_size=32,
            ),
            tooltip_bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY),
            min_y=0,
            max_y=4,
            min_x=0,
            max_x=14,
            expand=True,
        )
        
        # 创建切换数据按钮
        self.toggle_button = ft.FilledButton(
            "切换数据",
            on_click=self.toggle_data,
        )
        
        # 折线图
        self.bar_chart = ft.BarChart(
            bar_groups=[
                ft.BarChartGroup(
                    x=0,
                    bar_rods=[
                        ft.BarChartRod(
                            from_y=0,
                            to_y=40,
                            width=40,
                            color=ft.Colors.AMBER,
                            tooltip="苹果",
                            border_radius=0,
                        ),
                    ],
                ),
                ft.BarChartGroup(
                    x=1,
                    bar_rods=[
                        ft.BarChartRod(
                            from_y=0,
                            to_y=100,
                            width=40,
                            color=ft.Colors.BLUE,
                            tooltip="蓝莓",
                            border_radius=0,
                        ),
                    ],
                ),
                ft.BarChartGroup(
                    x=2,
                    bar_rods=[
                        ft.BarChartRod(
                            from_y=0,
                            to_y=30,
                            width=40,
                            color=ft.Colors.RED,
                            tooltip="樱桃",
                            border_radius=0,
                        ),
                    ],
                ),
                ft.BarChartGroup(
                    x=3,
                    bar_rods=[
                        ft.BarChartRod(
                            from_y=0,
                            to_y=60,
                            width=40,
                            color=ft.Colors.ORANGE,
                            tooltip="橙子",
                            border_radius=0,
                        ),
                    ],
                ),
            ],
            border=ft.border.all(1, ft.Colors.GREY_400),
            left_axis=ft.ChartAxis(
                labels_size=40, title=ft.Text("水果供应量"), title_size=40
            ),
            bottom_axis=ft.ChartAxis(
                labels=[
                    ft.ChartAxisLabel(
                        value=0, label=ft.Container(ft.Text("苹果"), padding=10)
                    ),
                    ft.ChartAxisLabel(
                        value=1, label=ft.Container(ft.Text("蓝莓"), padding=10)
                    ),
                    ft.ChartAxisLabel(
                        value=2, label=ft.Container(ft.Text("樱桃"), padding=10)
                    ),
                    ft.ChartAxisLabel(
                        value=3, label=ft.Container(ft.Text("橙子"), padding=10)
                    ),
                ],
                labels_size=40,
            ),
            horizontal_grid_lines=ft.ChartGridLines(
                color=ft.Colors.GREY_300, width=1, dash_pattern=[3, 3]
            ),
            tooltip_bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.GREY_300),
            max_y=110,
            interactive=True,
            expand=True,
        )
        
        self.content = ft.Column([
            self.build_section("条形图", self.bar_chart),
            self.build_section("折线图", ft.Column([self.toggle_button, self.line_chart], spacing=10)),
            self.build_pie_chart(),
        ], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
        
        return self.content