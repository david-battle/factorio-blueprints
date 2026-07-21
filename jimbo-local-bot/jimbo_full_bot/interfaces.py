"""Dependency boundaries for the full Jimbo bot.

Protocols keep Step 1 free of provider, RCON, log, and storage side effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, Sequence

from .archive import ArchiveRecord
from .contracts import (
    AuthorityDecision,
    DeliveryResult,
    NormalizedEvent,
    RenderedMessage,
    RequestPlan,
    ToolResult,
)


class EventSource(Protocol):
    def read_available(self) -> Iterable[NormalizedEvent]: ...


class EventArchive(Protocol):
    def append(self, record: ArchiveRecord) -> bool: ...

    def iter_records(self) -> Iterable[ArchiveRecord]: ...


class StateStore(Protocol):
    def load(self, name: str) -> dict[str, str]: ...

    def replace(self, name: str, values: dict[str, str]) -> None: ...


class Router(Protocol):
    def plan(self, event: NormalizedEvent) -> RequestPlan | None: ...


class AuthorityPolicy(Protocol):
    def decide(self, actor: str, capability: str) -> AuthorityDecision: ...


class ModelGateway(Protocol):
    def generate(
        self,
        request: RequestPlan,
        *,
        history: Sequence[tuple[str, str]] = (),
        tool_results: Sequence[ToolResult] = (),
    ) -> str: ...


class Calculator(Protocol):
    def calculate(self, operation: str, inputs: dict[str, object]) -> ToolResult: ...


class ReadOnlyTools(Protocol):
    def execute(self, operation: str, arguments: dict[str, object]) -> ToolResult: ...


class PlacementService(Protocol):
    def validate(self, design_text: str) -> ToolResult: ...


class Renderer(Protocol):
    def render(self, plan: RequestPlan, response: str) -> RenderedMessage: ...


class DeliveryTransport(Protocol):
    def deliver(self, message: RenderedMessage) -> DeliveryResult: ...


class SecretReader(Protocol):
    def read(self, path: Path) -> str: ...
