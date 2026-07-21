from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from collections import deque
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jimbo_bot import (
    ConversationMemory,
    FallbackClient,
    GroqClient,
    GroqError,
    LogFollower,
    ModelError,
    OllamaClient,
    OllamaError,
    RequestGate,
    RconClient,
    RconError,
    Transcript,
    build_public_reply_command,
    extract_jimbo_request,
    find_jimbo_requests,
    format_public_reply,
    generate_with_memory,
    parse_chat_line,
    sanitize_chat_text,
)


class ChatParsingTests(unittest.TestCase):
    def test_parses_public_chat(self) -> None:
        message = parse_chat_line(
            "2026-07-21 09:09:36 [CHAT] itsnotyouitsme: Jimbo who is online?"
        )

        self.assertIsNotNone(message)
        assert message is not None
        self.assertEqual(message.player, "itsnotyouitsme")
        self.assertEqual(message.message, "Jimbo who is online?")

    def test_ignores_non_chat_and_malformed_records(self) -> None:
        self.assertIsNone(
            parse_chat_line("2026-07-21 08:58:49 [JOIN] somebody joined the game")
        )
        self.assertIsNone(parse_chat_line("not a Factorio record"))

    def test_matches_complete_word_case_insensitively(self) -> None:
        message = parse_chat_line(
            "2026-07-21 10:00:00 [CHAT] player: hey JIMBO, check power"
        )
        assert message is not None

        request = extract_jimbo_request(message)

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.request, "check power")

    def test_does_not_match_jimbob(self) -> None:
        message = parse_chat_line(
            "2026-07-21 10:00:00 [CHAT] player: jimbob check power"
        )
        assert message is not None
        self.assertIsNone(extract_jimbo_request(message))

    def test_empty_request_is_preserved_as_empty(self) -> None:
        message = parse_chat_line(
            "2026-07-21 10:00:00 [CHAT] player: Jimbo!!!"
        )
        assert message is not None
        request = extract_jimbo_request(message)
        assert request is not None
        self.assertEqual(request.request, "")

    def test_later_mention_does_not_trigger(self) -> None:
        message = parse_chat_line(
            "2026-07-21 10:00:00 [CHAT] player: Start with Jimbo and it replies"
        )
        assert message is not None
        self.assertIsNone(extract_jimbo_request(message))

    def test_accepts_leading_punctuation_and_hey_jimbo(self) -> None:
        message = parse_chat_line(
            "2026-07-21 10:00:00 [CHAT] player: ... Hey, Jimbo: check power"
        )
        assert message is not None
        request = extract_jimbo_request(message)
        assert request is not None
        self.assertEqual(request.request, "check power")

    def test_server_authored_jimbo_message_is_ignored(self) -> None:
        lines = [
            "2026-07-21 10:00:00 [CHAT] <server>: Jimbo to player: hello",
            "2026-07-21 10:00:01 [CHAT] player: Jimbo hello",
        ]

        requests = find_jimbo_requests(lines)

        self.assertEqual([request.player for request in requests], ["player"])


