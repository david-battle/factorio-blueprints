"""Offline acceptance tests for Full Bot Step 1."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from jimbo_full_bot.__main__ import main
from jimbo_full_bot.app import FullBotApplication
from jimbo_full_bot.config import ConfigurationError, FullBotConfig
from jimbo_full_bot.contracts import (
    AuthorityDecision,
    DeliveryResult,
    EventKind,
    NormalizedEvent,
    RenderedMessage,
    RequestPlan,
    ResultStatus,
    RouteKind,
    Provenance,
    ToolResult,
)


class FullBotConfigurationTests(unittest.TestCase):
    def test_offline_defaults_disable_every_live_capability(self) -> None:
        config = FullBotConfig.offline()

        self.assertEqual(config.provider, "opencode")
        self.assertEqual(config.model, "big-pickle")
        self.assertEqual(config.management_player, "dlbattle")
        self.assertFalse(config.public_replies_enabled)
        self.assertFalse(config.welcomes_enabled)
        self.assertFalse(config.live_log_enabled)
        self.assertFalse(config.live_rcon_enabled)
        self.assertFalse(config.placement_enabled)

    def test_defaults_reference_existing_key_path_without_reading_it(self) -> None:
        with patch.object(Path, "read_text", side_effect=AssertionError("key read")):
            config = FullBotConfig.offline()
            report = FullBotApplication(config).run_offline()

        self.assertEqual(config.api_key_path.name, "auth.json")
        self.assertIn(("api_key", "configured path (not read)"), report.summary)

    def test_safe_summary_does_not_expose_secret_path_or_secret_value(self) -> None:
        secret_path = Path("runtime") / "super-secret-value.txt"
        config = FullBotConfig(api_key_path=secret_path).validate()
        summary = str(config.safe_summary())

        self.assertNotIn("super-secret-value", summary)
        self.assertNotIn(str(secret_path), summary)
        self.assertNotIn("rconpw", summary.casefold())

    def test_validated_overrides_round_trip(self) -> None:
        config = FullBotConfig.offline().with_overrides(
            queue_limit=7,
            chat_character_limit=200,
            provider_timeout_seconds=30.0,
        )

        self.assertEqual(config.queue_limit, 7)
        self.assertEqual(config.chat_character_limit, 200)
        self.assertEqual(config.provider_timeout_seconds, 30.0)

    def test_unknown_override_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "unknown configuration"):
            FullBotConfig.offline().with_overrides(not_a_setting=True)

    def test_invalid_limits_are_rejected(self) -> None:
        invalid = (
            {"queue_limit": 0},
            {"chat_character_limit": 10},
            {"provider_timeout_seconds": 0},
            {"rcon_timeout_seconds": -1},
            {"archive_rotation_bytes": 100},
        )
        for change in invalid:
            with self.subTest(change=change):
                with self.assertRaises(ConfigurationError):
                    FullBotConfig.offline().with_overrides(**change)

    def test_live_feature_dependencies_are_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "public replies require"):
            FullBotConfig(public_replies_enabled=True).validate()
        with self.assertRaisesRegex(ConfigurationError, "welcomes require"):
            FullBotConfig(welcomes_enabled=True).validate()
        with self.assertRaisesRegex(ConfigurationError, "placement requires"):
            FullBotConfig(placement_enabled=True).validate()

    def test_first_release_provider_is_groq_only(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "provider must be 'groq'"):
            FullBotConfig(provider="ollama").validate()


class FullBotContractTests(unittest.TestCase):
    def test_normalized_event_preserves_required_provenance(self) -> None:
        event = NormalizedEvent(
            event_id="source:10:20",
            kind=EventKind.PUBLIC_CHAT,
            occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            source_instance="server-log-1",
            byte_start=10,
            byte_end=20,
            raw_text="[CHAT] player: Jimbo hello",
            actor="player",
            message="Jimbo hello",
        )

        self.assertEqual(event.kind.value, "public_chat")
        self.assertEqual(event.actor, "player")
        self.assertEqual((event.byte_start, event.byte_end), (10, 20))

    def test_event_contract_round_trips_through_plain_data(self) -> None:
        event = NormalizedEvent(
            event_id="event-1",
            kind=EventKind.PLAYER_JOIN,
            occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            source_instance="source-1",
            byte_start=5,
            byte_end=25,
            raw_text="player joined",
            actor="Flürki",
        )

        self.assertEqual(NormalizedEvent.from_data(event.to_data()), event)

    def test_tool_result_round_trip_preserves_status_and_provenance(self) -> None:
        result = ToolResult(
            status=ResultStatus.PARTIAL,
            summary="two pages inspected",
            provenance=Provenance(
                source="read-only-rcon",
                collected_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
                scope="surface=nauvis",
                filters=("type=container",),
                complete=False,
            ),
            values={"count": 12},
            warnings=("page limit reached",),
        )

        self.assertEqual(ToolResult.from_data(result.to_data()), result)

    def test_normalized_event_rejects_naive_time_and_bad_range(self) -> None:
        common = dict(
            event_id="event",
            kind=EventKind.DIAGNOSTIC,
            source_instance="source",
            raw_text="text",
        )
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            NormalizedEvent(
                occurred_at=datetime(2026, 7, 21),
                byte_start=0,
                byte_end=1,
                **common,
            )
        with self.assertRaisesRegex(ValueError, "byte range"):
            NormalizedEvent(
                occurred_at=datetime.now(UTC),
                byte_start=2,
                byte_end=1,
                **common,
            )

    def test_request_plan_keeps_authority_outside_model_text(self) -> None:
        authority = AuthorityDecision(
            actor="player",
            is_management=False,
            allowed=False,
            capability="ghost_place",
            reason="management only",
        )
        plan = RequestPlan(
            correlation_id="request-1",
            event_id="event-1",
            actor="player",
            request_text="place this",
            route=RouteKind.DECLINE,
            authority=authority,
        )

        self.assertFalse(plan.authority.allowed)
        self.assertEqual(plan.route, RouteKind.DECLINE)

    def test_rendered_message_requires_exact_single_line_count(self) -> None:
        message = RenderedMessage(
            correlation_id="request-1",
            recipient="player",
            text="Jimbo to player: hello",
            character_count=22,
        )
        self.assertEqual(message.character_count, len(message.text))
        with self.assertRaisesRegex(ValueError, "one physical line"):
            RenderedMessage("id", "player", "line one\nline two", 17)

    def test_delivery_not_attempted_is_explicit(self) -> None:
        result = DeliveryResult.not_attempted("request-1", "offline mode")

        self.assertEqual(result.status, ResultStatus.REJECTED)
        self.assertEqual(result.attempts, 0)
        self.assertEqual(result.exact_text, "")
        self.assertEqual(result.detail, "offline mode")


class FullBotOfflineApplicationTests(unittest.TestCase):
    @patch("urllib.request.urlopen", side_effect=AssertionError("network call"))
    @patch("subprocess.run", side_effect=AssertionError("process call"))
    def test_offline_run_has_no_network_or_process_side_effect(
        self, _: object, __: object
    ) -> None:
        report = FullBotApplication.offline().run_offline()

        self.assertEqual(report.status, "offline shell ready")
        self.assertIn("public_replies: disabled", report.as_text())
        self.assertIn("live_rcon: disabled", report.as_text())

    def test_cli_requires_explicit_offline_mode(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit) as raised:
            main([])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("supports only --offline", error.getvalue())

    def test_cli_prints_redacted_offline_report(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["--offline"])

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("Jimbo full bot: offline shell ready", text)
        self.assertIn("api_key: configured path (not read)", text)
        self.assertNotIn("groq-api-key.txt", text)
        self.assertIn("placement: disabled", text)


if __name__ == "__main__":
    unittest.main()
