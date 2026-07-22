"""Fixed read-only RCON snapshot for the initial Step 6 follow-up."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .contracts import Provenance, ResultStatus, ToolResult
from .rcon_transport import DirectRconTransport


SNAPSHOT_COMMAND = (
    '/silent-command local p={} for _,v in pairs(game.connected_players) do '
    'p[#p+1]=v.name end local s={} for n,_ in pairs(game.surfaces) do '
    's[#s+1]=n end table.sort(p) table.sort(s) local r=game.forces.player.current_research '
    'rcon.print("JIMBO_FULL_STATE|players="..table.concat(p,",").."|research="..'
    '(r and r.name or "none").."|progress="..string.format("%.3f",'
    'game.forces.player.research_progress).."|tick="..game.tick.."|surfaces="..'
    'table.concat(s,","))'
)
RESULT_RE = re.compile(
    r"JIMBO_FULL_STATE\|players=(?P<players>.*?)\|research=(?P<research>[^|\r\n]+)"
    r"\|progress=(?P<progress>\d+(?:\.\d+)?)\|tick=(?P<tick>\d+)"
    r"\|surfaces=(?P<surfaces>[^\r\n]*)"
)


class LiveStateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LiveServerState:
    players: tuple[str, ...]
    research: str | None
    research_progress: float
    tick: int
    surfaces: tuple[str, ...]

    def answer(self, query: str) -> str:
        if query == "players":
            return "Online players: " + (", ".join(self.players) if self.players else "none") + "."
        if query == "research":
            if self.research is None:
                return "No research is currently active."
            return f"Current research: {self.research} ({self.research_progress * 100:.1f}%)."
        if query == "game_time":
            total_minutes = self.tick // 3600
            hours, minutes = divmod(total_minutes, 60)
            return f"The save has run for about {hours}h {minutes}m of game time."
        if query == "surfaces":
            return "Available surfaces: " + (", ".join(self.surfaces) if self.surfaces else "none") + "."
        raise ValueError(f"unsupported live-state query: {query}")


class FixedLiveStateProvider:
    def __init__(self, *, transport: DirectRconTransport) -> None:
        self.transport = transport

    def collect(self) -> LiveServerState:
        try:
            output = self.transport.command(SNAPSHOT_COMMAND)
        except Exception as error:
            raise LiveStateError(f"live-state query failed: {error}") from error
        match = RESULT_RE.search(output)
        if match is None:
            raise LiveStateError("live-state query was not confirmed")
        return LiveServerState(
            players=_items(match.group("players")),
            research=None if match.group("research") == "none" else match.group("research"),
            research_progress=float(match.group("progress")),
            tick=int(match.group("tick")),
            surfaces=_items(match.group("surfaces")),
        )

    def execute(self, tools: tuple[str, ...]) -> tuple[ToolResult, ...]:
        """Execute one fixed snapshot and project only model-selected observations."""
        if not tools:
            return ()
        state = self.collect()
        collected_at = datetime.now(UTC)
        return tuple(_tool_result(tool, state, collected_at) for tool in tools)


def _tool_result(tool: str, state: LiveServerState, collected_at: datetime) -> ToolResult:
    provenance = Provenance(
        source="fixed_read_only_rcon",
        collected_at=collected_at,
        scope="force=player;server=current",
        complete=True,
    )
    if tool == "get_connected_players":
        values: dict[str, object] = {"players": list(state.players)}
        summary = state.answer("players")
    elif tool == "get_current_research":
        values = {"research": state.research, "progress": state.research_progress}
        summary = state.answer("research")
    elif tool == "get_game_time":
        values = {"tick": state.tick}
        summary = state.answer("game_time")
    elif tool == "get_available_surfaces":
        values = {"surfaces": list(state.surfaces)}
        summary = state.answer("surfaces")
    else:
        raise ValueError("unsupported live-state tool")
    return ToolResult(
        status=ResultStatus.COMPLETE,
        summary=summary,
        provenance=provenance,
        values={"operation": tool, **values},
    )


def _items(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
