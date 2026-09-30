from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import generators
from game_core import MatchRoom
from game_server import GameHub


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.messages.append(dict(data))

    def messages_of_type(self, event_type: str) -> list[dict[str, object]]:
        return [message for message in self.messages if message.get("type") == event_type]


class RuleTests(unittest.TestCase):
    def test_secret_has_requested_unique_digits(self) -> None:
        for count in range(generators.MIN_DIGITS, generators.MAX_DIGITS + 1):
            secret = generators.create_to_solve_task(count)
            self.assertEqual(count, len(secret))
            self.assertEqual(count, len(set(secret)))

    def test_hit_and_blow_evaluation(self) -> None:
        self.assertEqual((1, 2), generators.evaluate_guess([1, 2, 3, 4], "1352"))
        self.assertEqual((4, 0), generators.evaluate_guess([0, 1, 2, 3], "0123"))
        self.assertEqual((0, 0), generators.evaluate_guess([0, 1, 2], "345"))

    def test_guess_validation(self) -> None:
        self.assertTrue(generators.validate_guess("0123", 4)[0])
        self.assertFalse(generators.validate_guess("0012", 4)[0])
        self.assertFalse(generators.validate_guess("123", 4)[0])
        self.assertFalse(generators.validate_guess("12a3", 4)[0])

    def test_first_correct_answer_finishes_match(self) -> None:
        room = MatchRoom("ABC123", 4)
        room.add_player("p1", "Alice")
        room.add_player("p2", "Bob")
        room.start(now=100.0)
        room.players["p1"].secret = [0, 1, 2, 3]
        result = room.submit_guess("p1", "0123")
        self.assertTrue(result.correct)
        self.assertEqual("p1", room.winner_id)
        with self.assertRaisesRegex(ValueError, "終了"):
            room.submit_guess("p2", "4567")


class OnlineHubTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "scores.db"
        self.hub = GameHub(database)
        self.alice_socket = FakeSocket()
        self.bob_socket = FakeSocket()
        self.alice = await self.hub.connect(self.alice_socket)
        self.bob = await self.hub.connect(self.bob_socket)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_private_room_broadcasts_both_logs_and_result(self) -> None:
        await self.hub.handle(
            self.alice.player_id,
            {"action": "create_room", "nickname": "Alice", "digits": 4},
        )
        waiting = self.alice_socket.messages_of_type("room_waiting")[-1]
        room_code = str(waiting["room_code"])
        await self.hub.handle(
            self.bob.player_id,
            {"action": "join_room", "nickname": "Bob", "room_code": room_code},
        )

        self.assertEqual(1, len(self.alice_socket.messages_of_type("match_started")))
        self.assertEqual(1, len(self.bob_socket.messages_of_type("match_started")))
        room = self.hub.rooms[room_code]
        room.players[self.alice.player_id].secret = [0, 1, 2, 3]

        await self.hub.handle(
            self.alice.player_id,
            {"action": "guess", "guess": "0123"},
        )

        alice_attempt = self.alice_socket.messages_of_type("attempt")[-1]
        bob_attempt = self.bob_socket.messages_of_type("attempt")[-1]
        self.assertEqual(alice_attempt, bob_attempt)
        self.assertEqual(4, alice_attempt["hits"])
        self.assertEqual(
            self.alice.player_id,
            self.bob_socket.messages_of_type("match_finished")[-1]["winner_id"],
        )
        self.assertEqual("Alice", self.hub.scores.leaderboard()[0]["nickname"])

                                                                               
                                           
        before = len(self.bob_socket.messages_of_type("opponent_left"))
        await self.hub.handle(self.alice.player_id, {"action": "cancel"})
        self.assertEqual(before, len(self.bob_socket.messages_of_type("opponent_left")))

    async def test_quick_match_pairs_equal_digit_counts(self) -> None:
        await self.hub.handle(
            self.alice.player_id,
            {"action": "quick_match", "nickname": "Alice", "digits": 5},
        )
        self.assertTrue(self.alice_socket.messages_of_type("queue_waiting"))
        await self.hub.handle(
            self.bob.player_id,
            {"action": "quick_match", "nickname": "Bob", "digits": 5},
        )
        started = self.bob_socket.messages_of_type("match_started")[-1]
        self.assertEqual(5, started["digits"])
        self.assertEqual(2, len(started["players"]))

    async def test_duplicate_guess_is_rejected_server_side(self) -> None:
        await self.hub.handle(
            self.alice.player_id,
            {"action": "create_room", "nickname": "Alice", "digits": 4},
        )
        code = str(self.alice_socket.messages_of_type("room_waiting")[-1]["room_code"])
        await self.hub.handle(
            self.bob.player_id,
            {"action": "join_room", "nickname": "Bob", "room_code": code},
        )
        await self.hub.handle(
            self.alice.player_id,
            {"action": "guess", "guess": "0012"},
        )
        error = self.alice_socket.messages_of_type("error")[-1]
        self.assertIn("同じ数字", str(error["message"]))
        self.assertFalse(self.bob_socket.messages_of_type("attempt"))


if __name__ == "__main__":
    unittest.main()