class LogFollowerTests(unittest.TestCase):
    def test_starts_at_end_and_returns_only_new_complete_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server-console.log"
            path.write_text(
                "2026-07-21 09:00:00 [CHAT] old: Jimbo old message\n",
                encoding="utf-8",
            )

            with LogFollower(path, start_at_end=True) as follower:
                self.assertEqual(follower.read_new_lines(), [])
                with path.open("ab") as log:
                    log.write(b"2026-07-21 10:00:00 [CHAT] new: Jimbo new")
                    log.flush()
                    self.assertEqual(follower.read_new_lines(), [])
                    log.write(b" message\n2026-07-21 10:00:01 [JOIN] new joined\n")
                    log.flush()

                self.assertEqual(
                    follower.read_new_lines(),
                    [
                        "2026-07-21 10:00:00 [CHAT] new: Jimbo new message",
                        "2026-07-21 10:00:01 [JOIN] new joined",
                    ],
                )


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class OllamaClientTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_sends_bounded_non_thinking_request(self, urlopen: object) -> None:
        urlopen.return_value = FakeResponse(
            b'{"message":{"role":"assistant","content":"Build green science next."}}'
        )
        client = OllamaClient(timeout=12.0)

        response = client.generate("What should we build next?")

        self.assertEqual(response, "Build green science next.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_ctx"], 2048)
        self.assertEqual(payload["options"]["num_predict"], 80)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 12.0)

    @patch("urllib.request.urlopen")
    def test_empty_request_gets_a_small_fallback_prompt(self, urlopen: object) -> None:
        urlopen.return_value = FakeResponse(
            b'{"message":{"role":"assistant","content":"Hi! What do you need?"}}'
        )

        OllamaClient().generate("")

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            payload["messages"][-1]["content"], "Say hello and ask what I need."
        )

    @patch("urllib.request.urlopen")
    def test_rejects_missing_response_content(self, urlopen: object) -> None:
        urlopen.return_value = FakeResponse(b'{"message":{"role":"assistant"}}')

        with self.assertRaises(OllamaError):
            OllamaClient().generate("hello")


class GroqClientTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_sends_authenticated_bounded_chat_request(self, urlopen: object) -> None:
        urlopen.return_value = FakeResponse(
            b'{"choices":[{"message":{"role":"assistant","content":"Use iron plates and copper cable."}}]}'
        )
        client = GroqClient(api_key="secret-key", timeout=9.0)

        history = [
            {"role": "user", "content": "What about red circuits?"},
            {"role": "assistant", "content": "They are advanced circuits."},
        ]
        response = client.generate(
            "And blue?",
            history=history,
        )

        self.assertEqual(response, "Use iron plates and copper cable.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            request.full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIn("groq-python", request.get_header("User-agent"))
        self.assertEqual(payload["model"], "openai/gpt-oss-120b")
        self.assertEqual(payload["messages"][1:3], history)
        self.assertEqual(payload["messages"][-1]["content"], "And blue?")
        self.assertEqual(payload["max_completion_tokens"], 256)
        self.assertFalse(payload["include_reasoning"])
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 9.0)

    def test_loads_key_from_ignored_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "groq-api-key.txt"
            key_path.write_text("secret-key\n", encoding="utf-8")

            client = GroqClient.from_key_file(key_path)

            self.assertEqual(client.api_key, "secret-key")

    def test_missing_key_file_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GroqError, "key file is unavailable"):
                GroqClient.from_key_file(Path(directory) / "missing.txt")

    @patch("urllib.request.urlopen")
    def test_reports_rate_limit_retry_time(self, urlopen: object) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            429,
            "Too Many Requests",
            {"Retry-After": "3"},
            None,
        )

        with self.assertRaisesRegex(GroqError, "retry after 3 seconds"):
            GroqClient(api_key="secret-key").generate("hello")

    @patch("urllib.request.urlopen")
    def test_reports_safe_http_error_detail(self, urlopen: object) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            403,
            "Forbidden",
            {},
            FakeResponse(b'{"error":{"message":"Model access is disabled"}}'),
        )

        with self.assertRaisesRegex(GroqError, "Model access is disabled"):
            GroqClient(api_key="secret-key").generate("hello")

    @patch("urllib.request.urlopen")
    def test_reports_network_timeout(self, urlopen: object) -> None:
        urlopen.side_effect = TimeoutError("timed out")

        with self.assertRaisesRegex(GroqError, "timed out"):
            GroqClient(api_key="secret-key").generate("hello")


class StubModelClient:
    def __init__(self, provider: str, response: str = "", fail: bool = False) -> None:
        self.provider = provider
        self.model = f"{provider}-model"
        self.last_provider = provider
        self.last_model = self.model
        self.response = response
        self.fail = fail

    def generate(
        self, _: str, *, history: list[dict[str, str]] | None = None
    ) -> str:
        if self.fail:
            raise ModelError(f"{self.provider} failed")
        return self.response


