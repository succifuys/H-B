from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import flet as ft
import generators
from network import NetworkClient


                                                                   
                                                                        
BG = "#050505"
SURFACE = "#100F0D"
SURFACE_ALT = "#1A1814"
IVORY = "#F4F0E6"
SAND = "#D4C3A5"
CREAM = "#E8DDC9"
TAUPE = "#A69579"
TEXT_MUTED = "#9D978D"


class HitAndBlowApp:
    def __init__(self, page: ft.Page) -> None:
                                                                             
                                                                             
        self.page = page
        self.network = NetworkClient(
            os.getenv("GAME_WS_URL", "ws://127.0.0.1:8000/api/ws")
        )
        self.event_task: asyncio.Task[None] | None = None
        self.timer_task: asyncio.Task[None] | None = None
        self.screen = "lobby"
        self.leaderboard_rows: list[dict[str, Any]] = []
        self.selected_digits = 4
        self.nickname = os.getenv("USERNAME") or os.getenv("USER") or "Player"
        self.current_digits = 4
        self.match_started_monotonic = 0.0
        self.match_finished = False

        self.switcher: ft.AnimatedSwitcher
        self.nickname_field: ft.TextField
        self.room_code_field: ft.TextField
        self.digit_label: ft.Text
        self.connection_text: ft.Text
        self.timer_text: ft.Text | None = None
        self.status_text: ft.Text | None = None
        self.self_log: ft.ListView | None = None
        self.opponent_log: ft.ListView | None = None
        self.guess_field: ft.TextField | None = None
        self.guess_container: ft.Container | None = None
        self.guess_button: ft.Button | None = None
        self.result_switcher: ft.AnimatedSwitcher | None = None

        self.practice_secret: list[int] = []
        self.practice_attempts = 0

    async def start(self) -> None:
                                                                             
                                                                             
        self._configure_page()
        self.switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            expand=True,
            duration=350,
            reverse_duration=180,
            transition=ft.AnimatedSwitcherTransition.FADE,
            switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
            switch_out_curve=ft.AnimationCurve.EASE_IN_CUBIC,
        )
        self.page.add(ft.SafeArea(content=self.switcher, expand=True))
        self._show_lobby()
        self.page.on_disconnect = self._on_disconnect
        self.page.on_close = self._on_disconnect
        await self._connect(show_error=False)

    def _configure_page(self) -> None:
                                                                            
        self.page.title = "DNTSNE | ヒット＆ブロー"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG
        self.page.padding = 0
        self.page.theme = ft.Theme(
            color_scheme_seed=IVORY,
            scaffold_bgcolor=BG,
        )
        try:
            self.page.window.width = 1180
            self.page.window.height = 820
            self.page.window.min_width = 760
            self.page.window.min_height = 620
        except Exception:
            pass

    async def _connect(self, show_error: bool = True) -> bool:
                                                                             
                                                  
        if self.network.connected:
            return True
        if self.connection_text:
            self.connection_text.value = "● 接続中..."
            self.connection_text.color = SAND
            self.connection_text.update()
        try:
            await self.network.connect()
            if self.event_task is None or self.event_task.done():
                self.event_task = asyncio.create_task(self._event_loop())
            if self.connection_text:
                self.connection_text.value = "● オンライン"
                self.connection_text.color = CREAM
                self.connection_text.update()
            return True
        except Exception:
            if self.connection_text:
                self.connection_text.value = "● オフライン"
                self.connection_text.color = TAUPE
                self.connection_text.update()
            if show_error:
                self._snack("サーバーに接続できません。練習モードは利用できます。", error=True)
            return False

    async def _on_disconnect(self, _event: Any) -> None:
        await self.network.close()
        self._cancel_timer()

    def _show_lobby(self) -> None:
                                                                             
                                                    
        self.screen = "lobby"
        self.match_finished = False
        self._cancel_timer()

        self.nickname_field = ft.TextField(
            label="プレイヤー名",
            value=self.nickname,
            max_length=16,
            border_color="#3B3730",
            focused_border_color=IVORY,
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )
        self.room_code_field = ft.TextField(
            label="ルームコード",
            hint_text="ABC123",
            max_length=6,
            capitalization=ft.TextCapitalization.CHARACTERS,
            border_color="#3B3730",
            focused_border_color=SAND,
            prefix_icon=ft.Icons.KEY_OUTLINED,
            on_submit=self._join_room,
        )
        self.digit_label = ft.Text(
            f"{self.selected_digits} 桁", size=18, weight=ft.FontWeight.BOLD, color=IVORY
        )
        digit_slider = ft.Slider(
            min=generators.MIN_DIGITS,
            max=generators.MAX_DIGITS,
            divisions=generators.MAX_DIGITS - generators.MIN_DIGITS,
            value=self.selected_digits,
            active_color=IVORY,
            inactive_color="#3B3730",
            on_change=self._change_digits,
        )
        self.connection_text = ft.Text(
            "● オンライン" if self.network.connected else "● オフライン",
            size=12,
            color=CREAM if self.network.connected else TAUPE,
        )

        online_card = self._card(
            ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("オンライン対戦", size=22, weight=ft.FontWeight.BOLD),
                            self.connection_text,
                        ],
                    ),
                    self.nickname_field,
                    ft.Row(
                        controls=[ft.Text("桁数", color=TEXT_MUTED), self.digit_label],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    digit_slider,
                    ft.Button(
                        "クイックマッチ",
                        icon=ft.Icons.BOLT,
                        on_click=self._quick_match,
                        width=420,
                        height=48,
                        bgcolor=IVORY,
                        color=BG,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                "ルームを作る",
                                icon=ft.Icons.ADD,
                                on_click=self._create_room,
                                expand=True,
                            ),
                            ft.OutlinedButton(
                                "コードで参加",
                                icon=ft.Icons.LOGIN,
                                on_click=self._join_room,
                                expand=True,
                            ),
                        ]
                    ),
                    self.room_code_field,
                    ft.Divider(color="#2E2A24"),
                    ft.Button(
                        "ひとりで練習",
                        icon=ft.Icons.SPORTS_ESPORTS_OUTLINED,
                        on_click=self._start_practice,
                        width=420,
                    ),
                ],
            ),
            accent=IVORY,
        )

        ranking_card = self._card(self._build_leaderboard(), accent=SAND)
        rules_card = self._card(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Text("遊び方", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("・数字は重複なし", color=TEXT_MUTED),
                    ft.Text("・位置も数字も正解 → ヒット", color=TEXT_MUTED),
                    ft.Text("・数字だけ正解 → ブロー", color=TEXT_MUTED),
                    ft.Text("・オンラインは先に当てた人の勝ち", color=TEXT_MUTED),
                ],
            ),
            accent="#5C5447",
        )

        content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=28, vertical=22),
            content=ft.Column(
                spacing=20,
                controls=[
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=340,
                                height=130,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Image(
                                    src="/dntsne_logo.png",
                                    fit=ft.BoxFit.CONTAIN,
                                ),
                            ),
                            ft.Text(
                                "HIT & BLOW ONLINE",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=IVORY,
                            ),
                            ft.Text(
                                "HHT Project by 1 week",
                                size=11,
                                color=TEXT_MUTED,
                            ),
                            ft.Text("ヒット＆ブロー", size=14, color=SAND),
                        ],
                    ),
                    ft.ResponsiveRow(
                        spacing=20,
                        run_spacing=20,
                        controls=[
                            ft.Container(
                                content=online_card,
                                col={
                                    ft.ResponsiveRowBreakpoint.XS: 12,
                                    ft.ResponsiveRowBreakpoint.MD: 7,
                                },
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[ranking_card, rules_card], spacing=20
                                ),
                                col={
                                    ft.ResponsiveRowBreakpoint.XS: 12,
                                    ft.ResponsiveRowBreakpoint.MD: 5,
                                },
                            ),
                        ],
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        self._switch(content)

    def _build_leaderboard(self) -> ft.Column:
                                                                            
                                                                              
        controls: list[ft.Control] = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("ランキング", size=22, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="更新",
                        on_click=self._refresh_leaderboard,
                    ),
                ],
            )
        ]
        if not self.leaderboard_rows:
            controls.append(ft.Text("まだ対戦記録がありません。", color=TEXT_MUTED))
        else:
            for index, row in enumerate(self.leaderboard_rows[:10], start=1):
                best = row.get("best_attempts")
                controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                        border_radius=10,
                        bgcolor="#090908",
                        content=ft.Row(
                            controls=[
                                ft.Text(
                                    str(index),
                                    width=26,
                                    color=SAND if index <= 3 else TEXT_MUTED,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    str(row.get("nickname", "-")),
                                    expand=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"{row.get('wins', 0)}勝",
                                    color=CREAM,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"BEST {best if best is not None else '-'}",
                                    size=11,
                                    color=TEXT_MUTED,
                                ),
                            ]
                        ),
                    )
                )
        return ft.Column(controls=controls, spacing=8)

    def _card(self, content: ft.Control, accent: str) -> ft.Container:
                                                                              
        return ft.Container(
            content=content,
            padding=22,
            bgcolor=SURFACE,
            border=ft.Border.all(1, accent),
            border_radius=18,
            shadow=ft.BoxShadow(
                blur_radius=22,
                spread_radius=-6,
                color="#66000000",
                offset=ft.Offset(0, 8),
            ),
        )

    def _change_digits(self, event: ft.Event[ft.Slider]) -> None:
        self.selected_digits = int(float(event.control.value))
        self.digit_label.value = f"{self.selected_digits} 桁"
        try:
            self.digit_label.update()
        except RuntimeError:
            pass

    def _get_identity(self) -> tuple[str, int] | None:
                                                            
        nickname = (self.nickname_field.value or "").strip()
        if not nickname:
            self._snack("プレイヤー名を入力してください。", error=True)
            return None
        self.nickname = nickname
        return nickname, self.selected_digits

    async def _create_room(self, _event: Any) -> None:
                                                                           
        identity = self._get_identity()
        if identity is None or not await self._connect():
            return
        nickname, digits = identity
        await self.network.send("create_room", nickname=nickname, digits=digits)

    async def _join_room(self, _event: Any) -> None:
                                                                             
        identity = self._get_identity()
        if identity is None or not await self._connect():
            return
        code = (self.room_code_field.value or "").strip().upper()
        if not code:
            self._snack("ルームコードを入力してください。", error=True)
            return
        nickname, _digits = identity
        await self.network.send("join_room", nickname=nickname, room_code=code)

    async def _quick_match(self, _event: Any) -> None:
                                                           
        identity = self._get_identity()
        if identity is None or not await self._connect():
            return
        nickname, digits = identity
        await self.network.send("quick_match", nickname=nickname, digits=digits)

    async def _refresh_leaderboard(self, _event: Any) -> None:
        if await self._connect():
            await self.network.send("leaderboard")

    def _show_waiting(self, title: str, detail: str, room_code: str | None = None) -> None:
                                                                            
                                                 
        self.screen = "waiting"
        controls: list[ft.Control] = [
            ft.ProgressRing(color=IVORY, width=52, height=52, stroke_width=4),
            ft.Text(title, size=28, weight=ft.FontWeight.BOLD),
            ft.Text(detail, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        ]
        if room_code:
            controls.extend(
                [
                    ft.Text("ルームコード", color=TEXT_MUTED),
                    ft.SelectionArea(
                        content=ft.Text(
                            room_code,
                            size=40,
                            weight=ft.FontWeight.BOLD,
                            color=SAND,
                        )
                    ),
                    ft.Text("このコードを相手に送ってください。", color=TEXT_MUTED),
                ]
            )
        controls.append(ft.OutlinedButton("キャンセル", on_click=self._cancel_waiting))
        self._switch(
            ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=self._card(
                    ft.Column(
                        controls=controls,
                        spacing=18,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True,
                    ),
                    accent=SAND,
                ),
            )
        )

    async def _cancel_waiting(self, _event: Any) -> None:
        if self.network.connected:
            await self.network.send("cancel")
        self._show_lobby()

    def _show_online_match(self, message: dict[str, Any]) -> None:
                                                                          
                                                                           
        self.screen = "online_match"
        self.match_finished = False
        self.current_digits = int(message["digits"])
        players = list(message["players"])
        me = next(
            (player for player in players if player["id"] == self.network.player_id),
            players[-1],
        )
        opponent = next(player for player in players if player["id"] != me["id"])
        self.nickname = str(me["nickname"])
        self.self_log = ft.ListView(expand=True, spacing=8, auto_scroll=True, padding=4)
        self.opponent_log = ft.ListView(expand=True, spacing=8, auto_scroll=True, padding=4)
        self.timer_text = ft.Text("00:00.0", color=IVORY, weight=ft.FontWeight.BOLD)
        self.status_text = ft.Text("対戦中", color=CREAM, weight=ft.FontWeight.BOLD)
        self.result_switcher = ft.AnimatedSwitcher(
            content=ft.Container(height=0),
            duration=420,
            transition=ft.AnimatedSwitcherTransition.SCALE,
        )

        header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            bgcolor=SURFACE,
            border_radius=14,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.TextButton("退出", icon=ft.Icons.ARROW_BACK, on_click=self._leave_match),
                    ft.Column(
                        spacing=1,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                f"ROOM {message['room_code']}  •  {self.current_digits}桁",
                                size=12,
                                color=TEXT_MUTED,
                            ),
                            self.status_text,
                        ],
                    ),
                    self.timer_text,
                ],
            ),
        )
        opponent_panel = self._player_panel(
            title="相手",
            nickname=str(opponent["nickname"]),
            log=self.opponent_log,
            accent=SAND,
            is_self=False,
        )
        self_panel = self._player_panel(
            title="あなた",
            nickname=str(me["nickname"]),
            log=self.self_log,
            accent=IVORY,
            is_self=True,
        )
        battlefield = ft.Row(
            expand=True,
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(content=opponent_panel, expand=True),
                ft.Container(
                    width=54,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Container(
                        padding=10,
                        border_radius=28,
                        bgcolor="#26221C",
                        content=ft.Text("VS", weight=ft.FontWeight.BOLD, color=SAND),
                    ),
                ),
                ft.Container(content=self_panel, expand=True),
            ],
        )
        self._switch(
            ft.Container(
                padding=18,
                content=ft.Column(
                    expand=True,
                    controls=[header, battlefield, self.result_switcher],
                    spacing=12,
                ),
            )
        )
        self.match_started_monotonic = time.monotonic()
        self._start_timer()

    def _player_panel(
        self,
        title: str,
        nickname: str,
        log: ft.ListView,
        accent: str,
        is_self: bool,
    ) -> ft.Container:
                                                                           
                                                                          
        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Container(width=5, height=34, bgcolor=accent, border_radius=3),
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(title, size=11, color=TEXT_MUTED),
                            ft.Text(
                                nickname,
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                ]
            ),
            ft.Divider(color="#2E2A24"),
            ft.Container(content=log, expand=True, bgcolor="#090908", border_radius=12),
        ]
        if is_self:
            self.guess_field = ft.TextField(
                label=f"{self.current_digits}桁の数字",
                hint_text="例: 0123",
                max_length=self.current_digits,
                keyboard_type=ft.KeyboardType.NUMBER,
                text_align=ft.TextAlign.CENTER,
                border_color="#3B3730",
                focused_border_color=IVORY,
                on_submit=self._send_guess,
                autofocus=True,
                expand=True,
            )
            self.guess_button = ft.Button(
                "予想する",
                icon=ft.Icons.SEND,
                on_click=self._send_guess,
                bgcolor=IVORY,
                color=BG,
                height=48,
            )
            self.guess_container = ft.Container(
                offset=ft.Offset(0, 0),
                animate_offset=ft.Animation(90, ft.AnimationCurve.EASE_IN_OUT),
                content=ft.Row(controls=[self.guess_field, self.guess_button]),
            )
            controls.append(self.guess_container)
        else:
            controls.append(
                ft.Container(
                    height=48,
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(1, "#3D382F"),
                    border_radius=10,
                    content=ft.Text("相手の入力をリアルタイムで表示", color=TEXT_MUTED, size=12),
                )
            )
        return ft.Container(
            expand=True,
            padding=16,
            bgcolor=SURFACE,
            border=ft.Border.all(1, accent),
            border_radius=16,
            content=ft.Column(expand=True, controls=controls, spacing=10),
        )

    async def _send_guess(self, _event: Any) -> None:
                                                                             
                                                                            
        if self.match_finished or self.guess_field is None:
            return
        guess = (self.guess_field.value or "").strip()
        valid, message = generators.validate_guess(guess, self.current_digits)
        if not valid:
            self._snack(message, error=True)
            await self._shake_guess()
            return
        self.guess_field.value = ""
        self.guess_field.update()
        try:
            await self.network.send("guess", guess=guess)
        except Exception:
            self._snack("予想を送信できませんでした。", error=True)

    async def _append_attempt(self, message: dict[str, Any]) -> None:
                                                                                
                                                                       
        is_self = message["player_id"] == self.network.player_id
        target = self.self_log if is_self else self.opponent_log
        if target is None:
            return
        accent = IVORY if is_self else SAND
        if message.get("correct"):
            accent = CREAM
        attempt_control = ft.Container(
            opacity=0,
            offset=ft.Offset(0, 0.25),
            animate_opacity=180,
            animate_offset=ft.Animation(220, ft.AnimationCurve.EASE_OUT_CUBIC),
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            bgcolor=SURFACE_ALT,
            border=ft.Border.only(left=ft.BorderSide(3, accent)),
            border_radius=10,
            content=ft.Row(
                controls=[
                    ft.Text(f"#{message['attempt']}", color=TEXT_MUTED, size=11),
                    ft.Text(
                        " ".join(str(message["guess"])),
                        expand=True,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(f"H {message['hits']}", color=CREAM, weight=ft.FontWeight.BOLD),
                    ft.Text(f"B {message['blows']}", color=SAND, weight=ft.FontWeight.BOLD),
                ]
            ),
        )
        target.controls.append(attempt_control)
        target.update()
        await asyncio.sleep(0.02)
        attempt_control.opacity = 1
        attempt_control.offset = ft.Offset(0, 0)
        attempt_control.update()

    def _finish_match(self, message: dict[str, Any]) -> None:
                                                                            
        self.match_finished = True
        self._cancel_timer()
        won = message["winner_id"] == self.network.player_id
        if self.status_text:
            self.status_text.value = "勝利！" if won else "敗北"
            self.status_text.color = CREAM if won else TAUPE
            self.status_text.update()
        if self.guess_field:
            self.guess_field.disabled = True
            self.guess_field.update()
        if self.guess_button:
            self.guess_button.disabled = True
            self.guess_button.update()
        if self.result_switcher:
            self.result_switcher.content = ft.Container(
                padding=14,
                border_radius=14,
                bgcolor="#262119" if won else "#1B1916",
                border=ft.Border.all(1, CREAM if won else TAUPE),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.EMOJI_EVENTS if won else ft.Icons.FLAG, color=CREAM if won else TAUPE),
                        ft.Text(
                            (
                                f"勝利！ {message['attempts']}回・{message['elapsed_seconds']:.1f}秒"
                                if won
                                else f"{message['winner_name']} の勝利"
                            ),
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Button("ロビーへ", on_click=self._leave_match),
                    ],
                ),
            )
            self.result_switcher.update()

    async def _leave_match(self, _event: Any) -> None:
        if self.network.connected:
            try:
                await self.network.send("cancel")
            except Exception:
                pass
        self._show_lobby()

    def _start_practice(self, _event: Any) -> None:
                                                                               
        identity = self._get_identity()
        if identity is None:
            return
        nickname, digits = identity
        self.screen = "practice"
        self.current_digits = digits
        self.nickname = nickname
        self.practice_secret = generators.create_to_solve_task(digits)
        self.practice_attempts = 0
        self.match_finished = False
        self.self_log = ft.ListView(expand=True, spacing=8, auto_scroll=True, padding=4)
        self.opponent_log = None
        self.timer_text = ft.Text("00:00.0", color=IVORY, weight=ft.FontWeight.BOLD)
        self.status_text = ft.Text("練習中", color=CREAM, weight=ft.FontWeight.BOLD)
        self.result_switcher = ft.AnimatedSwitcher(
            content=ft.Container(height=0),
            duration=420,
            transition=ft.AnimatedSwitcherTransition.SCALE,
        )
        panel = self._player_panel(
            title="練習モード",
            nickname=nickname,
            log=self.self_log,
            accent=IVORY,
            is_self=True,
        )
        assert self.guess_field is not None
        self.guess_field.on_submit = self._practice_guess
        assert self.guess_button is not None
        self.guess_button.on_click = self._practice_guess
        self._switch(
            ft.Container(
                padding=18,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.Container(
                            padding=12,
                            bgcolor=SURFACE,
                            border_radius=14,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.TextButton(
                                        "戻る", icon=ft.Icons.ARROW_BACK, on_click=self._back_to_lobby
                                    ),
                                    self.status_text,
                                    self.timer_text,
                                ],
                            ),
                        ),
                        ft.Container(content=panel, expand=True, width=650),
                        self.result_switcher,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            )
        )
        self.match_started_monotonic = time.monotonic()
        self._start_timer()

    async def _practice_guess(self, _event: Any) -> None:
                                                                           
        if self.match_finished or self.guess_field is None:
            return
        guess = (self.guess_field.value or "").strip()
        valid, message = generators.validate_guess(guess, self.current_digits)
        if not valid:
            self._snack(message, error=True)
            await self._shake_guess()
            return
        self.practice_attempts += 1
        hits, blows = generators.evaluate_guess(self.practice_secret, guess)
        self.guess_field.value = ""
        self.guess_field.update()
        await self._append_attempt(
            {
                "player_id": self.network.player_id,
                "guess": guess,
                "hits": hits,
                "blows": blows,
                "attempt": self.practice_attempts,
                "correct": hits == self.current_digits,
            }
        )
        if hits == self.current_digits:
            elapsed = time.monotonic() - self.match_started_monotonic
            self._finish_practice(elapsed)

    def _finish_practice(self, elapsed: float) -> None:
        self.match_finished = True
        self._cancel_timer()
        if self.status_text:
            self.status_text.value = "クリア！"
            self.status_text.color = CREAM
            self.status_text.update()
        if self.guess_field:
            self.guess_field.disabled = True
            self.guess_field.update()
        if self.guess_button:
            self.guess_button.disabled = True
            self.guess_button.update()
        score = generators.calculate_score(
            self.current_digits, self.practice_attempts, elapsed
        )
        if self.result_switcher:
            self.result_switcher.content = ft.Container(
                padding=14,
                border_radius=14,
                bgcolor="#262119",
                border=ft.Border.all(1, CREAM),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=CREAM),
                        ft.Text(
                            f"正解！ {self.practice_attempts}回・{elapsed:.1f}秒・{score}点",
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Button("もう一度", on_click=self._start_practice),
                    ],
                ),
            )
            self.result_switcher.update()

    def _back_to_lobby(self, _event: Any) -> None:
        self._show_lobby()

    async def _event_loop(self) -> None:
                                                                          
                                  
        while True:
            message = await self.network.events.get()
            try:
                await self._handle_server_event(message)
            except Exception as exc:
                self._snack(f"画面の更新中にエラーが発生しました: {exc}", error=True)

    async def _handle_server_event(self, message: dict[str, Any]) -> None:
                                                                           
                                                             
        event_type = message.get("type")
        if event_type == "hello":
            self.leaderboard_rows = list(message.get("leaderboard", []))
        elif event_type == "leaderboard":
            self.leaderboard_rows = list(message.get("rows", []))
            if self.screen == "lobby":
                self._show_lobby()
        elif event_type == "room_waiting":
            self._show_waiting(
                "対戦相手を待っています",
                f"{message['digits']}桁の対戦",
                str(message["room_code"]),
            )
        elif event_type == "queue_waiting":
            self._show_waiting(
                "対戦相手を探しています",
                f"{message['digits']}桁でマッチング中...",
            )
        elif event_type == "match_started":
            self._show_online_match(message)
        elif event_type == "attempt" and self.screen == "online_match":
            await self._append_attempt(message)
        elif event_type == "match_finished" and self.screen == "online_match":
            self.leaderboard_rows = list(message.get("leaderboard", []))
            self._finish_match(message)
        elif event_type == "opponent_left":
            self._snack(str(message.get("message", "対戦相手が退出しました。")), error=True)
            self._show_lobby()
        elif event_type == "error":
            self._snack(str(message.get("message", "エラーが発生しました。")), error=True)
        elif event_type == "connection_lost":
            self._snack(str(message.get("message", "接続が切れました。")), error=True)
            self._show_lobby()

    async def _shake_guess(self) -> None:
                                                                                 
        if self.guess_container is None:
            return
        for offset in (-0.025, 0.025, -0.015, 0):
            self.guess_container.offset = ft.Offset(offset, 0)
            self.guess_container.update()
            await asyncio.sleep(0.07)

    def _start_timer(self) -> None:
        self._cancel_timer()
        self.timer_task = asyncio.create_task(self._timer_loop())

    def _cancel_timer(self) -> None:
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self.timer_task = None

    async def _timer_loop(self) -> None:
                                                                              
                                                                                
        try:
            while not self.match_finished and self.timer_text is not None:
                elapsed = time.monotonic() - self.match_started_monotonic
                minutes, seconds = divmod(elapsed, 60)
                self.timer_text.value = f"{int(minutes):02d}:{seconds:04.1f}"
                self.timer_text.update()
                await asyncio.sleep(0.1)
        except (asyncio.CancelledError, AssertionError):
            return

    def _switch(self, content: ft.Control) -> None:
                                                                         
                                                                       
                                                                       
        background_watermark = ft.TransparentPointer(
            expand=True,
            content=ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                opacity=0.035,
                content=ft.Image(
                    src="/dntsne_logo.png",
                    width=760,
                    fit=ft.BoxFit.CONTAIN,
                ),
            )
        )
        corner_watermark = ft.TransparentPointer(
            expand=True,
            content=ft.Container(
                expand=True,
                alignment=ft.Alignment.BOTTOM_RIGHT,
                padding=ft.Padding.only(right=18, bottom=12),
                opacity=0.32,
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text(
                            "DNTSNE",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=IVORY,
                        ),
                        ft.Text(
                            "by Voidbrained",
                            size=8,
                            color=SAND,
                        ),
                    ],
                ),
            )
        )
        self.switcher.content = ft.Stack(
            expand=True,
            controls=[
                ft.Container(content=content, expand=True),
                background_watermark,
                corner_watermark,
            ],
        )
        self.switcher.update()

    def _snack(self, message: str, error: bool = False) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message),
                bgcolor="#201D18" if error else "#262119",
                show_close_icon=True,
            )
        )


async def main(page: ft.Page) -> None:
    await HitAndBlowApp(page).start()


if __name__ == "__main__":
                                                                        
                                                          
    ft.run(main, assets_dir="assets")
