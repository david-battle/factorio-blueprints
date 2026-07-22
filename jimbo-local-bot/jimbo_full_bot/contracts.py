"""Typed data contracts shared by full-bot components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping


STATE_TOOL_NAMES = (
    "get_connected_players",
    "get_current_research",
    "get_game_time",
    "get_available_surfaces",
)


class EventKind(StrEnum):
    PUBLIC_CHAT = "public_chat"
    PLAYER_JOIN = "player_join"
    PLAYER_LEAVE = "player_leave"
    DIAGNOSTIC = "diagnostic"


class RouteKind(StrEnum):
    DIRECT_RUNTIME_FACT = "direct_runtime_fact"
    DIRECT_ARCHIVE_QUERY = "direct_archive_query"
    DIRECT_LIVE_QUERY = "direct_live_query"
    CALCULATION = "calculation"
    INVESTIGATION = "investigation"
    CONVERSATION = "conversation"
    PREFERENCE_COMMAND = "preference_command"
    GHOST_DESIGN = "ghost_design"
    GHOST_PLACE = "ghost_place"
    DECLINE = "decline"


class ResultStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    STALE = "stale"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    FAILED = "failed"


class ErrorCategory(StrEnum):
    INVALID_INPUT = "invalid_input"
    POLICY = "policy"
    PROVIDER = "provider"
    RCON = "rcon"
    RENDERER = "renderer"
    DELIVERY = "delivery"
    STORAGE = "storage"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    event_id: str
    kind: EventKind
    occurred_at: datetime
    source_instance: str
    byte_start: int
    byte_end: int
    raw_text: str
    actor: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id cannot be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.byte_start < 0 or self.byte_end < self.byte_start:
            raise ValueError("event byte range is invalid")

    def to_data(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "occurred_at": self.occurred_at.isoformat(),
            "source_instance": self.source_instance,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "raw_text": self.raw_text,
            "actor": self.actor,
            "message": self.message,
        }

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> NormalizedEvent:
        return cls(
            event_id=_required_str(data, "event_id"),
            kind=EventKind(_required_str(data, "kind")),
            occurred_at=datetime.fromisoformat(_required_str(data, "occurred_at")),
            source_instance=_required_str(data, "source_instance"),
            byte_start=_required_int(data, "byte_start"),
            byte_end=_required_int(data, "byte_end"),
            raw_text=_required_str(data, "raw_text", allow_empty=True),
            actor=_optional_str(data, "actor"),
            message=_optional_str(data, "message"),
        )


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    actor: str
    is_management: bool
    allowed: bool
    capability: str
    reason: str


@dataclass(frozen=True, slots=True)
class RequestPlan:
    correlation_id: str
    event_id: str
    actor: str
    request_text: str
    route: RouteKind
    authority: AuthorityDecision
    allowed_tool_families: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StateNeedsPlan:
    """Provider-neutral selection of facts, adapters, or one free-form RCON command."""

    tools: tuple[str, ...] = ()
    investigation_steps: tuple[Mapping[str, object], ...] = ()
    fact_steps: tuple[Mapping[str, object], ...] = ()
    subjects: tuple[str, ...] = ()
    rcon_command: str | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    collected_at: datetime
    scope: str
    filters: tuple[str, ...] = ()
    complete: bool = True

    @classmethod
    def now(cls, source: str, scope: str) -> Provenance:
        return cls(source=source, collected_at=datetime.now(UTC), scope=scope)


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: ResultStatus
    summary: str
    provenance: Provenance | None = None
    values: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_data(self) -> dict[str, object]:
        provenance = None
        if self.provenance is not None:
            provenance = {
                "source": self.provenance.source,
                "collected_at": self.provenance.collected_at.isoformat(),
                "scope": self.provenance.scope,
                "filters": list(self.provenance.filters),
                "complete": self.provenance.complete,
            }
        return {
            "status": self.status.value,
            "summary": self.summary,
            "provenance": provenance,
            "values": dict(self.values),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> ToolResult:
        raw_provenance = data.get("provenance")
        provenance = None
        if raw_provenance is not None:
            if not isinstance(raw_provenance, Mapping):
                raise ValueError("provenance must be a mapping or null")
            raw_filters = raw_provenance.get("filters", ())
            if not isinstance(raw_filters, (list, tuple)) or not all(
                isinstance(value, str) for value in raw_filters
            ):
                raise ValueError("provenance filters must contain strings")
            complete = raw_provenance.get("complete")
            if not isinstance(complete, bool):
                raise ValueError("provenance complete must be a boolean")
            provenance = Provenance(
                source=_required_str(raw_provenance, "source"),
                collected_at=datetime.fromisoformat(
                    _required_str(raw_provenance, "collected_at")
                ),
                scope=_required_str(raw_provenance, "scope"),
                filters=tuple(raw_filters),
                complete=complete,
            )
        raw_values = data.get("values", {})
        if not isinstance(raw_values, Mapping):
            raise ValueError("values must be a mapping")
        raw_warnings = data.get("warnings", ())
        if not isinstance(raw_warnings, (list, tuple)) or not all(
            isinstance(value, str) for value in raw_warnings
        ):
            raise ValueError("warnings must contain strings")
        return cls(
            status=ResultStatus(_required_str(data, "status")),
            summary=_required_str(data, "summary", allow_empty=True),
            provenance=provenance,
            values=dict(raw_values),
            warnings=tuple(raw_warnings),
        )


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    correlation_id: str
    recipient: str
    text: str
    character_count: int

    def __post_init__(self) -> None:
        if self.character_count != len(self.text):
            raise ValueError("character_count must match text length")
        if "\n" in self.text or "\r" in self.text:
            raise ValueError("rendered chat must be one physical line")


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    correlation_id: str
    status: ResultStatus
    exact_text: str
    attempts: int
    completed_at: datetime
    detail: str = ""

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("attempts cannot be negative")
        if self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")

    @classmethod
    def not_attempted(cls, correlation_id: str, detail: str) -> DeliveryResult:
        return cls(
            correlation_id=correlation_id,
            status=ResultStatus.REJECTED,
            exact_text="",
            attempts=0,
            completed_at=datetime.now(UTC),
            detail=detail,
        )


def _required_str(
    data: Mapping[str, object], name: str, *, allow_empty: bool = False
) -> str:
    value = data.get(name)
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"{name} must be a string")
    return value


def _optional_str(data: Mapping[str, object], name: str) -> str | None:
    value = data.get(name)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{name} must be a string or null")


def _required_int(data: Mapping[str, object], name: str) -> int:
    value = data.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value
