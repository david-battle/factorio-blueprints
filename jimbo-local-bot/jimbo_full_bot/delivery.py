"""Minimal inert chat rendering and fixed-wrapper delivery for Step 5."""

from __future__ import annotations

import hashlib
import re
import threading
import unicodedata
from datetime import UTC, datetime

from .archive import ArchiveRecord, TextEventArchive, redact_sensitive
from .contracts import DeliveryResult, RenderedMessage, ResultStatus
from .interactions import WelcomeIntent, WelcomeService
from .rcon_transport import DirectRconTransport
from .state import FlatTextStateStore


RCON_SUCCESS_MARKER = "JIMBO_FULL_REPLY_SENT"
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"\s+")
BOT_PREFIX_RE = re.compile(r"^Jimbo\s+to\s+[^:]{1,32}:\s*", re.IGNORECASE)
TRUSTED_RICH_NAME_RE = re.compile(r"^\[(?:item|planet|entity|fluid|quality)=[a-z0-9][a-z0-9-]{0,99}\]$")
OVERLONG_FALLBACK = "My reply was too long for chat. Please ask for a shorter answer."
EMPTY_FALLBACK = "I don't have a response yet."
ASCII_TRANSLATION = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2026": "...",
        "\u00a0": " ", "\u202f": " ",
    }
)


class DeliveryError(RuntimeError):
    """Raised when the fixed RCON transport cannot confirm delivery."""


class MinimalRenderer:
    def __init__(self, *, character_limit: int = 220) -> None:
        if character_limit < 80:
            raise ValueError("character_limit must be at least 80")
        self.character_limit = character_limit

    def render_reply(
        self, correlation_id: str, recipient: str, response: str,
        *, trusted_rich_text: tuple[str, ...] = (),
    ) -> RenderedMessage:
        safe_recipient = self._plain_text(recipient)[:32] or "player"
        prefix = f"Jimbo to {safe_recipient}: "
        body = BOT_PREFIX_RE.sub(
            "", self._plain_text(response, trusted_rich_text=trusted_rich_text)
        ).strip() or EMPTY_FALLBACK
        return self._render(correlation_id, safe_recipient, prefix, body)

    def render_welcome(self, intent: WelcomeIntent) -> RenderedMessage:
        recipient = self._plain_text(intent.display_name)[:32] or "player"
        return self._render(intent.event_id, recipient, "Jimbo: ", intent.text)

    def _render(
        self, correlation_id: str, recipient: str, prefix: str, body: str
    ) -> RenderedMessage:
        text = prefix + body
        if len(text) > self.character_limit:
            available = self.character_limit - len(prefix)
            shortened = body[: available + 1]
            if len(shortened) > available:
                shortened = shortened[:available].rsplit(" ", 1)[0].rstrip(" ,;:-")
            text = prefix + (shortened + "..." if len(shortened) + 3 <= available else shortened)
        if len(text) > self.character_limit or not text[len(prefix):].strip():
            text = prefix + OVERLONG_FALLBACK
        if len(text) > self.character_limit:
            raise ValueError("reply prefix leaves no room for the fallback")
        return RenderedMessage(correlation_id, recipient, text, len(text))

    @staticmethod
    def _plain_text(value: str, *, trusted_rich_text: tuple[str, ...] = ()) -> str:
        placeholders: dict[str, str] = {}
        for index, candidate in enumerate(dict.fromkeys(trusted_rich_text)):
            if TRUSTED_RICH_NAME_RE.fullmatch(candidate):
                token = f"JIMBOTRUSTEDRICHTOKEN{index}"
                value = value.replace(candidate, token)
                placeholders[token] = candidate
        # Untrusted brackets are spelled out so model-authored rich text stays
        # inert and literal values are not silently changed.
        value = CONTROL_RE.sub(" ", value)
        value = value.replace("[", " left-bracket ").replace("]", " right-bracket ")
        value = value.replace("**", "").replace("__", "").replace("`", "")
        value = value.translate(ASCII_TRANSLATION)
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        value = WHITESPACE_RE.sub(" ", value).strip()
        for token, candidate in placeholders.items():
            value = value.replace(token, candidate)
        return value


