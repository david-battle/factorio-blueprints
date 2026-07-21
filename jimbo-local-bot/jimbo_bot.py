"""Foreground log watcher for the Jimbo Factorio bot proof of concept."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Callable, Protocol


DEFAULT_LOG_PATH = Path(r"D:\factorio-server\server-console.log")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:1.7b"
DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
REPOSITORY_PATH = Path(__file__).resolve().parent.parent
DEFAULT_RCON_WRAPPER = REPOSITORY_PATH / "tools" / "factorio-rcon.ps1"
DEFAULT_RCON_COMMAND_PATH = REPOSITORY_PATH / "tools" / "rcon-command.txt"
DEFAULT_TRANSCRIPT_PATH = Path(__file__).resolve().parent / "runtime" / "transcript.jsonl"
DEFAULT_GROQ_KEY_PATH = Path(__file__).resolve().parent / "runtime" / "groq-api-key.txt"
POWERSHELL_PATH = Path(
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
)
RCON_SUCCESS_MARKER = "JIMBO_REPLY_SENT"
MAX_CHAT_LENGTH = 240
SYSTEM_PROMPT = (
    "You are Jimbo, a concise and friendly chatbot on a Factorio multiplayer "
    "server. Carefully respect facts stated by the player and never recommend "
    "building something they say is already complete. Useful goals after basic "
    "iron and copper plate automation include green circuits, a small mall, and "
    "red or green science. Factorio players use 'green circuits' for electronic "
    "circuits, 'red circuits' for advanced circuits, and 'blue circuits' for "
    "processing units. When asked for a recipe, state only that item's "
    "direct recipe ingredients unless the player explicitly asks for subrecipe "
    "or raw-resource totals. Reply directly in one short message. Do not "
    "describe your reasoning and do not use a thinking block."
)
CHAT_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[CHAT\] (?P<player>[^:]+): (?P<message>.*)$"
)
LEADING_JIMBO_RE = re.compile(
    r"^[\s,.:;!?\-]*(?:hey[\s,.:;!?\-]+)?jimbo(?!\w)[\s,.:;!?\-]*",
    re.IGNORECASE,
)
LEADING_CHAT_PUNCTUATION_RE = re.compile(r"^[\s,.:;!?\-]+")
REPEATED_WHITESPACE_RE = re.compile(r"\s+")
CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class ChatMessage:
    timestamp: str
    player: str
    message: str


@dataclass(frozen=True)
class JimboRequest:
    timestamp: str
    player: str
    original_message: str
    request: str


@dataclass(frozen=True)
class Exchange:
    user: str
    assistant: str


class ConversationMemory:
    def __init__(self, *, max_exchanges: int = 3) -> None:
        if max_exchanges < 1:
            raise ValueError("max_exchanges must be at least one")
        self.max_exchanges = max_exchanges
        self._by_player: dict[str, deque[Exchange]] = {}

    def messages_for(self, player: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for exchange in self._by_player.get(player.casefold(), ()):
            messages.append({"role": "user", "content": exchange.user})
            messages.append({"role": "assistant", "content": exchange.assistant})
        return messages

    def remember(self, player: str, user: str, assistant: str) -> None:
        player_key = player.casefold()
        exchanges = self._by_player.setdefault(player_key, deque())
        exchanges.append(Exchange(user=user, assistant=assistant))
        while len(exchanges) > self.max_exchanges:
            exchanges.popleft()


class RequestGate:
    """Bound pending work and apply a small per-player completion cooldown."""

    def __init__(
        self,
        *,
        cooldown_seconds: float = 5.0,
        max_queue: int = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        if max_queue < 1:
            raise ValueError("max_queue must be at least one")
        self.cooldown_seconds = cooldown_seconds
        self.max_queue = max_queue
        self.clock = clock
        self._queue: deque[JimboRequest] = deque()
        self._pending_players: set[str] = set()
        self._next_allowed: dict[str, float] = {}

    def offer(self, request: JimboRequest) -> str | None:
        player_key = request.player.casefold()
        now = self.clock()
        if player_key in self._pending_players:
            return "player already has a pending request"
        if now < self._next_allowed.get(player_key, 0.0):
            return "player cooldown is active"
        if len(self._queue) >= self.max_queue:
            return "global queue is full"
        self._queue.append(request)
        self._pending_players.add(player_key)
        return None

    def pop_next(self) -> JimboRequest | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def complete(self, request: JimboRequest) -> None:
        player_key = request.player.casefold()
        self._pending_players.discard(player_key)
        self._next_allowed[player_key] = self.clock() + self.cooldown_seconds


class Transcript:
    """Append small structured runtime events and make each one immediately visible."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, event: str, **fields: object) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "event": event,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as transcript:
            transcript.write(json.dumps(entry, ensure_ascii=False) + "\n")
            transcript.flush()


