"""Minimal model-authored RCON execution path for Step 10."""

from __future__ import annotations

from .contracts import Provenance, ResultStatus, ToolResult
from .rcon_transport import DirectRconTransport


MAX_CAPTURE_CHARS = 200_000

_RCON_FIXUPS = [
    ("game.space_platforms", "game.forces.player.platforms"),
    ("game.find_entities_filtered", "game.surfaces.nauvis.find_entities_filtered"),
]


def fix_rcon(command: str) -> str:
    for bad, good in _RCON_FIXUPS:
        command = command.replace(bad, good)
    return command


class FreeformRconError(RuntimeError):
    """Raised when a generated RCON command cannot be executed observably."""


class FreeformRconProvider:
    def __init__(self, *, transport: DirectRconTransport) -> None:
        self.transport = transport

    def execute(self, command: str) -> ToolResult:
        command = fix_rcon(command)
        try:
            output = self.transport.command(command)
        except Exception as error:
            raise FreeformRconError(f"free-form RCON failed: {error}") from error
        truncated = len(output) > MAX_CAPTURE_CHARS
        captured = output[:MAX_CAPTURE_CHARS]
        return ToolResult(
            ResultStatus.PARTIAL if truncated else ResultStatus.COMPLETE,
            "Free-form RCON returned output" + (" (truncated)." if truncated else "."),
            Provenance.now("model_authored_rcon", "server=current"),
            {"output": captured},
            ("RCON output exceeded capture limit",) if truncated else (),
        )
