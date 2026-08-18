import json
import os
import threading
from typing import List, Any, Optional
from pydantic import BaseModel, Field

class ThemeConfig(BaseModel):
    mode: str = "dark"
    color: str = "ft.Colors.BLUE"
    background_image: str = "images/backgrounds/background1.jpg"

class FontConfig(BaseModel):
    windows: List[str] = ["Segoe UI", "Microsoft YaHei UI", "Arial"]
    macos: List[str] = ["SF Pro", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB"]
    linux: List[str] = ["Ubuntu", "Noto Sans CJK SC", "DejaVu Sans"]

class WindowConfig(BaseModel):
    width: int = 1300
    height: int = 800
    min_width: int = 500
    min_height: int = 400
    font: FontConfig = Field(default_factory=FontConfig)

class MusicConfig(BaseModel):
    # 基础配置
    music_dir: str = "assets/musics"
    default_cover: str = "images/default_cover.jpg"
    
    # 播放状态
    current_playlist: str = "所有歌曲"  # 当前播放列表名称
    current_song_path: str = ""        # 当前播放歌曲的完整路径
    last_position: int = 0             # 上次播放位置（毫秒）
    
    # 播放模式
    shuffle_mode: bool = True         # 随机播放
    repeat_mode: bool = False          # 列表循环
    single_repeat_mode: bool = False   # 单曲循环
    
    # 播放器设置
    volume: float = 0.75              # 音量
    
    # 每个播放列表的最后播放歌曲路径
    playlist_states: dict = Field(default_factory=lambda: {
        "所有歌曲": {
            "last_song_path": "",
            "last_position": 0
        }
    })

class AppSettings(BaseModel):
    Theme: ThemeConfig = Field(default_factory=ThemeConfig)
    Window: WindowConfig = Field(default_factory=WindowConfig)
    Music: MusicConfig = Field(default_factory=MusicConfig)
    
class AppConfig:
    # 类属性
    _instance: Optional['AppConfig'] = None
    _lock = threading.Lock()

    # 实例属性类型注解
    Theme: ThemeConfig
    Window: WindowConfig
    Music: MusicConfig
    main_path: str
    config_file: str
    _initialized: bool
    _settings: AppSettings

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # 在这里初始化基本属性
                cls._instance._initialized = False
                cls._instance._settings = None
        return cls._instance
    
    def __init__(self, main_path: str = ""):
        if not self._initialized:
            self._initialized = True
            self.main_path = main_path
            self.config_file = os.path.join(main_path, "app/config/config.json")
            self._ensure_config_file()
            self._settings = self.load_config()
            # 设置属性以获得IDE提示
            self.Theme = self._settings.Theme
            self.Window = self._settings.Window
            self.Music = self._settings.Music
            print("加载配置管理器成功")
        
    def _ensure_config_file(self) -> None:
        """确保配置文件和目录存在"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        if not os.path.exists(self.config_file):
            self._create_default_config()

    def _create_default_config(self) -> None:
        """创建默认配置"""
        settings = AppSettings()
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(settings.model_dump(), f, indent=4, ensure_ascii=False)

    def load_config(self) -> AppSettings:
        """加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return AppSettings.model_validate(data)
        except (FileNotFoundError, json.JSONDecodeError):
            return AppSettings()

    def save_config(self) -> None:
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._settings.model_dump(), f, indent=4, ensure_ascii=False)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置值"""
        section_data = getattr(self._settings, section, {})
        if isinstance(section_data, BaseModel):
            return getattr(section_data, key, default)
        return default

    def set(self, section: str, key: str, value: Any) -> None:
        """设置配置值并保存"""
        if hasattr(self._settings, section):
            section_model = getattr(self._settings, section)
            if hasattr(section_model, key):
                setattr(section_model, key, value)
                # 同步更新实例属性
                setattr(self, section, section_model)
                self.save_config()
            else:
                raise AttributeError(f"'{section}' has no attribute '{key}'")
        else:
            raise AttributeError(f"Settings has no section '{section}'")

    def config_sections(self) -> List[str]:
        """获取所有配置节名称"""
        return list(self._settings.model_dump().keys())

    def get_font_family(self, platform: str, index: int = 0) -> str:
        """获取指定平台的字体"""
        return self.Window.font.__getattribute__(platform.lower())[index]