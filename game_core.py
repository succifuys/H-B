from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import generators


@dataclass(slots=True)
class PlayerState:
                                                                          
    player_id: str
    nickname: str
    secret: list[int] = field(default_factory=list)
    attempts: int = 0


@dataclass(slots=True)
class MatchAttempt:
                                                                          
    player_id: str
    nickname: str
    guess: str
    hits: int
    blows: int
    attempt: int
    correct: bool

    def as_message(self) -> dict[str, object]:
        return {
            "type": "attempt",
            "player_id": self.player_id,
            "nickname": self.nickname,
            "guess": self.guess,
            "hits": self.hits,
            "blows": self.blows,
            "attempt": self.attempt,
            "correct": self.correct,
        }


@dataclass(slots=True)
class MatchRoom:
                                                                                  
    code: str
    digit_count: int
    players: dict[str, PlayerState] = field(default_factory=dict)
    status: str = "waiting"
    started_at: float | None = None
    winner_id: str | None = None

    def add_player(self, player_id: str, nickname: str) -> None:
        if self.status != "waiting" or len(self.players) >= 2:
            raise ValueError("このルームには参加できません。")
        self.players[player_id] = PlayerState(player_id, nickname)

    def start(self, now: float | None = None) -> None:
                                                                       
        if len(self.players) != 2:
            raise ValueError("対戦相手がまだいません。")
        for player in self.players.values():
            player.secret = generators.create_to_solve_task(self.digit_count)
            player.attempts = 0
        self.status = "playing"
        self.started_at = time.time() if now is None else now

    def submit_guess(self, player_id: str, guess: str) -> MatchAttempt:
                                                                             
        if self.status != "playing":
            raise ValueError("この対戦はすでに終了しています。")
        if player_id not in self.players:
            raise ValueError("プレイヤーが見つかりません。")

        valid, message = generators.validate_guess(guess, self.digit_count)
        if not valid:
            raise ValueError(message)

        player = self.players[player_id]
        player.attempts += 1
        hits, blows = generators.evaluate_guess(player.secret, guess)
        correct = hits == self.digit_count
        if correct:
            self.status = "finished"
            self.winner_id = player_id

        return MatchAttempt(
            player_id=player_id,
            nickname=player.nickname,
            guess=guess,
            hits=hits,
            blows=blows,
            attempt=player.attempts,
            correct=correct,
        )

    def public_players(self) -> list[dict[str, str]]:
        return [
            {"id": player.player_id, "nickname": player.nickname}
            for player in self.players.values()
        ]

    def elapsed(self, now: float | None = None) -> float:
        if self.started_at is None:
            return 0.0
        return max(0.0, (time.time() if now is None else now) - self.started_at)


class ScoreRepository:
                                                                            

    def __init__(self, database_path: str | Path = "data/hit_and_blow.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
                                                                                
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    nickname TEXT PRIMARY KEY COLLATE NOCASE,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    best_attempts INTEGER,
                    best_seconds REAL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def record_match(
        self,
        winner: str,
        loser: str,
        attempts: int,
        elapsed_seconds: float,
    ) -> None:
                                                                        
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO players (
                    nickname, wins, losses, best_attempts, best_seconds, updated_at
                ) VALUES (?, 1, 0, ?, ?, ?)
                ON CONFLICT(nickname) DO UPDATE SET
                    wins = wins + 1,
                    best_attempts = CASE
                        WHEN best_attempts IS NULL OR excluded.best_attempts < best_attempts
                        THEN excluded.best_attempts ELSE best_attempts END,
                    best_seconds = CASE
                        WHEN best_seconds IS NULL OR excluded.best_seconds < best_seconds
                        THEN excluded.best_seconds ELSE best_seconds END,
                    updated_at = excluded.updated_at
                """,
                (winner, attempts, elapsed_seconds, now),
            )
            connection.execute(
                """
                INSERT INTO players (nickname, wins, losses, updated_at)
                VALUES (?, 0, 1, ?)
                ON CONFLICT(nickname) DO UPDATE SET
                    losses = losses + 1,
                    updated_at = excluded.updated_at
                """,
                (loser, now),
            )

    def leaderboard(self, limit: int = 20) -> list[dict[str, object]]:
                                                                                 
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT nickname, wins, losses, best_attempts, best_seconds
                FROM players
                ORDER BY wins DESC,
                         CASE WHEN best_attempts IS NULL THEN 1 ELSE 0 END,
                         best_attempts ASC,
                         best_seconds ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
