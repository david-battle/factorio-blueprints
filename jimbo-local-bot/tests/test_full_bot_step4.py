"""Offline first-pass tests for Full Bot Step 4 interactions."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from jimbo_full_bot.contracts import EventKind, NormalizedEvent
from jimbo_full_bot.interactions import InvocationClassifier, WelcomeService
from jimbo_full_bot.state import FlatTextStateStore


def event(
    event_id: str,
    kind: EventKind,
    actor: str,
    message: str | None = None,
) -> NormalizedEvent:
    raw = message or f"{actor} joined the game"
    return NormalizedEvent(
        event_id=event_id,
        kind=kind,
        occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        source_instance="source-1",
        byte_start=0,
        byte_end=len(raw.encode("utf-8")),
        raw_text=raw,
        actor=actor,
        message=message,
    )


class InvocationClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = InvocationClassifier()

    def chat(self, message: str, *, actor: str = "Alice") -> object:
        return self.classifier.classify(
            event("event-1", EventKind.PUBLIC_CHAT, actor, message)
        )

    def test_accepts_required_leading_forms_case_insensitively(self) -> None:
        cases = {
            "Jimbo hello": "hello",
            "hey jimbo, hello": "hello",
            "  !!! HEY, JIMBO:   who is online?": "who is online?",
            "jImBo": "",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                decision = self.chat(message)
                assert decision is not None
                self.assertTrue(decision.accepted)
                self.assertEqual(decision.request_text, expected)

    def test_rejects_longer_word_later_mention_quote_and_third_person(self) -> None:
        for message in (
            "Jimbob hello",
            "Alice asked Jimbo for help",
            '"Jimbo, say hello"',
            "we were discussing Jimbo",
        ):
            with self.subTest(message=message):
                decision = self.chat(message)
                assert decision is not None
                self.assertFalse(decision.accepted)
                self.assertEqual(decision.reason, "no leading invocation")

    def test_ignores_server_and_jimbo_authored_chat_to_prevent_loops(self) -> None:
        for actor in ("<server>", "SERVER", "Jimbo"):
            with self.subTest(actor=actor):
                decision = self.chat("Jimbo to Alice: hello", actor=actor)
                assert decision is not None
                self.assertFalse(decision.accepted)
                self.assertEqual(decision.reason, "self-authored chat")

    def test_non_chat_event_has_no_invocation_decision(self) -> None:
        self.assertIsNone(
            self.classifier.classify(event("join-1", EventKind.PLAYER_JOIN, "Alice"))
        )

    def test_whitespace_is_normalized_in_request(self) -> None:
        decision = self.chat("Jimbo,  how\t many\n furnaces?")
        assert decision is not None
        self.assertEqual(decision.request_text, "how many furnaces?")


class WelcomeServiceTests(unittest.TestCase):
    def make_service(self, root: Path) -> WelcomeService:
        return WelcomeService(FlatTextStateStore(root / "state"))

    def test_first_join_uses_welcome_and_required_invocation_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))

            intent = service.prepare(
                event("join-1", EventKind.PLAYER_JOIN, "Alice"), enabled=True
            )

            assert intent is not None
            self.assertFalse(intent.returning)
            self.assertEqual(intent.text, "Welcome, Alice! Begin queries with Jimbo.")
            self.assertIn("Jimbo", intent.text)

    def test_later_join_is_welcome_back_and_keeps_latest_display_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            first = service.prepare(
                event("join-1", EventKind.PLAYER_JOIN, "Alice"), enabled=True
            )
            assert first is not None
            service.mark_delivered(first)

            returning = service.prepare(
                event("join-2", EventKind.PLAYER_JOIN, "ALICE"), enabled=True
            )

            assert returning is not None
            self.assertTrue(returning.returning)
            self.assertEqual(
                returning.text, "Welcome back, ALICE! Begin queries with Jimbo."
            )
            self.assertEqual(service.latest_display_name("alice"), "ALICE")

    def test_pending_intent_survives_restart_with_same_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            join = event("join-1", EventKind.PLAYER_JOIN, "Alice")
            first = self.make_service(root).prepare(join, enabled=True)

            replay = self.make_service(root).prepare(join, enabled=True)

            self.assertEqual(replay, first)

    def test_delivered_join_is_not_greeted_again_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            join = event("join-1", EventKind.PLAYER_JOIN, "Alice")
            service = self.make_service(root)
            intent = service.prepare(join, enabled=True)
            assert intent is not None
            service.mark_delivered(intent)

            replay = self.make_service(root).prepare(join, enabled=True)

            self.assertIsNone(replay)

    def test_disabled_and_suppressed_joins_create_no_intent_or_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(root)
            disabled = event("join-1", EventKind.PLAYER_JOIN, "Alice")
            suppressed = event("join-2", EventKind.PLAYER_JOIN, "Bob")

            self.assertIsNone(service.prepare(disabled, enabled=False))
            self.assertIsNone(
                service.prepare(suppressed, enabled=True, suppressed=True)
            )
            self.assertIsNone(service.prepare(disabled, enabled=True))
            self.assertIsNone(service.prepare(suppressed, enabled=True))

    def test_disabled_first_join_still_makes_later_distinct_join_returning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            service.prepare(
                event("join-1", EventKind.PLAYER_JOIN, "Alice"), enabled=False
            )

            intent = service.prepare(
                event("join-2", EventKind.PLAYER_JOIN, "Alice"), enabled=True
            )

            assert intent is not None
            self.assertTrue(intent.returning)

    def test_retained_chat_makes_first_bot_observed_join_welcome_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            historical_chat = event(
                "chat-before-launch",
                EventKind.PUBLIC_CHAT,
                "Moon-O-Cronic",
                "hello before Jimbo launched",
            )

            changed = service.seed_seen_players((historical_chat,))
            intent = service.prepare(
                event("join-after-launch", EventKind.PLAYER_JOIN, "moon-o-cronic"),
                enabled=True,
            )

            self.assertEqual(changed, 1)
            assert intent is not None
            self.assertTrue(intent.returning)
            self.assertEqual(
                intent.text,
                "Welcome back, moon-o-cronic! Begin queries with Jimbo.",
            )

    def test_history_seed_emits_nothing_and_uses_chat_join_and_leave(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            retained = (
                event("chat-1", EventKind.PUBLIC_CHAT, "Alice", "hello"),
                event("join-1", EventKind.PLAYER_JOIN, "Bob"),
                event("leave-1", EventKind.PLAYER_LEAVE, "Carol"),
                event("server-chat", EventKind.PUBLIC_CHAT, "<server>", "notice"),
            )

            changed = service.seed_seen_players(retained)

            self.assertEqual(changed, 4)
            for player in ("Alice", "Bob", "Carol"):
                self.assertIsNotNone(service.latest_display_name(player))
            self.assertIsNone(service.latest_display_name("<server>"))
            state = service.state.load("seen_players")
            self.assertEqual(sum(key.startswith("join.") for key in state), 1)

    def test_historical_join_replay_does_not_emit_a_greeting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            historical_join = event("join-while-stopped", EventKind.PLAYER_JOIN, "Alice")

            service.seed_seen_players((historical_join,))

            self.assertIsNone(service.prepare(historical_join, enabled=True))

    def test_reseeding_history_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            retained = (event("leave-1", EventKind.PLAYER_LEAVE, "Alice"),)

            self.assertEqual(service.seed_seen_players(retained), 1)
            self.assertEqual(service.seed_seen_players(retained), 0)

    def test_non_join_event_produces_no_welcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            self.assertIsNone(
                service.prepare(
                    event("chat-1", EventKind.PUBLIC_CHAT, "Alice", "Jimbo hi"),
                    enabled=True,
                )
            )

    def test_welcome_path_has_no_model_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.make_service(Path(directory))
            intent = service.prepare(
                event("join-1", EventKind.PLAYER_JOIN, "HANYUEYUE"), enabled=True
            )

            assert intent is not None
            self.assertEqual(
                intent.text, "Welcome, HANYUEYUE! Begin queries with Jimbo."
            )


if __name__ == "__main__":
    unittest.main()