class ModelError(RuntimeError):
    """Raised when a configured model provider cannot return a valid answer."""


class ModelClient(Protocol):
    provider: str
    model: str
    last_provider: str
    last_model: str

    def generate(
        self, prompt: str, *, history: list[dict[str, str]] | None = None
    ) -> str: ...


class OllamaError(ModelError):
    """Raised when local Ollama generation fails or returns invalid data."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self.provider = "ollama"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_provider = self.provider
        self.last_model = self.model
        self.timeout = timeout

    def generate(
        self, prompt: str, *, history: list[dict[str, str]] | None = None
    ) -> str:
        effective_prompt = prompt.strip() or "Say hello and ask what I need."
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": "2m",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *(history or []),
                {"role": "user", "content": effective_prompt},
            ],
            "options": {
                "num_ctx": 2048,
                "num_predict": 80,
                "temperature": 0.7,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise OllamaError(f"Ollama request failed: {error}") from error

        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned no response content")
        self.last_provider = self.provider
        self.last_model = self.model
        return content.strip()


class GroqError(ModelError):
    """Raised when Groq cannot return a valid hosted-model answer."""


class GroqClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_GROQ_URL,
        model: str = DEFAULT_GROQ_MODEL,
        timeout: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise GroqError("Groq API key is empty")
        self.provider = "groq"
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_provider = self.provider
        self.last_model = self.model
        self.timeout = timeout

    @classmethod
    def from_key_file(
        cls,
        key_path: Path,
        **kwargs: object,
    ) -> GroqClient:
        try:
            api_key = key_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise GroqError(f"Groq API key file is unavailable: {key_path}") from error
        return cls(api_key=api_key, **kwargs)

    def generate(
        self, prompt: str, *, history: list[dict[str, str]] | None = None
    ) -> str:
        effective_prompt = prompt.strip() or "Say hello and ask what I need."
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *(history or []),
                {"role": "user", "content": effective_prompt},
            ],
            "temperature": 0.3,
            "max_completion_tokens": 256,
            "include_reasoning": False,
            "reasoning_effort": "low",
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "groq-python/1.0 jimbo-factorio-bot/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry_after = error.headers.get("Retry-After", "unknown")
                raise GroqError(
                    f"Groq rate limit reached; retry after {retry_after} seconds"
                ) from error
            detail = ""
            try:
                raw_error = error.read().decode("utf-8", errors="replace").strip()
                try:
                    error_body = json.loads(raw_error)
                    candidate = error_body.get("error", {}).get("message", "")
                    if isinstance(candidate, str):
                        detail = candidate.strip()
                except json.JSONDecodeError:
                    detail = REPEATED_WHITESPACE_RE.sub(" ", raw_error)[:300]
            except (AttributeError, OSError):
                pass
            suffix = f": {detail}" if detail else ""
            raise GroqError(f"Groq HTTP error {error.code}{suffix}") from error
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise GroqError(f"Groq request failed: {error}") from error

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise GroqError("Groq returned an invalid chat response") from error
        if not isinstance(content, str) or not content.strip():
            raise GroqError("Groq returned no response content")
        self.last_provider = self.provider
        self.last_model = self.model
        return content.strip()


class FallbackClient:
    def __init__(self, primary: ModelClient, fallback: ModelClient) -> None:
        self.primary = primary
        self.fallback = fallback
        self.provider = primary.provider
        self.model = primary.model
        self.last_provider = primary.provider
        self.last_model = primary.model

    def generate(
        self, prompt: str, *, history: list[dict[str, str]] | None = None
    ) -> str:
        try:
            response = self.primary.generate(prompt, history=history)
            selected = self.primary
        except ModelError:
            response = self.fallback.generate(prompt, history=history)
            selected = self.fallback
        self.last_provider = selected.last_provider
        self.last_model = selected.last_model
        return response


class RconError(RuntimeError):
    """Raised when a fixed public-chat RCON reply fails."""


def sanitize_chat_text(text: str) -> str:
    """Reduce generated or player text to safe, single-line Factorio chat."""

    text = CONTROL_CHARACTER_RE.sub(" ", text)
    text = text.replace("[", "").replace("]", "")
    return REPEATED_WHITESPACE_RE.sub(" ", text).strip()


def format_public_reply(player: str, response: str) -> str:
    safe_player = sanitize_chat_text(player)[:32] or "player"
    prefix = f"Jimbo to {safe_player}: "
    safe_response = sanitize_chat_text(response)
    available = MAX_CHAT_LENGTH - len(prefix)
    if available < 1:
        raise RconError("Reply prefix exceeds the chat length limit")
    if len(safe_response) > available:
        safe_response = safe_response[: max(1, available - 1)].rstrip() + "…"
    return prefix + (safe_response or "I don't have a response yet.")


def build_public_reply_command(player: str, response: str) -> tuple[str, str]:
    message = format_public_reply(player, response)
    command = (
        f"/silent-command game.print([[{message}]]);"
        f"rcon.print([[{RCON_SUCCESS_MARKER}]])"
    )
    return message, command


class RconClient:
    def __init__(
        self,
        *,
        wrapper_path: Path = DEFAULT_RCON_WRAPPER,
        command_path: Path = DEFAULT_RCON_COMMAND_PATH,
        timeout: float = 15.0,
    ) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout = timeout

    def send_public_reply(self, player: str, response: str) -> str:
        message, command = build_public_reply_command(player, response)
        original_command = self.command_path.read_bytes()
        try:
            self.command_path.write_text(command + "\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    str(POWERSHELL_PATH),
                    "-NoProfile",
                    "-File",
                    str(self.wrapper_path),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RconError(f"RCON invocation failed: {error}") from error
        finally:
            self.command_path.write_bytes(original_command)

        output = (completed.stdout + "\n" + completed.stderr).strip()
        if completed.returncode != 0 or RCON_SUCCESS_MARKER not in output:
            raise RconError(
                f"RCON reply was not confirmed (exit {completed.returncode}): {output}"
            )
        return message


def parse_chat_line(line: str) -> ChatMessage | None:
    """Parse one Factorio public-chat record, ignoring other log records."""

    match = CHAT_LINE_RE.fullmatch(line.rstrip("\r\n"))
    if match is None:
        return None
    return ChatMessage(
        timestamp=match.group("timestamp"),
        player=match.group("player").strip(),
        message=match.group("message"),
    )


def extract_jimbo_request(message: ChatMessage) -> JimboRequest | None:
    """Return a cleaned request when the complete word 'jimbo' is present."""

    if LEADING_JIMBO_RE.search(message.message) is None:
        return None

    request = LEADING_JIMBO_RE.sub("", message.message, count=1)
    request = LEADING_CHAT_PUNCTUATION_RE.sub("", request)
    request = REPEATED_WHITESPACE_RE.sub(" ", request).strip()
    return JimboRequest(
        timestamp=message.timestamp,
        player=message.player,
        original_message=message.message,
        request=request,
    )


class LogFollower:
    """Read complete lines appended after this follower opens a log file."""

    def __init__(self, path: Path, *, start_at_end: bool = True) -> None:
        self.path = path
        self.start_at_end = start_at_end
        self._file: BinaryIO | None = None
        self._buffer = b""

    def __enter__(self) -> LogFollower:
        self._file = self.path.open("rb")
        if self.start_at_end:
            self._file.seek(0, 2)
        return self

    def __exit__(self, *_: object) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def read_new_lines(self) -> list[str]:
        if self._file is None:
            raise RuntimeError("LogFollower must be used as a context manager")

        current_size = self.path.stat().st_size
        if current_size < self._file.tell():
            self._file.seek(0)
            self._buffer = b""

        chunk = self._file.read()
        if not chunk:
            return []

        parts = (self._buffer + chunk).splitlines(keepends=True)
        self._buffer = b""
        if parts and not parts[-1].endswith((b"\n", b"\r")):
            self._buffer = parts.pop()

        return [part.rstrip(b"\r\n").decode("utf-8", errors="replace") for part in parts]


def find_jimbo_requests(lines: list[str]) -> list[JimboRequest]:
    requests: list[JimboRequest] = []
    for line in lines:
        chat = parse_chat_line(line)
        if chat is None:
            continue
        if chat.player.casefold() in {"<server>", "server"}:
            continue
        request = extract_jimbo_request(chat)
        if request is not None:
            requests.append(request)
    return requests


def generate_with_memory(
    client: ModelClient,
    memory: ConversationMemory,
    *,
    player: str,
    request: str,
) -> str:
    history = memory.messages_for(player)
    response = client.generate(request, history=history)
    memory.remember(player, request, response)
    return response


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch new Factorio chat and print requests addressed to Jimbo."
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--poll-interval", type=float, default=0.25)
    parser.add_argument(
        "--prompt",
        action="append",
        help="Generate a response and exit; repeat for a contextual smoke conversation.",
    )
    parser.add_argument(
        "--provider", choices=("ollama", "groq"), default="ollama"
    )
    parser.add_argument(
        "--fallback-provider", choices=("none", "ollama"), default="none"
    )
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--groq-url", default=DEFAULT_GROQ_URL)
    parser.add_argument("--groq-key-file", type=Path, default=DEFAULT_GROQ_KEY_PATH)
    parser.add_argument(
        "--model",
        help="Override the selected provider's default model identifier.",
    )
    parser.add_argument("--model-timeout", type=float, default=60.0)
    parser.add_argument("--cooldown", type=float, default=5.0)
    parser.add_argument("--max-queue", type=int, default=5)
    parser.add_argument("--transcript", type=Path, default=DEFAULT_TRANSCRIPT_PATH)
    parser.add_argument(
        "--send-to",
        help="With --prompt, send the generated response publicly to this player.",
    )
    return parser


def build_model_client(args: argparse.Namespace) -> ModelClient:
    if args.provider == "ollama":
        primary: ModelClient = OllamaClient(
            base_url=args.ollama_url,
            model=args.model or DEFAULT_MODEL,
            timeout=args.model_timeout,
        )
    else:
        primary = GroqClient.from_key_file(
            args.groq_key_file,
            base_url=args.groq_url,
            model=args.model or DEFAULT_GROQ_MODEL,
            timeout=args.model_timeout,
        )

    if args.fallback_provider == "ollama" and args.provider != "ollama":
        fallback = OllamaClient(
            base_url=args.ollama_url,
            model=DEFAULT_MODEL,
            timeout=args.model_timeout,
        )
        return FallbackClient(primary, fallback)
    return primary


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    args = build_argument_parser().parse_args()
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be greater than zero")
    if args.model_timeout <= 0:
        raise SystemExit("--model-timeout must be greater than zero")
    if args.cooldown < 0:
        raise SystemExit("--cooldown cannot be negative")
    if args.max_queue < 1:
        raise SystemExit("--max-queue must be at least one")

    try:
        client = build_model_client(args)
    except ModelError as error:
        raise SystemExit(str(error)) from error
    transcript = Transcript(args.transcript)
    transcript.record(
        "startup",
        mode="prompt" if args.prompt is not None else "watch",
        provider=client.provider,
        model=client.model,
    )
    if args.prompt is not None:
        if args.send_to and len(args.prompt) != 1:
            raise SystemExit("--send-to requires exactly one --prompt")
        memory = ConversationMemory(max_exchanges=3)
        try:
            for prompt in args.prompt:
                history_exchanges = len(memory.messages_for("cli")) // 2
                transcript.record("request_accepted", source="cli", request=prompt)
                response = generate_with_memory(
                    client, memory, player="cli", request=prompt
                )
                transcript.record(
                    "model_response",
                    source="cli",
                    provider=client.last_provider,
                    model=client.last_model,
                    history_exchanges=history_exchanges,
                    response=response,
                )
                print(response, flush=True)
            if args.send_to:
                public_message = format_public_reply(args.send_to, response)
                transcript.record(
                    "public_message", player=args.send_to, message=public_message
                )
                sent = RconClient().send_public_reply(args.send_to, response)
                transcript.record(
                    "rcon_confirmed", player=args.send_to, message=sent
                )
                print(f"RCON confirmed: {sent}", flush=True)
        except ModelError as error:
            transcript.record(
                "model_error",
                source="cli",
                provider=client.provider,
                model=client.model,
                error=str(error),
            )
            print(f"Bot error: {error}", file=sys.stderr, flush=True)
            transcript.record("shutdown", reason="error")
            return 1
        except RconError as error:
            transcript.record("rcon_error", player=args.send_to, error=str(error))
            print(f"Bot error: {error}", file=sys.stderr, flush=True)
            transcript.record("shutdown", reason="error")
            return 1
        transcript.record("shutdown", reason="clean")
        return 0
    if args.send_to:
        raise SystemExit("--send-to requires --prompt")

    if not args.log.is_file():
        raise SystemExit(f"Factorio server log does not exist: {args.log}")

    print(f"Watching new chat in {args.log} (press Ctrl+C to stop)", flush=True)
    gate = RequestGate(
        cooldown_seconds=args.cooldown,
        max_queue=args.max_queue,
    )
    memory = ConversationMemory(max_exchanges=3)
    try:
        with LogFollower(args.log, start_at_end=True) as follower:
            while True:
                for request in find_jimbo_requests(follower.read_new_lines()):
                    rejection = gate.offer(request)
                    if rejection is not None:
                        transcript.record(
                            "request_ignored",
                            player=request.player,
                            request=request.request,
                            reason=rejection,
                        )
                        print(
                            f"Ignored {request.player}: {rejection}",
                            flush=True,
                        )
                    else:
                        transcript.record(
                            "request_accepted",
                            player=request.player,
                            request=request.request,
                        )

                while (request := gate.pop_next()) is not None:
                    cleaned = request.request or "<empty request>"
                    print(
                        f"[{request.timestamp}] {request.player} -> {cleaned}",
                        flush=True,
                    )
                    try:
                        history_exchanges = len(memory.messages_for(request.player)) // 2
                        response = generate_with_memory(
                            client,
                            memory,
                            player=request.player,
                            request=request.request,
                        )
                        transcript.record(
                            "model_response",
                            player=request.player,
                            provider=client.last_provider,
                            model=client.last_model,
                            history_exchanges=history_exchanges,
                            response=response,
                        )
                        print(f"Jimbo -> {request.player}: {response}", flush=True)
                    except ModelError as error:
                        transcript.record(
                            "model_error",
                            player=request.player,
                            provider=client.provider,
                            model=client.model,
                            error=str(error),
                        )
                        print(f"Bot error: {error}", file=sys.stderr, flush=True)
                        gate.complete(request)
                        continue

                    try:
                        public_message = format_public_reply(
                            request.player, response
                        )
                        transcript.record(
                            "public_message",
                            player=request.player,
                            message=public_message,
                        )
                        sent = RconClient().send_public_reply(
                            request.player, response
                        )
                        transcript.record(
                            "rcon_confirmed",
                            player=request.player,
                            message=sent,
                        )
                        print(f"RCON confirmed: {sent}", flush=True)
                    except RconError as error:
                        transcript.record(
                            "rcon_error",
                            player=request.player,
                            error=str(error),
                        )
                        print(f"Bot error: {error}", file=sys.stderr, flush=True)
                    finally:
                        gate.complete(request)

                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        transcript.record("shutdown", reason="interrupted")
    else:
        transcript.record("shutdown", reason="clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
