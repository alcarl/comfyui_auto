<h1 align="center">PyDracula-flet</h1>

[English](README_EN.md) | 简体中文

PyDracula-flet 是一个基于 Flet 参考 PyDracula 构建的现代化桌面应用程序模版。它提供了一套完整的主题系统、导航系统和配置管理, flet template。

## 注意事项
1. 项目主要在macos开发，windows可能存在一些问题，我会在windows上测试，如果存在问题，我会及时修复。

2. 主题配色，我在macos上测试，windows 的颜色和对比度差异可能比较大，您可以在 `app/config/theme.py` 中修改颜色，以适应您的windows系统。

## 特性

- 🌓 深色/浅色主题支持，可自定义主题色
- 📱 响应式布局，支持窗口大小调整
- 🎯 可配置的导航栏，支持主导航和子导航
- ⚙️ 配置持久化，自动保存用户偏好
- 🎨 现代化 UI 设计
- 🎢 内置轮播图组件
- 💾 本地存储支持
- 🖥️ 跨平台支持 (macOS, Windows)
- 📢 内置多种通知系统
- 🎵 音乐播放器示例
- ✅ Todo 应用示例
- 🧮 计算器示例

# 项目预览

## 图片预览
## 图片预览
| ![Image 1](docs/images/screenshot1.png) | ![Image 2](docs/images/screenshot3.png) |
|-----------------------------------------|-----------------------------------------|
| ![Image 3](docs/images/screenshot2.png) | ![Image 4](docs/images/screenshot4.png) |


## 安装

1. 克隆仓库：

```bash
git clone https://github.com/clarencejh/PyDracula-flet.git
cd PyDracula-flet
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行应用：

```bash
flet run main.py
```

## 项目结构

```
PyDracula-flet/
├── assets/            # 静态资源文件
│   └── images/       # 图片资源
├── components/        # 可重用组件
│   └── fletcarousel/ # 轮播图组件
├── app/              # 核心功能
│   ├── app.py       # 主应用类
│   ├── base_page.py # 基础页面类
│   ├── theme.py     # 主题管理
│   ├── utils/       # 工具函数
│   ├── pages/       # 页面
│   │   ├── home.py      # 主页
│   │   ├── calc.py      # 计算器
│   │   ├── player.py    # 音乐播放器
│   │   ├── todo.py      # Todo应用
│   │   ├── inputs.py    # 输入控件
│   │   ├── carousel.py  # 轮播图示例
│   │   ├── settings.py  # 设置页面
│   │   └── stack_page.py # Stack布局示例
│   ├── sub_navigation_bar/ # 子导航示例
│   └── config_manager.py  # 配置管理
├── storage/          # 本地存储
├── main.py          # 应用入口
└── requirements.txt  # 项目依赖
```

## 内置页面说明

1. 主页 (HomePage)
   - 展示应用概览和基本信息

2. 子导航示例 (SubNavigationBar)
   - 演示如何实现多级导航结构

3. 音乐播放器 (MusicPlayer)
   - 基础的音乐播放功能示例

4. 输入控件展示 (InputsPage)
   - 各类输入控件的使用示例

5. 轮播图 (CarouselPage)
   - 图片轮播组件示例

6. Stack布局 (StackPage)
   - Stack布局使用示例

7. Todo应用 (TodoPage)
   - 完整的待办事项管理功能

8. 计算器 (CalcPage)
   - 基础计算器功能实现

## 如何添加新页面

1. 在 `app/pages` 目录下创建新的页面文件，例如 `my_page.py`：

```python
from flet import Column, Container, Text, padding, border_radius
from core.base import BasePage

class MyPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="我的页面", **kwargs)

    def build_content(self) -> Column:
        container = Column(
            controls=[
                self.build_section(
                    "标题",
                    Container(
                        content=Text("Hello, World!")
                    )
                )
            ],
            scroll="auto",
            spacing=20,
        )
        return container
```

2. 在 `main.py` 中注册新页面：

```python
from app.pages.my_page import MyPage

def main(page: ft.Page):
    # ... 其他代码保持不变 ...
    
    pages = [
        # ... 现有页面 ...
        {"icon": ft.Icons.STAR, "name": "我的页面", "page_class": MyPage},
    ]
    
    app.register_pages(pages)
```

## 主题系统

### 主题配置

在 `app/config_manager.py` 中可以配置：

- 主题模式（深色/浅色）
- 主题颜色
- 字体设置
- 语言设置

### 颜色系统

主题系统提供以下颜色变量：

- `bg_color`: 背景色
- `nav_color`: 导航栏颜色
- `card_color`: 卡片颜色
- `text_color`: 文本颜色
- `divider_color`: 分隔线颜色
- `accent_color`: 强调色

## 开发建议

1. 状态管理
   - 将需要在主题切换时保持的控件定义为类属性
   - 使用配置管理器保存用户设置

2. 页面开发
   - 继承 BasePage 类
   - 使用 build_section 方法组织内容
   - 保持合适的间距和布局结构

3. 性能优化
   - 合理使用异步操作
   - 避免频繁重建控件
   - 适当使用缓存机制

## 贡献指南

1. 轮播图组件使用的是 [fletcarousel](https://github.com/clarencejh/fletcarousel)
2. flet 中文文档: [https://flet.qiannianlu.com/docs/getting-started/](https://flet.qiannianlu.com/docs/getting-started/)
3. flet 官方文档: [https://flet.dev/docs/](https://flet.dev/docs/)

## 单独的运行文件

在 `single_main.py` 中，可以单独运行，不需要使用其他文件。但不再更新内容。

## 许可证

此项目采用 MIT 许可证。有关详细信息，请参阅 [LICENSE](LICENSE) 文件。

## 联系

如需更多信息，请访问我们的 GitHub 页面：[PyDracula-flet](https://github.com/clarencejh/PyDracula-flet)
