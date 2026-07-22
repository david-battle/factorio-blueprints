"""Offline first-pass tests for Full Bot Step 5 delivery."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_full_bot.archive import TextEventArchive
from jimbo_full_bot.contracts import DeliveryResult, EventKind, NormalizedEvent, ResultStatus
from jimbo_full_bot.delivery import (
    DeliveryError,
    MinimalDeliveryWorker,
    MinimalRenderer,
    OVERLONG_FALLBACK,
    RCON_SUCCESS_MARKER,
    RconDeliveryTransport,
    build_print_command,
)
from jimbo_full_bot.interactions import WelcomeService
from jimbo_full_bot.state import FlatTextStateStore


class MinimalRendererTests(unittest.TestCase):
    def test_reply_is_one_plain_line_and_normalizes_unicode_for_rcon(self) -> None:
        rendered = MinimalRenderer().render_reply(
            "request-1", "Flürki[red]", "hello\n  åäö\tworld"
        )

        self.assertEqual(
            rendered.recipient, "Flurki left-bracket red right-br"
        )
        self.assertEqual(
            rendered.text,
            "Jimbo to Flurki left-bracket red right-br: hello aao world",
        )
        self.assertNotIn("\n", rendered.text)

    def test_typographic_punctuation_becomes_readable_ascii(self) -> None:
        rendered = MinimalRenderer().render_reply(
            "request-1", "Alice", "I\u2019m chat\u2011only\u2014for now\u2026"
        )
        self.assertEqual(rendered.text, "Jimbo to Alice: I'm chat-only-for now...")

    def test_overlong_reply_is_shortened_to_the_chat_budget(self) -> None:
        rendered = MinimalRenderer(character_limit=100).render_reply(
            "request-1", "Alice", "word " * 100
        )

        self.assertLessEqual(len(rendered.text), 100)
        self.assertTrue(rendered.text.endswith("..."))
        self.assertNotIn(OVERLONG_FALLBACK, rendered.text)

    def test_removes_model_prefix_and_markdown_residue(self) -> None:
        rendered = MinimalRenderer().render_reply(
            "request-1", "Alice", "Jimbo to Alice: **Platform One** has `10` science."
        )
        self.assertEqual(
            rendered.text, "Jimbo to Alice: Platform One has 10 science."
        )

    def test_spells_out_literal_brackets_without_enabling_rich_text(self) -> None:
        rendered = MinimalRenderer().render_reply(
            "request-1", "Alice", 'The exact name is "[item=space-science-pack]".'
        )
        self.assertEqual(
            rendered.text,
            'Jimbo to Alice: The exact name is " left-bracket item=space-science-pack right-bracket ".',
        )
        self.assertNotIn("[", rendered.text)

    def test_preserves_only_exact_locally_trusted_rich_name(self) -> None:
        renderer = MinimalRenderer()
        trusted = renderer.render_reply(
            "request-1", "Alice", "The platform is [item=space-science-pack].",
            trusted_rich_text=("[item=space-science-pack]",),
        )
        untrusted = renderer.render_reply(
            "request-2", "Alice", "Try [color=red]danger[/color].",
            trusted_rich_text=("[color=red]",),
        )
        self.assertEqual(
            trusted.text, "Jimbo to Alice: The platform is [item=space-science-pack]."
        )
        self.assertNotIn("[", untrusted.text)

    def test_slash_and_command_shaped_text_remains_inert_printed_text(self) -> None:
        rendered = MinimalRenderer().render_reply(
            "request-1", "Alice", "/promote Bob; rcon.print('no') ]]"
        )
        command = build_print_command(rendered)

        self.assertIn("/promote Bob", rendered.text)
        self.assertNotIn("]]", rendered.text)
        self.assertTrue(command.startswith("/silent-command game.print([["))
        self.assertEqual(command.count("/silent-command"), 1)


class RconDeliveryTransportTests(unittest.TestCase):
    @patch("jimbo_full_bot.delivery.subprocess.run")
    def test_uses_fixed_wrapper_and_restores_command_file(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command_path = Path(directory) / "rcon-command.txt"
            command_path.write_text("/players\n", encoding="utf-8")
            original = command_path.read_bytes()

            def confirm(*_: object, **__: object) -> CompletedProcess[str]:
                written = command_path.read_text("utf-8")
                self.assertIn("game.print([[Jimbo to Alice: hello]])", written)
                return CompletedProcess([], 0, RCON_SUCCESS_MARKER, "")

            run.side_effect = confirm
            message = MinimalRenderer().render_reply("request-1", "Alice", "hello")
            result = RconDeliveryTransport(
                wrapper_path=Path("fixed-wrapper.ps1"),
                command_path=command_path,
            ).deliver(message)

            self.assertEqual(result.status, ResultStatus.COMPLETE)
            self.assertEqual(result.exact_text, message.text)
            self.assertEqual(command_path.read_bytes(), original)

    @patch("jimbo_full_bot.delivery.subprocess.run")
    def test_requires_confirmation_and_does_not_retry(self, run: object) -> None:
        run.return_value = CompletedProcess([], 0, "no marker", "")
        with tempfile.TemporaryDirectory() as directory:
            command_path = Path(directory) / "rcon-command.txt"
            command_path.write_text("/players\n", encoding="utf-8")
            message = MinimalRenderer().render_reply("request-1", "Alice", "hello")

            with self.assertRaises(DeliveryError):
                RconDeliveryTransport(
                    wrapper_path=Path("fixed-wrapper.ps1"),
                    command_path=command_path,
                ).deliver(message)

            self.assertEqual(run.call_count, 1)


class FakeTransport:
    def __init__(self, *, fail: bool = False, delay: float = 0.0) -> None:
        self.fail = fail
        self.delay = delay
        self.messages: list[str] = []
        self.active = 0
        self.maximum_active = 0
        self._guard = threading.Lock()

    def deliver(self, message: object) -> DeliveryResult:
        with self._guard:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.fail:
                raise DeliveryError("fake failure")
            self.messages.append(message.text)
            return DeliveryResult(
                message.correlation_id,
                ResultStatus.COMPLETE,
                message.text,
                1,
                datetime.now(UTC),
            )
        finally:
            with self._guard:
                self.active -= 1


def build_worker(root: Path, transport: object, *, enabled: bool) -> tuple[
    MinimalDeliveryWorker, TextEventArchive, FlatTextStateStore
]:
    archive = TextEventArchive(root / "archive")
    state = FlatTextStateStore(root / "state")
    return (
        MinimalDeliveryWorker(
            transport=transport, archive=archive, state=state, enabled=enabled
        ),
        archive,
        state,
    )


class MinimalDeliveryWorkerTests(unittest.TestCase):
    def test_disabled_worker_does_not_call_transport_and_archives_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transport = FakeTransport()
            worker, archive, _ = build_worker(Path(directory), transport, enabled=False)
            message = MinimalRenderer().render_reply("request-1", "Alice", "hello")

            result = worker.deliver(message)

            self.assertEqual(result.status, ResultStatus.REJECTED)
            self.assertEqual(transport.messages, [])
            records = tuple(archive.iter_records())
            self.assertEqual([record.kind for record in records], ["render", "delivery"])
            self.assertEqual(records[0].payload, message.text)

    def test_confirmed_delivery_is_archived_exactly_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transport = FakeTransport()
            worker, archive, _ = build_worker(Path(directory), transport, enabled=True)
            message = MinimalRenderer().render_reply("request-1", "Alice", "hello")

            first = worker.deliver(message)
            duplicate = worker.deliver(message)

            self.assertEqual(first.exact_text, message.text)
            self.assertEqual(duplicate.attempts, 0)
            self.assertEqual(transport.messages, [message.text])
            records = tuple(archive.iter_records())
            self.assertIn("text=" + message.text, records[-1].payload)

    def test_failure_is_archived_and_not_automatically_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transport = FakeTransport(fail=True)
            worker, archive, _ = build_worker(Path(directory), transport, enabled=True)
            message = MinimalRenderer().render_reply("request-1", "Alice", "hello")

            result = worker.deliver(message)

            self.assertEqual(result.status, ResultStatus.FAILED)
            self.assertEqual(result.attempts, 1)
            self.assertIn("fake failure", tuple(archive.iter_records())[-1].payload)

    def test_concurrent_calls_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transport = FakeTransport(delay=0.03)
            worker, _, _ = build_worker(Path(directory), transport, enabled=True)
            renderer = MinimalRenderer()
            messages = [
                renderer.render_reply(f"request-{index}", "Alice", str(index))
                for index in range(3)
            ]
            threads = [threading.Thread(target=worker.deliver, args=(item,)) for item in messages]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(transport.maximum_active, 1)
            self.assertEqual(len(transport.messages), 3)

    def test_confirmed_welcome_marks_intent_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = FlatTextStateStore(root / "state")
            welcomes = WelcomeService(state)
            join = NormalizedEvent(
                "join-1",
                EventKind.PLAYER_JOIN,
                datetime.now(UTC),
                "source",
                0,
                10,
                "Alice joined",
                "Alice",
            )
            intent = welcomes.prepare(join, enabled=True)
            assert intent is not None
            transport = FakeTransport()
            archive = TextEventArchive(root / "archive")
            worker = MinimalDeliveryWorker(
                transport=transport, archive=archive, state=state, enabled=True
            )

            result = worker.deliver_welcome(intent, MinimalRenderer(), welcomes)

            self.assertEqual(result.status, ResultStatus.COMPLETE)
            self.assertEqual(
                transport.messages,
                ["Jimbo: Welcome, Alice! Begin queries with Jimbo."],
            )
            self.assertIsNone(welcomes.prepare(join, enabled=True))


if __name__ == "__main__":
    unittest.main()