class FallbackClientTests(unittest.TestCase):
    def test_uses_primary_when_available(self) -> None:
        client = FallbackClient(
            StubModelClient("groq", response="hosted"),
            StubModelClient("ollama", response="local"),
        )

        self.assertEqual(client.generate("hello"), "hosted")
        self.assertEqual(client.last_provider, "groq")

    def test_uses_local_fallback_after_provider_error(self) -> None:
        client = FallbackClient(
            StubModelClient("groq", fail=True),
            StubModelClient("ollama", response="local"),
        )

        self.assertEqual(client.generate("hello"), "local")
        self.assertEqual(client.last_provider, "ollama")


class RconReplyTests(unittest.TestCase):
    def test_sanitizes_controls_formatting_and_whitespace(self) -> None:
        self.assertEqual(
            sanitize_chat_text("hello\n[color=red]  world\t"),
            "hello color=red world",
        )

    def test_formats_and_limits_public_reply(self) -> None:
        message = format_public_reply("player[name]", "x" * 400)

        self.assertTrue(message.startswith("Jimbo to playername: "))
        self.assertLessEqual(len(message), 240)
        self.assertTrue(message.endswith("…"))

    def test_command_has_only_fixed_lua_and_safe_long_string(self) -> None:
        message, command = build_public_reply_command(
            "player]", "hi ]] /command\nsecond line"
        )

        self.assertEqual(message, "Jimbo to player: hi /command second line")
        self.assertEqual(
            command,
            "/silent-command game.print([[Jimbo to player: hi /command second line]]);"
            "rcon.print([[JIMBO_REPLY_SENT]])",
        )

    @patch("subprocess.run")
    def test_rcon_uses_wrapper_and_restores_command_file(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command_path = Path(directory) / "rcon-command.txt"
            command_path.write_text("/players\n", encoding="utf-8")
            original_command = command_path.read_bytes()

            def confirmed(*_: object, **__: object) -> CompletedProcess[str]:
                command = command_path.read_text(encoding="utf-8")
                self.assertIn("game.print([[Jimbo to player: hello]])", command)
                return CompletedProcess([], 0, "JIMBO_REPLY_SENT", "")

            run.side_effect = confirmed
            sent = RconClient(
                wrapper_path=Path("fixed-wrapper.ps1"),
                command_path=command_path,
            ).send_public_reply("player", "hello")

            self.assertEqual(sent, "Jimbo to player: hello")
            self.assertEqual(command_path.read_bytes(), original_command)

    @patch("subprocess.run")
    def test_rcon_requires_confirmation_marker(self, run: object) -> None:
        run.return_value = CompletedProcess([], 0, "no confirmation", "")
        with tempfile.TemporaryDirectory() as directory:
            command_path = Path(directory) / "rcon-command.txt"
            command_path.write_text("/players\n", encoding="utf-8")

            with self.assertRaises(RconError):
                RconClient(
                    wrapper_path=Path("fixed-wrapper.ps1"),
                    command_path=command_path,
                ).send_public_reply("player", "hello")


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_request(player: str, request: str = "hello") -> object:
    message = parse_chat_line(
        f"2026-07-21 10:00:00 [CHAT] {player}: Jimbo {request}"
    )
    assert message is not None
    result = extract_jimbo_request(message)
    assert result is not None
    return result


class RequestGateTests(unittest.TestCase):
    def test_allows_only_one_pending_request_per_player(self) -> None:
        gate = RequestGate(cooldown_seconds=5, max_queue=5)

        self.assertIsNone(gate.offer(make_request("player", "one")))
        self.assertEqual(
            gate.offer(make_request("PLAYER", "two")),
            "player already has a pending request",
        )

    def test_applies_cooldown_after_completion(self) -> None:
        clock = FakeClock()
        gate = RequestGate(cooldown_seconds=5, max_queue=5, clock=clock)
        first = make_request("player", "one")
        self.assertIsNone(gate.offer(first))
        self.assertEqual(gate.pop_next(), first)
        gate.complete(first)

        self.assertEqual(
            gate.offer(make_request("player", "two")),
            "player cooldown is active",
        )
        clock.now += 5
        self.assertIsNone(gate.offer(make_request("player", "three")))

    def test_bounds_global_queue(self) -> None:
        gate = RequestGate(cooldown_seconds=0, max_queue=2)

        self.assertIsNone(gate.offer(make_request("one")))
        self.assertIsNone(gate.offer(make_request("two")))
        self.assertEqual(
            gate.offer(make_request("three")), "global queue is full"
        )


class RecordingModelClient(StubModelClient):
    def __init__(self, responses: list[str], *, fail: bool = False) -> None:
        super().__init__("recording", fail=fail)
        self.responses = deque(responses)
        self.histories: list[list[dict[str, str]]] = []

    def generate(
        self, _: str, *, history: list[dict[str, str]] | None = None
    ) -> str:
        self.histories.append(list(history or []))
        if self.fail:
            raise ModelError("recording failed")
        return self.responses.popleft()


class ConversationMemoryTests(unittest.TestCase):
    def test_follow_up_uses_structured_history_in_order(self) -> None:
        memory = ConversationMemory(max_exchanges=3)
        client = RecordingModelClient(["red answer", "blue answer"])

        generate_with_memory(
            client, memory, player="player", request="What about red circuits?"
        )
        generate_with_memory(
            client, memory, player="player", request="And blue?"
        )

        self.assertEqual(client.histories[0], [])
        self.assertEqual(
            client.histories[1],
            [
                {"role": "user", "content": "What about red circuits?"},
                {"role": "assistant", "content": "red answer"},
            ],
        )

    def test_keeps_only_three_completed_exchanges(self) -> None:
        memory = ConversationMemory(max_exchanges=3)
        for index in range(4):
            memory.remember("player", f"user {index}", f"assistant {index}")

        messages = memory.messages_for("player")

        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["content"], "user 1")
        self.assertEqual(messages[-1]["content"], "assistant 3")

    def test_isolates_players_case_insensitively(self) -> None:
        memory = ConversationMemory(max_exchanges=3)
        memory.remember("Alice", "alice question", "alice answer")
        memory.remember("Bob", "bob question", "bob answer")

        self.assertEqual(
            memory.messages_for("ALICE"),
            [
                {"role": "user", "content": "alice question"},
                {"role": "assistant", "content": "alice answer"},
            ],
        )
        self.assertNotIn("bob question", str(memory.messages_for("Alice")))

    def test_failed_generation_is_not_remembered(self) -> None:
        memory = ConversationMemory(max_exchanges=3)
        client = RecordingModelClient([], fail=True)

        with self.assertRaises(ModelError):
            generate_with_memory(
                client, memory, player="player", request="failed request"
            )

        self.assertEqual(memory.messages_for("player"), [])


class TranscriptTests(unittest.TestCase):
    def test_writes_utf8_json_line_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime" / "transcript.jsonl"
            transcript = Transcript(path)

            transcript.record(
                "model_response", player="Flürki", response="copper ✓"
            )

            raw = path.read_bytes()
            self.assertIn("Flürki".encode("utf-8"), raw)
            self.assertIn("copper ✓".encode("utf-8"), raw)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["event"], "model_response")
            self.assertEqual(event["player"], "Flürki")
            self.assertIn("timestamp", event)

    def test_only_explicit_events_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.jsonl"
            transcript = Transcript(path)
            unrelated = "ordinary unrelated server chat"

            transcript.record("startup", mode="watch", model="qwen3:1.7b")

            contents = path.read_text(encoding="utf-8")
            self.assertNotIn(unrelated, contents)
            self.assertNotIn("password", contents.casefold())


if __name__ == "__main__":
    unittest.main()
