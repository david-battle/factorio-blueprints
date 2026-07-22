"""Offline tests for authoritative Step 6 runtime, history, and permission facts."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_full_bot.archive import TextEventArchive
from jimbo_full_bot.authoritative import (
    AuthoritativeFactProvider,
    PermissionProvider,
    direct_fact_answer,
)
from jimbo_full_bot.config import FullBotConfig
from jimbo_full_bot.contracts import EventKind, NormalizedEvent, ResultStatus


class FakeModel:
    last_usage = {"total_tokens": 42}
    last_rate_limits = {"x-ratelimit-remaining-requests": "99"}


def historical(kind: EventKind, actor: str, minute: int) -> NormalizedEvent:
    return NormalizedEvent(
        f"event-{kind.value}-{minute}", kind,
        datetime(2026, 7, 21, 12, minute, tzinfo=UTC), "source", minute, minute + 1,
        "raw", actor, "hello" if kind is EventKind.PUBLIC_CHAT else None,
    )


class AuthoritativeFactTests(unittest.TestCase):
    def provider(self, root: Path, history=()) -> AuthoritativeFactProvider:
        config = FullBotConfig.offline().with_overrides(runtime_dir=root)
        return AuthoritativeFactProvider(
            config, TextEventArchive(root / "archive"), history, FakeModel(),
            PermissionProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=root / "command.txt",
                timeout_seconds=5,
            ),
        )

    def test_runtime_and_server_identity_are_configuration_owned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = self.provider(Path(directory))
            runtime, server = provider.execute((
                {"op": "runtime_identity"}, {"op": "server_identity"},
            ))
            self.assertEqual(runtime.values["model"], "big-pickle")
            self.assertIsNone(runtime.values["model_parameter_count"])
            self.assertEqual(runtime.values["observed_usage"]["total_tokens"], 42)
            self.assertEqual(server.values["server_owner"], "dlbattle")
            self.assertEqual(server.values["jimbo_operator"], "dlbattle")
            self.assertEqual(server.values["moderator_roster"], [])
            self.assertIn("Humans decide", server.values["philosophy"])
            self.assertNotIn("moderator", server.summary.casefold())

            overview = provider.execute(
                ({"op": "server_identity"},), subjects=("server",)
            )[0]
            self.assertIn("Factorio 2.1.12", overview.summary)
            self.assertIn("player freedom", overview.summary)
            self.assertNotIn("server owner", overview.summary)

    def test_history_is_case_insensitive_and_missing_evidence_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            history = (
                historical(EventKind.PUBLIC_CHAT, "Alice", 1),
                historical(EventKind.PLAYER_JOIN, "ALICE", 2),
                historical(EventKind.PLAYER_LEAVE, "Alice", 3),
            )
            provider = self.provider(Path(directory), history)
            found, missing = provider.execute((
                {"op": "player_history", "player": "alice"},
                {"op": "player_history", "player": "Nobody"},
            ))
            self.assertEqual(found.status, ResultStatus.COMPLETE)
            self.assertEqual(found.values["joins"], 1)
            self.assertEqual(found.values["leaves"], 1)
            self.assertIn("last seen 2026-07-21 12:03 UTC", found.summary)
            self.assertEqual(missing.status, ResultStatus.UNKNOWN)
            self.assertIn("does not prove", missing.warnings[0])

    @patch("jimbo_full_bot.authoritative.subprocess.run")
    def test_permission_results_distinguish_admins_groups_and_actions(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = root / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            original = command.read_bytes()
            payloads = iter((
                {"admins": ["Alice"]},
                {"player": "Bob", "found": True, "admin": False,
                 "group": "Default", "action": "ban", "input_action": "admin_action",
                 "action_known": True, "allowed": False},
            ))
            def completed(*_args, **_kwargs):
                self.assertIn("helpers.table_to_json", command.read_text(encoding="utf-8"))
                return CompletedProcess(
                    [], 0, "JIMBO_PERMISSIONS|" + json.dumps(next(payloads)), ""
                )
            run.side_effect = completed
            results = PermissionProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5,
            ).execute((
                {"op": "list_admins"},
                {"op": "player_permissions", "player": "Bob", "action": "ban"},
            ))
            self.assertIn("not server ownership", results[0].summary)
            self.assertNotIn("moderator", results[0].summary.casefold())
            self.assertIn("not allowed", results[1].summary)
            self.assertIn("input action=admin_action", results[1].summary)
            self.assertEqual(command.read_bytes(), original)

    @patch("jimbo_full_bot.authoritative.subprocess.run")
    def test_connected_admin_query_uses_connected_players_only(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "command.txt"
            command.write_text("/players\n", encoding="utf-8")
            def completed(*_args, **_kwargs):
                current = command.read_text(encoding="utf-8")
                self.assertIn("game.connected_players", current)
                self.assertNotIn("pairs(game.players)", current)
                return CompletedProcess(
                    [], 0, 'JIMBO_PERMISSIONS|{"admins":["Alice"]}', ""
                )
            run.side_effect = completed
            result = PermissionProvider(
                wrapper_path=Path("wrapper.ps1"), command_path=command, timeout_seconds=5,
            ).execute(({"op": "list_admins", "connected_only": True},))[0]
            self.assertIn("Currently connected", result.summary)
            self.assertTrue(result.values["connected_only"])

    def test_direct_answer_uses_exact_application_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.provider(Path(directory)).execute(({"op": "server_identity"},))
            self.assertEqual(direct_fact_answer(result), result[0].summary)

    def test_permission_help_requests_an_exact_player(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.provider(Path(directory)).execute((
                {"op": "player_permissions_help"},
            ))[0]
            self.assertEqual(result.status, ResultStatus.UNKNOWN)
            self.assertIn("exact player name", result.summary)


if __name__ == "__main__":
    unittest.main()
