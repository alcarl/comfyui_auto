from datetime import datetime, timedelta
import flet as ft
from app.base import BasePage

class TimePickerPage(BasePage):
    """时间选择器示例页面"""
    
    def __init__(self, **kwargs):
        super().__init__(title="时间选择", **kwargs)
    
    
    def handle_change(self, e):
        self.content.controls.append(ft.Text(f"TimePicker change: {self.time_picker.value}"))
        self.content.update()
        
    def handle_dismissal(self, e):
        self.content.controls.append(ft.Text(f"TimePicker dismissed: {self.time_picker.value}"))
        self.content.update()
        
    def handle_entry_mode_change(self, e):
        self.content.controls.append(ft.Text(f"TimePicker Entry mode changed to {e.entry_mode}"))
        self.content.update()
        
    
    def handle_change_date(self, e):
        self.content.controls.append(ft.Text(f"Date changed: {e.control.value.strftime('%Y-%m-%d')}"))
        self.content.update()

    def handle_dismissal_date(self, e):
        self.content.controls.append(ft.Text("DatePicker dismissed"))
        self.content.update()
        
    def build_content(self) -> ft.Control:
        self.time_picker = ft.TimePicker(
            on_change=self.handle_change,
            on_dismiss=self.handle_dismissal,
            on_entry_mode_change=self.handle_entry_mode_change,
        )
        
        self.time_picker_button = ft.FloatingActionButton(
            "选择时间", 
            width=120,
            on_click=lambda e: self.page.open(self.time_picker))
        
        self.date_picker = ft.DatePicker(
                    first_date=datetime.now().date(),
                    last_date=datetime.now().date() + timedelta(days=30),
                    on_change=self.handle_change_date,
                    on_dismiss=self.handle_dismissal_date,
                )
        
        self.date_picker_button = ft.FloatingActionButton(
            "选择日期", 
            width=120,
            on_click=lambda e: self.page.open(self.date_picker))
        
        self.date_picker_range = ft.DatePicker(
                    first_date=datetime.now().date(),
                    last_date=datetime.now().date() + timedelta(days=30),
                    on_change=self.handle_change_date,
                    on_dismiss=self.handle_dismissal_date,
                    visible=True
                )
        
        self.content = ft.Column([
            ft.Row([ self.date_picker_button, ft.Container(width=300), self.time_picker_button], alignment=ft.MainAxisAlignment.CENTER),
            self.date_picker_range
            ], spacing=10)
        
        return self.build_section("时间选择器", self.content)
