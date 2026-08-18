# Flet 堆叠通知管理器

这个 NotificationManager 类是一个用于 Flet 应用程序的堆叠通知管理器。它允许你在应用程序中显示多个可自定义的通知，支持不同的通知类型和样式。

## 特性

- 支持多种预定义通知类型（信息、成功、警告、错误）
- 可自定义通知样式和类型
- 通知自动堆叠显示
- 可设置最大同时显示的通知数量
- 支持自定义通知显示时间
- 可为通知添加自定义操作按钮
- 单例模式，确保全局只有一个通知管理器实例

## 安装

确保你已经安装了 Flet：

```
pip install flet
```

将 `notification_manager.py` 文件复制到你的项目中。

## 基本使用

1. 在你的 Flet 应用中导入并初始化 NotificationManager：

```python
from notification_manager import NotificationManager, NotificationType

def main(page: ft.Page):
    notifications = NotificationManager(page)
    
    # 你的应用代码...

ft.app(target=main)
```

2. 显示通知：

```python
notifications.show("这是一条信息通知", type=NotificationType.INFO)
notifications.show("操作成功", type=NotificationType.SUCCESS)
notifications.show("请注意", type=NotificationType.WARNING)
notifications.show("发生错误", type=NotificationType.ERROR)
```

## 高级用法

### 自定义通知显示时间

```python
notifications.show("这条通知会显示5秒", duration=5)
```

### 添加自定义操作按钮

```python
action = ft.TextButton("确定", on_click=lambda _: print("按钮被点击"))
notifications.show("带按钮的通知", action=action)
```

### 添加自定义通知类型

```python
from notification_manager import NotificationStyle

custom_type = notifications.add_custom_style(
    "CUSTOM",
    NotificationStyle(
        bgcolor=ft.Colors.PURPLE,
        icon=ft.icons.STAR,
    )
)

notifications.show("这是自定义类型的通知", type=custom_type)
```

### 设置最大显示数量

```python
notifications.set_max_notifications(3)
```

### 设置默认显示时间

```python
notifications.set_default_duration(5)
```

### 清除所有通知

```python
notifications.clear()
```

## 许可

MIT License