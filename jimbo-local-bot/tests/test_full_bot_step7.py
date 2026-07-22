"""Quota-free tests for Full Bot Step 7."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from jimbo_full_bot.config import FullBotConfig
from jimbo_full_bot.contracts import DeliveryResult, ResultStatus
from jimbo_full_bot.interactions import InvocationDecision
from jimbo_full_bot.model import (
    ConversationMemory, GroqModelGateway, ModelError, ModelRateLimitError, SYSTEM_POLICY,
)
from jimbo_full_bot.routing import MinimalConversationRouter


class FakeResponse:
    def __init__(self, value: object) -> None:
        self.value = value
    def __enter__(self) -> "FakeResponse":
        return self
    def __exit__(self, *_: object) -> None:
        return None
    def read(self, *_: object) -> bytes:
        return json.dumps(self.value).encode("utf-8")


def plan(actor: str = "Alice", text: str = "How do belts work?"):
    handoff = MinimalConversationRouter(FullBotConfig()).route(
        InvocationDecision("event-1", actor, True, text, "accepted")
    )
    assert handoff is not None
    return handoff


class ConversationMemoryTests(unittest.TestCase):
    def test_limit_and_order(self) -> None:
        memory = ConversationMemory(3)
        for number in range(4):
            memory.commit("Alice", f"q{number}", f"a{number}")
        self.assertEqual(memory.exchanges_for("alice"), (
            ("q1", "a1"), ("q2", "a2"), ("q3", "a3")
        ))

    def test_players_are_isolated_case_insensitively(self) -> None:
        memory = ConversationMemory()
        memory.commit("Alice", "red?", "advanced circuits")
        memory.commit("Bob", "blue?", "processing units")
        self.assertEqual(memory.exchanges_for("ALICE"), (("red?", "advanced circuits"),))
        self.assertEqual(memory.exchanges_for("bob"), (("blue?", "processing units"),))

    def test_new_instance_loses_history(self) -> None:
        first = ConversationMemory()
        first.commit("Alice", "q", "a")
        self.assertEqual(ConversationMemory().exchanges_for("Alice"), ())


class GroqGatewayTests(unittest.TestCase):
    def test_rate_limit_has_distinct_error_and_makes_one_call(self) -> None:
        calls = []
        def rate_limited(request, *, timeout):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 429, "limited", {}, None)
        gateway = GroqModelGateway(
            api_key="x", model="m", timeout_seconds=1, opener=rate_limited
        )
        with self.assertRaises(ModelRateLimitError):
            gateway.plan_state_needs(plan().plan)
        self.assertEqual(len(calls), 1)

    def test_payload_separates_policy_context_history_and_player_text(self) -> None:
        captured = {}
        def open_request(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"choices": [{"message": {"content": "Use splitters."}}]})
        gateway = GroqModelGateway(
            api_key="test-secret", model="test-model", timeout_seconds=12,
            opener=open_request,
        )
        handoff = plan(text="EM")
        answer = gateway.generate(
            handoff.plan,
            history=(("How much electronic circuit?", "Use three copper cable."),),
            trusted_context=handoff.context,
        )
        payload = json.loads(captured["request"].data)
        self.assertEqual(answer, "Use splitters.")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual([item["role"] for item in payload["messages"]],
                         ["system", "system", "user", "assistant", "user"])
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_POLICY)
        self.assertIn("No fresh live-game snapshot", payload["messages"][1]["content"])
        self.assertEqual(payload["messages"][-1]["content"], "EM")
        self.assertNotIn("test-secret", json.dumps(payload))
        self.assertEqual(captured["request"].headers["Authorization"], "Bearer test-secret")

    def test_missing_content_is_rejected(self) -> None:
        gateway = GroqModelGateway(
            api_key="x", model="m", timeout_seconds=1,
            opener=lambda *_args, **_kwargs: FakeResponse({"choices": []}),
        )
        with self.assertRaisesRegex(ModelError, "invalid chat response"):
            gateway.generate(plan().plan)

    def test_malformed_json_is_rejected(self) -> None:
        class BadResponse(FakeResponse):
            def read(self, *_: object) -> bytes:
                return b"not json"
        gateway = GroqModelGateway(
            api_key="x", model="m", timeout_seconds=1,
            opener=lambda *_args, **_kwargs: BadResponse({}),
        )
        with self.assertRaisesRegex(ModelError, "request failed"):
            gateway.generate(plan().plan)

    def test_timeout_is_rejected(self) -> None:
        def timeout(*_args, **_kwargs):
            raise TimeoutError("timed out")
        gateway = GroqModelGateway(api_key="x", model="m", timeout_seconds=1, opener=timeout)
        with self.assertRaisesRegex(ModelError, "request failed"):
            gateway.generate(plan().plan)

    def test_key_file_is_read_only_when_gateway_is_constructed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key.txt"
            path.write_text("existing-key\n", encoding="utf-8")
            gateway = GroqModelGateway.from_key_file(
                path, model="m", timeout_seconds=1,
                opener=lambda *_args, **_kwargs: FakeResponse(
                    {"choices": [{"message": {"content": "ok"}}]}
                ),
            )
            self.assertEqual(gateway.generate(plan().plan), "ok")
            self.assertEqual(path.read_text(encoding="utf-8"), "existing-key\n")


class CommitBoundaryTests(unittest.TestCase):
    def test_only_complete_delivery_is_committed(self) -> None:
        memory = ConversationMemory()
        request, response = "and blue?", "Processing units need red and green circuits."
        failed = DeliveryResult.not_attempted("c", "renderer or delivery rejected")
        if failed.status is ResultStatus.COMPLETE:
            memory.commit("Alice", request, failed.exact_text)
        self.assertEqual(memory.exchanges_for("Alice"), ())
        complete = DeliveryResult("c", ResultStatus.COMPLETE, response, 1,
                                  failed.completed_at)
        if complete.status is ResultStatus.COMPLETE:
            memory.commit("Alice", request, complete.exact_text)
        self.assertEqual(memory.exchanges_for("Alice"), ((request, response),))


if __name__ == "__main__":
    unittest.main()
