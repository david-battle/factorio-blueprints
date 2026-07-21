"""Minimal invocation and welcome decisions for Full Bot Step 4."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode

from .contracts import EventKind, NormalizedEvent
from .state import FlatTextStateStore


LEADING_INVOCATION_RE = re.compile(
    r"^[\s,.:;!?\-]*(?:hey[\s,.:;!?\-]+)?jimbo(?!\w)[\s,.:;!?\-]*",
    re.IGNORECASE,
)
LEADING_PUNCTUATION_RE = re.compile(r"^[\s,.:;!?\-]+")
REPEATED_WHITESPACE_RE = re.compile(r"\s+")
BOT_ACTORS = frozenset({"<server>", "server", "jimbo"})


@dataclass(frozen=True, slots=True)
class InvocationDecision:
    event_id: str
    actor: str
    accepted: bool
    request_text: str
    reason: str


@dataclass(frozen=True, slots=True)
class WelcomeIntent:
    event_id: str
    player_key: str
    display_name: str
    returning: bool
    text: str


class InvocationClassifier:
    """Classify only deterministic leading invocations; never call a model."""

    def classify(self, event: NormalizedEvent) -> InvocationDecision | None:
        if event.kind is not EventKind.PUBLIC_CHAT:
            return None
        actor = event.actor or ""
        message = event.message or ""
        if actor.casefold() in BOT_ACTORS:
            return InvocationDecision(
                event.event_id, actor, False, "", "self-authored chat"
            )
        match = LEADING_INVOCATION_RE.match(message)
        if match is None:
            return InvocationDecision(
                event.event_id, actor, False, "", "no leading invocation"
            )
        request = LEADING_PUNCTUATION_RE.sub("", message[match.end() :], count=1)
        request = REPEATED_WHITESPACE_RE.sub(" ", request).strip()
        return InvocationDecision(event.event_id, actor, True, request, "accepted")


class WelcomeService:
    """Persist join classification and emit deterministic delivery intents."""

    def __init__(self, state: FlatTextStateStore) -> None:
        self.state = state

    def prepare(
        self,
        event: NormalizedEvent,
        *,
        enabled: bool,
        suppressed: bool = False,
    ) -> WelcomeIntent | None:
        if event.kind is not EventKind.PLAYER_JOIN:
            return None
        display_name = (event.actor or "").strip()
        if not display_name:
            return None
        values = self.state.load("seen_players")
        event_key = self._event_key(event.event_id)
        existing = values.get(event_key)
        if existing is not None:
            return self._pending_intent(event.event_id, existing)

        player_key = display_name.casefold()
        player_state_key = self._player_key(player_key)
        returning = player_state_key in values
        now = datetime.now(UTC).isoformat()
        previous = self._parse(values.get(player_state_key, ""))
        values[player_state_key] = urlencode(
            {
                "key": player_key,
                "display": display_name,
                "first_seen": previous.get("first_seen", now),
                "last_seen": now,
            }
        )
        if not enabled or suppressed:
            values[event_key] = urlencode(
                {
                    "status": "suppressed" if suppressed else "disabled",
                    "player_key": player_key,
                    "display": display_name,
                    "returning": str(returning).lower(),
                }
            )
            self.state.replace("seen_players", values)
            return None

        text = self._welcome_text(display_name, returning)
        values[event_key] = urlencode(
            {
                "status": "pending",
                "player_key": player_key,
                "display": display_name,
                "returning": str(returning).lower(),
                "text": text,
            }
        )
        self.state.replace("seen_players", values)
        return WelcomeIntent(event.event_id, player_key, display_name, returning, text)

    def mark_delivered(self, intent: WelcomeIntent) -> None:
        values = self.state.load("seen_players")
        event_key = self._event_key(intent.event_id)
        existing = self._parse(values.get(event_key, ""))
        if existing.get("status") == "delivered":
            return
        if existing.get("status") != "pending":
            raise ValueError("welcome intent is not pending")
        existing["status"] = "delivered"
        values[event_key] = urlencode(existing)
        self.state.replace("seen_players", values)

    def latest_display_name(self, player_name: str) -> str | None:
        values = self.state.load("seen_players")
        parsed = self._parse(values.get(self._player_key(player_name.casefold()), ""))
        return parsed.get("display")

    @staticmethod
    def _welcome_text(display_name: str, returning: bool) -> str:
        prefix = "Welcome back" if returning else "Welcome"
        return f"{prefix}, {display_name}! Begin queries with Jimbo."

    def _pending_intent(self, event_id: str, encoded: str) -> WelcomeIntent | None:
        values = self._parse(encoded)
        if values.get("status") != "pending":
            return None
        return WelcomeIntent(
            event_id=event_id,
            player_key=values["player_key"],
            display_name=values["display"],
            returning=values.get("returning") == "true",
            text=values["text"],
        )

    @staticmethod
    def _player_key(player_key: str) -> str:
        return "player." + hashlib.sha256(player_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_key(event_id: str) -> str:
        return "join." + hashlib.sha256(event_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse(encoded: str) -> dict[str, str]:
        if not encoded:
            return {}
        parsed = parse_qs(encoded, keep_blank_values=True, strict_parsing=True)
        return {key: values[0] for key, values in parsed.items() if len(values) == 1}
