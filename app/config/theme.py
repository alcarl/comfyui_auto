from dataclasses import dataclass

@dataclass
class ThemeColors:
    current_color: str = ""
    def __init__(self, is_dark: bool = True):
        if is_dark:
            # 深色主题 - 参考微信深色风格
            self.title_bar_color = "#191919"  # 更柔和的标题栏颜色
            self.bg_color = "#111111"         # 更深的背景色
            self.nav_color = "#191919"        # 导航栏颜色
            self.sub_nav_color = "#232323"    # 次级导航颜色
            self.card_color = "#232323"       # 卡片颜色
            self.divider_color = "#2F2F2F"    # 分割线颜色
            self.text_color = "#CCCCCC"       # 文字颜色
            self.accent_color = "#07C160"     # 微信特色绿色
            self.secondary_accent = "#576B95"  # 次要强调色(链接蓝)
        else:
            # 浅色主题 - 参考微信浅色风格
            self.title_bar_color = "#EDEDED"  # 微信特有的浅灰色
            self.bg_color = "#F7F7F7"        # 背景色
            self.nav_color = "#EDEDED"       # 导航栏颜色
            self.sub_nav_color = "#F7F7F7"   # 次级导航颜色
            self.card_color = "#FFFFFF"      # 纯白卡片
            self.divider_color = "#D9D9D9"   # 分割线颜色
            self.text_color = "#191919"      # 主文本颜色
            self.accent_color = "#07C160"    # 微信绿
            self.secondary_accent = "#576B95" # 链接蓝色