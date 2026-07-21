"""Fixed read-only RCON snapshot for the initial Step 6 follow-up."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .delivery import POWERSHELL_PATH


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
    def __init__(self, *, wrapper_path: Path, command_path: Path, timeout_seconds: float) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout_seconds = timeout_seconds

    def collect(self) -> LiveServerState:
        original = self.command_path.read_bytes()
        try:
            self.command_path.write_text(SNAPSHOT_COMMAND + "\n", encoding="utf-8")
            completed = subprocess.run(
                [str(POWERSHELL_PATH), "-NoProfile", "-File", str(self.wrapper_path)],
                capture_output=True, text=True, timeout=self.timeout_seconds, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise LiveStateError(f"live-state query failed: {error}") from error
        finally:
            self.command_path.write_bytes(original)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        match = RESULT_RE.search(output)
        if completed.returncode != 0 or match is None:
            raise LiveStateError(f"live-state query was not confirmed (exit {completed.returncode})")
        return LiveServerState(
            players=_items(match.group("players")),
            research=None if match.group("research") == "none" else match.group("research"),
            research_progress=float(match.group("progress")),
            tick=int(match.group("tick")),
            surfaces=_items(match.group("surfaces")),
        )


def _items(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