def build_print_command(message: RenderedMessage) -> str:
    if "]]" in message.text or "\n" in message.text or "\r" in message.text:
        raise DeliveryError("rendered text is not contained for a Lua long string")
    return (
        f"/silent-command game.print([[{message.text}]]);"
        f"rcon.print([[{RCON_SUCCESS_MARKER}]])"
    )


class RconDeliveryTransport:
    """Send one already rendered inert message through the fixed wrapper."""

    def __init__(
        self,
        *,
        transport: DirectRconTransport,
    ) -> None:
        self.transport = transport

    def deliver(self, message: RenderedMessage) -> DeliveryResult:
        command = build_print_command(message)
        try:
            output = self.transport.command(command)
        except Exception as error:
            raise DeliveryError(f"RCON delivery failed: {error}") from error
        if RCON_SUCCESS_MARKER not in output:
            raise DeliveryError("RCON delivery was not confirmed")
        return DeliveryResult(
            correlation_id=message.correlation_id,
            status=ResultStatus.COMPLETE,
            exact_text=message.text,
            attempts=1,
            completed_at=datetime.now(UTC),
        )


class MinimalDeliveryWorker:
    """Serialize sends, archive outcomes, and suppress confirmed duplicates."""

    def __init__(
        self,
        *,
        transport: object,
        archive: TextEventArchive,
        state: FlatTextStateStore,
        enabled: bool = False,
    ) -> None:
        self.transport = transport
        self.archive = archive
        self.state = state
        self.enabled = enabled
        self._lock = threading.Lock()

    def deliver(self, message: RenderedMessage) -> DeliveryResult:
        with self._lock:
            key = self._delivery_key(message.correlation_id)
            deliveries = self.state.load("deliveries")
            if deliveries.get(key) == "complete":
                return DeliveryResult(
                    message.correlation_id,
                    ResultStatus.COMPLETE,
                    message.text,
                    0,
                    datetime.now(UTC),
                    "already delivered",
                )
            self.archive.append(
                ArchiveRecord.now(
                    "render",
                    redact_sensitive(message.text),
                    correlation_id=message.correlation_id,
                    actor=message.recipient,
                )
            )
            if not self.enabled:
                result = DeliveryResult.not_attempted(
                    message.correlation_id, "public delivery is disabled"
                )
                self._archive_result(result, message.recipient)
                return result
            try:
                result = self.transport.deliver(message)
            except DeliveryError as error:
                result = DeliveryResult(
                    message.correlation_id,
                    ResultStatus.FAILED,
                    "",
                    1,
                    datetime.now(UTC),
                    str(error),
                )
                self._archive_result(result, message.recipient)
                return result
            deliveries[key] = "complete"
            self.state.replace("deliveries", deliveries)
            self._archive_result(result, message.recipient)
            return result

    def deliver_welcome(
        self,
        intent: WelcomeIntent,
        renderer: MinimalRenderer,
        welcomes: WelcomeService,
    ) -> DeliveryResult:
        result = self.deliver(renderer.render_welcome(intent))
        if result.status is ResultStatus.COMPLETE:
            welcomes.mark_delivered(intent)
        return result

    def _archive_result(self, result: DeliveryResult, actor: str) -> None:
        payload = (
            f"status={result.status.value};attempts={result.attempts};"
            f"text={redact_sensitive(result.exact_text)};detail={redact_sensitive(result.detail)}"
        )
        self.archive.append(
            ArchiveRecord.now(
                "delivery",
                payload,
                correlation_id=result.correlation_id,
                actor=actor,
            )
        )

    @staticmethod
    def _delivery_key(correlation_id: str) -> str:
        return "delivery." + hashlib.sha256(correlation_id.encode("utf-8")).hexdigest()
