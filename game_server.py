                                                                  

from __future__ import annotations

import asyncio
import secrets
import string
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import generators
from game_core import MatchRoom, ScoreRepository


class SocketLike(Protocol):
                                                                         
    async def send_json(self, data: Any) -> None: ...


@dataclass(slots=True)
class ConnectedPlayer:
                                                                       
    player_id: str
    socket: SocketLike
    nickname: str = ""
    room_code: str | None = None
    queued_digits: int | None = None


class GameHub:
                                                                         

    def __init__(self, database_path: str | Path = "data/hit_and_blow.db") -> None:
                                                                                
        self.players: dict[str, ConnectedPlayer] = {}
        self.rooms: dict[str, MatchRoom] = {}
        self.quick_queues: dict[int, deque[str]] = defaultdict(deque)
        self.scores = ScoreRepository(database_path)
        self._lock = asyncio.Lock()

    async def connect(self, socket: SocketLike) -> ConnectedPlayer:
                                                                           
        player = ConnectedPlayer(uuid.uuid4().hex, socket)
        async with self._lock:
            self.players[player.player_id] = player
        await self._safe_send(
            player,
            {
                "type": "hello",
                "player_id": player.player_id,
                "leaderboard": self.scores.leaderboard(),
            },
        )
        return player

    async def disconnect(self, player_id: str) -> None:
                                                                               
        dispatch: list[tuple[ConnectedPlayer, dict[str, object]]] = []
        async with self._lock:
            player = self.players.pop(player_id, None)
            if player is None:
                return
            self._remove_from_queue_locked(player)
            dispatch.extend(self._leave_room_locked(player, disconnected=True))
        await self._dispatch(dispatch)

    async def handle(self, player_id: str, payload: dict[str, Any]) -> None:
                                                                               
                                                                            
        dispatch: list[tuple[ConnectedPlayer, dict[str, object]]] = []
        async with self._lock:
            player = self.players.get(player_id)
            if player is None:
                return
            action = str(payload.get("action", ""))
            try:
                if action == "create_room":
                    dispatch.extend(self._create_room_locked(player, payload))
                elif action == "join_room":
                    dispatch.extend(self._join_room_locked(player, payload))
                elif action == "quick_match":
                    dispatch.extend(self._quick_match_locked(player, payload))
                elif action == "guess":
                    dispatch.extend(self._guess_locked(player, payload))
                elif action == "cancel":
                    self._remove_from_queue_locked(player)
                    dispatch.extend(self._leave_room_locked(player))
                    dispatch.append((player, {"type": "returned_to_lobby"}))
                elif action == "leaderboard":
                    dispatch.append(
                        (
                            player,
                            {"type": "leaderboard", "rows": self.scores.leaderboard()},
                        )
                    )
                else:
                    raise ValueError("不明な操作です。")
            except ValueError as exc:
                dispatch.append((player, {"type": "error", "message": str(exc)}))
        await self._dispatch(dispatch)

    def _identity(self, player: ConnectedPlayer, payload: dict[str, Any]) -> tuple[str, int]:
                                                                                    
        nickname = str(payload.get("nickname", "")).strip()
        if not nickname:
            raise ValueError("プレイヤー名を入力してください。")
        if len(nickname) > 16:
            raise ValueError("プレイヤー名は16文字以内にしてください。")
        digits = generators.normalize_digit_count(payload.get("digits"), default=-1)
        if digits == -1:
            raise ValueError(
                f"桁数は{generators.MIN_DIGITS}～{generators.MAX_DIGITS}にしてください。"
            )
        player.nickname = nickname
        return nickname, digits

    def _ensure_available(self, player: ConnectedPlayer) -> None:
        if player.room_code:
            room = self.rooms.get(player.room_code)
            if room and room.status == "playing":
                raise ValueError("対戦中は別のルームに移動できません。")
            self._leave_room_locked(player)
        self._remove_from_queue_locked(player)

    def _create_room_locked(
        self, player: ConnectedPlayer, payload: dict[str, Any]
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
                                                                               
        nickname, digits = self._identity(player, payload)
        self._ensure_available(player)
        code = self._new_room_code()
        room = MatchRoom(code, digits)
        room.add_player(player.player_id, nickname)
        self.rooms[code] = room
        player.room_code = code
        return [
            (
                player,
                {"type": "room_waiting", "room_code": code, "digits": digits},
            )
        ]

    def _join_room_locked(
        self, player: ConnectedPlayer, payload: dict[str, Any]
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
                                                                                 
        nickname = str(payload.get("nickname", "")).strip()
        if not nickname:
            raise ValueError("プレイヤー名を入力してください。")
        if len(nickname) > 16:
            raise ValueError("プレイヤー名は16文字以内にしてください。")
        code = str(payload.get("room_code", "")).strip().upper()
        if not code:
            raise ValueError("ルームコードを入力してください。")
        room = self.rooms.get(code)
        if room is None or room.status != "waiting" or len(room.players) != 1:
            raise ValueError("ルームが見つからないか、すでに満員です。")
        if player.player_id in room.players:
            raise ValueError("自分のルームには参加済みです。")

        self._ensure_available(player)
        player.nickname = nickname
        player.room_code = code
        room.add_player(player.player_id, nickname)
        return self._start_room_locked(room)

    def _quick_match_locked(
        self, player: ConnectedPlayer, payload: dict[str, Any]
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
                                                                          
                                                  
        nickname, digits = self._identity(player, payload)
        self._ensure_available(player)
        queue = self.quick_queues[digits]

        opponent: ConnectedPlayer | None = None
        while queue:
            candidate_id = queue.popleft()
            candidate = self.players.get(candidate_id)
            if (
                candidate
                and candidate.player_id != player.player_id
                and candidate.room_code is None
                and candidate.queued_digits == digits
            ):
                opponent = candidate
                break

        if opponent is None:
            player.queued_digits = digits
            queue.append(player.player_id)
            return [(player, {"type": "queue_waiting", "digits": digits})]

        opponent.queued_digits = None
        code = self._new_room_code()
        room = MatchRoom(code, digits)
        room.add_player(opponent.player_id, opponent.nickname)
        room.add_player(player.player_id, nickname)
        self.rooms[code] = room
        opponent.room_code = code
        player.room_code = code
        return self._start_room_locked(room)

    def _start_room_locked(
        self, room: MatchRoom
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
        room.start()
        message: dict[str, object] = {
            "type": "match_started",
            "room_code": room.code,
            "digits": room.digit_count,
            "players": room.public_players(),
            "started_at": room.started_at or 0.0,
        }
        return [
            (self.players[player_id], message)
            for player_id in room.players
            if player_id in self.players
        ]

    def _guess_locked(
        self, player: ConnectedPlayer, payload: dict[str, Any]
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
                                                                                  
                                                                  
        if not player.room_code or player.room_code not in self.rooms:
            raise ValueError("参加中の対戦がありません。")
        room = self.rooms[player.room_code]
        guess = str(payload.get("guess", "")).strip()
        attempt = room.submit_guess(player.player_id, guess)
        participants = [
            self.players[player_id]
            for player_id in room.players
            if player_id in self.players
        ]
        dispatch: list[tuple[ConnectedPlayer, dict[str, object]]] = [
            (participant, attempt.as_message()) for participant in participants
        ]

        if attempt.correct:
            opponent = next(
                state for state in room.players.values() if state.player_id != player.player_id
            )
            elapsed = room.elapsed()
            self.scores.record_match(
                winner=attempt.nickname,
                loser=opponent.nickname,
                attempts=attempt.attempt,
                elapsed_seconds=elapsed,
            )
            finish_message: dict[str, object] = {
                "type": "match_finished",
                "winner_id": player.player_id,
                "winner_name": attempt.nickname,
                "attempts": attempt.attempt,
                "elapsed_seconds": round(elapsed, 2),
                "leaderboard": self.scores.leaderboard(),
            }
            dispatch.extend((participant, finish_message) for participant in participants)
        return dispatch

    def _leave_room_locked(
        self, player: ConnectedPlayer, disconnected: bool = False
    ) -> list[tuple[ConnectedPlayer, dict[str, object]]]:
                                                                                
        if not player.room_code:
            return []
        code = player.room_code
        player.room_code = None
        room = self.rooms.get(code)
        if room is None:
            return []

        should_notify = room.status != "finished"
        room.players.pop(player.player_id, None)
        dispatch: list[tuple[ConnectedPlayer, dict[str, object]]] = []
        for opponent_id in room.players:
            opponent = self.players.get(opponent_id)
            if opponent:
                opponent.room_code = None
                if should_notify:
                    dispatch.append(
                        (
                            opponent,
                            {
                                "type": "opponent_left",
                                "message": "対戦相手との接続が切れました。"
                                if disconnected
                                else "対戦相手がルームを退出しました。",
                            },
                        )
                    )
        self.rooms.pop(code, None)
        return dispatch

    def _remove_from_queue_locked(self, player: ConnectedPlayer) -> None:
        if player.queued_digits is None:
            return
        queue = self.quick_queues[player.queued_digits]
        try:
            queue.remove(player.player_id)
        except ValueError:
            pass
        player.queued_digits = None

    def _new_room_code(self) -> str:
                                                                            
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if code not in self.rooms:
                return code

    async def _dispatch(
        self, messages: list[tuple[ConnectedPlayer, dict[str, object]]]
    ) -> None:
                                                                          
        if not messages:
            return
        await asyncio.gather(
            *(self._safe_send(player, message) for player, message in messages),
            return_exceptions=True,
        )

    async def _safe_send(
        self, player: ConnectedPlayer, message: dict[str, object]
    ) -> None:
        try:
            result: Awaitable[None] = player.socket.send_json(message)
            await result
        except Exception:
                                                                     
            return
