import os
import random
import math
import asyncio
import flet as ft
from app.base import BasePage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.app import App


class MusicPlayer(BasePage):
    def __init__(self, app, **kwargs):
        self.app: "App" = app
        self.title = "音乐播放器"

        # 从配置加载设置
        self.is_playing = False
        self.shuffle_mode = self.app.config.Music.shuffle_mode
        self.repeat_mode = self.app.config.Music.repeat_mode
        self.single_repeat_mode = self.app.config.Music.single_repeat_mode

        self.current_lyrics = "歌词未找到"
        self.current_cover = self.app.config.Music.default_cover

        self.is_animating = False
        self.rotation_animation_task = None
        self.current_index = 0
        self.mute = False
        # 初始化音乐目录和播放列表
        self.music_dir = os.path.join(self.app.config.main_path, self.app.config.Music.music_dir)

        # 初始化播放列表, 提供一些基础信息
        self.playlists = {
            "所有歌曲": ["稻香", "晴天", "七里香", "简单爱", "青花瓷"],
            "华语经典": ["稻香", "晴天", "七里香"],
            "轻音乐": ["River Flows in You", "Kiss the Rain"],
            "收藏夹": ["简单爱", "青花瓷"],
        }
        self.current_playlist = "所有歌曲"

        # 确保音乐目录存在
        if not os.path.exists(self.music_dir):
            try:
                os.makedirs(self.music_dir)
                print(f"创建音乐目录: {self.music_dir}")
            except Exception as e:
                print(f"创建音乐目录失败: {str(e)}")

        # 初始化音频控件
        self.audio = ft.Audio(src="default_music.mp3", volume=self.app.config.Music.volume)

        # 调用父类初始化
        super().__init__(title=self.title, app=app, **kwargs)

        # 添加音频控件到页面
        self.page.overlay.append(self.audio)
        self.page.update()


    def rotate_album_cover(self):
        if not self.is_animating and self.is_playing:
            self.is_animating = True
            self.page.run_task(self.rotation_animation)
        elif not self.is_playing:
            self.stop_rotation()

    async def rotation_animation(self):
        while self.is_animating:
            self.album_cover_rotation_angle += math.radians(1)  # Increment by 1 degree in radians
            self.album_cover.rotate = ft.transform.Rotate(self.album_cover_rotation_angle)
            self.page.update()
            await asyncio.sleep(0.016)  # Approximately 60 FPS

    def stop_rotation(self):
        if self.is_animating:
            self.is_animating = False
            self.page.update()  # Update to stop animation

    def toggle_play_pause(self, e):
        if self.is_playing:
            self.audio.pause()
            self.stop_rotation()  # Stop the rotation when pausing
        else:
            self.audio.play()
        self.is_playing = not self.is_playing
        self.update_play_button()
        self.rotate_album_cover()  # Start the rotation when playing

    def update_play_button(self):
        self.play_button.icon = ft.Icons.PAUSE if self.is_playing else ft.Icons.PLAY_ARROW
        self.page.update()

    def next_song(self, e):
        """播放下一首歌曲"""
        return

    def previous_song(self, e):
        """播放上一首歌曲"""
        return

    def show_playlist(self, playlist_name):
        """切换播放列表视图，不影响当前播放"""
        # 如果是同一个播放列表，只更新显示
        if self.current_playlist == playlist_name:
            return

        # 更新当前播放列表
        self.current_playlist = playlist_name

        # 获取新播放列表的歌曲
        songs = self.playlists.get(playlist_name, [])

        # 如果新播放列表为空，不进行切换
        if not songs:
            print(f"播放列表 {playlist_name} 为空")
            return

        # 更新播放列表视图
        self.current_playlist_view.controls = [
            ft.ListTile(
                title=ft.Text(
                    f"{i + 1}. {song}",
                ),
            )
            for i, song in enumerate(songs)
        ]

        # 更新UI
        self.current_playlist_view.update()

        # 保存当前播放列表设置（但不影响播放状态）
        self.app.config.set("Music", "current_playlist", self.current_playlist)


    def build_content(self):
        """构建播放器界面"""
        try:

            # 正常构建播放器界面
            self.album_cover_rotation_angle = 0
            self.album_cover = ft.CircleAvatar(
                foreground_image_src="images/default_cover.jpg",  # Default cover
                width=60,
                height=60,
                content=ft.Icon(ft.Icons.MUSIC_NOTE, size=40),
                rotate=ft.transform.Rotate(0),  # Initial rotation is 0
                animate_rotation=ft.animation.Animation(16, "linear"),  # Smooth linear animation over 1 second for each 360 degrees，
            )

            self.current_song_text = ft.Text(
                "歌曲名称",
                size=14,
                weight=ft.FontWeight.BOLD,
                width=200,
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=1,
                color=self.theme_colors.accent_color,
                selectable=True,
            )

            # 歌手
            self.current_song_singer = ft.Text("歌手", size=12, weight=ft.FontWeight.NORMAL, width=200, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, color=self.theme_colors.secondary_accent, selectable=True, tooltip="歌手")
            # 专辑
            self.current_song_album = ft.Text("专辑", size=12, weight=ft.FontWeight.NORMAL, width=200, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, color=self.theme_colors.secondary_accent, selectable=True, tooltip="专辑")
            # 刷新按钮
            self.refresh_button = ft.TextButton("刷新歌曲信息", height=20, tooltip="刷新歌曲信息")

            # Scrollable lyrics
            self.lyrics_text = ft.Column(
                controls=[ft.Text("歌词", size=20, weight=ft.FontWeight.BOLD)],
                width=400,
                expand=True,
                scroll=ft.ScrollMode.ALWAYS,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

            self.progress = ft.Slider(
                min=0,
                max=1,
                value=0,
                width=400,
            )

            self.time_display = ft.Text("00:00 / 00:00", size=12)

            self.play_button = ft.IconButton(icon=ft.Icons.PLAY_ARROW, on_click=self.toggle_play_pause, icon_size=32, icon_color=self.theme_colors.accent_color)

            self.mute_button = ft.IconButton(icon=ft.Icons.VOLUME_OFF if self.mute else ft.Icons.VOLUME_UP, icon_size=24, tooltip="静音 快捷键:M", selected=self.mute)

            self.volume_slider = ft.Slider(
                min=0,
                max=1,
                value=self.app.config.Music.volume,  # 使用保存的音量值
                width=150,
                tooltip="音量 快捷键:上下",
            )

            # 保存按钮为类属性
            self.shuffle_button = ft.IconButton(icon=ft.Icons.SHUFFLE_ON if self.shuffle_mode else ft.Icons.SHUFFLE, icon_size=24, tooltip="随机播放", selected=self.shuffle_mode)

            self.repeat_button = ft.IconButton(icon=ft.Icons.REPEAT_ON if self.repeat_mode else ft.Icons.REPEAT,  icon_size=24, tooltip="重复列表", selected=self.repeat_mode)

            self.single_repeat_button = ft.IconButton(
                icon=ft.Icons.REPEAT_ONE_ON if self.single_repeat_mode else ft.Icons.REPEAT_ONE, icon_size=24, tooltip="单曲循环", selected=self.single_repeat_mode
            )

            control_buttons = ft.Row(
                controls=[
                    ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, on_click=self.previous_song, icon_size=24, icon_color=self.theme_colors.accent_color, tooltip="上一首 快捷键:左"),
                    self.play_button,
                    ft.IconButton(icon=ft.Icons.SKIP_NEXT, on_click=self.next_song, icon_size=24, icon_color=self.theme_colors.accent_color, tooltip="下一首 快捷键:右"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            )

            additional_controls = ft.Row(controls=[self.shuffle_button, self.repeat_button, self.single_repeat_button], alignment=ft.MainAxisAlignment.CENTER, spacing=10)

            # Create a ListView for playlists
            self.playlist_list = ft.ListView(
                controls=[
                    ft.ListTile(
                        title=ft.Text(playlist_name, color=self.theme_colors.accent_color if playlist_name == self.current_playlist else None),
                        bgcolor=self.theme_colors.card_color if playlist_name == self.current_playlist else "transparent",
                        on_click=lambda e, playlist_name=playlist_name: self.show_playlist(playlist_name),
                    )
                    for playlist_name in list(self.playlists.keys())
                ],
                expand=True,
                width=150,  # Adjust width as needed
            )

            # Placeholder for the current playlist's songs
            self.current_playlist_view = ft.ListView(
                controls=[],
                expand=True,
                width=250,  # Adjust width as needed
            )

            self.show_playlist(self.current_playlist)

            player_bar = ft.Container(
                content=ft.Row(
                    controls=[
                        self.album_cover,
                        ft.Column(
                            controls=[
                                self.current_song_text,
                                self.current_song_singer,
                                self.current_song_album,
                                self.refresh_button,
                            ],
                            width=150,
                        ),
                        ft.Column(
                            controls=[
                                ft.Row(controls=[ft.Container(), control_buttons, ft.Row([self.mute_button, self.volume_slider])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                                ft.Row(controls=[self.progress, self.time_display, additional_controls], spacing=10, alignment=ft.MainAxisAlignment.CENTER, expand=True),
                            ],
                            spacing=5,
                            expand=True,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                padding=10,
                bgcolor=self.theme_colors.card_color,
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
            )

            playlist_with_lyrics = ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("播放列表", size=20, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=self.playlist_list,
                                        padding=ft.padding.only(right=10),
                                    ),
                                    self.current_playlist_view,
                                ],
                                expand=True,
                            ),
                        ],
                        expand=True,
                    ),
                    # 竖向分割线
                    ft.VerticalDivider(1),
                    ft.Container(
                        content=self.lyrics_text,
                        alignment=ft.alignment.center_left,
                        width=400,
                        padding=ft.padding.only(left=10),
                    ),
                ],
                expand=True,
            )

            return ft.Column(
                controls=[
                    ft.Container(
                        content=playlist_with_lyrics,
                        expand=True,
                        padding=20,
                        border_radius=ft.border_radius.all(10),
                    ),
                    player_bar,
                ],
                spacing=0,
                expand=True,
            )
        except Exception as e:
            print(f"构建播放器界面时出错: {str(e)}")
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("构建播放器界面时出错", size=20, color=self.theme_colors.accent_color),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                alignment=ft.alignment.center,
                expand=True,
            )