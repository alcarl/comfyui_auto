import flet as ft
from app.base import BasePage

class InputsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="输入控件", **kwargs)

    def build_content(self) -> ft.Column:
        """构建输入控件页面内容"""
        container = ft.Column([
            self._build_text_inputs(),
            self._build_dropdowns(),
            self._build_checkboxes(),
            self._build_radios(),
            self._build_switches(),
            self._build_sliders(),
        ], scroll="auto", spacing=20)
        return container
        
    def _build_text_inputs(self) -> ft.Container:
        self.text_field = ft.TextField()
        self.content = ft.Column([
            self.text_field,
            ft.TextField(
                label="带图标的输入框",
                hint_text="搜索...",
                prefix_icon=ft.Icons.SEARCH,
                suffix_icon=ft.Icons.CLEAR,
            ),
            ft.TextField(
                label="密码输入框",
                password=True,
                can_reveal_password=True,
            ),
            ft.TextField(
                label="多行输入框",
                multiline=True,
                min_lines=3,
                max_lines=5,
            ),
        ], spacing=20)
        
        return self.build_section("文本输入", self.content)

    def _build_dropdowns(self) -> ft.Container:
        """下拉选择示例"""
        self.content = ft.Row([
            # 基本下拉框
            ft.Dropdown(
                label="基本下拉框",
                options=[
                    ft.dropdown.Option("选项1"),
                    ft.dropdown.Option("选项2"),
                    ft.dropdown.Option("选项3"),
                ],
                width=200,
            ),
            # 使用前缀图标的下拉框
            ft.Dropdown(
                label="带图标的下拉框",
                prefix_icon=ft.Icons.SETTINGS,
                options=[
                    ft.dropdown.Option("编辑"),
                    ft.dropdown.Option("删除"),
                    ft.dropdown.Option("保存"),
                ],
                width=200,
            ),
            # 禁用状态的下拉框
            ft.Dropdown(
                label="禁用状态",
                options=[
                    ft.dropdown.Option("选项1"),
                    ft.dropdown.Option("选项2"),
                ],
                width=200,
                disabled=True,
            ),
        ], spacing=20)
        
        return self.build_section("下拉选择", self.content)

    def _build_checkboxes(self) -> ft.Container:
        self.content = ft.Column([
            ft.Checkbox(label="基本复选框"),
            ft.Checkbox(label="默认选中", value=True),
            ft.Checkbox(label="三态复选框", tristate=True),
            ft.Checkbox(label="禁用状态", disabled=True),
        ], spacing=10)
        
        return self.build_section("复选框", self.content)

    def _build_radios(self) -> ft.Container:
        self.content = ft.Row([
            ft.Radio(value="option1", label="选项1"),
            ft.Radio(value="option2", label="选项2"),
            ft.Radio(value="option3", label="选项3", disabled=True),
        ], spacing=10)
        
        return self.build_section("单选框", self.content)

    def _build_switches(self) -> ft.Container:
        self.content = ft.Row([
            ft.Switch(label="基本开关"),
            ft.Switch(label="默认开启", value=True),
            ft.Switch(label="禁用状态", disabled=True),
        ], spacing=20)
        
        return self.build_section("开关", self.content)

    def _build_sliders(self) -> ft.Container:
        self.content = ft.Column([
            ft.Slider(
                min=0,
                max=100,
                value=40,
                label="{value}%",
            ),
            ft.Slider(
                min=0,
                max=100,
                value=60,
                divisions=10,
                label="{value}",
            ),
        ], spacing=20)
        
        return self.build_section("滑块", self.content)